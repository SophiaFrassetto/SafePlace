from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from SafeSpace.forms import EmailLoginForm, SignUpForm


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
