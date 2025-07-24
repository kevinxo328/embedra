from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.file import File


class FileRepository:
    def __init__(self, session: AsyncSession):
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

        base_stmt = select(File).where(File.collection_id == collection_id)

        if filename:
            base_stmt = base_stmt.where(File.filename.ilike(f"%{filename}%"))

        if content_type:
            base_stmt = base_stmt.where(File.content_type == content_type)

        # Count total files before applying limit and offset
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar_one()

        # Apply limit and offset for pagination
        stmt = base_stmt

        if sort_by:
            if sort_order == "asc":
                stmt = stmt.order_by(getattr(File, sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(File, sort_by).desc())

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        files = result.scalars().all()

        return files, total_count

    async def get_by_id(self, id: str):
        """Retrieve a file by its ID."""
        stmt = select(File).where(File.id == id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def stage_create(self, file: File):
        """Create a new file."""
        self.session.add(file)
        return file

    async def stage_update(self, file: File):
        """
        Update an existing file.
        This method does not commit the transaction.
        """
        await self.session.merge(file)
        return file

    async def stage_delete(self, file: File):
        """
        Delete a file.
        This method does not commit the transaction.
        """
        await self.session.delete(file)
        return True

    async def stage_delete_by_collection_id(self, collection_id: str):
        """
        Delete all files associated with a specific collection.

        This method does not commit the transaction.
        """
        await self.session.execute(
            delete(File).where(File.collection_id == collection_id)
        )
        return True
