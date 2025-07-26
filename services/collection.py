from typing import Union

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from celery_tasks import process_file
from database.models.collection import CollectionModel
from database.models.file import FileModel
from domains.collection import SelectFilter as CollectionSelectFilter
from domains.file import OffsetBasedPagination as FileOffsetPagination
from domains.file import SelectFilter as FileSelectFilter
from repositories.collection.asyncio import CollectionRepositoryAsync
from repositories.file.asyncio import FileRepositoryAsync
from schemas.collection import (
    CollectionCreate,
    CollectionFilter,
    CollectionPaginationParams,
    CollectionUpdate,
)
from schemas.common import DeleteResponse, PaginatedResponse
from schemas.file import FileFilter, FilePaginationParams, ValidatedUploadFile
from utils.embeddings import (
    EmbeddingModelProvider,
    get_embedding_model_by_provider_name,
)
from utils.file_uploader import delete_local_file, save_file_to_local
from vector_database.pgvector.repositories.asyncio import PgVectorRepositoryAsync


class CollectionServiceException(Exception):
    pass


class CollectionNotFoundException(CollectionServiceException):
    def __init__(self, collection_id: str):
        super().__init__(f"Collection with ID {collection_id} not found")
        self.collection_id = collection_id


class CollectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.collection_repository = CollectionRepositoryAsync(session)
        self.file_repository = FileRepositoryAsync(session)
        self.vector_repository = PgVectorRepositoryAsync(session)

    def __create_vector_table_name(self, collection_id: str) -> str:
        """
        Create a vector table name for the collection.
        PostgreSQL doesn't allow hyphens in table names, so we replace them with underscores.
        """

        return f"collection_{str(collection_id).replace('-', '_')}"

    async def __validate_collection_exists(self, collection_id: str):
        """
        Validate if a collection exists by its ID.
        Raises CollectionNotFoundException if not found.
        """
        collection = await self.collection_repository.select_one_or_none(
            CollectionSelectFilter(id=collection_id),
        )
        if not collection:
            raise CollectionNotFoundException(collection_id)
        return collection

    async def get_collections(
        self, filter: CollectionFilter, pagination: CollectionPaginationParams
    ):
        """
        Retrieve collections from the database with optional filtering and pagination.

        ### Args:
        - name: Filter collections by name (optional). Uses case-insensitive partial matching.
        - embedding_model: Filter collections by embedding model name (optional). Uses exact matching.
        - offset: The number of items to skip for pagination.
        - limit: The maximum number of items to return per page.
        - sort_by: The field to sort by (optional). Defaults to **created_at**.
        - sort_order: The order of sorting (optional). Can be **asc** or **desc**. Defaults to **desc**.

        ### Returns:
        - data: A paginated list of collections.
        - total: Total number of collections before pagination.
        - page: Current page number.
        - page_size: Number of items per page.
        """

        collections, total = await self.collection_repository.get(
            name=filter.name,
            embedding_model=filter.embedding_model,
            limit=pagination.limit,
            offset=pagination.offset,
            sort_by=pagination.sort_by,
            sort_order=pagination.sort_order,
        )

        return PaginatedResponse(
            data=collections,
            total=total,
            page=pagination.offset // pagination.limit + 1,
            page_size=pagination.limit,
        )

    async def get_collection_by_id_or_none(self, id: str):
        return await self.collection_repository.select_one_or_none(
            CollectionSelectFilter(id=id)
        )

    async def create_collection(self, data: CollectionCreate):
        """
        Create a new collection.
        This will also create a vector table for the collection in the vector store.

        ### Args:
        - name: The name of the collection.
        - description: A brief description of the collection.
        - embedding_model_provider: The provider of the embedding model. See [**/api/embeddings/providers**](#/embeddings/get_embedding_providers_api_embeddings_providers_get) for available providers.
        - embedding_model: The name of the embedding model to use. See [Langchain documentation](https://python.langchain.com/docs/integrations/text_embedding/) for more information.
        - embedding_model_metadata: Additional metadata for the embedding model, such as endpoint and dimensions.
        """
        # Validate the embedding model provider
        try:
            EmbeddingModelProvider(data.embedding_model_provider)
        except ValueError:
            raise CollectionServiceException(
                f"Invalid embedding model provider '{data.embedding_model_provider}'. Only supported providers are: {', '.join(e.value for e in EmbeddingModelProvider)}"
            )

        collection = CollectionModel(**data.model_dump())

        await self.collection_repository.stage_create(collection)
        await self.session.flush()  # Ensure the collection ID is generated

        # Create a vector table for the new collection
        vector_table_name = self.__create_vector_table_name(collection.id)
        await self.vector_repository.stage_create_table_if_not_exists(vector_table_name)

        # Refresh the collection to apply ORM mappings
        await self.session.refresh(collection)
        return collection

    async def update_collection(self, id: str, data: CollectionUpdate):
        """
        Update an existing collection in the database.

        ### Args:
        - name: The new name of the collection (optional).
        - description: The new description of the collection (optional).

        ### Returns:
        The updated collection object.

        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        """
        collection = await self.__validate_collection_exists(id)

        # Update collection fields
        for key, value in data.model_dump().items():
            if value is not None:
                setattr(collection, key, value)

        await self.collection_repository.stage_update(collection)

        await self.session.refresh(collection)
        return collection

    # TODO: Need to check if any files are processing in celery before deleting the collection.
    async def delete_collection_by_id(self, id: str):
        """
        Delete a collection and its associated vector table.
        Files deletion is not critical for data consistency, but should be done to avoid orphan files.

        Design Rationale:
        The function is designed to separate database operations from file system
        operations. It returns a list of associated file paths instead of deleting
        the files directly. This prevents the critical database transaction from being
        blocked by potentially slow or failing I/O operations. The caller is responsible
        for handling the physical file deletion, which helps to avoid orphan files
        while maintaining data consistency and system responsiveness.

        ### Returns:
        List of file paths that require deletion to complete cleanup.

        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        """
        collection = await self.__validate_collection_exists(id)
        files = await self.file_repository.select(
            FileSelectFilter(collection_id=collection.id)
        )
        vector_table_name = self.__create_vector_table_name(collection.id)

        # Store file paths before deletion for cleanup
        file_paths = [file.path for file in files]

        await self.collection_repository.stage_delete(collection)
        await self.vector_repository.stage_drop_table_if_exists(vector_table_name)

        return file_paths

    async def get_collection_files(
        self, collection_id: str, filter: FileFilter, pagination: FilePaginationParams
    ):
        """
        Retrieve files associated with a specific collection.

        Returns:
            data: A paginated list of files in the collection.
            total: Total number of files in the collection before pagination.
            page: Current page number.
            page_size: Number of items per page.

        Raises:
            NoResultFound: If the collection ID is not found
        """
        await self.__validate_collection_exists(collection_id)

        select_filter = FileSelectFilter(
            collection_id=collection_id,
            filename=filter.filename,
            content_type=filter.content_type,
        )

        offset_pagination = FileOffsetPagination(
            limit=pagination.limit,
            offset=pagination.offset,
            sort_by=pagination.sort_by,
            sort_order=pagination.sort_order,
        )

        files, total = await self.file_repository.select_with_pagination(
            filter=select_filter,
            pagination=offset_pagination,
        )

        return PaginatedResponse(
            data=files,
            total=total,
            page=pagination.offset // pagination.limit + 1,
            page_size=pagination.limit,
        )

    async def upload_file_to_collection(
        self, collection_id: str, file: ValidatedUploadFile
    ):
        """
        Upload a file to a specific collection.

        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        """
        # TODO: Digest the file content and store it in the vector store in the background.

        await self.__validate_collection_exists(collection_id)

        try:
            save_file_path = save_file_to_local(file, save_dir=f"docs/{collection_id}")
            new_file = FileModel(
                filename=file.filename,
                size=file.size,
                path=save_file_path,
                content_type=file.content_type,
                collection_id=collection_id,
            )
            await self.file_repository.stage_create(new_file)
            await self.session.flush()

            # Process the file in the background using Celery
            table_name = self.__create_vector_table_name(collection_id)
            process_file.apply_async(
                kwargs={"file_id": new_file.id, "table_name": table_name}
            )

        except Exception:
            delete_local_file(save_file_path)

        # Refresh the new file to apply ORM mappings
        await self.session.refresh(new_file)
        return new_file

    # TODO: Need to check if any files are processing in celery before deleting the collection.
    async def delete_collection_files(
        self, collection_id: str, file_ids: Union[list[str], None], all: bool
    ):
        """
        Delete specific files in a specific collection.
        If `all` is True, delete all files in the collection.

        ### Args:
        - collection_id (str): The ID of the collection.
        - file_ids (list[str] | None): List of file IDs to delete. If None, no specific files are deleted.
        - all (bool): If True, delete all files in the collection.

        ### Returns:
        - deleted_file_ids (list[str]): List of deleted file IDs.
        - failed_file_ids (list[str]): List of file IDs that were not found in the collection.
        - failed_messages (list[str]): List of error messages for failed deletions.
        - delete_file_paths (list[str]): List of file paths that need to be processed for deletion.


        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        - CollectionServiceException: If no files are specified for deletion and `all` is False.
        """

        # Validate collection ID
        collection = await self.__validate_collection_exists(collection_id)
        files = await self.file_repository.select(
            FileSelectFilter(collection_id=collection.id)
        )

        if not file_ids and not all:
            raise CollectionServiceException(
                "No files specified for deletion. Provide file IDs or set 'all' to True."
            )

        deleted_file_ids = []
        failed_file_ids = []
        failed_messages = []
        delete_file_paths = []

        if all and files:
            delete_file_paths = [file.path for file in files]
            deleted_file_ids = [str(file.id) for file in files]

            # Delete all files in the collection and their vectors
            await self.file_repository.stage_delete_by_collection_id(collection_id)
            await self.vector_repository.stage_delete_documents(
                table_name=self.__create_vector_table_name(collection_id)
            )

        elif file_ids:
            for file_id in file_ids:

                # Begin a nested transaction to ensure atomicity
                # This allows us to rollback only the current file deletion if it fails
                # while keeping the session open for other operations.
                try:
                    async with self.session.begin_nested():
                        file = await self.file_repository.select_one(
                            filter=FileSelectFilter(id=file_id)
                        )

                        await self.file_repository.stage_delete(file)
                        await self.vector_repository.stage_delete_documents(
                            table_name=self.__create_vector_table_name(collection_id),
                            file_id=file_id,
                        )

                        delete_file_paths.append(file.path)
                        deleted_file_ids.append(file_id)

                except Exception as e:
                    failed_file_ids.append(file_id)
                    if isinstance(e, SQLAlchemyError):
                        failed_messages.append(
                            f"Database error while deleting file with ID {file_id} in collection {collection_id}: {str(e)}"
                        )
                    else:
                        failed_messages.append(
                            f"Unexpected error while deleting file with ID {file_id} in collection {collection_id}: {str(e)}"
                        )
        return (
            DeleteResponse(
                deleted_ids=deleted_file_ids,
                failed_ids=failed_file_ids,
                failed_messages=failed_messages,
            ),
            delete_file_paths,
        )

    async def cosine_similarity_search(
        self,
        collection_id: str,
        query: str,
        top_k: int = 5,
        threshold: Union[float, None] = None,
    ):
        """
        Perform a similarity search in the specified collection.

        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        """
        collection = await self.__validate_collection_exists(collection_id)
        vector_table_name = self.__create_vector_table_name(collection_id)

        # Get the embedding model for the collection
        embedding_model = collection.embedding_model
        embedding_model_provider = collection.embedding_model_provider
        embedding_metadata = collection.embedding_model_metadata

        try:
            embeddings = get_embedding_model_by_provider_name(
                embedding_model_provider, embedding_model, embedding_metadata
            )
        except ValueError as e:
            raise ValueError(
                f"Invalid embedding model provider '{embedding_model_provider}' or model '{embedding_model}'."
            ) from e

        # Embed the query
        query_vector = embeddings.embed_query(query)

        try:
            results = await self.vector_repository.cosine_similarity_search(
                table_name=vector_table_name,
                query_vector=query_vector,
                top_k=top_k,
                threshold=threshold,
            )
        except ValueError as e:
            raise ValueError(
                f"Vector model for collection {collection_id} not found"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to perform similarity search in collection {collection_id}. {str(e)}"
            ) from e

        return results
