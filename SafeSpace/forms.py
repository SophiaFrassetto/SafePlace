from typing import cast

from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import QueryDict

from SafeSpace.models import (
    CrisisInstructions,
    DiaryEntry,
    User,
    UserHealthProfile,
    UserSosPreferences,
)


class SignUpForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    password = forms.CharField(
        max_length=128,
        strip=False,
        widget=forms.PasswordInput,
    )
    password_confirmation = forms.CharField(
        max_length=128,
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean_name(self) -> str:
        return self.cleaned_data["name"].strip()

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().casefold()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Não foi possível criar a conta com esses dados."
            )
        return email

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirmation = cleaned_data.get("password_confirmation")

        if password and confirmation and password != confirmation:
            self.add_error(
                "password_confirmation",
                "As senhas não coincidem.",
            )
            return cleaned_data

        if password:
            candidate_user = User.objects.model(
                name=cleaned_data.get("name", ""),
                email=cleaned_data.get("email", ""),
            )
            try:
                validate_password(password, user=candidate_user)
            except ValidationError as error:
                self.add_error("password", error)

        return cleaned_data

    def save(self) -> User:
        if not self.is_valid():
            raise ValueError("A valid signup form is required.")

        return User.objects.create_user(
            email=self.cleaned_data["email"],
            name=self.cleaned_data["name"],
            password=self.cleaned_data["password"],
        )


class DiaryEntryForm(forms.ModelForm):
    class Meta:
        model = DiaryEntry
        fields = ("entry_date", "mood", "content")
        widgets = {
            "entry_date": forms.DateInput(
                attrs={"type": "date", "class": "diary-date-input"},
                format="%Y-%m-%d",
            ),
            "mood": forms.Select(attrs={"class": "diary-mood-input"}),
            "content": forms.Textarea(
                attrs={
                    "rows": 7,
                    "class": "diary-entry",
                    "placeholder": "Este espaço é seu. Escreva sem pressa...",
                }
            ),
        }


class DiaryTaskForm(forms.Form):
    text = forms.CharField(
        max_length=160,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "todo-task-input",
                "placeholder": "Adicionar um afazer",
                "required": True,
                "form": "diary-entry-form",
            }
        ),
    )


class EmailLoginForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password = forms.CharField(
        max_length=128,
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().casefold()


class ProfileGeneralForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "name",
            "birth_date",
            "gender",
            "profile_picture",
            "address_street",
            "address_number",
            "address_complement",
            "address_neighborhood",
            "address_city",
        )
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "birth_date": forms.DateInput(
                attrs={"type": "date", "autocomplete": "bday"},
                format="%Y-%m-%d",
            ),
            "gender": forms.Select(),
            "profile_picture": forms.FileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/webp",
                    "data-profile-photo": "",
                }
            ),
            "address_street": forms.TextInput(
                attrs={"autocomplete": "address-line1", "maxlength": 180}
            ),
            "address_number": forms.TextInput(
                attrs={"autocomplete": "address-line2", "maxlength": 32}
            ),
            "address_complement": forms.TextInput(attrs={"maxlength": 100}),
            "address_neighborhood": forms.TextInput(
                attrs={"autocomplete": "address-level3", "maxlength": 100}
            ),
            "address_city": forms.TextInput(
                attrs={"autocomplete": "address-level2", "maxlength": 100}
            ),
        }

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if not name:
            raise ValidationError("Informe seu nome.")
        return name


def _coerce_optional_boolean(value: str) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "":
        return None
    raise ValueError("Selecione uma opção válida.")


class OptionalBooleanChoiceField(forms.TypedChoiceField):
    def prepare_value(self, value: object) -> object:
        if value is True:
            return "true"
        if value is False:
            return "false"
        return super().prepare_value(value)


class HealthProfileForm(forms.ModelForm):
    conditions = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    allergies_summary = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    surgeries_summary = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    is_smoker = OptionalBooleanChoiceField(
        choices=(("", "Não informado"), ("true", "Sim"), ("false", "Não")),
        coerce=_coerce_optional_boolean,
        required=False,
        widget=forms.RadioSelect(attrs={"class": "choice-options"}),
    )
    consumes_alcohol = OptionalBooleanChoiceField(
        choices=(("", "Não informado"), ("true", "Sim"), ("false", "Não")),
        coerce=_coerce_optional_boolean,
        required=False,
        widget=forms.RadioSelect(attrs={"class": "choice-options"}),
    )

    class Meta:
        model = UserHealthProfile
        fields = (
            "weight_kg",
            "height_cm",
            "blood_type",
            "conditions",
            "allergies_summary",
            "surgeries_summary",
            "is_smoker",
            "consumes_alcohol",
        )
        widgets = {
            "weight_kg": forms.NumberInput(
                attrs={"min": "0", "max": "999.99", "step": "0.1", "inputmode": "decimal"}
            ),
            "height_cm": forms.NumberInput(
                attrs={"min": "0", "max": "999.99", "step": "0.1", "inputmode": "decimal"}
            ),
        }


