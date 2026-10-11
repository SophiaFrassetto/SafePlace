from django.db import models

from SafeSpace.models.base import BaseModel


class DiaryEntry(BaseModel):
    class Mood(models.TextChoices):
        HAPPY = "happy", "Feliz"
        CALM = "calm", "Tranquilo(a)"
        EXCITED = "excited", "Animado(a)"
        TIRED = "tired", "Cansado(a)"
        ANXIOUS = "anxious", "Ansioso(a)"
        SAD = "sad", "Triste"
        OTHER = "other", "Outro"

    user = models.ForeignKey(
        "SafeSpace.User",
        on_delete=models.CASCADE,
        related_name="diary_entries",
    )
    entry_date = models.DateField(null=True, blank=True)
    mood = models.CharField(max_length=16, choices=Mood.choices, blank=True)
    content = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="diary_owner_date_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return "Diary entry"


class DiaryTask(BaseModel):
    diary_entry = models.ForeignKey(
        DiaryEntry,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    text = models.CharField(max_length=160)
    is_completed = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(
                fields=["diary_entry", "is_completed"],
                name="task_entry_done_idx",
            ),
        ]
        ordering = ["position", "created_at"]

    def __str__(self) -> str:
        return "Diary task"
