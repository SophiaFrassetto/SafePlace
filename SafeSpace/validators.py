import warnings

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_PROFILE_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_profile_image(upload: UploadedFile) -> None:
    if upload.size is not None and upload.size > MAX_PROFILE_IMAGE_BYTES:
        raise ValidationError("A imagem deve ter no máximo 5 MB.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(upload)
            if image.format not in ALLOWED_PROFILE_IMAGE_FORMATS:
                raise ValidationError(
                    "Use uma imagem JPEG, PNG ou WebP."
                )
            image.verify()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
    ) as error:
        raise ValidationError("O arquivo enviado não é uma imagem válida.") from error
    finally:
        upload.seek(0)