class CrisisInstructionsForm(forms.ModelForm):
    instructions = forms.CharField(
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    class Meta:
        model = CrisisInstructions
        fields = ("instructions",)


class SosPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserSosPreferences
        fields = (
            "share_address",
            "share_profile_picture",
            "share_blood_type",
            "share_allergies",
            "share_medications",
            "share_conditions",
            "share_emergency_contacts",
            "share_crisis_instructions",
            "share_weight",
            "share_height",
            "share_smoker",
            "share_alcohol",
        )
        labels = {
            "share_address": "Endereço",
            "share_profile_picture": "Foto de perfil",
            "share_blood_type": "Tipo sanguíneo",
            "share_allergies": "Alergias",
            "share_medications": "Medicamentos",
            "share_conditions": "Condições importantes",
            "share_emergency_contacts": "Contato de emergência",
            "share_crisis_instructions": "Orientações em caso de crise",
            "share_weight": "Peso",
            "share_height": "Altura",
            "share_smoker": "Fumante",
            "share_alcohol": "Consome bebida alcoólica",
        }
        widgets = {
            "share_address": forms.CheckboxInput(),
            "share_profile_picture": forms.CheckboxInput(),
            "share_blood_type": forms.CheckboxInput(),
            "share_allergies": forms.CheckboxInput(),
            "share_medications": forms.CheckboxInput(),
            "share_conditions": forms.CheckboxInput(),
            "share_emergency_contacts": forms.CheckboxInput(),
            "share_crisis_instructions": forms.CheckboxInput(),
            "share_weight": forms.CheckboxInput(),
            "share_height": forms.CheckboxInput(),
            "share_smoker": forms.CheckboxInput(),
            "share_alcohol": forms.CheckboxInput(),
        }


class ProfilePasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "profile-password-input"})


class MedicationListForm(forms.Form):
    max_medications = 30

    def medication_items(self) -> list[dict[str, str]]:
        value = self.cleaned_data["medications"]
        if not isinstance(value, list) or not all(
            isinstance(item, dict) for item in value
        ):
            raise ValueError("Medication list form was not validated.")
        return cast(list[dict[str, str]], value)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if not isinstance(self.data, QueryDict):
            return cleaned_data

        names = self.data.getlist("medication[]")
        dosages = self.data.getlist("medication_dosage[]")
        instructions = self.data.getlist("medication_instructions[]")
        if len(names) > self.max_medications:
            raise ValidationError("Você pode cadastrar até 30 medicamentos.")
        if len(names) != len(dosages) or len(names) != len(instructions):
            raise ValidationError("Confira os campos dos medicamentos.")

        medications: list[dict[str, str]] = []
        for name, dosage, instruction in zip(names, dosages, instructions):
            name = name.strip()
            dosage = dosage.strip()
            instruction = instruction.strip()
            if not name:
                if dosage or instruction:
                    raise ValidationError(
                        "Informe o nome de cada medicamento preenchido."
                    )
                continue
            if len(name) > 160 or len(dosage) > 120 or len(instruction) > 240:
                raise ValidationError("Confira o tamanho dos campos de medicamento.")
            medications.append(
                {"name": name, "dosage": dosage, "instructions": instruction}
            )

        cleaned_data["medications"] = medications
        return cleaned_data


class EmergencyContactListForm(forms.Form):
    max_contacts = 3
    max_submitted_rows = 30

    def contact_items(self) -> list[dict[str, str]]:
        value = self.cleaned_data["contacts"]
        if not isinstance(value, list) or not all(
            isinstance(item, dict) for item in value
        ):
            raise ValueError("Emergency contact form was not validated.")
        return cast(list[dict[str, str]], value)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if not isinstance(self.data, QueryDict):
            return cleaned_data

        names = self.data.getlist("emergency_contact_name[]")
        relationships = self.data.getlist("emergency_contact_relationship[]")
        phones = self.data.getlist("emergency_contact_phone[]")
        if len(names) > self.max_submitted_rows:
            raise ValidationError("Revise a quantidade de contatos enviados.")
        if len(names) != len(relationships) or len(names) != len(phones):
            raise ValidationError("Confira os campos dos contatos de emergência.")

        contacts: list[dict[str, str]] = []
        for name, relationship, phone in zip(names, relationships, phones):
            name = name.strip()
            relationship = relationship.strip()
            phone = phone.strip()
            if not name and not relationship and not phone:
                continue
            if not name or not phone:
                raise ValidationError(
                    "Informe o nome e o telefone de cada contato preenchido."
                )
            if len(name) > 150 or len(relationship) > 80 or len(phone) > 32:
                raise ValidationError("Confira o tamanho dos campos de contato.")
            contacts.append(
                {"name": name, "relationship": relationship, "phone": phone}
            )

        if len(contacts) > self.max_contacts:
            raise ValidationError("Você pode cadastrar até 3 contatos.")

        cleaned_data["contacts"] = contacts
        return cleaned_data
