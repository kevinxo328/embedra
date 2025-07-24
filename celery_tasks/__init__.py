from .celery import app as celery_app
from .tasks import process_file

__all__ = ["celery_app", "process_file"]
