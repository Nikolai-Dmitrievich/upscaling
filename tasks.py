import os
import logging
from celery import Celery
from io import BytesIO
from upscale import upscale

logger = logging.getLogger(__name__)

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')


app_celery = Celery(
    'tasks',
    broker=broker_url,
    backend=result_backend,
    include=['tasks']
)

app_celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
)


@app_celery.task(bind=True, max_retries=1)
def upscale_task(self, image_bytes: bytes, use_edsr: bool = False):
    """
    Увеличивает картинку в фоне (Celery задача)
    Аргументы:
        image_bytes: PNG байты от браузера
        use_edsr: True=нейросеть (медленно+красиво), False=быстро
    Возвращает:
        Увеличенную PNG (байты)
    """
    input_bytes = BytesIO(image_bytes)
    output_bytes = BytesIO()
    method = "edsr" if use_edsr else "opencv"
    
    try:
        logger.info(f"Starting upscale task {self.request.id} with method: {method}")
        upscale(input_bytes, output_bytes, method=method)
        logger.info(f"Completed upscale task {self.request.id}")
        return output_bytes.getvalue()
    except FileNotFoundError as exc:
        logger.error(f"Model file not found for task {self.request.id}: {exc}")
        raise
    except ValueError as exc:
        logger.error(f"Invalid image for task {self.request.id}: {exc}")
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error in task {self.request.id}: {exc}")
        try:
            self.retry(exc=exc, countdown=5)
        except self.MaxRetriesExceededError:
            logger.error(f"Task {self.request.id} exceeded max retries")
            raise
