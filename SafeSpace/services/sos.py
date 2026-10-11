import base64
import io
import textwrap
from dataclasses import dataclass
from html import escape
from uuid import UUID

import qrcode
from PIL import Image, ImageOps
from qrcode.constants import ERROR_CORRECT_M
from django.contrib.staticfiles import finders
from django.core import signing
from django.core.signing import BadSignature

from SafeSpace.models import (
    CrisisInstructions,
    EmergencyContact,
    Medication,
    User,
    UserHealthProfile,
    UserSosPreferences,
)

SOS_TOKEN_SALT = "SafeSpace.public-sos-card.v1"


class InvalidSosToken(ValueError):
    """Raised when a public SOS card token is invalid or has been revoked."""


@dataclass(frozen=True, slots=True)
class SosCardData:
    display_name: str
    profile_picture_data_uri: str
    profile_picture_shared: bool
    blood_type: str
    weight: str
    height: str
    smoker: str
    alcohol: str
    address: str
    allergies: str
    medications: tuple[str, ...]
    conditions: str
    emergency_contacts: tuple[str, ...]
    crisis_instructions: str


def create_sos_token(preferences: UserSosPreferences) -> str:
    if preferences.public_token_version is None:
        raise ValueError("A SOS card token version must exist.")

    return signing.dumps(
        {
            "preferences_id": str(preferences.pk),
            "version": str(preferences.public_token_version),
        },
        salt=SOS_TOKEN_SALT,
    )


def resolve_sos_token(token: str) -> UserSosPreferences:
    try:
        payload = signing.loads(token, salt=SOS_TOKEN_SALT)
        if not isinstance(payload, dict):
            raise InvalidSosToken
        preferences_id = UUID(payload["preferences_id"])
        version = UUID(payload["version"])
    except (BadSignature, KeyError, TypeError, ValueError) as error:
        raise InvalidSosToken from error

    preferences = UserSosPreferences.objects.filter(
        pk=preferences_id,
        public_token_version=version,
    ).first()
    if preferences is None:
        raise InvalidSosToken
    return preferences


def _optional_value(value: str, *, shared: bool) -> str:
    if not shared:
        return "Não compartilhado"
    return value.strip() or "Não informado"


def _boolean_display(value: bool | None) -> str:
    if value is True:
        return "Sim"
    if value is False:
        return "Não"
    return ""


def _profile_picture_data_uri(user: User, *, shared: bool) -> str:
    if not shared or not user.profile_picture:
        return ""

    with user.profile_picture.open("rb") as uploaded_image:
        with Image.open(uploaded_image) as image:
            thumbnail = ImageOps.fit(
                image.convert("RGB"),
                (256, 256),
                method=Image.Resampling.LANCZOS,
            )
            output = io.BytesIO()
            thumbnail.save(output, format="JPEG", quality=82, optimize=True)

    image_data = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{image_data}"


