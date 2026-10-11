import uuid

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.files.storage import default_storage
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, UnidentifiedImageError

from SafeSpace.forms import (
    CrisisInstructionsForm,
    DiaryEntryForm,
    DiaryTaskForm,
    EmailLoginForm,
    EmergencyContactListForm,
    HealthProfileForm,
    MedicationListForm,
    ProfileGeneralForm,
    ProfilePasswordChangeForm,
    SignUpForm,
    SosPreferencesForm,
)
from SafeSpace.models import (
    CrisisInstructions,
    DiaryEntry,
    DiaryTask,
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


def _app_context(request: HttpRequest, page: str) -> dict[str, str]:
    user = request.user
    if isinstance(user, User):
        display_name = user.name
        profile_image_url = (
            reverse("profile_picture") if user.profile_picture else ""
        )
    else:
        display_name = "Seu perfil"
        profile_image_url = ""

    profile_initials = "".join(
        part[0].upper() for part in display_name.split()[:2]
    )
    return {
        "display_name": display_name,
        "profile_initials": profile_initials or "?",
        "profile_image_url": profile_image_url,
        "active_page": page,
        "welcome_message": (
            f"Que bom ter você aqui, {display_name}."
            if user.is_authenticated
            else "Que bom ter você aqui."
        ),
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


def index(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")

    form = EmailLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            messages.error(request, "E-mail ou senha incorretos.")
        else:
            login(request, user)
            next_url = request.POST.get("next", "")
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("home")

    return render(request, "auth/login.html", {"form": form})


@login_required
def home(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        raise Http404

    tasks = DiaryTask.objects.filter(
        diary_entry__user=user,
        is_completed=False,
    ).select_related("diary_entry")
    task_page = Paginator(tasks.order_by("created_at", "pk"), 4).get_page(
        request.GET.get("task_page")
    )
    return render(
        request,
        "home.html",
        {
            **_app_context(request, "home"),
            "tasks_page": task_page,
            "has_completed_tasks": DiaryTask.objects.filter(
                diary_entry__user=user,
                is_completed=True,
            ).exists(),
            "sos_settings_url": reverse("sos"),
        },
    )


def _diary_page_has_content(entry: DiaryEntry) -> bool:
    return bool(
        entry.entry_date
        or entry.mood
        or entry.content.strip()
        or DiaryTask.objects.filter(diary_entry=entry).exists()
    )


def _get_diary_entry(user: User, entry_id: str) -> DiaryEntry | None:
    if not entry_id:
        return None
    try:
        parsed_id = uuid.UUID(entry_id)
    except ValueError as error:
        raise Http404 from error
    return get_object_or_404(DiaryEntry, user=user, pk=parsed_id)


def _adjacent_diary_entry(
    user: User,
    entry: DiaryEntry,
    *,
    direction: int,
) -> DiaryEntry | None:
    entries = DiaryEntry.objects.filter(user=user)
    if direction < 0:
        return (
            entries.filter(
                Q(created_at__lt=entry.created_at)
                | Q(created_at=entry.created_at, pk__lt=entry.pk)
            )
            .order_by("-created_at", "-pk")
            .first()
        )
    return (
        entries.filter(
            Q(created_at__gt=entry.created_at)
            | Q(created_at=entry.created_at, pk__gt=entry.pk)
        )
        .order_by("created_at", "pk")
        .first()
    )


@login_required
def diary(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        raise Http404

    requested_entry = request.GET.get("entry", "")
    if request.method == "POST":
        requested_entry = request.POST.get("entry_id", "")
    active_entry = (
        _get_diary_entry(user, requested_entry)
        if requested_entry
        else DiaryEntry.objects.filter(user=user)
        .order_by("-created_at", "-pk")
        .first()
    )
    entry_form = DiaryEntryForm(
        instance=active_entry or DiaryEntry(user=user),
    )
    task_form = DiaryTaskForm()

    if request.method == "POST":
        task_id_value = request.POST.get("toggle_task_id", "")
        action = (
            "toggle_task"
            if task_id_value
            else request.POST.get("action", "")
        )
        if action == "toggle_task":
            entry_form = DiaryEntryForm(
                request.POST,
                instance=active_entry or DiaryEntry(user=user),
            )
            if active_entry is None:
                raise Http404
            if not entry_form.is_valid():
                messages.error(request, "Revise os campos da página.")
            else:
                with transaction.atomic():
                    saved_entry = entry_form.save(commit=False)
                    saved_entry.user = user
                    saved_entry.save()
                    try:
                        parsed_task_id = uuid.UUID(task_id_value)
                    except ValueError as error:
                        raise Http404 from error
                    task = DiaryTask.objects.select_for_update().filter(
                        pk=parsed_task_id,
                        diary_entry=saved_entry,
                    ).first()
                    if task is None:
                        raise Http404
                    task.is_completed = not task.is_completed
                    task.save(update_fields=["is_completed", "updated_at"])
                return redirect(
                    f"{reverse('diary')}?entry={saved_entry.pk}#diary-tasks"
                )

        elif action in {"save_entry", "add_task"}:
            entry_form = DiaryEntryForm(
                request.POST,
                instance=active_entry or DiaryEntry(user=user),
            )
            if action == "save_entry" and entry_form.is_valid():
                saved_entry = entry_form.save(commit=False)
                saved_entry.user = user
                saved_entry.save()
                messages.success(request, "Página do diário salva.")
                return redirect(f"{reverse('diary')}?entry={saved_entry.pk}")

            if action == "add_task":
                task_form = DiaryTaskForm(request.POST)
                if entry_form.is_valid() and task_form.is_valid():
                    with transaction.atomic():
                        saved_entry = entry_form.save(commit=False)
                        saved_entry.user = user
                        saved_entry.save()
                        DiaryTask.objects.create(
                            diary_entry=saved_entry,
                            text=task_form.cleaned_data["text"],
                            position=DiaryTask.objects.filter(
                                diary_entry=saved_entry
                            ).count(),
                        )
                    messages.success(request, "Afazer adicionado à página.")
                    return redirect(
                        f"{reverse('diary')}?entry={saved_entry.pk}#diary-tasks"
                    )
                messages.error(
                    request,
                    "Revise a página e informe um afazer válido.",
                )
            else:
                messages.error(request, "Revise os campos da página.")

        elif action == "delete_entry":
            if active_entry is None:
                raise Http404
            target_entry = _adjacent_diary_entry(
                user,
                active_entry,
                direction=1,
            ) or _adjacent_diary_entry(
                user,
                active_entry,
                direction=-1,
            )
            with transaction.atomic():
                active_entry.delete()
            messages.success(request, "Página do diário apagada.")
            if target_entry is None:
                return redirect("diary")
            return redirect(f"{reverse('diary')}?entry={target_entry.pk}")

        elif action in {"previous_page", "next_page"}:
            if active_entry is None:
                if action == "next_page":
                    messages.warning(
                        request,
                        "Preencha e salve esta página antes de avançar.",
                    )
                    return redirect("diary")
                raise Http404
            if action == "previous_page":
                target_entry = _adjacent_diary_entry(
                    user,
                    active_entry,
                    direction=-1,
                )
                if target_entry is None:
                    raise Http404
            else:
                if not _diary_page_has_content(active_entry):
                    messages.warning(
                        request,
                        "Preencha e salve esta página antes de avançar.",
                    )
                    return redirect(
                        f"{reverse('diary')}?entry={active_entry.pk}"
                    )
                target_entry = _adjacent_diary_entry(
                    user,
                    active_entry,
                    direction=1,
                ) or DiaryEntry.objects.create(user=user)
            return redirect(f"{reverse('diary')}?entry={target_entry.pk}")
        else:
            raise Http404

    if active_entry is None:
        page_number = 1
        has_previous_page = False
        page_tasks: list[DiaryTask] = []
        has_content = False
    else:
        previous_entry = _adjacent_diary_entry(
            user,
            active_entry,
            direction=-1,
        )
        page_number = (
            DiaryEntry.objects.filter(user=user)
            .filter(
                Q(created_at__lt=active_entry.created_at)
                | Q(
                    created_at=active_entry.created_at,
                    pk__lt=active_entry.pk,
                )
            )
            .count()
            + 1
        )
        has_previous_page = previous_entry is not None
        page_tasks = list(
            DiaryTask.objects.filter(diary_entry=active_entry).order_by(
                "position", "created_at"
            )
        )
        has_content = bool(
            active_entry.entry_date
            or active_entry.mood
            or active_entry.content.strip()
            or page_tasks
        )

    return render(
        request,
        "diary.html",
        {
            **_app_context(request, "diary"),
            "entry_form": entry_form,
            "task_form": task_form,
            "active_entry": active_entry,
            "page_tasks": page_tasks,
            "page_number": page_number,
            "has_previous_page": has_previous_page,
            "can_advance_page": has_content,
        },
    )


@login_required
@require_POST
def complete_diary_task(request: HttpRequest, task_id: uuid.UUID) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        raise Http404
    task = get_object_or_404(
        DiaryTask,
        pk=task_id,
        diary_entry__user=user,
    )
    if not task.is_completed:
        task.is_completed = True
        task.save(update_fields=["is_completed", "updated_at"])
        messages.success(request, "Afazer concluído.")

    try:
        page_number = max(1, int(request.POST.get("task_page", "1")))
    except ValueError:
        page_number = 1
    return redirect(f"{reverse('home')}?task_page={page_number}#home-tasks")


@login_required
def health(request: HttpRequest) -> HttpResponse:
    return render(request, "health.html", _app_context(request, "health"))


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
            **_app_context(request, "sos"),
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
        **_app_context(request, "profile"),
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


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("SafeSpace:index")


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error("email", "Não foi possível criar a conta com esses dados.")
            messages.error(request, "Não foi possível criar a conta.")
            return render(request, "auth/signup.html", {"form": form})

        login(request, user)
        messages.success(request, "Sua conta foi criada com sucesso.")
        return redirect("home")

    if request.method == "POST" and form.errors:
        if "password_confirmation" in form.errors:
            messages.error(request, "As senhas não coincidem.")
        elif form.non_field_errors():
            messages.error(request, "Não foi possível criar a conta.")

    return render(request, "auth/signup.html", {"form": form})
