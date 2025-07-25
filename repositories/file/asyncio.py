from sqlalchemy.ext.asyncio import AsyncSession

from database.models import File
from domains.file import OffsetBasedPagination, SelectFilter

from .core import FileRepositoryCore


class FileRepositoryAsync(FileRepositoryCore):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session

    async def select(self, filter: SelectFilter):
        """Retrieve a list of files with optional filters."""
        stmt = self._select_expression(filter)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def select_with_pagination(
        self,
        filter: SelectFilter,
        pagination: OffsetBasedPagination,
    ):
        """Retrieve a list of collections with pagination."""

        stmt, total_stmt = self._select_with_pagination_expression(
            filter=filter,
            pagination=pagination,
        )

        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar_one()

        result = await self.session.execute(stmt)
        files = result.scalars().all()

        return files, total_count

    async def select_one(self, filter: SelectFilter):
        """Retrieve a file."""
        stmt = self._select_expression(filter)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def stage_create(self, file: File):
        """Create a new file."""
        self.session.add(file)
        return file

    async def stage_delete(self, file: File):
        """
        Delete a file.
        #### This method does not commit the transaction.
        """
        await self.session.delete(file)
        return True

    async def stage_delete_by_collection_id(self, collection_id: str):
        """
        Delete all files associated with a specific collection.

        #### This method does not commit the transaction.
        """
        stmt = self._delete_expression(collection_id=collection_id)
        await self.session.execute(stmt)
        return True
