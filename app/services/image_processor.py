"""
Core image processing logic using OpenCV and EDSR.
"""

import logging
from typing import Any

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


_edsr_model = None


def _get_edsr_model() -> Any:
    """Lazy initialization of the EDSR model."""
    global _edsr_model
    if _edsr_model is None:
        logger.info(f"Loading EDSR model from {settings.edsr_model_path}...")
        _edsr_model = cv2.dnn_superres.DnnSuperResImpl_create()  # type: ignore[attr-defined]
        _edsr_model.readModel(settings.edsr_model_path)
        _edsr_model.setModel("edsr", 2)
        logger.info("EDSR model loaded successfully.")
    return _edsr_model


def upscale_image(input_bytes: bytes, use_edsr: bool = False) -> bytes:
    """
    Upscale an image by a factor of 2.

    Args:
        input_bytes: Raw image bytes (JPEG, PNG, etc.).
        use_edsr: If True, use EDSR neural network. Otherwise, use OpenCV Bicubic.

    Returns:
        Upscaled image as PNG bytes.

    Raises:
        ValueError: If the image cannot be decoded or exceeds dimension limits.
        FileNotFoundError: If the EDSR model file is missing.
    """
    nparr = np.frombuffer(input_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Failed to decode image. Invalid or corrupted file.")

    h, w = img.shape[:2]
    if max(h, w) > settings.max_image_dimension:
        raise ValueError(
            f"Image resolution {w}x{h}px exceeds maximum allowed dimension "
            f"of {settings.max_image_dimension}px. Please resize before uploading."
        )

    if use_edsr:
        model = _get_edsr_model()
        result = model.upsample(img)
        method_str = "EDSR"
    else:
        result = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        method_str = "OpenCV Bicubic"

    _, buffer = cv2.imencode(".png", result, [cv2.IMWRITE_PNG_COMPRESSION, 1])

    logger.info(
        "Image upscaled successfully using %s. Output size: %s bytes.", method_str, len(buffer)
    )
    return buffer.tobytes()
