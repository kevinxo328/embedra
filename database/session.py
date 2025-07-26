from collections.abc import AsyncGenerator

from sqlalchemy import exc
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from settings import env

engine = create_async_engine(env.DATABASE_URL, echo=True)
factory = async_sessionmaker(engine)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    This function provides an asynchronous session for database operations.
    It ensures that the session is properly committed or rolled back in case of errors.
    """
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except exc.SQLAlchemyError:
            await session.rollback()
            raise
