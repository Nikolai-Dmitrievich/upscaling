"""
Celery task tests.

The task runs in ``task_always_eager`` mode, which executes it inline and keeps
the assertions about payload shape and error handling honest without a broker.
"""

import cv2
import numpy as np
import pytest

from app.tasks import worker


@pytest.fixture(autouse=True)
def eager_mode(monkeypatch):
    """Runs tasks synchronously so no Redis is required."""
    from app.tasks.celery_app import celery_app

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    yield


class TestUpscaleTask:
    def test_returns_png_bytes_and_renamed_file(self, tiny_image_bytes):
        result = worker.process_upscale_task.delay(
            image_bytes=tiny_image_bytes,
            use_edsr=False,
            original_filename="holiday.jpg",
        ).get()

        assert result["filename"] == "holiday_upscaled.png"
        assert result["image_bytes"][:8] == b"\x89PNG\r\n\x1a\n"

        source = cv2.imdecode(np.frombuffer(tiny_image_bytes, np.uint8), cv2.IMREAD_COLOR)
        output = cv2.imdecode(np.frombuffer(result["image_bytes"], np.uint8), cv2.IMREAD_COLOR)
        assert output.shape[:2] == (source.shape[0] * 2, source.shape[1] * 2)

    def test_result_survives_json_serialization(self, tiny_image_bytes):
        """The broker only accepts JSON, so bytes must round-trip through it."""
        from kombu.serialization import dumps, loads

        result = worker.process_upscale_task.delay(
            image_bytes=tiny_image_bytes, use_edsr=False, original_filename="a.png"
        ).get()

        content_type, encoding, raw = dumps(result, serializer="json")
        assert loads(raw, content_type, encoding) == result

    def test_download_name_stays_safe_for_path_traversal(self, tiny_image_bytes):
        result = worker.process_upscale_task.delay(
            image_bytes=tiny_image_bytes, use_edsr=False, original_filename="../../etc/passwd"
        ).get()
        assert result["filename"] == "passwd_upscaled.png"

    def test_corrupted_payload_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to decode image"):
            worker.process_upscale_task.delay(
                image_bytes=b"garbage", use_edsr=False, original_filename="a.png"
            ).get()
