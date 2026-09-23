"""
HTTP layer tests: routing, validation order, error handling.

Celery is never involved: ``process_upscale_task.delay`` is stubbed in the
``app_client`` fixture and ``AsyncResult`` is replaced by a controllable fake,
so the suite does not need a running Redis.
"""

import io

import pytest

from app.core.config import settings


def _upload(client, filename="pic.png", data=None, model="opencv"):
    return client.post(
        "/upscale",
        data={
            "image": (io.BytesIO(data if data is not None else client.upload_image), filename),
            "model": model,
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )


@pytest.fixture
def fake_task(monkeypatch):
    """Replaces AsyncResult so task states can be simulated without Redis."""
    import app.api.views as views

    class _FakeAsyncResult:
        state = "PENDING"
        info = None
        result = None

        def __init__(self, task_id, app=None):
            pass

    monkeypatch.setattr(views, "AsyncResult", _FakeAsyncResult)
    return _FakeAsyncResult


class TestPublicPages:
    def test_index_is_available(self, app_client):
        response = app_client.get("/")
        assert response.status_code == 200
        assert b'name="image"' in response.data

    def test_health_reports_configuration(self, app_client):
        response = app_client.get("/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "ok"
        assert body["max_file_size_mb"] == settings.max_file_size_mb

    def test_result_page_renders_for_unknown_task(self, app_client, fake_task):
        response = app_client.get("/result/does-not-exist")
        assert response.status_code == 200
        assert "wait" in response.get_data(as_text=True).lower()


class TestUpscaleUpload:
    def test_valid_png_redirects_to_result_page(self, app_client):
        response = _upload(app_client)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/result/test-task-id")

    def test_task_receives_bytes_and_requested_model(self, app_client):
        _upload(app_client, model="edsr")
        assert app_client.recorded_task_kwargs["use_edsr"] is True
        assert app_client.recorded_task_kwargs["original_filename"] == "pic.png"
        assert app_client.recorded_task_kwargs["image_bytes"] == app_client.upload_image

    def test_missing_model_field_falls_back_to_opencv(self, app_client):
        response = app_client.post(
            "/upscale",
            data={"image": (io.BytesIO(app_client.upload_image), "pic.png")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 302
        assert app_client.recorded_task_kwargs["use_edsr"] is False

    def test_no_file_at_all_is_rejected(self, app_client):
        response = app_client.post("/upscale", data={})
        assert response.status_code == 400
        assert "No image provided" in response.get_json()["error"]

    def test_file_without_extension_is_rejected(self, app_client):
        response = _upload(app_client, filename="noextension")
        assert response.status_code == 400
        assert "Invalid filename" in response.get_json()["error"]

    def test_disallowed_extension_is_rejected(self, app_client):
        response = _upload(app_client, filename="payload.exe", data=b"MZ\x00\x00")
        assert response.status_code == 400
        assert "Allowed extensions" in response.get_json()["error"]

    def test_spoofed_extension_is_rejected_by_mime_check(self, app_client):
        """A .png file whose content is not an image must not reach the worker."""
        response = _upload(app_client, filename="evil.png", data=b"\x7fELF" + b"\x00" * 64)
        assert response.status_code == 400
        assert "Invalid file type" in response.get_json()["error"]
        assert app_client.recorded_task_kwargs == {}

    def test_empty_file_is_rejected(self, app_client):
        response = _upload(app_client, data=b"")
        assert response.status_code == 400
        assert "empty" in response.get_json()["error"]

    def test_oversize_upload_returns_html_413(self, app_client):
        """MAX_CONTENT_LENGTH aborts before the view, so the error handler matters."""
        app_client.application.config["MAX_CONTENT_LENGTH"] = 16
        response = _upload(app_client, data=b"x" * 4096)
        assert response.status_code == 413
        assert b"MB" in response.data
        assert b"Error" in response.data


class TestTaskStatusEndpoint:
    def test_pending_task_returns_status_json(self, app_client, fake_task):
        response = app_client.get("/upscale/test-task-id")
        assert response.status_code == 200
        assert response.get_json()["status"] == "PENDING"

    def test_failed_task_reports_error_to_the_browser(self, app_client, fake_task):
        fake_task.state = "FAILURE"
        fake_task.info = "Image resolution too large"

        response = app_client.get("/upscale/test-task-id")
        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "FAILURE"
        assert "resolution" in body["info"]

    def test_successful_task_is_returned_as_download(self, app_client, fake_task):
        fake_task.state = "SUCCESS"
        fake_task.result = {"image_bytes": app_client.upload_image, "filename": "pic_up.png"}

        response = app_client.get("/upscale/test-task-id")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/png"
        assert "pic_up.png" in response.headers["Content-Disposition"]
        assert response.data == app_client.upload_image

    def test_corrupted_result_does_not_crash(self, app_client, fake_task):
        fake_task.state = "SUCCESS"
        fake_task.result = "unexpected string payload"

        response = app_client.get("/upscale/test-task-id")
        assert response.status_code == 500
        assert "error" in response.get_json()


def test_settings_limits_are_consistent():
    assert settings.max_content_length == settings.max_file_size_mb * 1024 * 1024
    assert "image/png" in settings.allowed_mime_types
