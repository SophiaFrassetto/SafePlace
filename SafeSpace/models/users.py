from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models

from SafeSpace.models.base import BaseModel
from SafeSpace.models.managers import UserManager
from SafeSpace.validators import validate_profile_image


class User(BaseModel, AbstractUser):
    class Gender(models.TextChoices):
        CIS_WOMAN = "cis_woman", "Mulher cis"
        TRANS_WOMAN = "trans_woman", "Mulher trans"
        CIS_MAN = "cis_man", "Homem cis"
        TRANS_MAN = "trans_man", "Homem trans"
        NON_BINARY = "non_binary", "Pessoa não binária"
        GENDERQUEER = "genderqueer", "Pessoa genderqueer"
        AGENDER = "agender", "Pessoa agênero"
        GENDER_FLUID = "gender_fluid", "Pessoa de gênero fluido"
        BIGENDER = "bigender", "Pessoa bigênero"
        PANGENDER = "pangender", "Pessoa pangênero"
        DEMIWOMAN = "demiwoman", "Demimulher"
        DEMIMAN = "demiman", "Demihomem"
        DEMIGENDER = "demigender", "Pessoa demigênero"
        NEUTROIS = "neutrois", "Pessoa neutrois"
        TRAVESTI = "travesti", "Travesti"
        TWO_SPIRIT = "two_spirit", "Two-spirit"
        QUESTIONING = "questioning", "Questionando"
        OTHER = "other", "Outra identidade"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefiro não informar"

    username = None
    first_name = None
    last_name = None
    date_joined = None

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    profile_picture = models.ImageField(
        upload_to="profile-pictures/",
        blank=True,
        validators=[validate_profile_image],
    )
    address_street = models.CharField(max_length=180, blank=True)
    address_number = models.CharField(max_length=32, blank=True)
    address_complement = models.CharField(max_length=100, blank=True)
    address_neighborhood = models.CharField(max_length=100, blank=True)
    address_city = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=32,
        choices=Gender.choices,
        blank=True,
    )

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        indexes = [
            models.Index(fields=["created_at"], name="user_created_idx"),
        ]

    def __str__(self) -> str:
        return "SafeSpace user"
