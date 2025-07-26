from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from env import env
from settings import logger

from .model.factory import PgVectorModelFactory


async def init_db():
    """
    Initialize the pgvector database.
    This function creates ensures that the necessary extensions and enum are enabled.
    """
    logger.info("Starting to migrate pgvector database")

    engine = create_async_engine(env.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(
            text(PgVectorModelFactory()._create_enum_if_not_exists_sql())
        )

    logger.info("Done migrating pgvector database")
