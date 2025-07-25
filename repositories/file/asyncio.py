from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import File

from .core import FileRepositoryCore


class FileRepositoryAsync(FileRepositoryCore):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session

    async def get(
        self,
        collection_id: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """Retrieve a list of collections with pagination."""

        stmt, total_stmt = self._get_expression(
            collection_id=collection_id,
            filename=filename,
            content_type=content_type,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar_one()

        result = await self.session.execute(stmt)
        files = result.scalars().all()

        return files, total_count

    async def get_by_id(self, id: str):
        """Retrieve a file by its ID."""
        stmt = self._get_by_id_expression(id)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id_or_none(self, id: str):
        """Retrieve a file by its ID or return None if not found."""
        stmt = self._get_by_id_expression(id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def stage_create(self, file: File):
        """Create a new file."""
        self.session.add(file)
        return file

    async def stage_update(self, file: File):
        """
        Update an existing file.
        #### This method does not commit the transaction.
        """
        await self.session.merge(file)
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
