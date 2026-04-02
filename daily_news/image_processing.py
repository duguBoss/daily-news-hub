"""Image processing utilities (convert, compress, resize)."""
from __future__ import annotations

import io
from typing import Any

MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
JPEG_QUALITY = 85


def process_image_to_jpeg(image_data: bytes, max_size_bytes: int = MAX_IMAGE_SIZE_BYTES) -> bytes:
    """Convert image to JPEG and compress if needed."""
    try:
        from PIL import Image
    except ImportError:
        return image_data

    img = Image.open(io.BytesIO(image_data))

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    jpeg_data = output.getvalue()

    if len(jpeg_data) <= max_size_bytes:
        return jpeg_data

    quality = JPEG_QUALITY
    while len(jpeg_data) > max_size_bytes and quality > 30:
        quality -= 5
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        jpeg_data = output.getvalue()

    if len(jpeg_data) > max_size_bytes:
        img = _resize_image_to_fit(img, max_size_bytes)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=70, optimize=True)
        jpeg_data = output.getvalue()

    return jpeg_data


def _resize_image_to_fit(img: Any, max_size_bytes: int) -> Any:
    """Resize image to fit within size limit."""
    from PIL import Image

    width, height = img.size
    ratio = 0.9

    while True:
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        resized.save(output, format="JPEG", quality=70, optimize=True)

        if output.tell() <= max_size_bytes or ratio < 0.3:
            return resized

        ratio *= 0.9
