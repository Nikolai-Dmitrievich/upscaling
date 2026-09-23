"""
File validation utilities for uploaded images.

This module provides functions to validate file extensions, MIME types,
and file sizes before processing.
"""

import logging

import magic

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_allowed_extension(filename: str) -> bool:
    """
    Check if the file has an allowed extension.

    Args:
        filename: The original name of the uploaded file.

    Returns:
        True if the extension is in the allowed set, False otherwise.
    """
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in settings.allowed_extensions


def validate_mime_type(file_bytes: bytes) -> tuple[bool, str]:
    """
    Validate the actual MIME type of the uploaded file using python-magic.

    This function inspects the file's binary content to determine its true type,
    preventing spoofed extensions (e.g., a .jpg file that's actually a .exe).

    Args:
        file_bytes: The raw byte content of the uploaded file.

    Returns:
        A tuple containing:
            - bool: True if the MIME type is allowed, False otherwise.
            - str: The detected MIME type (e.g., "image/jpeg").
    """
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(file_bytes)
        is_valid = mime_type in settings.allowed_mime_types
        return is_valid, mime_type
    except Exception as e:
        logger.warning(f"Failed to detect MIME type: {e}")
        return False, "unknown"


def validate_file_size(file_bytes: bytes) -> bool:
    """
    Check if the file size is within the allowed limit.

    Note: Flask's MAX_CONTENT_LENGTH also enforces this at the HTTP level,
    but this function provides an explicit check for business logic.

    Args:
        file_bytes: The raw byte content of the uploaded file.

    Returns:
        True if the file size is within limits, False otherwise.
    """
    return len(file_bytes) <= settings.max_content_length
