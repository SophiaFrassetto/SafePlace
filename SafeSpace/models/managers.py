from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.auth.password_validation import validate_password

if TYPE_CHECKING:
    from SafeSpace.models.users import User


class UserManager(DjangoUserManager["User"]):
    use_in_migrations = True

    def create_user(
        self,
        email: str,
        name: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        normalized_email = self.normalize_email(email).strip().casefold()
        if not normalized_email:
            raise ValueError("An email address is required.")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("A display name is required.")

        user = self.model(
            email=normalized_email,
            name=normalized_name,
            **extra_fields,
        )
        if password is not None:
            validate_password(password, user=user)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        name: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if password is None:
            raise ValueError("A password is required for a superuser.")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields["is_staff"] is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(email, name, password, **extra_fields)
