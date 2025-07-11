import logging

from sqlalchemy.ext.asyncio import create_async_engine

from database.models.base import Base
from settings import DATABASE_URL

logger = logging.getLogger()
logger.setLevel(logging.INFO)


async def init_db():
    """Initialize the database."""
    logger.info("Starting to migrate")

    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Done migrating")
