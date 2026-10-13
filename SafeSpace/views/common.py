from django.http import HttpRequest
from django.urls import reverse

from SafeSpace.models import User


def app_context(request: HttpRequest, page: str) -> dict[str, str]:
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
