import datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable, cast
from urllib.parse import urlsplit
from uuid import UUID

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError, transaction
from django.db.models import UUIDField
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from PIL import Image

from SafeSpace.forms import HealthProfileForm
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
from SafeSpace.services.sos import create_sos_token
from SafeSpace.validators import (
    MAX_PROFILE_IMAGE_BYTES,
    validate_profile_image,
)

TEST_PASSWORD = "Nuvem-Lilas-2036!"


def empty_response(_: HttpRequest) -> HttpResponse:
    return HttpResponse()


class AuthenticationPageTests(TestCase):
    def create_user(self) -> User:
        return User.objects.create_user(
            email="pessoa@example.com",
            name="Pessoa Exemplo",
            password=TEST_PASSWORD,
        )

    def test_authentication_pages_render_with_shared_theme(self) -> None:
        user = self.create_user()
        protected_pages = {"home", "diary", "health", "sos", "profile"}
        pages = (
            ("SafeSpace:index", "Bem-vinde ao SafeSpace"),
            ("SafeSpace:password_reset", "Vamos recuperar seu acesso"),
            ("SafeSpace:signup", "Seu espaço começa aqui"),
            ("home", "Que bom ter você aqui, Pessoa Exemplo."),
            ("diary", "Meu diário"),
            ("health", "Saúde"),
            ("sos", "Meu SOS"),
            ("profile", "Meu perfil"),
        )

        for route_name, heading in pages:
            with self.subTest(route_name=route_name):
                if route_name in protected_pages:
                    self.client.force_login(user)
                else:
                    self.client.logout()
                response = self.client.get(reverse(route_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)
                self.assertContains(response, "SafeSpace/css/theme.css")
                if route_name not in {"home", "diary", "health", "sos", "profile"}:
                    self.assertContains(response, "SafeSpace/css/auth.css")
                    self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_home_contains_shared_navigation_and_profile_controls(self) -> None:
        self.client.force_login(self.create_user())
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'data-app-tabs')
        self.assertNotContains(response, 'data-menu-toggle')
        self.assertContains(response, 'data-notification-toggle')
        self.assertContains(response, 'SafeSpace/css/home.css?v=9')
        self.assertContains(response, 'SafeSpace/js/site.js')
        self.assertContains(response, 'class="profile-avatar profile-initials"')
        self.assertContains(response, "Diário")
        self.assertContains(response, "Saúde")
        self.assertContains(response, "SOS")
        self.assertContains(response, "Meu perfil")
        self.assertContains(response, "Sair da conta")
        self.assertContains(response, "app-profile-popover-name")
        self.assertNotContains(response, "app-profile-name")
        self.assertLess(
            response.content.index("Notifica".encode()),
            response.content.index(b'class="profile-avatar'),
        )
        self.assertContains(response, "Meus afazeres")
        self.assertContains(response, "Aqui está seu QR Code")
        self.assertContains(response, "Acesse as configurações clicando aqui.")
        self.assertContains(response, reverse("sos"))
        self.assertContains(response, 'class="home-sos-icon"')

    def test_home_keeps_sos_icon_when_qr_code_exists(self) -> None:
        user = self.create_user()
        self.client.force_login(user)
        self.client.post(reverse("sos"), {"share_blood_type": "on"})

        response = self.client.get(reverse("home"))

        self.assertContains(response, 'class="home-sos-icon"')
        self.assertNotContains(response, 'class="home-sos-qr"')

    def test_home_shows_pending_tasks_with_diary_link_and_pagination(self) -> None:
        user = self.create_user()
        first_entry = DiaryEntry.objects.create(user=user, content="Página inicial")
        first_entry.entry_date = datetime.date(2026, 10, 13)
        first_entry.save()
        for index in range(6):
            DiaryTask.objects.create(
                diary_entry=first_entry,
                text=f"Afazer {index + 1}",
                position=index,
            )
        self.client.force_login(user)

        first_page = self.client.get(reverse("home"))
        second_page = self.client.get(reverse("home"), {"task_page": "2"})

        self.assertContains(first_page, "Afazer 1 ")
        self.assertContains(first_page, "Afazer 5")
        self.assertNotContains(first_page, "Afazer 6")
        self.assertContains(first_page, "- 13/10/2026")
        self.assertContains(first_page, "diario/?entry=")
        self.assertContains(first_page, "Mais afazeres")
        self.assertContains(second_page, "Afazer 6")

    def test_diary_requires_saved_content_before_creating_next_page(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        response = self.client.get(reverse("diary"))
        self.assertContains(
            response,
            'title="Salve conteúdo da página antes de avançar"',
        )
        blocked_response = self.client.post(
            reverse("diary"),
            {"action": "next_page"},
        )
        self.assertEqual(blocked_response.status_code, 302)
        self.assertEqual(DiaryEntry.objects.filter(user=user).count(), 0)

        self.client.post(
            reverse("diary"),
            {
                "action": "save_entry",
                "entry_date": "",
                "mood": "",
                "content": "",
            },
        )
        empty_entry = DiaryEntry.objects.get(user=user)
        self.client.post(
            reverse("diary"),
            {
                "action": "next_page",
                "entry_id": str(empty_entry.pk),
            },
        )
        self.assertEqual(DiaryEntry.objects.filter(user=user).count(), 1)

        save_response = self.client.post(
            reverse("diary"),
            {
                "action": "save_entry",
                "entry_id": str(empty_entry.pk),
                "entry_date": "2026-10-11",
                "mood": "happy",
                "content": "Meu registro do dia.",
            },
        )
        self.assertEqual(save_response.status_code, 302)
        first_entry = DiaryEntry.objects.get(user=user)
        self.assertEqual(first_entry.content, "Meu registro do dia.")
        self.assertEqual(str(first_entry.entry_date), "2026-10-11")

        page_response = self.client.get(
            f"{reverse('diary')}?entry={first_entry.pk}"
        )
        self.assertContains(page_response, 'value="2026-10-11"')
        self.assertContains(page_response, "value=\"next_page\"")
        next_response = self.client.post(
            reverse("diary"),
            {
                "action": "next_page",
                "entry_id": str(first_entry.pk),
            },
        )
        self.assertEqual(next_response.status_code, 302)
        self.assertEqual(DiaryEntry.objects.filter(user=user).count(), 2)
        next_url = next_response.headers.get("Location")
        self.assertIsInstance(next_url, str)
        if not isinstance(next_url, str):
            self.fail("The next-page redirect did not include a location.")
        self.assertContains(self.client.get(next_url), "Página 2")

    def test_diary_tasks_persist_and_completed_tasks_remain_on_their_page(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        add_response = self.client.post(
            reverse("diary"),
            {
                "action": "add_task",
                "entry_date": "2026-10-11",
                "mood": "",
                "content": "Planejamento",
                "text": "Separar documentos",
            },
        )
        self.assertEqual(add_response.status_code, 302)
        entry = DiaryEntry.objects.get(user=user)
        task = DiaryTask.objects.get(diary_entry__user=user)
        self.assertEqual(task.text, "Separar documentos")

        home_response = self.client.get(reverse("home"))
        self.assertContains(home_response, task.text)
        self.assertContains(home_response, f"entry={entry.pk}")

        complete_response = self.client.post(
            reverse("diary_task_complete", kwargs={"task_id": task.pk}),
            {"task_page": "1"},
        )
        self.assertEqual(complete_response.status_code, 302)
        task.refresh_from_db()
        self.assertTrue(task.is_completed)
        self.assertEqual(DiaryTask.objects.filter(pk=task.pk).count(), 1)
        self.assertNotContains(self.client.get(reverse("home")), task.text)

        diary_response = self.client.get(
            f"{reverse('diary')}?entry={entry.pk}"
        )
        self.assertContains(diary_response, task.text)
        self.assertContains(diary_response, "Concluído")

    def test_diary_tasks_sit_beside_the_page_with_five_per_page(self) -> None:
        user = self.create_user()
        entry = DiaryEntry.objects.create(user=user, content="Meu registro")
        for index in range(1, 7):
            DiaryTask.objects.create(
                diary_entry=entry,
                text=f"Passo {index}",
                position=index,
            )
        self.client.force_login(user)
        url = reverse("diary")

        first = self.client.get(url, {"entry": str(entry.pk)})
        self.assertContains(first, "diary-layout")
        self.assertContains(first, "Passo 5")
        self.assertNotContains(first, "Passo 6")
        self.assertContains(first, "task_page=2")

        second = self.client.get(url, {"entry": str(entry.pk), "task_page": "2"})
        self.assertContains(second, "Passo 6")
        self.assertNotContains(second, "Passo 1<")

        add = self.client.post(
            url,
            {
                "entry_id": str(entry.pk),
                "entry_date": "",
                "mood": "",
                "content": entry.content,
                "action": "add_task",
                "text": "Passo 7",
            },
        )
        self.assertEqual(add.status_code, 302)
        self.assertIn("task_page=2", add["Location"])

    def test_diary_task_can_be_completed_and_reopened_from_its_page(self) -> None:
        user = self.create_user()
        entry = DiaryEntry.objects.create(user=user, content="Meu registro")
        task = DiaryTask.objects.create(
            diary_entry=entry,
            text="Organizar os documentos",
        )
        self.client.force_login(user)

        pending_response = self.client.get(
            reverse("diary"),
            {"entry": str(entry.pk)},
        )
        self.assertContains(
            pending_response,
            f'value="{task.pk}" formnovalidate',
        )
        self.assertContains(pending_response, "aria-pressed=\"false\"")

        complete_response = self.client.post(
            reverse("diary"),
            {
                "entry_id": str(entry.pk),
                "entry_date": "",
                "mood": "",
                "content": entry.content,
                "toggle_task_id": str(task.pk),
            },
        )
        self.assertEqual(complete_response.status_code, 302)
        task.refresh_from_db()
        self.assertTrue(task.is_completed)

        completed_response = self.client.get(
            reverse("diary"),
            {"entry": str(entry.pk)},
        )
        self.assertContains(completed_response, "aria-pressed=\"true\"")
        self.assertContains(completed_response, "Desconcluir tarefa")

        reopen_response = self.client.post(
            reverse("diary"),
            {
                "entry_id": str(entry.pk),
                "entry_date": "",
                "mood": "",
                "content": entry.content,
                "toggle_task_id": str(task.pk),
            },
        )
        self.assertEqual(reopen_response.status_code, 302)
        task.refresh_from_db()
        self.assertFalse(task.is_completed)

    def test_diary_save_does_not_require_a_new_task(self) -> None:
        user = self.create_user()
        self.client.force_login(user)
        response = self.client.get(reverse("diary"))

        self.assertContains(response, 'id="id_text"')
        self.assertContains(response, "required")
        self.assertContains(response, 'value="save_entry" formnovalidate')

        save_response = self.client.post(
            reverse("diary"),
            {
                "action": "save_entry",
                "entry_date": "",
                "mood": "",
                "content": "Salvar sem adicionar afazer",
                "text": "",
            },
        )

        self.assertEqual(save_response.status_code, 302)
        self.assertEqual(
            DiaryEntry.objects.get(user=user).content,
            "Salvar sem adicionar afazer",
        )

    def test_diary_page_delete_requires_confirmation_and_removes_related_tasks(self) -> None:
        user = self.create_user()
        first_entry = DiaryEntry.objects.create(
            user=user,
            content="Página anterior",
        )
        active_entry = DiaryEntry.objects.create(
            user=user,
            content="Página para apagar",
        )
        task = DiaryTask.objects.create(
            diary_entry=active_entry,
            text="Afazer vinculado",
        )
        self.client.force_login(user)

        page_response = self.client.get(
            reverse("diary"),
            {"entry": str(active_entry.pk)},
        )
        self.assertContains(page_response, 'data-delete-dialog-open')
        self.assertContains(page_response, "<dialog")
        self.assertContains(page_response, "Apagar esta página?")
        self.assertContains(page_response, "Manter página")

        self.assertTrue(DiaryEntry.objects.filter(pk=active_entry.pk).exists())
        delete_response = self.client.post(
            reverse("diary"),
            {
                "action": "delete_entry",
                "entry_id": str(active_entry.pk),
            },
        )

        self.assertRedirects(
            delete_response,
            f"{reverse('diary')}?entry={first_entry.pk}",
        )
        self.assertFalse(DiaryEntry.objects.filter(pk=active_entry.pk).exists())
        self.assertFalse(DiaryTask.objects.filter(pk=task.pk).exists())

    def test_diary_page_delete_rejects_another_users_entry(self) -> None:
        owner = self.create_user()
        other_user = User.objects.create_user(
            email="outra@example.com",
            name="Outra Pessoa",
            password=TEST_PASSWORD,
        )
        private_entry = DiaryEntry.objects.create(
            user=other_user,
            content="Página privada",
        )
        self.client.force_login(owner)

        response = self.client.post(
            reverse("diary"),
            {
                "action": "delete_entry",
                "entry_id": str(private_entry.pk),
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(DiaryEntry.objects.filter(pk=private_entry.pk).exists())

    def test_diary_entries_and_tasks_are_isolated_between_users(self) -> None:
        owner = self.create_user()
        other_user = User.objects.create_user(
            email="outra@example.com",
            name="Outra Pessoa",
            password=TEST_PASSWORD,
        )
        private_entry = DiaryEntry.objects.create(
            user=other_user,
            content="Anotação privada",
        )
        own_entry = DiaryEntry.objects.create(
            user=owner,
            content="Anotação própria",
        )
        private_task = DiaryTask.objects.create(
            diary_entry=private_entry,
            text="Afazer privado",
        )
        self.client.force_login(owner)

        self.assertEqual(
            self.client.get(
                reverse("diary"),
                {"entry": str(private_entry.pk)},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("diary_task_complete", kwargs={"task_id": private_task.pk}),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("diary"),
                {
                    "entry_id": str(own_entry.pk),
                    "entry_date": "",
                    "mood": "",
                    "content": own_entry.content,
                    "toggle_task_id": str(private_task.pk),
                },
            ).status_code,
            404,
        )
        private_task.refresh_from_db()
        self.assertFalse(private_task.is_completed)
        self.assertNotContains(self.client.get(reverse("home")), private_task.text)

    def test_diary_has_page_controls_mood_and_todo_list(self) -> None:
        self.client.force_login(self.create_user())
        response = self.client.get(reverse("diary"))

        self.assertContains(response, 'type="date"')
        self.assertContains(response, "Humor do dia")
        self.assertContains(response, "data-page-next")
        self.assertContains(response, "data-page-previous")
        self.assertContains(response, "diary-corner-controls")
        self.assertContains(response, "SafeSpace/css/diary.css?v=6")
        self.assertNotContains(response, "diary-pagination")
        self.assertContains(response, 'name="action"')
        self.assertContains(response, 'value="save_entry"')
        self.assertContains(response, "Salvar página")
        self.assertContains(response, "data-page-transition-form")

    def test_health_sos_and_profile_have_requested_sections(self) -> None:
        self.client.force_login(self.create_user())
        health_response = self.client.get(reverse("health"))
        sos_response = self.client.get(reverse("sos"))
        profile_response = self.client.get(reverse("profile"))

        self.assertContains(health_response, "histórico")
        self.assertContains(health_response, "médicos e contatos")
        self.assertContains(sos_response, "gerar QR Code")
        self.assertContains(sos_response, "Salvar e gerar QR Code")
        self.assertContains(sos_response, "QR Code")
        self.assertContains(sos_response, "?v=11")
        self.assertContains(sos_response, "data-print-card")
        self.assertContains(sos_response, "Complete suas informações")
        self.assertContains(sos_response, "Configurar meu perfil")
        self.assertContains(
            sos_response,
            f'href="{reverse("profile")}"',
        )
        self.assertContains(profile_response, "Informações gerais")
        self.assertContains(profile_response, "Endereço")
        self.assertContains(profile_response, "data-photo-crop-dialog")
        self.assertContains(profile_response, "Redefinir senha")
        self.assertContains(profile_response, "Tipo sanguíneo")
        self.assertContains(profile_response, "Orientações em caso de crise")
        self.assertContains(profile_response, "data-phone-mask")
        self.assertContains(profile_response, "choice-options")
        self.assertNotContains(profile_response, "Como gostaria de se identificar?")
        self.assertNotContains(profile_response, "Observações importantes")
        self.assertContains(profile_response, "profile.js?v=2")
        self.assertContains(profile_response, 'data-phone-mask="br"')
        self.assertContains(profile_response, "emergency_contact_name[]")
        self.assertContains(profile_response, "emergency_contact_relationship[]")
        self.assertContains(profile_response, "emergency_contact_phone[]")
        self.assertContains(profile_response, "data-add-emergency-contact")
        self.assertContains(
            profile_response,
            'aria-label="Remover contato de emergência"',
        )

    def test_diary_page_turn_has_smooth_two_direction_transitions(self) -> None:
        user = self.create_user()
        entry = DiaryEntry.objects.create(user=user)
        self.client.force_login(user)
        response = self.client.get(
            reverse("diary"),
            {"entry": str(entry.pk)},
        )
        stylesheet = (
            Path(__file__).resolve().parent
            / "static"
            / "SafeSpace"
            / "css"
            / "diary.css"
        ).read_text(encoding="utf-8")
        script = (
            Path(__file__).resolve().parent
            / "static"
            / "SafeSpace"
            / "js"
            / "diary.js"
        ).read_text(encoding="utf-8")

        self.assertContains(response, "SafeSpace/js/diary.js?v=3")
        self.assertContains(response, 'data-delete-dialog-open')
        self.assertIn("is-turning-next", stylesheet)
        self.assertIn("is-turning-previous", stylesheet)
        self.assertEqual(stylesheet.count("1300ms cubic-bezier"), 2)
        self.assertIn("@keyframes diary-page-curl-shadow", stylesheet)
        self.assertIn("inset: 50% 0.75rem auto 1.5rem;", stylesheet)
        self.assertIn("z-index: 4;", stylesheet)
        self.assertIn("stroke: currentColor;", stylesheet)
        self.assertIn('addEventListener("animationend", finishTurn)', script)
        self.assertIn('prefers-reduced-motion: reduce', script)
        self.assertIn("form.requestSubmit(button);", script)
        self.assertIn("data-page-transition-form", script)
        self.assertIn("Você tem alterações sem salvar.", script)
        self.assertContains(response, "Salve conteúdo da página antes de avançar")

    def test_profile_photo_crop_waits_for_dialog_layout_before_sizing_image(self) -> None:
        script = (
            Path(__file__).resolve().parent
            / "static"
            / "SafeSpace"
            / "js"
            / "profile.js"
        ).read_text(encoding="utf-8")
        image_load_handler = script.split(
            'cropImage.addEventListener("load", () => {',
            maxsplit=1,
        )[1].split("}, { once: true });", maxsplit=1)[0]

        self.assertLess(
            image_load_handler.index("cropDialog.showModal();"),
            image_load_handler.index("updateCropImage();"),
        )
        self.assertIn("cropTranslationX = Math.max(", script)
        self.assertIn("cropTranslationY = Math.max(", script)

    def test_authentication_pages_link_to_each_other(self) -> None:
        login_response = self.client.get(reverse("SafeSpace:index"))
        reset_response = self.client.get(reverse("SafeSpace:password_reset"))
        signup_response = self.client.get(reverse("SafeSpace:signup"))

        self.assertContains(
            login_response,
            reverse("SafeSpace:password_reset"),
        )
        self.assertContains(login_response, reverse("SafeSpace:signup"))
        self.assertContains(reset_response, reverse("SafeSpace:index"))
        self.assertContains(signup_response, reverse("SafeSpace:index"))

    def test_signup_displays_password_requirements_and_strength_meter(self) -> None:
        response = self.client.get(reverse("SafeSpace:signup"))

        self.assertContains(response, 'minlength="8"')
        self.assertContains(response, 'data-password-input')
        self.assertContains(response, 'data-password-confirmation')
        self.assertContains(response, 'data-strength-meter')
        self.assertContains(response, "Pelo menos 1 letra maiúscula")
        self.assertContains(response, "Pelo menos 1 letra minúscula")
        self.assertContains(response, "Pelo menos 1 caractere especial")

    def test_signup_rejects_mismatched_password_confirmation(self) -> None:
        response = self.client.post(
            reverse("SafeSpace:signup"),
            {
                "name": "Pessoa",
                "email": "pessoa@example.com",
                "password": "SenhaSegura1!",
                "password_confirmation": "SenhaDiferente1!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "As senhas não coincidem.")
        self.assertContains(response, 'class="toast toast--error"')

    def test_signup_creates_uuid_user_with_a_hashed_password(self) -> None:
        response = self.client.post(
            reverse("SafeSpace:signup"),
            {
                "name": "Pessoa Nova",
                "email": "PESSOA.NOVA@example.com",
                "password": TEST_PASSWORD,
                "password_confirmation": TEST_PASSWORD,
            },
        )

        user = User.objects.get(email="pessoa.nova@example.com")
        self.assertRedirects(response, reverse("home"))
        self.assertIsInstance(user.pk, UUID)
        self.assertNotEqual(user.password, TEST_PASSWORD)
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertIn("_auth_user_id", self.client.session)

    def test_signup_rejects_passwords_missing_required_complexity(self) -> None:
        response = self.client.post(
            reverse("SafeSpace:signup"),
            {
                "name": "Pessoa Nova",
                "email": "pessoa.nova@example.com",
                "password": "senhafraca123",
                "password_confirmation": "senhafraca123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "letra maiúscula")
        self.assertFalse(
            User.objects.filter(email="pessoa.nova@example.com").exists()
        )

    def test_login_uses_generic_errors_and_rejects_external_redirects(self) -> None:
        self.create_user()
        failed_response = self.client.post(
            reverse("SafeSpace:index"),
            {"email": "pessoa@example.com", "password": "incorreta"},
        )
        self.assertContains(failed_response, "E-mail ou senha incorretos.")

        response = self.client.post(
            reverse("SafeSpace:index"),
            {
                "email": "PESSOA@EXAMPLE.COM",
                "password": TEST_PASSWORD,
                "next": "https://example.invalid/",
            },
        )
        self.assertRedirects(response, reverse("home"))

    def test_private_pages_require_authentication(self) -> None:
        for route_name in ("home", "diary", "health", "sos", "profile"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("SafeSpace:index"), response["Location"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_changes_password_and_invalidates_token(self) -> None:
        user = self.create_user()

        response = self.client.post(
            reverse("SafeSpace:password_reset"),
            {"email": "pessoa@example.com"},
        )

        self.assertRedirects(response, reverse("SafeSpace:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        reset_url = next(
            part
            for part in mail.outbox[0].body.split()
            if part.startswith("http")
        )
        reset_path = urlsplit(reset_url).path
        initial_confirm_response = self.client.get(reset_path)
        self.assertEqual(initial_confirm_response.status_code, 302)
        confirm_path = urlsplit(initial_confirm_response["Location"]).path
        self.assertContains(self.client.get(confirm_path), "id_new_password1")
        confirm_response = self.client.post(
            confirm_path,
            {
                "new_password1": "Brisa-Coral-2037!",
                "new_password2": "Brisa-Coral-2037!",
            },
        )

        self.assertRedirects(
            confirm_response,
            reverse("SafeSpace:password_reset_complete"),
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("Brisa-Coral-2037!"))
        self.assertContains(
            self.client.get(confirm_path),
            "Este link expirou ou já foi usado",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_does_not_reveal_unknown_accounts(self) -> None:
        response = self.client.post(
            reverse("SafeSpace:password_reset"),
            {"email": "nao-existe@example.com"},
        )

        self.assertRedirects(response, reverse("SafeSpace:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_every_application_model_uses_uuid_and_has_indexes(self) -> None:
        for model in apps.get_app_config("SafeSpace").get_models():
            with self.subTest(model=model.__name__):
                self.assertIsInstance(model._meta.pk, UUIDField)
                self.assertTrue(model._meta.indexes)
                self.assertIsNotNone(model._meta.get_field("created_at"))
                self.assertIsNotNone(model._meta.get_field("updated_at"))

    def test_profile_images_are_size_limited(self) -> None:
        upload = SimpleUploadedFile(
            "profile.png",
            b"x" * (MAX_PROFILE_IMAGE_BYTES + 1),
            content_type="image/png",
        )

        with self.assertRaisesMessage(ValidationError, "no máximo 5 MB"):
            validate_profile_image(upload)

    def test_profile_images_are_validated_by_content(self) -> None:
        upload = SimpleUploadedFile(
            "not-an-image.png",
            b"not an image",
            content_type="image/png",
        )

        with self.assertRaisesMessage(ValidationError, "imagem válida"):
            validate_profile_image(upload)

    def test_health_measurement_ranges_are_database_enforced(self) -> None:
        user = self.create_user()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserHealthProfile.objects.create(user=user, weight_kg=-1)

    def test_security_settings_are_explicit(self) -> None:
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_state_changing_auth_requests_require_csrf(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        login_response = csrf_client.post(
            reverse("SafeSpace:index"),
            {"email": "pessoa@example.com", "password": TEST_PASSWORD},
        )
        signup_response = csrf_client.post(
            reverse("SafeSpace:signup"),
            {
                "name": "Pessoa",
                "email": "pessoa@example.com",
                "password": TEST_PASSWORD,
                "password_confirmation": TEST_PASSWORD,
            },
        )
        self.assertEqual(login_response.status_code, 403)
        self.assertEqual(signup_response.status_code, 403)
        self.assertEqual(
            self.client.get(reverse("logout")).status_code,
            405,
        )

    def test_toasts_render_django_message_levels(self) -> None:
        request = RequestFactory().get(reverse("SafeSpace:index"))
        SessionMiddleware(empty_response).process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        messages.error(request, "Senha incorreta.")
        messages.warning(request, "Confira os dados informados.")
        messages.success(request, "Alterações salvas.")

        html = render_to_string("auth/base_auth.html", request=request)

        self.assertIn('class="toast-region"', html)
        self.assertIn('class="toast toast--error"', html)
        self.assertIn('class="toast toast--warning"', html)
        self.assertIn('class="toast toast--success"', html)
        self.assertIn('role="alert"', html)
        self.assertIn('data-toast-dismiss', html)
        self.assertIn("Senha incorreta.", html)


class ProfilePersistenceAndSosTests(TestCase):
    def create_user(self, email: str = "pessoa@example.com") -> User:
        return User.objects.create_user(
            email=email,
            name="Pessoa Exemplo",
            password=TEST_PASSWORD,
        )

    def test_profile_general_and_health_forms_persist_for_owner(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        general_response = self.client.post(
            reverse("profile"),
            {
                "save_general": "",
                "name": "Nome Atualizado",
                "birth_date": "1995-03-11",
                "gender": User.Gender.NON_BINARY,
                "address_street": "Rua das Flores",
                "address_number": "42",
                "address_complement": "Apto 3",
                "address_neighborhood": "Centro",
                "address_city": "São Paulo",
            },
        )
        self.assertRedirects(general_response, reverse("profile") + "#panel-general")
        user.refresh_from_db()
        self.assertEqual(user.name, "Nome Atualizado")
        self.assertEqual(str(user.birth_date), "1995-03-11")
        self.assertEqual(user.gender, User.Gender.NON_BINARY)
        self.assertEqual(user.address_street, "Rua das Flores")
        self.assertEqual(user.address_number, "42")
        self.assertEqual(user.address_complement, "Apto 3")
        self.assertEqual(user.address_neighborhood, "Centro")
        self.assertEqual(user.address_city, "São Paulo")

        health_response = self.client.post(
            reverse("profile"),
            {
                "save_health": "",
                "weight_kg": "62.5",
                "height_cm": "168",
                "blood_type": "O+",
                "conditions": "Asma",
                "allergies_summary": "Amendoim",
                "surgeries_summary": "",
                "is_smoker": "false",
                "consumes_alcohol": "false",
                "medication[]": ["Inalador", ""],
                "medication_dosage[]": ["2 jatos", ""],
                "medication_instructions[]": ["Se necessário", ""],
            },
        )
        self.assertRedirects(health_response, reverse("profile") + "#panel-health")
        profile = UserHealthProfile.objects.get(user=user)
        self.assertEqual(str(profile.weight_kg), "62.50")
        self.assertEqual(profile.blood_type, "O+")
        self.assertEqual(
            profile._meta.get_field("conditions").get_internal_type(),
            "TextField",
        )
        self.assertEqual(
            profile._meta.get_field("allergies_summary").get_internal_type(),
            "TextField",
        )
        self.assertEqual(
            profile._meta.get_field("surgeries_summary").get_internal_type(),
            "TextField",
        )
        self.assertFalse(profile.is_smoker)
        self.assertFalse(profile.consumes_alcohol)
        profile_response = self.client.get(reverse("profile"))
        self.assertRegex(
            profile_response.content.decode(),
            r'<input[^>]*name="is_smoker"[^>]*value="false"[^>]*checked',
        )
        self.assertRegex(
            profile_response.content.decode(),
            r'<input[^>]*name="consumes_alcohol"[^>]*value="false"[^>]*checked',
        )
        medication = Medication.objects.get(user=user)
        self.assertEqual(medication.name, "Inalador")
        self.assertEqual(medication.dosage, "2 jatos")

    def test_profile_multiline_fields_and_unneeded_fields(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertContains(response, '<textarea name="conditions"')
        self.assertContains(response, '<textarea name="allergies_summary"')
        self.assertContains(response, '<textarea name="surgeries_summary"')
        self.assertContains(response, '<textarea name="instructions"')
        self.assertNotContains(response, "other_gender")
        self.assertNotContains(response, "name=\"notes\"")
        self.assertNotIn("other_gender", {field.name for field in User._meta.fields})
        self.assertNotIn(
            "notes",
            {field.name for field in UserHealthProfile._meta.fields},
        )

    def test_profile_phone_fields_render_mask_attributes(self) -> None:
        user = self.create_user()
        EmergencyContact.objects.create(
            user=user,
            name="Contato",
            phone="31999999999",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertContains(response, 'type="tel"')
        self.assertContains(response, "data-phone-mask")
        script = (
            Path(__file__).resolve().parent
            / "static"
            / "SafeSpace"
            / "js"
            / "site.js"
        ).read_text(encoding="utf-8")
        self.assertIn("formatBrazilianPhoneNumber", script)
        profile_script = (
            Path(__file__).resolve().parent
            / "static"
            / "SafeSpace"
            / "js"
            / "profile.js"
        ).read_text(encoding="utf-8")
        self.assertIn('name: "medication_dosage[]"', profile_script)
        self.assertIn('name: "medication_instructions[]"', profile_script)
        self.assertIn("field.mask", profile_script)

    def test_profile_and_sos_writes_require_csrf(self) -> None:
        user = self.create_user()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(user)

        profile_response = csrf_client.post(
            reverse("profile"),
            {"save_general": "", "name": "Alteração sem token"},
        )
        sos_response = csrf_client.post(
            reverse("sos"),
            {"share_blood_type": "on"},
        )

        self.assertEqual(profile_response.status_code, 403)
        self.assertEqual(sos_response.status_code, 403)
        user.refresh_from_db()
        self.assertEqual(user.name, "Pessoa Exemplo")
        self.assertFalse(UserSosPreferences.objects.filter(user=user).exists())

    def test_profile_sos_contacts_and_crisis_instructions_persist(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("profile"),
            {
                "save_sos": "",
                "emergency_contact_name[]": ["Alex", "Sam", "Jo"],
                "emergency_contact_relationship[]": ["Amigue", "Irmãe", "Amigue"],
                "emergency_contact_phone[]": [
                    "+5511999999999",
                    "+5511888888888",
                    "+5511777777777",
                ],
                "instructions": "Fale com calma e ligue para Alex.",
            },
        )

        self.assertRedirects(response, reverse("profile") + "#panel-sos")
        self.assertEqual(
            list(
                EmergencyContact.objects.filter(user=user)
                .order_by("priority")
                .values_list("name", flat=True)
            ),
            ["Alex", "Sam", "Jo"],
        )
        self.assertEqual(
            CrisisInstructions.objects.get(user=user).instructions,
            "Fale com calma e ligue para Alex.",
        )

    def test_emergency_contact_limit_is_three_and_preserves_existing_contacts(self) -> None:
        user = self.create_user()
        self.client.force_login(user)
        for index, name in enumerate(("Alex", "Sam", "Jo")):
            EmergencyContact.objects.create(
                user=user,
                name=name,
                phone=f"+551199999999{index}",
                priority=index,
            )

        response = self.client.post(
            reverse("profile"),
            {
                "save_sos": "",
                "emergency_contact_name[]": ["Alex", "Sam", "Jo", "Kim"],
                "emergency_contact_relationship[]": ["", "", "", ""],
                "emergency_contact_phone[]": [
                    "+5511999999990",
                    "+5511999999991",
                    "+5511999999992",
                    "+5511999999993",
                ],
                "instructions": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Você pode cadastrar até 3 contatos.")
        self.assertEqual(
            list(
                EmergencyContact.objects.filter(user=user)
                .order_by("priority")
                .values_list("name", flat=True)
            ),
            ["Alex", "Sam", "Jo"],
        )
        self.assertContains(response, "Adicione até 3 pessoas")

    def test_invalid_incremental_profile_data_does_not_partially_save(self) -> None:
        user = self.create_user()
        profile = UserHealthProfile.objects.create(
            user=user,
            blood_type="A+",
            conditions="Dados anteriores",
        )
        Medication.objects.create(user=user, name="Medicamento anterior")
        self.client.force_login(user)

        response = self.client.post(
            reverse("profile"),
            {
                "save_health": "",
                "weight_kg": "70",
                "height_cm": "170",
                "blood_type": "O+",
                "conditions": "",
                "allergies_summary": "",
                "surgeries_summary": "",
                "is_smoker": "",
                "consumes_alcohol": "",
                "medication[]": ["Novo medicamento"],
                "medication_dosage[]": [],
                "medication_instructions[]": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.blood_type, "A+")
        self.assertEqual(profile.conditions, "Dados anteriores")
        self.assertEqual(
            list(Medication.objects.filter(user=user).values_list("name", flat=True)),
            ["Medicamento anterior"],
        )

    def test_profile_password_change_preserves_authenticated_session(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("profile"),
            {
                "save_password": "",
                "old_password": TEST_PASSWORD,
                "new_password1": "Aurora-Lilas-2038!",
                "new_password2": "Aurora-Lilas-2038!",
            },
        )

        self.assertRedirects(
            response,
            reverse("profile") + "#panel-password",
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("Aurora-Lilas-2038!"))
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)

    def test_sos_card_exposes_only_selected_data_and_qr_is_local(self) -> None:
        user = self.create_user()
        user.address_street = "Rua Secreta"
        user.address_number = "42"
        user.address_city = "São Paulo"
        user.save()
        UserHealthProfile.objects.create(
            user=user,
            blood_type="O+",
            allergies_summary="Amendoim",
            conditions="Asma",
        )
        Medication.objects.create(user=user, name="Inalador")
        Medication.objects.create(user=user, name="Remédio diário")
        EmergencyContact.objects.create(
            user=user,
            name="Contato Privado",
            phone="+5511999999999",
        )
        CrisisInstructions.objects.create(
            user=user,
            instructions="Orientação Privada",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("sos"),
            {
                "share_blood_type": "on",
                "share_allergies": "on",
            },
        )
        self.assertRedirects(response, reverse("sos"))
        preferences = UserSosPreferences.objects.get(user=user)
        sos_preview_response = self.client.get(reverse("sos"))
        self.assertContains(sos_preview_response, "id-card-medications")
        token = create_sos_token(preferences)
        card_response = self.client.get(
            reverse("sos_card", kwargs={"token": token})
        )

        self.assertEqual(card_response.status_code, 200)
        self.assertContains(card_response, "Pessoa Exemplo")
        self.assertContains(card_response, "O+")
        self.assertContains(card_response, "Amendoim")
        self.assertContains(card_response, "Informações de emergência")
        self.assertContains(card_response, "public-card-details")
        self.assertContains(card_response, "SafeSpace/css/theme.css")
        self.assertContains(card_response, "SafeSpace/css/sos.css?v=6")
        self.assertNotContains(card_response, "public-card-actions")
        self.assertNotContains(card_response, "Baixar cartão para impressão")
        self.assertNotContains(card_response, "data-print-card")
        self.assertNotContains(card_response, "FRENTE")
        self.assertNotContains(card_response, "VERSO")
        self.assertContains(card_response, "Não compartilhado")
        self.assertNotContains(card_response, "Rua Secreta")
        self.assertNotContains(card_response, "Inalador")
        self.assertNotContains(card_response, "Remédio diário")
        self.assertNotContains(card_response, "Asma")
        self.assertNotContains(card_response, "Contato Privado")
        self.assertNotContains(card_response, "Orientação Privada")
        self.assertEqual(card_response["Cache-Control"], "no-store, private")
        qr_response = self.client.get(reverse("sos_qr", kwargs={"token": token}))
        self.assertEqual(qr_response["Content-Type"], "image/png")
        qr_image = Image.open(BytesIO(qr_response.content))
        self.assertEqual(qr_image.format, "PNG")
        download_response = self.client.get(
            reverse("sos_card_download", kwargs={"token": token})
        )
        self.assertEqual(download_response["Content-Type"], "image/svg+xml")
        self.assertIn(b"data:image/png;base64,", download_response.content)
        self.assertIn(b'width="107.96mm" height="85.6mm"', download_response.content)
        self.assertIn(b'viewBox="0 0 800 635"', download_response.content)
        self.assertIn(b"VERSO", download_response.content)
        self.assertIn(b"FRENTE", download_response.content)
        self.assertNotIn(b"field-box", download_response.content)
        self.assertIn(b"Medicamentos", download_response.content)
        self.client.post(reverse("sos"), {"share_address": "on"})
        preferences.refresh_from_db()
        shared_address_response = self.client.get(
            reverse(
                "sos_card",
                kwargs={"token": create_sos_token(preferences)},
            )
        )
        self.assertContains(shared_address_response, "Rua Secreta")
        self.assertContains(shared_address_response, "São Paulo")

        self.client.post(reverse("sos"), {"share_medications": "on"})
        preferences.refresh_from_db()
        shared_medications_response = self.client.get(
            reverse(
                "sos_card",
                kwargs={"token": create_sos_token(preferences)},
            )
        )
        self.assertContains(
            shared_medications_response,
            "Inalador, Remédio diário",
        )
        medication_download_response = self.client.get(
            reverse(
                "sos_card_download",
                kwargs={"token": create_sos_token(preferences)},
            )
        )
        self.assertIn(b"Medicamentos", medication_download_response.content)
        self.assertIn(b"Inalador", medication_download_response.content)
        self.assertIn(b"Rem\xc3\xa9dio di\xc3\xa1rio", medication_download_response.content)
        self.assertIn(b'x="424"', medication_download_response.content)
        self.assertIn(b'x="602"', medication_download_response.content)

    def test_sos_sharing_options_show_saved_values_and_card_availability(self) -> None:
        user = self.create_user()
        UserHealthProfile.objects.create(
            user=user,
            weight_kg="68.5",
            height_cm="174",
            is_smoker=False,
            consumes_alcohol=False,
        )
        Medication.objects.create(user=user, name="Vitamina D")
        self.client.force_login(user)

        response = self.client.get(reverse("sos"))

        self.assertContains(response, "Peso")
        self.assertContains(response, "68.5 kg")
        self.assertContains(response, "Altura")
        self.assertContains(response, "174 cm")
        self.assertContains(response, "Fumante")
        self.assertContains(response, "Consome bebida alcoólica")
        self.assertContains(response, "Nenhuma informação preenchida.")
        self.assertContains(response, "Vitamina D")
        self.assertEqual(
            response.content.decode().count("(disponível no cartão)"),
            8,
        )

    def test_sos_token_is_revoked_when_preferences_are_saved_again(self) -> None:
        user = self.create_user()
        self.client.force_login(user)
        self.client.post(reverse("sos"), {"share_blood_type": "on"})
        preference = UserSosPreferences.objects.get(user=user)
        token = create_sos_token(preference)

        self.client.post(reverse("sos"), {"share_blood_type": "on"})
        old_response = self.client.get(
            reverse("sos_card", kwargs={"token": token})
        )
        self.assertEqual(old_response.status_code, 404)

    def test_sos_default_preferences_are_checked_and_name_is_mandatory(self) -> None:
        user = self.create_user()
        self.client.force_login(user)

        response = self.client.get(reverse("sos"))

        preferences = UserSosPreferences(user=user)
        for field_name in (
            "share_address",
            "share_profile_picture",
            "share_blood_type",
            "share_allergies",
            "share_medications",
            "share_conditions",
            "share_emergency_contacts",
            "share_crisis_instructions",
        ):
            self.assertTrue(getattr(preferences, field_name))
            self.assertContains(response, f'name="{field_name}"')
        for field_name in (
            "share_weight",
            "share_height",
            "share_smoker",
            "share_alcohol",
        ):
            self.assertFalse(getattr(preferences, field_name))
            self.assertContains(response, f'name="{field_name}"')
        self.assertEqual(
            response.content.decode().count("(disponível no cartão)"),
            8,
        )
        self.assertNotContains(response, 'name="share_name"')
        self.assertContains(response, user.name)

    def test_false_health_radio_values_remain_selected_when_loaded(self) -> None:
        user = self.create_user()
        profile = UserHealthProfile.objects.create(
            user=user,
            is_smoker=False,
            consumes_alcohol=False,
        )

        form = HealthProfileForm(instance=profile)

        self.assertRegex(
            str(form["is_smoker"]),
            r'<input[^>]*value="false"[^>]*checked',
        )
        self.assertRegex(
            str(form["consumes_alcohol"]),
            r'<input[^>]*value="false"[^>]*checked',
        )

    def test_optional_health_details_are_only_in_public_link(self) -> None:
        user = self.create_user()
        UserHealthProfile.objects.create(
            user=user,
            weight_kg="62.50",
            height_cm="168.00",
            is_smoker=False,
            consumes_alcohol=True,
        )
        self.client.force_login(user)

        self.client.post(
            reverse("sos"),
            {
                "share_weight": "on",
                "share_height": "on",
                "share_smoker": "on",
                "share_alcohol": "on",
            },
        )
        preferences = UserSosPreferences.objects.get(user=user)
        token = create_sos_token(preferences)
        public_response = self.client.get(
            reverse("sos_card", kwargs={"token": token})
        )
        download_response = self.client.get(
            reverse("sos_card_download", kwargs={"token": token})
        )

        self.assertContains(public_response, "62.50 kg")
        self.assertContains(public_response, "168.00 cm")
        self.assertContains(public_response, "<dd>Não</dd>", html=True)
        self.assertContains(public_response, "<dd>Sim</dd>", html=True)
        card_only_labels = (
            "Peso",
            "Altura",
            "Fumante",
            "Consome bebida alcoólica",
        )
        for label in card_only_labels:
            self.assertNotIn(label.encode(), download_response.content)

    def test_sos_bearer_link_is_public_and_malformed_tokens_fail(self) -> None:
        owner = self.create_user()
        other_user = self.create_user("outra@example.com")
        self.client.force_login(owner)
        self.client.post(reverse("sos"), {"share_blood_type": "on"})
        preferences = UserSosPreferences.objects.get(user=owner)
        token = create_sos_token(preferences)
        self.client.force_login(other_user)

        bad_response = self.client.get(
            reverse("sos_card", kwargs={"token": "not-a-valid-token"})
        )
        self.assertEqual(bad_response.status_code, 404)
        public_response = self.client.get(
            reverse("sos_card", kwargs={"token": token})
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, owner.name)
        self.assertEqual(
            self.client.get(reverse("profile_picture")).status_code,
            404,
        )

    def test_profile_photo_is_validated_and_served_only_when_authenticated(
        self,
    ) -> None:
        image_buffer = BytesIO()
        Image.new("RGB", (32, 24), color="pink").save(image_buffer, format="PNG")
        upload = SimpleUploadedFile(
            "profile.png",
            image_buffer.getvalue(),
            content_type="image/png",
        )
        user = self.create_user()
        self.client.force_login(user)
        response = self.client.post(
            reverse("profile"),
            {
                "save_general": "",
                "name": user.name,
                "birth_date": "",
                "gender": "",
                "profile_picture": upload,
            },
        )

        self.assertRedirects(response, reverse("profile") + "#panel-general")
        user.refresh_from_db()
        self.assertTrue(user.profile_picture.name.startswith("profile-pictures/"))
        self.addCleanup(user.profile_picture.delete, save=False)
        photo_response = self.client.get(reverse("profile_picture"))
        self.assertIsInstance(photo_response, StreamingHttpResponse)
        self.assertEqual(photo_response["Content-Type"], "image/png")
        self.assertEqual(photo_response["Cache-Control"], "private, no-store")
        stream_response = cast(StreamingHttpResponse, photo_response)
        image_chunks = cast(Iterable[bytes], stream_response.streaming_content)
        served_image = Image.open(BytesIO(b"".join(image_chunks)))
        self.assertEqual(served_image.size, (32, 24))

        self.client.post(
            reverse("sos"),
            {"share_profile_picture": "on"},
        )
        preferences = UserSosPreferences.objects.get(user=user)
        token = create_sos_token(preferences)
        public_card = self.client.get(reverse("sos_card", kwargs={"token": token}))
        self.assertContains(public_card, "data:image/jpeg;base64,")
        download_card = self.client.get(
            reverse("sos_card_download", kwargs={"token": token})
        )
        self.assertIn(b"data:image/jpeg;base64,", download_card.content)

        self.client.post(reverse("sos"), {"share_blood_type": "on"})
        preferences.refresh_from_db()
        private_photo_card = self.client.get(
            reverse(
                "sos_card",
                kwargs={"token": create_sos_token(preferences)},
            )
        )
        self.assertNotContains(private_photo_card, "data:image/jpeg;base64,")

        self.client.logout()
        unauthorized_response = self.client.get(reverse("profile_picture"))
        self.assertEqual(unauthorized_response.status_code, 302)
        other_user = self.create_user("outra@example.com")
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(reverse("profile_picture")).status_code,
            404,
        )
