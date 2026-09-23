"""
Tests for the file validation layer.
"""

import pytest

from app.core.config import settings
from app.core.validator import (
    is_allowed_extension,
    validate_file_size,
    validate_mime_type,
)


class TestIsAllowedExtension:
    @pytest.mark.parametrize("name", ["photo.jpg", "photo.jpeg", "pic.PNG", "a.webp", "x.gif"])
    def test_allows_known_image_extensions(self, name):
        assert is_allowed_extension(name) is True

    @pytest.mark.parametrize("name", ["payload.exe", "script.py", "archive.tar.gz.bak", "noext"])
    def test_rejects_unknown_extensions(self, name):
        assert is_allowed_extension(name) is False

    @pytest.mark.parametrize("name", ["", None, "justdots..."])
    def test_rejects_malformed_names(self, name):
        assert is_allowed_extension(name) is False


class TestValidateMimeType:
    def test_detects_real_png(self, tiny_image_bytes):
        is_valid, mime_type = validate_mime_type(tiny_image_bytes)
        assert is_valid is True
        assert mime_type == "image/png"

    def test_rejects_executable_disguised_as_image(self):
        fake = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 64
        is_valid, mime_type = validate_mime_type(fake)
        assert is_valid is False
        assert mime_type not in settings.allowed_mime_types

    def test_empty_buffer_is_rejected(self):
        is_valid, mime_type = validate_mime_type(b"")
        assert is_valid is False
        assert mime_type == "application/x-empty"


class TestValidateFileSize:
    def test_file_at_limit_is_accepted(self):
        assert validate_file_size(b"x" * settings.max_content_length) is True

    def test_file_over_limit_is_rejected(self):
        assert validate_file_size(b"x" * (settings.max_content_length + 1)) is False
