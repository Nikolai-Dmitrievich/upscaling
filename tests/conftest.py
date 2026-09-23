"""
Shared pytest fixtures.

Test images are generated with OpenCV on the fly, so the suite has no binary
fixtures to maintain and never touches the real EDSR model file.
"""

import cv2
import numpy as np
import pytest


@pytest.fixture
def tiny_image_bytes() -> bytes:
    """Valid 8x8 PNG produced in memory."""
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :, 0] = 255
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


@pytest.fixture
def app_client(tiny_image_bytes, monkeypatch):
    """Flask test client with the Celery broker call replaced by a stub."""
    from app.core.config import settings
    from app.tasks.celery_app import celery_app

    monkeypatch.setattr(settings, "edsr_model_path", "models/EDSR_x2.pb")
    # Keeps the suite independent of a running Redis: results live in process
    # memory, and every broker call is stubbed below anyway.
    monkeypatch.setattr(celery_app.conf, "result_backend", "cache+memory://")
    # Celery caches the backend instance, so the cached Redis backend has to be
    # dropped for the in-memory one above to take effect.
    monkeypatch.setattr(celery_app, "_backend_cache", None, raising=False)

    from app.main import create_app

    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False

    class _StubTask:
        id = "test-task-id"

    recorded = {}

    def fake_delay(**kwargs):
        recorded.update(kwargs)
        return _StubTask()

    import app.api.views as views

    monkeypatch.setattr(views.process_upscale_task, "delay", fake_delay)

    with app.test_client() as client:
        client.upload_image = tiny_image_bytes
        client.recorded_task_kwargs = recorded
        yield client
