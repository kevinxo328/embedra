from sqlalchemy.ext.asyncio import create_async_engine

from database.models.base import Base
from settings import env, logger


async def init_db():
    """
    Initialize the database.
    This function creates the database tables and ensures that the necessary extensions are enabled.
    """
    logger.info("Starting to migrate")

    engine = create_async_engine(env.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Done migrating")
