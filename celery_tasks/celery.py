from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from env import env

app = Celery(
    "tasks",
    broker=env.CELERY_BROKER_URL,
    backend=env.CELERY_RESULT_BACKEND,
)
engine = create_engine(env.DATABASE_URL)
Session = sessionmaker(bind=engine)

# echo enables verbose logging from SQLAlchemy.
app.conf.database_engine_options = {"echo": True}
app.conf.database_table_names = {
    "task": "celery_taskmeta",
    "group": "celery_groupmeta",
}

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
