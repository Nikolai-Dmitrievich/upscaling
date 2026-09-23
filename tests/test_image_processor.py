"""
Tests for the image processing pipeline.

The EDSR branch is exercised with a mocked model: the real network needs a
38 MB weights file and tens of seconds of CPU, which does not belong in a unit
test suite.
"""

import cv2
import numpy as np
import pytest

from app.core.config import settings
from app.services import image_processor
from app.services.image_processor import upscale_image


def _decode(payload: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)


class TestOpenCVPath:
    def test_doubles_both_dimensions(self, tiny_image_bytes):
        result = upscale_image(tiny_image_bytes, use_edsr=False)
        source, output = _decode(tiny_image_bytes), _decode(result)
        assert output.shape[0] == source.shape[0] * 2
        assert output.shape[1] == source.shape[1] * 2

    def test_output_is_valid_png(self, tiny_image_bytes):
        result = upscale_image(tiny_image_bytes, use_edsr=False)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_accepts_jpeg_input(self):
        image = np.full((6, 10, 3), 128, dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", image)
        assert ok
        result = upscale_image(buffer.tobytes(), use_edsr=False)
        assert _decode(result).shape[:2] == (12, 20)


class TestEdsrPath:
    def test_calls_loaded_model_and_keeps_x2_scale(self, tiny_image_bytes, monkeypatch):
        calls = {}

        class _FakeModel:
            def upsample(self, img):
                calls["shape"] = img.shape
                return cv2.resize(img, (img.shape[1] * 2, img.shape[0] * 2))

        monkeypatch.setattr(image_processor, "_get_edsr_model", lambda: _FakeModel())

        result = upscale_image(tiny_image_bytes, use_edsr=True)

        assert calls["shape"][:2] == (8, 8)
        assert _decode(result).shape[:2] == (16, 16)

    def test_model_is_loaded_only_once(self, monkeypatch, tmp_path):
        reads = {"count": 0}

        class _FakeImpl:
            def readModel(self, _path):
                reads["count"] += 1

            def setModel(self, _name, _scale):
                pass

        monkeypatch.setattr(image_processor, "_edsr_model", None)
        monkeypatch.setattr(settings, "edsr_model_path", str(tmp_path / "model.pb"))
        monkeypatch.setattr(
            cv2.dnn_superres, "DnnSuperResImpl_create", lambda: _FakeImpl(), raising=False
        )

        image_processor._get_edsr_model()
        image_processor._get_edsr_model()

        assert reads["count"] == 1


class TestInvalidInput:
    def test_corrupted_bytes_raise_value_error(self):
        with pytest.raises(ValueError, match="Failed to decode image"):
            upscale_image(b"not an image at all", use_edsr=False)

    def test_oversized_image_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "max_image_dimension", 16)
        image = np.zeros((17, 17, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".png", image)
        assert ok

        with pytest.raises(ValueError, match="exceeds maximum allowed dimension"):
            upscale_image(buffer.tobytes(), use_edsr=False)