def get_sos_card_data(
    user: User,
    preferences: UserSosPreferences,
) -> SosCardData:
    needs_health_profile = any(
        (
            preferences.share_blood_type,
            preferences.share_allergies,
            preferences.share_conditions,
            preferences.share_weight,
            preferences.share_height,
            preferences.share_smoker,
            preferences.share_alcohol,
        )
    )
    profile = (
        UserHealthProfile.objects.filter(user=user).first()
        if needs_health_profile
        else None
    )

    medications: tuple[str, ...] = ()
    if preferences.share_medications:
        medication_rows = Medication.objects.filter(user=user).only(
            "name", "dosage", "instructions"
        )
        medications = tuple(
            ", ".join(
                part
                for part in (item.name, item.dosage, item.instructions)
                if part
            )
            for item in medication_rows
        )
    medication_values = (
        medications or ("Não informado",)
        if preferences.share_medications
        else ("Não compartilhado",)
    )

    contacts: tuple[str, ...] = ()
    if preferences.share_emergency_contacts:
        contact_rows = EmergencyContact.objects.filter(user=user).only(
            "name", "relationship", "phone"
        )
        contacts = tuple(
            " - ".join(
                part for part in (item.name, item.relationship, item.phone) if part
            )
            for item in contact_rows
        )
    contact_values = (
        contacts or ("Não informado",)
        if preferences.share_emergency_contacts
        else ("Não compartilhado",)
    )

    crisis_instructions = ""
    if preferences.share_crisis_instructions:
        crisis = (
            CrisisInstructions.objects.filter(user=user)
            .only("instructions")
            .first()
        )
        if crisis is not None:
            crisis_instructions = crisis.instructions

    blood_type_display = ""
    if profile is not None and preferences.share_blood_type:
        blood_type_display = next(
            (
                str(label)
                for blood_type, label in UserHealthProfile.BloodType.choices
                if blood_type == profile.blood_type
            ),
            "",
        )

    address = ""
    if preferences.share_address:
        address = ", ".join(
            part
            for part in (
                user.address_street,
                user.address_number,
                user.address_complement,
                user.address_neighborhood,
                user.address_city,
            )
            if part
        )

    allergies = (
        profile.allergies_summary
        if profile is not None and preferences.share_allergies
        else ""
    )
    conditions = (
        profile.conditions
        if profile is not None and preferences.share_conditions
        else ""
    )
    weight = (
        f"{profile.weight_kg} kg"
        if profile is not None and profile.weight_kg is not None
        else ""
    )
    height = (
        f"{profile.height_cm} cm"
        if profile is not None and profile.height_cm is not None
        else ""
    )
    smoker = _boolean_display(
        profile.is_smoker
        if profile is not None and preferences.share_smoker
        else None
    )
    alcohol = _boolean_display(
        profile.consumes_alcohol
        if profile is not None and preferences.share_alcohol
        else None
    )

    return SosCardData(
        display_name=user.name,
        profile_picture_data_uri=_profile_picture_data_uri(
            user,
            shared=preferences.share_profile_picture,
        ),
        profile_picture_shared=preferences.share_profile_picture,
        blood_type=_optional_value(
            blood_type_display,
            shared=preferences.share_blood_type,
        ),
        weight=_optional_value(weight, shared=preferences.share_weight),
        height=_optional_value(height, shared=preferences.share_height),
        smoker=_optional_value(smoker, shared=preferences.share_smoker),
        alcohol=_optional_value(alcohol, shared=preferences.share_alcohol),
        address=_optional_value(address, shared=preferences.share_address),
        allergies=_optional_value(
            allergies,
            shared=preferences.share_allergies,
        ),
        medications=medication_values,
        conditions=_optional_value(
            conditions,
            shared=preferences.share_conditions,
        ),
        emergency_contacts=contact_values,
        crisis_instructions=_optional_value(
            crisis_instructions,
            shared=preferences.share_crisis_instructions,
        ),
    )


def generate_qr_png(value: str) -> bytes:
    code = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    code.add_data(value)
    code.make(fit=True)
    image = code.make_image(fill_color="#26384a", back_color="#ffffff")
    output = io.BytesIO()
    image.save(output)
    return output.getvalue()


def _svg_text(
    label: str,
    value: str,
    *,
    x: int,
    y: int,
    width: int,
    max_lines: int = 2,
) -> str:
    lines = textwrap.wrap(
        value,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    )[:max_lines] or ["Não informado"]
    text_lines = "".join(
        f'<tspan x="{x}" dy="{17 if index else 0}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (
        f'<text x="{x}" y="{y}" class="field-label">{escape(label)}</text>'
        f'<text x="{x}" y="{y + 15}" class="field-value">{text_lines}</text>'
    )


def _svg_medication_columns(medications: tuple[str, ...]) -> str:
    columns: list[list[str]] = [[], []]
    column_lines = [0, 0]
    for medication in medications:
        wrapped_lines = textwrap.wrap(
            medication,
            width=20,
            break_long_words=True,
            break_on_hyphens=False,
        ) or ["Não informado"]
        wrapped_lines[0] = f"• {wrapped_lines[0]}"
        column_index = 0 if column_lines[0] <= column_lines[1] else 1
        columns[column_index].extend(wrapped_lines)
        column_lines[column_index] += len(wrapped_lines)

    column_markup: list[str] = []
    for index, lines in enumerate(columns):
        x = 424 if index == 0 else 602
        text_lines = "".join(
            f'<tspan x="{x}" dy="{16 if line_index else 0}">{escape(line)}</tspan>'
            for line_index, line in enumerate(lines)
        )
        column_markup.append(
            f'<text x="{x}" y="112" class="field-value medication-list">'
            f"{text_lines}</text>"
        )
    return "".join(column_markup)


def render_sos_card_svg(data: SosCardData, qr_png: bytes) -> str:
    icon_path = finders.find("SafeSpace/img/icon_safe_place.png")
    if not isinstance(icon_path, str):
        raise FileNotFoundError("SafeSpace emergency card icon was not found.")
    with open(icon_path, "rb") as icon_file:
        icon_data = base64.b64encode(icon_file.read()).decode("ascii")
    qr_data = base64.b64encode(qr_png).decode("ascii")
    name_lines = textwrap.wrap(
        data.display_name,
        width=22,
        break_long_words=True,
        break_on_hyphens=False,
    )[:3] or ["Nome"]
    name = "".join(
        f'<tspan x="24" dy="{25 if index else 0}">{escape(line)}</tspan>'
        for index, line in enumerate(name_lines)
    )
    photo = (
        f'<image x="24" y="178" width="120" height="120" '
        f'preserveAspectRatio="xMidYMid slice" href="{data.profile_picture_data_uri}"/>'
        if data.profile_picture_data_uri
        else (
            '<rect x="24" y="178" width="120" height="120" rx="18" class="photo-placeholder"/>'
            f'<text x="84" y="244" text-anchor="middle" class="field-label">'
            f'{"Sem foto cadastrada" if data.profile_picture_shared else "Não compartilhada"}</text>'
        )
    )
    contact_text = ", ".join(data.emergency_contacts)
    qr_image = f"data:image/png;base64,{qr_data}"
    medication_columns = _svg_medication_columns(data.medications)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="107.96mm" height="85.6mm" viewBox="0 0 800 635" role="img" aria-label="Cartão de emergência SafeSpace, frente e verso vertical">
