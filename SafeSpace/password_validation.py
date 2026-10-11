import re

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    def validate(
        self,
        password: str,
        _user: AbstractBaseUser | None = None,
    ) -> None:
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra maiúscula."),
                code="password_no_uppercase",
            )
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra minúscula."),
                code="password_no_lowercase",
            )
        if not re.search(r"[^A-Za-z0-9\s]", password):
            raise ValidationError(
                _("A senha deve conter pelo menos um caractere especial."),
                code="password_no_special",
            )

    def get_help_text(self) -> str:
        return _(
            "A senha deve conter uma letra maiúscula, uma letra minúscula "
            "e um caractere especial."
        )
