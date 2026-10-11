from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from SafeSpace.models.base import BaseModel


class UserHealthProfile(BaseModel):
    class BloodType(models.TextChoices):
        A_POSITIVE = "A+", "A+"
        A_NEGATIVE = "A-", "A-"
        B_POSITIVE = "B+", "B+"
        B_NEGATIVE = "B-", "B-"
        AB_POSITIVE = "AB+", "AB+"
        AB_NEGATIVE = "AB-", "AB-"
        O_POSITIVE = "O+", "O+"
        O_NEGATIVE = "O-", "O-"
        UNKNOWN = "unknown", "Não sei"

    user = models.OneToOneField(
        "SafeSpace.User",
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999.99)],
    )
    height_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999.99)],
    )
    blood_type = models.CharField(
        max_length=8,
        choices=BloodType.choices,
        blank=True,
    )
    conditions = models.TextField(blank=True)
    allergies_summary = models.TextField(blank=True)
    surgeries_summary = models.TextField(blank=True)
    is_smoker = models.BooleanField(null=True, blank=True)
    consumes_alcohol = models.BooleanField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["updated_at"], name="health_updated_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(weight_kg__isnull=True) | Q(weight_kg__gte=0),
                name="health_weight_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(height_cm__isnull=True) | Q(height_cm__gte=0),
                name="health_height_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return "Health profile"


class Medication(BaseModel):
    user = models.ForeignKey(
        "SafeSpace.User",
        on_delete=models.CASCADE,
        related_name="medications",
    )
    name = models.CharField(max_length=160)
    dosage = models.CharField(max_length=120, blank=True)
    instructions = models.CharField(max_length=240, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "name"],
                name="med_owner_name_idx",
            ),
        ]
        ordering = ["name", "created_at"]

    def __str__(self) -> str:
        return "Medication"


class EmergencyContact(BaseModel):
    user = models.ForeignKey(
        "SafeSpace.User",
        on_delete=models.CASCADE,
        related_name="emergency_contacts",
    )
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=32)
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "priority"],
                name="contact_owner_order_idx",
            ),
        ]
        ordering = ["priority", "created_at"]

    def __str__(self) -> str:
        return "Emergency contact"


class CrisisInstructions(BaseModel):
    user = models.OneToOneField(
        "SafeSpace.User",
        on_delete=models.CASCADE,
        related_name="crisis_instructions",
    )
    instructions = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["updated_at"], name="crisis_updated_idx"),
        ]

    def __str__(self) -> str:
        return "Crisis instructions"


class UserSosPreferences(BaseModel):
    user = models.OneToOneField(
        "SafeSpace.User",
        on_delete=models.CASCADE,
        related_name="sos_preferences",
    )
    share_address = models.BooleanField(default=True)
    share_profile_picture = models.BooleanField(default=True)
    share_blood_type = models.BooleanField(default=True)
    share_allergies = models.BooleanField(default=True)
    share_medications = models.BooleanField(default=True)
    share_conditions = models.BooleanField(default=True)
    share_emergency_contacts = models.BooleanField(default=True)
    share_crisis_instructions = models.BooleanField(default=True)
    share_weight = models.BooleanField(default=False)
    share_height = models.BooleanField(default=False)
    share_smoker = models.BooleanField(default=False)
    share_alcohol = models.BooleanField(default=False)
    public_token_version = models.UUIDField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["updated_at"], name="sos_updated_idx"),
        ]

    def __str__(self) -> str:
        return "SOS preferences"
