from sqlalchemy.ext.asyncio import AsyncSession

from celery_tasks import embed_documents, process_file
from domains.file import SelectFilter as FileSelectFilter
from exceptions.common import FileStatusNotRetryableError, ResourceNotFoundError
from repositories.file.asyncio import FileRepositoryAsync
from schemas.file import FileStatus


class FileService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.file_repository = FileRepositoryAsync(session)

    # TODO: This method is duplicated in CollectionService, consider refactoring
    def __create_vector_table_name(self, collection_id: str) -> str:
        """
        Create a vector table name for the collection.
        PostgreSQL doesn't allow hyphens in table names, so we replace them with underscores.
        """

        return f"collection_{str(collection_id).replace('-', '_')}"

    async def get_file(self, file_id: str):
        """
        Retrieve a single file.
        """
        file = await self.file_repository.select_one_or_none(FileSelectFilter(file_id))
        if not file:
            raise ResourceNotFoundError(resource_name="File", resource_id=file_id)
        return file

    async def retry_file_task(self, file_id: str):
        file = await self.get_file(file_id)

        vector_table_name = self.__create_vector_table_name(file.collection_id)

        if file.status == FileStatus.CHUNK_FAILED or file.status == FileStatus.FAILED:
            # Retry whole file processing
            process_file.apply_async(
                kwargs={"file_id": file.id, "table_name": vector_table_name}
            )

        elif file.status == FileStatus.EMBEDDING_PARTIAL_FAILED:
            # Retry embedding the documents
            embed_documents.apply_async(
                kwargs={"file_id": file.id, "table_name": vector_table_name}
            )
        else:
            raise FileStatusNotRetryableError(
                file_id=file.id,
                status=file.status.value,
                retryable_statuses=[
                    FileStatus.CHUNK_FAILED.value,
                    FileStatus.FAILED.value,
                    FileStatus.EMBEDDING_PARTIAL_FAILED.value,
                ],
            )

        return True
