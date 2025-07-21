from typing import Union

from langchain_core.documents import Document
from sqlalchemy import delete, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.collection import Collection
from database.models.file import File
from schemas.collection import (
    CollectionCreate,
    CollectionFilter,
    CollectionPaginationParams,
    CollectionUpdate,
)
from schemas.common import DeleteResponse, PaginatedResponse
from schemas.embedding import EmbeddingModelMetadata
from schemas.file import FileFilter, FilePaginationParams, ValidatedUploadFile
from settings import VectorStore
from utils.doc_processor import markitdown_converter, split_markdown
from utils.embeddings import (
    EmbeddingModelProvider,
    get_embedding_model_by_provider_name,
)
from utils.file_uploader import delete_local_file, save_file_to_local
from utils.logger import logger


class CollectionServiceException(Exception):
    pass


class CollectionNotFoundException(CollectionServiceException):
    def __init__(self, collection_id: str):
        super().__init__(f"Collection with ID {collection_id} not found")
        self.collection_id = collection_id


class CollectionService:
    def __init__(self):
        pass

    def __generate_collection_vector_table_name(self, collection_id: str) -> str:
        """
        Generate a vector table name for the collection.
        PostgreSQL doesn't allow hyphens in table names, so we replace them with underscores.
        """

        return f"collection_{str(collection_id).replace('-', '_')}"

    def __extract_file(self, path: str) -> list[Document]:
        """
        Extract documents from a file path.
        """
        convert_result = markitdown_converter(source=path)
        return split_markdown(markdown=convert_result.markdown)

    async def __store_documents_to_collection(
        self,
        docs: list[Document],
        collection_id: str,
        embedding_model_provider: str,
        embedding_model: str,
        embedding_metadata: Union[EmbeddingModelMetadata, None],
        file_id: str,
        session: AsyncSession,
    ):
        """Store documents to collection vector store."""
        vector_table_name = self.__generate_collection_vector_table_name(collection_id)
        VectorModel = VectorStore.get_vector_model(table_name=vector_table_name)

        if not VectorModel:
            raise ValueError(f"Vector model for collection {collection_id} not found")

        embeddings = get_embedding_model_by_provider_name(
            embedding_model_provider,
            embedding_model,
            embedding_metadata,
        )

        for doc in docs:
            embedding = embeddings.embed_query(doc.page_content)
            vector_row = VectorModel(
                text=doc.page_content,
                embedding=embedding,
                meta={
                    **doc.metadata,
                    "collection_id": collection_id,
                    "file_id": file_id,
                },
            )
            session.add(vector_row)

    @staticmethod
    async def get_collections(
        filter: CollectionFilter,
        pagination: CollectionPaginationParams,
        session: AsyncSession,
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
        base_stmt = select(Collection)

        # Apply filtering
        if filter.name:
            base_stmt = base_stmt.where(Collection.name.ilike(f"%{filter.name}%"))

        if filter.embedding_model:
            base_stmt = base_stmt.where(
                Collection.embedding_model == filter.embedding_model
            )

        # Count total items
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await session.execute(total_stmt)
        total = total_result.scalar_one()

        # Apply pagination
        stmt = base_stmt
        if pagination.sort_by:
            if pagination.sort_order == "asc":
                stmt = stmt.order_by(getattr(Collection, pagination.sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(Collection, pagination.sort_by).desc())
        stmt = stmt.offset(pagination.offset).limit(pagination.limit)

        result = await session.execute(stmt)
        collections = result.scalars().all()
        return PaginatedResponse(
            data=collections,
            total=total,
            page=pagination.offset // pagination.limit + 1,
            page_size=pagination.limit,
        )

    @staticmethod
    async def get_collection_by_id(
        collection_id: str, session: AsyncSession, with_files: bool = False
    ):
        """
        Retrieve a specific collection by its ID.

        ### Args:
        - collection_id: The ID of the collection to retrieve.
        - with_files: If True, also load associated files as well.

        ### Returns:
        The collection object or none if not found.
        """
        stmt = select(Collection).where(Collection.id == collection_id)

        if with_files:
            stmt = stmt.options(selectinload(Collection.files))

        result = await session.execute(stmt)

        return result.scalar_one_or_none()

    @classmethod
    async def create_collection(
        cls, collection_data: CollectionCreate, session: AsyncSession
    ):
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
        EmbeddingModelProvider(collection_data.embedding_model_provider)

        collection = Collection(**collection_data.model_dump())
        session.add(collection)
        await session.flush()  # Ensure the collection ID is generated

        # Create a vector table for the new collection
        instance = cls()
        vector_table_name = instance.__generate_collection_vector_table_name(
            collection.id
        )
        await VectorStore.create_vector_table(
            vector_table_name,
            session,
        )
        return collection

    @classmethod
    async def update_collection(
        cls,
        collection_id: str,
        collection_data: CollectionUpdate,
        session: AsyncSession,
    ):
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

        collection = await cls.get_collection_by_id(collection_id, session)
        if not collection:
            raise CollectionNotFoundException(collection_id)

        # Update collection fields
        for key, value in collection_data.model_dump().items():
            if value is not None:
                setattr(collection, key, value)

        await session.refresh(collection)
        return collection

    @classmethod
    async def delete_collection(cls, collection_id: str, session: AsyncSession):
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
        collection = await cls.get_collection_by_id(
            collection_id, session, with_files=True
        )

        if not collection:
            raise CollectionNotFoundException(collection_id)

        instance = cls()
        vector_table_name = instance.__generate_collection_vector_table_name(
            collection.id
        )

        # Store file paths before deletion for cleanup
        file_paths = [file.path for file in collection.files]

        await session.delete(collection)
        await VectorStore.drop_vector_table(vector_table_name, session)

        return file_paths

    @classmethod
    async def get_collection_files(
        cls,
        collection_id: str,
        filter: FileFilter,
        pagination: FilePaginationParams,
        session: AsyncSession,
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
        # Validate collection ID
        await cls.get_collection_by_id(collection_id, session)

        # Build the query
        base_stmt = select(File).where(File.collection_id == collection_id)

        # Apply filtering
        if filter.filename:
            base_stmt = base_stmt.where(File.filename.ilike(f"%{filter.filename}%"))

        if filter.content_type:
            base_stmt = base_stmt.where(File.content_type == filter.content_type)

        # Count total items
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await session.execute(total_stmt)
        total = total_result.scalar_one()

        # Apply pagination
        stmt = base_stmt
        if pagination.sort_by:
            if pagination.sort_order == "asc":
                stmt = stmt.order_by(getattr(File, pagination.sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(File, pagination.sort_by).desc())
        stmt = stmt.offset(pagination.offset).limit(pagination.limit)

        result = await session.execute(stmt)
        files = result.scalars().all()
        return PaginatedResponse(
            data=files,
            total=total,
            page=pagination.offset // pagination.limit + 1,
            page_size=pagination.limit,
        )

    @classmethod
    async def upload_file_to_collection(
        cls, collection_id: str, file: ValidatedUploadFile, session: AsyncSession
    ):
        """
        Upload a file to a specific collection.

        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        """
        # TODO: Digest the file content and store it in the vector store in the background.

        # Check if the collection exists using the private method
        collection = await cls.get_collection_by_id(
            collection_id=collection_id, session=session
        )

        if not collection:
            raise CollectionNotFoundException(collection_id)

        save_file_path = save_file_to_local(file, save_dir=f"docs/{collection_id}")
        new_file = File(
            filename=file.filename,
            size=file.size,
            path=save_file_path,
            content_type=file.content_type,
            collection_id=collection_id,
        )
        session.add(new_file)
        await session.flush()

        instance = cls()
        docs = instance.__extract_file(save_file_path)
        try:
            embedding_metadata = collection.embedding_model_metadata

            await instance.__store_documents_to_collection(
                docs=docs,
                collection_id=collection_id,
                embedding_model=collection.embedding_model,
                file_id=str(new_file.id),
                session=session,
                embedding_metadata=embedding_metadata,
                embedding_model_provider=collection.embedding_model_provider,
            )
        except Exception as e:
            delete_local_file(save_file_path)
            logger.error(f"Failed to store documents in collection: {e}")
            raise RuntimeError("Failed to store documents in collection") from e

        await session.refresh(new_file)
        return new_file

    @classmethod
    async def delete_collection_files(
        cls,
        collection_id: str,
        file_ids: Union[list[str], None],
        all: bool,
        session: AsyncSession,
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
        collection = await cls.get_collection_by_id(
            collection_id=collection_id, session=session, with_files=True
        )

        if not collection:
            raise CollectionNotFoundException(collection_id)

        if not file_ids and not all:
            raise CollectionServiceException(
                "No files specified for deletion. Provide file IDs or set 'all' to True."
            )

        VectorModel = VectorStore.get_vector_model(
            table_name=cls().__generate_collection_vector_table_name(collection_id),
        )

        deleted_file_ids = []
        failed_file_ids = []
        failed_messages = []
        delete_file_paths = []

        if all and collection.files:
            delete_file_paths = [file.path for file in collection.files]
            deleted_file_ids = [str(file.id) for file in collection.files]

            # Delete all files in the collection and their vectors
            await session.execute(
                delete(File).where(File.collection_id == collection_id)
            )
            if VectorModel:
                smst = delete(VectorModel).where(
                    VectorModel.meta["collection_id"].astext == collection_id  # type: ignore
                )
                await session.execute(smst)

        elif file_ids:
            for file_id in file_ids:
                # Begin a nested transaction to ensure atomicity
                # This allows us to rollback only the current file deletion if it fails
                # while keeping the session open for other operations.

                try:
                    async with session.begin_nested():
                        file_result = await session.execute(
                            select(File).where(
                                File.id == file_id, File.collection_id == collection_id
                            )
                        )
                        file = file_result.scalar_one()

                        # Delete the file and its associated vectors
                        await session.delete(file)
                        if VectorModel:
                            smst = delete(VectorModel).where(
                                VectorModel.meta["collection_id"].astext == collection_id,  # type: ignore
                                VectorModel.meta["file_id"].astext == file_id,  # type: ignore
                            )
                            await session.execute(smst)

                        delete_file_paths.append(file.path)
                        deleted_file_ids.append(file_id)

                except Exception as e:
                    failed_file_ids.append(file_id)
                    if isinstance(e, NoResultFound):
                        failed_messages.append(
                            f"File with ID {file_id} not found in collection {collection_id}."
                        )
                    elif isinstance(e, SQLAlchemyError):
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

    @classmethod
    async def similarity_search(
        cls,
        collection_id: str,
        query: str,
        session: AsyncSession,
        top_k: int = 5,
        threshold: Union[float, None] = None,
    ):
        """
        Perform a similarity search in the specified collection.

        ### Raises:
        - CollectionNotFoundException: If the collection with the specified ID does not exist.
        """
        instance = cls()
        collection = await cls.get_collection_by_id(
            collection_id=str(collection_id), session=session
        )

        if not collection:
            raise CollectionNotFoundException(str(collection_id))

        vector_table_name = instance.__generate_collection_vector_table_name(
            collection_id
        )

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
            results = await VectorStore.similarity_search(
                session=session,
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
                f"Failed to perform similarity search in collection {collection_id}"
            ) from e

        return results
