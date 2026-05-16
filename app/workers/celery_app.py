"""
Clarion — Celery App (async task worker)
Broker: Redis (CELERY_BROKER_URL từ .env)
"""
import os
from celery import Celery

celery_app = Celery(
    "clarion",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
)