<defs>
  <linearGradient id="paper" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fffdfd"/>
    <stop offset="1" stop-color="#fff0f3"/>
  </linearGradient>
  <pattern id="paper-dots" width="20" height="20" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="1" fill="#f5a9b8" opacity=".45"/>
  </pattern>
  <clipPath id="front-photo"><rect x="24" y="178" width="120" height="120" rx="18"/></clipPath>
  <style>
    text {{ font-family: Arial, sans-serif; fill: #31536b; }}
    .card {{ fill: url(#paper); stroke: #e5b6cd; stroke-width: 3; }}
    .inset {{ fill: none; stroke: #b9e9fa; stroke-width: 1.5; stroke-dasharray: 5 5; }}
    .field-label {{ font-size: 14px; font-weight: 700; fill: #547184; letter-spacing: .4px; }}
    .field-value {{ font-size: 16px; }}
    .medication-list {{ font-size: 15px; }}
    .name {{ font-size: 28px; font-weight: 700; }}
    .caption {{ font-size: 10px; letter-spacing: 1px; fill: #547184; }}
    .small {{ font-size: 12px; fill: #547184; }}
    .photo-placeholder {{ fill: #f3eef9; stroke: #e5b6cd; stroke-width: 2; }}
    .divider {{ stroke: #b9e9fa; stroke-width: 1.5; stroke-dasharray: 5 5; }}
  </style>
</defs>
<rect width="400" height="635" rx="24" class="card"/>
<rect width="400" height="635" rx="24" fill="url(#paper-dots)" opacity=".5"/>
<rect x="9" y="9" width="382" height="617" rx="18" class="inset"/>
<image x="24" y="16" width="40" height="40" href="data:image/png;base64,{icon_data}"/>
<text x="72" y="41" class="small">SafeSpace · cartão de emergência</text>
<text x="370" y="41" text-anchor="end" class="caption">FRENTE</text>
<text x="24" y="91" class="caption">NOME</text>
<text x="24" y="122" class="name">{name}</text>
<g clip-path="url(#front-photo)">{photo}</g>
{_svg_text("Tipo sanguíneo", data.blood_type, x=195, y=186, width=22, max_lines=2)}
{_svg_text("Contatos de emergência", contact_text, x=24, y=324, width=43, max_lines=6)}
<line x1="24" y1="442" x2="376" y2="442" class="divider"/>
{_svg_text("Endereço", data.address, x=24, y=466, width=27, max_lines=6)}
<rect x="258" y="458" width="122" height="122" rx="10" fill="#fffdfd" stroke="#d9f0f8" stroke-width="2"/>
<image x="265" y="465" width="108" height="108" href="{qr_image}" image-rendering="pixelated"/>
<text x="319" y="596" text-anchor="middle" class="caption">LEIA PARA VER OS DADOS</text>

<rect x="400" width="400" height="635" rx="24" class="card"/>
<rect x="400" width="400" height="635" rx="24" fill="url(#paper-dots)" opacity=".5"/>
<rect x="409" y="9" width="382" height="617" rx="18" class="inset"/>
<image x="424" y="16" width="40" height="40" href="data:image/png;base64,{icon_data}"/>
<text x="472" y="41" class="small">SafeSpace · informações de saúde</text>
<text x="770" y="41" text-anchor="end" class="caption">VERSO</text>
<text x="424" y="92" class="field-label">Medicamentos</text>
{medication_columns}
<line x1="424" y1="225" x2="776" y2="225" class="divider"/>
{_svg_text("Alergias", data.allergies, x=424, y=254, width=46, max_lines=5)}
<line x1="424" y1="352" x2="776" y2="352" class="divider"/>
{_svg_text("Condições importantes", data.conditions, x=424, y=382, width=46, max_lines=6)}
<line x1="424" y1="492" x2="776" y2="492" class="divider"/>
{_svg_text("Orientações em caso de crise", data.crisis_instructions, x=424, y=522, width=46, max_lines=7)}
<text x="770" y="612" text-anchor="end" class="small">Cuide de você</text>
</svg>"""
