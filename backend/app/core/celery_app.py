"""
VisionTrace AI – Celery Application Instance.
Configured for asynchronous background video processing and computer vision pipelines.
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "visiontrace",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.video_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=False,
    broker_connection_timeout=1.0,
    broker_transport_options={
        "socket_timeout": 1.0,
        "socket_connect_timeout": 1.0,
        "max_retries": 1,
    },
)
