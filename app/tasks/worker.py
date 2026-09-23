"""
Celery task definitions for asynchronous image processing.
"""

import logging
from pathlib import Path
from typing import Any

from celery import Task

from app.services.image_processor import upscale_image
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.process_upscale_task")  # type: ignore[untyped-decorator]
def process_upscale_task(
    self: Task, image_bytes: bytes, use_edsr: bool = False, original_filename: str = "image"
) -> dict[str, Any]:
    """
    Background task to upscale an image asynchronously.

    Returns:
        dict: Contains 'image_bytes' (the processed image) and 'filename' (suggested download name).
    """
    task_id = self.request.id
    method = "EDSR" if use_edsr else "OpenCV Bicubic"

    try:
        logger.info(
            "[%s] Starting upscale (Method: %s, Size: %s bytes)", task_id, method, len(image_bytes)
        )

        result_bytes = upscale_image(image_bytes, use_edsr=use_edsr)

        safe_stem = Path(original_filename).stem or "image"
        new_filename = f"{safe_stem}_upscaled.png"

        logger.info(
            "[%s] Completed successfully. Output: %s (%s bytes)",
            task_id,
            new_filename,
            len(result_bytes),
        )

        return {"image_bytes": result_bytes, "filename": new_filename}

    except FileNotFoundError as exc:
        logger.error(f"[{task_id}] Model file not found: {exc}")
        raise
    except ValueError as exc:
        logger.error(f"[{task_id}] Invalid image data: {exc}")
        raise
    except Exception as exc:
        logger.exception("[%s] Unexpected error: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=5, max_retries=1) from exc
