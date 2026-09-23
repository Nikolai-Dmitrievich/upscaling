"""
Flask API routes and view handlers.
"""

import io
import logging
from typing import Any

from celery.result import AsyncResult
from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for
from flask.views import MethodView

from app.core.config import settings
from app.core.validator import is_allowed_extension, validate_file_size, validate_mime_type
from app.tasks.celery_app import celery_app
from app.tasks.worker import process_upscale_task

logger = logging.getLogger(__name__)


def init_routes(app: Flask) -> None:
    """Register all application routes."""
    app.add_url_rule("/", view_func=index, methods=["GET"])
    app.add_url_rule("/health", view_func=health, methods=["GET"])
    app.add_url_rule("/result/<task_id>", view_func=result_page, methods=["GET"])
    app.add_url_rule(
        "/upscale/<task_id>", view_func=UpscaleView.as_view("upscale_get"), methods=["GET"]
    )
    app.add_url_rule("/upscale", view_func=UpscaleView.as_view("upscale_post"), methods=["POST"])


def index() -> str:
    """Render the main upload page."""
    return render_template("index.html")


def health() -> Response:
    """
    Liveness probe for Docker/compose healthchecks.

    Only reports that the web process is serving requests: Redis and Celery are
    checked by their own healthchecks, a request here must not depend on them.
    """
    return jsonify({"status": "ok", "max_file_size_mb": settings.max_file_size_mb})


def result_page(task_id: str) -> str:
    """Render the task status page."""
    task = AsyncResult(task_id, app=celery_app)
    return render_template("result.html", task_id=task_id, task=task)


def _error(message: str, status: int = 400) -> tuple[Any, int]:
    """Build a JSON error response (also used by the 413 handler below)."""
    return jsonify({"error": message}), status


class UpscaleView(MethodView):
    """Handles image upload and status retrieval."""

    def get(self, task_id: str) -> Any:
        """Retrieve the result of a completed task."""
        task = AsyncResult(task_id, app=celery_app)

        if task.state == "SUCCESS":
            result = task.result
            if not isinstance(result, dict) or "image_bytes" not in result:
                logger.error("Task %s succeeded with an unexpected payload", task_id)
                return _error("Corrupted task result", 500)

            return send_file(
                io.BytesIO(result["image_bytes"]),
                mimetype="image/png",
                as_attachment=True,
                download_name=result["filename"],
            )
        return jsonify({"status": task.state, "info": str(task.info)})

    def post(self) -> Any:
        """Handle image upload and trigger background task."""
        use_edsr = request.form.get("model") == "edsr"

        if "image" not in request.files:
            logger.warning("No image provided in request")
            return _error("No image provided")

        file = request.files["image"]
        file_name = file.filename

        if not file_name or "." not in file_name:
            logger.warning("Invalid filename provided")
            return _error("Invalid filename")

        if not is_allowed_extension(file_name):
            logger.warning("Disallowed extension: %s", file_name)
            return _error(f"Allowed extensions: {', '.join(sorted(settings.allowed_extensions))}")

        file_bytes = file.read()

        if not file_bytes:
            logger.warning("Empty file uploaded: %s", file_name)
            return _error("Uploaded file is empty")

        if not validate_file_size(file_bytes):
            return _error(f"File exceeds the limit of {settings.max_file_size_mb} MB", 413)

        is_valid_mime, mime_type = validate_mime_type(file_bytes)
        if not is_valid_mime:
            logger.warning("Disallowed MIME type: %s for file: %s", mime_type, file_name)
            return _error(
                f"Invalid file type. Allowed: {', '.join(sorted(settings.allowed_mime_types))}"
            )

        logger.info("Processing: %s (MIME: %s, EDSR: %s)", file_name, mime_type, use_edsr)

        task = process_upscale_task.delay(
            image_bytes=file_bytes,
            use_edsr=use_edsr,
            original_filename=file_name,
        )
        return redirect(url_for("result_page", task_id=task.id))
