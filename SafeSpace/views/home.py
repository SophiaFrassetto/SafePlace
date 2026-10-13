from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from SafeSpace.models import DiaryTask, User
from SafeSpace.views.common import app_context


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
            **app_context(request, "home"),
            "tasks_page": task_page,
            "has_completed_tasks": DiaryTask.objects.filter(
                diary_entry__user=user,
                is_completed=True,
            ).exists(),
            "sos_settings_url": reverse("sos"),
        },
    )


@login_required
def health(request: HttpRequest) -> HttpResponse:
    return render(request, "health.html", app_context(request, "health"))
