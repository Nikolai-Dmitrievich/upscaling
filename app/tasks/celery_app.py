"""
Celery application instance configuration.

This module initializes the Celery app, connects it to the Redis broker/backend,
and sets global task execution policies.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "image_upscaler",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    task_default_retry_delay=5,
    task_max_retries=1,
)
