from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from PIL import Image, UnidentifiedImageError

from SafeSpace.forms import (
    CrisisInstructionsForm,
    EmergencyContactListForm,
    HealthProfileForm,
    MedicationListForm,
    ProfileGeneralForm,
    ProfilePasswordChangeForm,
)
from SafeSpace.models import (
    CrisisInstructions,
    EmergencyContact,
    Medication,
    User,
    UserHealthProfile,
)
from SafeSpace.views.common import app_context


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        raise Http404

    general_form = ProfileGeneralForm(instance=user)
    password_form = ProfilePasswordChangeForm(user)
    health_profile = UserHealthProfile.objects.filter(user=user).first()
    if health_profile is None:
        health_profile = UserHealthProfile(user=user)
    health_form = HealthProfileForm(instance=health_profile)
    crisis = CrisisInstructions.objects.filter(user=user).first()
    if crisis is None:
        crisis = CrisisInstructions(user=user)
    crisis_form = CrisisInstructionsForm(instance=crisis)
    contacts_form = EmergencyContactListForm()
    medication_form = MedicationListForm()
    active_profile_tab = "general"
    medications: list[dict[str, str]] = [
        {
            "name": medication.name,
            "dosage": medication.dosage,
            "instructions": medication.instructions,
        }
        for medication in Medication.objects.filter(user=user)
    ]
    contacts: list[EmergencyContact] = list(
        EmergencyContact.objects.filter(user=user)
    )

    if request.method == "POST":
        if "save_general" in request.POST:
            general_form = ProfileGeneralForm(
                request.POST,
                request.FILES,
                instance=user,
            )
            if general_form.is_valid():
                previous_picture = user.profile_picture.name
                general_form.save()
                current_picture = user.profile_picture.name
                if previous_picture and previous_picture != current_picture:
                    old_picture = previous_picture
                    transaction.on_commit(
                        lambda: default_storage.delete(old_picture)
                    )
                messages.success(request, "Informações do perfil salvas.")
                return redirect(f"{reverse('profile')}#panel-general")
            messages.error(request, "Revise as informações do perfil.")

        elif "save_password" in request.POST:
            active_profile_tab = "password"
            password_form = ProfilePasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                changed_user = password_form.save()
                update_session_auth_hash(request, changed_user)
                messages.success(request, "Sua senha foi atualizada.")
                return redirect(f"{reverse('profile')}#panel-password")
            messages.error(request, "Revise os campos de senha.")

        elif "save_health" in request.POST:
            active_profile_tab = "health"
            health_form = HealthProfileForm(
                request.POST,
                instance=health_profile,
            )
            medication_form = MedicationListForm(request.POST)
            if health_form.is_valid() and medication_form.is_valid():
                with transaction.atomic():
                    saved_profile = health_form.save(commit=False)
                    saved_profile.user = user
                    saved_profile.save()
                    Medication.objects.filter(user=user).delete()
                    Medication.objects.bulk_create(
                        [
                            Medication(user=user, **item)
                            for item in medication_form.medication_items()
                        ]
                    )
                messages.success(request, "Informações de saúde salvas.")
                return redirect(f"{reverse('profile')}#panel-health")
            messages.error(request, "Revise as informações de saúde.")
            medications = _posted_medication_rows(request)

        elif "save_sos" in request.POST:
            active_profile_tab = "sos"
            crisis_form = CrisisInstructionsForm(
                request.POST,
                instance=crisis,
            )
            contacts_form = EmergencyContactListForm(request.POST)
            if crisis_form.is_valid() and contacts_form.is_valid():
                with transaction.atomic():
                    saved_crisis = crisis_form.save(commit=False)
                    saved_crisis.user = user
                    saved_crisis.save()
                    EmergencyContact.objects.filter(user=user).delete()
                    EmergencyContact.objects.bulk_create(
                        [
                            EmergencyContact(
                                user=user,
                                priority=index,
                                **item,
                            )
                            for index, item in enumerate(
                                contacts_form.contact_items()
                            )
                        ]
                    )
                messages.success(
                    request,
                    "Contatos e orientações de emergência salvos.",
                )
                return redirect(f"{reverse('profile')}#panel-sos")
            messages.error(request, "Revise os contatos e as orientações.")
            contacts = _posted_contact_rows(request)

    if not medications:
        medications = [{"name": "", "dosage": "", "instructions": ""}]
    if not contacts:
        contacts = [
            EmergencyContact(name="", relationship="", phone="", priority=0)
        ]

    image_url = reverse("profile_picture") if user.profile_picture else ""
    context: dict[str, object] = {
        **app_context(request, "profile"),
        "general_form": general_form,
        "password_form": password_form,
        "health_form": health_form,
        "crisis_form": crisis_form,
        "contacts_form": contacts_form,
        "medication_form": medication_form,
        "medications": medications,
        "contacts": contacts,
        "profile_image_url": image_url,
        "active_profile_tab": active_profile_tab,
    }
    return render(request, "profile.html", context)


def _posted_medication_rows(request: HttpRequest) -> list[dict[str, str]]:
    names = request.POST.getlist("medication[]")
    dosages = request.POST.getlist("medication_dosage[]")
    instructions = request.POST.getlist("medication_instructions[]")
    row_count = max(len(names), len(dosages), len(instructions))
    return [
        {
            "name": names[index] if index < len(names) else "",
            "dosage": dosages[index] if index < len(dosages) else "",
            "instructions": (
                instructions[index] if index < len(instructions) else ""
            ),
        }
        for index in range(row_count)
    ]


def _posted_contact_rows(request: HttpRequest) -> list[EmergencyContact]:
    names = request.POST.getlist("emergency_contact_name[]")
    relationships = request.POST.getlist("emergency_contact_relationship[]")
    phones = request.POST.getlist("emergency_contact_phone[]")
    row_count = max(len(names), len(relationships), len(phones))
    return [
        EmergencyContact(
            name=names[index] if index < len(names) else "",
            relationship=relationships[index] if index < len(relationships) else "",
            phone=phones[index] if index < len(phones) else "",
            priority=index,
        )
        for index in range(row_count)
    ]


@login_required
@require_GET
def profile_picture(request: HttpRequest) -> FileResponse:
    user = request.user
    if not isinstance(user, User) or not user.profile_picture:
        raise Http404

    try:
        with user.profile_picture.open("rb") as image_file:
            with Image.open(image_file) as image:
                mime_type = Image.MIME.get(image.format or "")
                image_file.seek(0)
    except (OSError, UnidentifiedImageError) as error:
        raise Http404 from error

    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise Http404
    response = FileResponse(
        user.profile_picture.open("rb"),
        content_type=mime_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
