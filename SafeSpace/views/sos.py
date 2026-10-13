import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from SafeSpace.forms import SosPreferencesForm
from SafeSpace.models import (
    CrisisInstructions,
    EmergencyContact,
    Medication,
    User,
    UserHealthProfile,
    UserSosPreferences,
)
from SafeSpace.services.sos import (
    InvalidSosToken,
    SosCardData,
    create_sos_token,
    generate_qr_png,
    get_sos_card_data,
    render_sos_card_svg,
    resolve_sos_token,
)
from SafeSpace.views.common import app_context

SOS_CARD_PREFERENCE_FIELDS = {
    "share_address",
    "share_profile_picture",
    "share_blood_type",
    "share_allergies",
    "share_medications",
    "share_conditions",
    "share_emergency_contacts",
    "share_crisis_instructions",
}


def _sos_sharing_previews(user: User) -> dict[str, str]:
    profile = UserHealthProfile.objects.filter(user=user).first()
    blood_type = ""
    if profile is not None:
        blood_type = next(
            (
                str(label)
                for value, label in UserHealthProfile.BloodType.choices
                if value == profile.blood_type
            ),
            "",
        )
    address = ", ".join(
        part
        for part in (
            user.address_street,
            user.address_number,
            user.address_complement,
            user.address_neighborhood,
            user.address_city,
        )
        if part
    )
    medications = [
        ", ".join(
            part for part in (item.name, item.dosage, item.instructions) if part
        )
        for item in Medication.objects.filter(user=user)
    ]
    contacts = [
        " · ".join(part for part in (item.name, item.relationship, item.phone) if part)
        for item in EmergencyContact.objects.filter(user=user)
    ]
    crisis = CrisisInstructions.objects.filter(user=user).first()
    previews = {
        "share_address": address,
        "share_profile_picture": (
            "Foto cadastrada" if user.profile_picture else "Nenhuma foto cadastrada"
        ),
        "share_blood_type": blood_type,
        "share_allergies": profile.allergies_summary if profile else "",
        "share_medications": ", ".join(medications),
        "share_conditions": profile.conditions if profile else "",
        "share_emergency_contacts": " | ".join(contacts),
        "share_crisis_instructions": crisis.instructions if crisis else "",
        "share_weight": (
            f"{profile.weight_kg.normalize():f} kg"
            if profile and profile.weight_kg is not None
            else ""
        ),
        "share_height": (
            f"{profile.height_cm.normalize():f} cm"
            if profile and profile.height_cm is not None
            else ""
        ),
        "share_smoker": (
            "Sim" if profile and profile.is_smoker is True
            else "Não" if profile and profile.is_smoker is False
            else ""
        ),
        "share_alcohol": (
            "Sim" if profile and profile.consumes_alcohol is True
            else "Não" if profile and profile.consumes_alcohol is False
            else ""
        ),
    }
    return {
        name: value.strip() or "Nenhuma informação preenchida."
        for name, value in previews.items()
    }


@login_required
def sos(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        raise Http404

    preferences = UserSosPreferences.objects.filter(user=user).first()
    if preferences is None:
        preferences = UserSosPreferences(user=user)

    preferences_form = SosPreferencesForm(
        request.POST if request.method == "POST" else None,
        instance=preferences,
    )
    if request.method == "POST" and preferences_form.is_valid():
        with transaction.atomic():
            preferences = preferences_form.save(commit=False)
            preferences.user = request.user
            preferences.public_token_version = uuid.uuid4()
            preferences.save()
        messages.success(
            request,
            "Preferências salvas. Um novo QR Code foi gerado.",
        )
        return redirect("sos")

    if request.method == "POST":
        messages.error(request, "Revise as opções de compartilhamento.")

    token = (
        create_sos_token(preferences)
        if preferences.pk and preferences.public_token_version
        else ""
    )
    card_url = (
        request.build_absolute_uri(
            reverse("sos_card", kwargs={"token": token})
        )
        if token
        else ""
    )
    qr_url = (
        reverse("sos_qr", kwargs={"token": token}) if token else ""
    )
    download_url = (
        reverse("sos_card_download", kwargs={"token": token}) if token else ""
    )
    card_data = get_sos_card_data(user, preferences)
    sharing_previews = _sos_sharing_previews(user)
    return render(
        request,
        "sos.html",
        {
            **app_context(request, "sos"),
            "preferences_form": preferences_form,
            "card": card_data,
            "sharing_options": [
                {
                    "field": field,
                    "preview": sharing_previews[field.name],
                    "available_on_card": field.name
                    in SOS_CARD_PREFERENCE_FIELDS,
                }
                for field in preferences_form
            ],
            "card_url": card_url,
            "qr_url": qr_url,
            "download_url": download_url,
        },
    )


def _public_sos_data(token: str) -> SosCardData:
    try:
        preferences = resolve_sos_token(token)
    except InvalidSosToken as error:
        raise Http404 from error
    return get_sos_card_data(preferences.user, preferences)


def _sos_security_headers(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "no-store, private"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
def sos_card(request: HttpRequest, token: str) -> HttpResponse:
    card_data = _public_sos_data(token)
    response = render(
        request,
        "sos_card.html",
        {"card": card_data},
    )
    response = _sos_security_headers(response)
    response["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@require_GET
def sos_qr(request: HttpRequest, token: str) -> HttpResponse:
    try:
        preferences = resolve_sos_token(token)
    except InvalidSosToken as error:
        raise Http404 from error
    card_url = request.build_absolute_uri(
        reverse(
            "sos_card",
            kwargs={"token": create_sos_token(preferences)},
        )
    )
    response = HttpResponse(
        generate_qr_png(card_url),
        content_type="image/png",
    )
    return _sos_security_headers(response)


@require_GET
def sos_card_download(request: HttpRequest, token: str) -> HttpResponse:
    card_data = _public_sos_data(token)
    qr_url = request.build_absolute_uri(
        reverse("sos_card", kwargs={"token": token})
    )
    svg = render_sos_card_svg(card_data, generate_qr_png(qr_url))
    response = HttpResponse(svg, content_type="image/svg+xml")
    response["Content-Disposition"] = (
        'attachment; filename="cartao-emergencia.svg"'
    )
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return _sos_security_headers(response)
