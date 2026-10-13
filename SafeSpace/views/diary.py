import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from SafeSpace.forms import DiaryEntryForm, DiaryTaskForm
from SafeSpace.models import DiaryEntry, DiaryTask, User
from SafeSpace.views.common import app_context


def _diary_page_has_content(entry: DiaryEntry, *, has_tasks: bool) -> bool:
    return bool(
        entry.entry_date
        or entry.mood
        or entry.content.strip()
        or has_tasks
    )


def _tasks_redirect(entry: DiaryEntry, task_page: int) -> HttpResponse:
    return redirect(
        f"{reverse('diary')}?entry={entry.pk}&task_page={task_page}#diary-tasks"
    )


def _posted_task_page(request: HttpRequest) -> int:
    value = request.POST.get("task_page", "")
    return max(1, int(value)) if value.isdigit() else 1


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
                return _tasks_redirect(
                    saved_entry,
                    _posted_task_page(request),
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
                    return _tasks_redirect(
                        saved_entry,
                        -(
                            -DiaryTask.objects.filter(
                                diary_entry=saved_entry
                            ).count()
                            // 5
                        ),
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
                has_tasks = DiaryTask.objects.filter(
                    diary_entry=active_entry
                ).exists()
                if not _diary_page_has_content(
                    active_entry,
                    has_tasks=has_tasks,
                ):
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
        task_page_obj = None
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
        task_page_obj = Paginator(page_tasks, 5).get_page(
            request.GET.get("task_page")
        )
        has_content = _diary_page_has_content(
            active_entry,
            has_tasks=bool(page_tasks),
        )

    return render(
        request,
        "diary.html",
        {
            **app_context(request, "diary"),
            "entry_form": entry_form,
            "task_form": task_form,
            "active_entry": active_entry,
            "page_tasks": task_page_obj.object_list if task_page_obj else [],
            "task_page": task_page_obj,
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
