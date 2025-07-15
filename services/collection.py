import uuid
from typing import Union

from langchain_core.documents import Document
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.collection import Collection
from database.models.file import File
from schemas.collection import CollectionCreate, CollectionUpdate
from schemas.file import ValidatedUploadFile
from settings import VectorStore
from utils.doc_processor import markitdown_converter, split_markdown
from utils.embeddings import GoogleEmbeddingModel, get_google_embeddings
from utils.file_uploader import delete_file, save_file


class CollectionService:
    def __init__(self):
        pass

    def __generate_collection_vector_table_name(
        self, collection_id: Union[uuid.UUID, str]
    ) -> str:
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
        embedding_model: str,
        file_id: str,
        session: AsyncSession,
    ):
        """Store documents to collection vector store."""
        vector_table_name = self.__generate_collection_vector_table_name(collection_id)
        VectorModel = await VectorStore.get_vector_model(
            session=session, table_name=vector_table_name
        )

        if not VectorModel:
            raise ValueError(f"Vector model for collection {collection_id} not found")

        embeddings = get_google_embeddings(embedding_model)

        for doc in docs:
            embedding = embeddings.embed_query(doc.page_content)
            vector_row = VectorModel(
                text=doc.page_content,
                embedding=embedding,
                metadata={
                    **doc.metadata,
                    "collection_id": collection_id,
                    "file_id": file_id,
                },
            )
            session.add(vector_row)

        await session.commit()

    @staticmethod
    async def get_collections(session: AsyncSession):
        """
        Retrieve all collections from the database.

        Raises:
            RuntimeError: If database query fails
        """
        try:
            stmt = select(Collection).order_by(Collection.created_at.desc())
            result = await session.execute(stmt)
            collections = result.scalars().all()
            return [collection for collection in collections]
        except Exception as e:
            raise RuntimeError("Failed to retrieve collections from database") from e

    @staticmethod
    async def get_collection_by_id(
        collection_id: str, session: AsyncSession, with_files: bool = False
    ):
        """
        Retrieve a specific collection by its ID.

        Raises:
            RuntimeError: If database query fails
        """

        try:
            stmt = select(Collection).where(Collection.id == collection_id)

            if with_files:
                stmt = stmt.options(selectinload(Collection.files))

            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RuntimeError(
                f"Failed to retrieve collection with ID {collection_id}"
            ) from e

    @classmethod
    async def create_collection(
        cls, collection_data: CollectionCreate, session: AsyncSession
    ):
        """
        Create a new collection in the database.
        This also creates a vector table for the collection in the vector store.

        Raises:
            ValueError: If the embedding model is invalid
            RuntimeError: If database operations fail
            Exception: For vector store creation failures
        """

        # Validate the embedding model and get its dimension
        try:
            dimension = GoogleEmbeddingModel.from_name(
                collection_data.embedding_model
            ).output_dim
        except ValueError as e:
            raise ValueError(
                f"Invalid embedding model '{collection_data.embedding_model}'. "
            ) from e

        collection = Collection(**collection_data.model_dump())
        session.add(collection)

        try:
            await session.flush()  # Ensure the collection ID is generated
        except Exception as e:
            await session.rollback()
            raise RuntimeError("Failed to create collection in database.") from e

        # Create a vector table for the new collection
        instance = cls()
        vector_table_name = instance.__generate_collection_vector_table_name(
            collection.id
        )
        try:
            await VectorStore.create_vector_table(
                session,
                vector_table_name,
                dimension,
            )
        except Exception as e:
            await session.rollback()
            raise RuntimeError(
                f"Failed to create vector table '{vector_table_name}' for collection."
            ) from e

        try:
            await session.commit()
            await session.refresh(collection)
        except Exception as e:
            await session.rollback()
            raise RuntimeError("Failed to commit collection to database") from e

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
        """
        collection = await cls.get_collection_by_id(collection_id, session)

        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found")

        # Update collection fields
        for key, value in collection_data.model_dump().items():
            if value is not None:
                setattr(collection, key, value)

        try:
            await session.commit()
            await session.refresh(collection)
        except Exception as e:
            await session.rollback()
            raise RuntimeError("Failed to update collection in database") from e

        return collection

    @classmethod
    async def delete_collection(cls, collection_id: str, session: AsyncSession):
        """
        Delete a collection and its associated vector table.

        Raises:
            ValueError: If collection_id is invalid or collection not found
            RuntimeError: If deletion operations fail
        """
        collection = await cls.get_collection_by_id(
            collection_id, session, with_files=True
        )

        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found")

        # Store file paths before deletion for cleanup
        file_paths = [file.path for file in collection.files]
        instance = cls()
        vector_table_name = instance.__generate_collection_vector_table_name(
            collection.id
        )

        try:
            # Delete vector table first
            await VectorStore.drop_vector_table(session, vector_table_name)

            # Delete collection from database
            await session.delete(collection)
            await session.commit()

        except Exception as e:
            await session.rollback()
            raise RuntimeError(
                f"Failed to delete collection and vector table '{vector_table_name}'"
            ) from e

        # Clean up files after successful database operations
        # TODO: remove files without blocking in background task
        for file_path in file_paths:
            try:
                delete_file(file_path)
            except Exception:
                # Log the error but don't fail the operation
                # File cleanup is not critical for data consistency
                pass

        return True

    @classmethod
    async def get_collection_files(cls, collection_id: str, session: AsyncSession):
        """
        Retrieve all files associated with a specific collection.

        Raises:
            ValueError: If the collection ID is not found.
            RuntimeError: If database operations fail.
        """
        try:
            collection = await cls.get_collection_by_id(
                collection_id, session, with_files=True
            )
            if not collection:
                raise ValueError(f"Collection with ID {collection_id} not found")
            return collection.files

        except Exception as e:
            raise RuntimeError(
                f"Failed to retrieve files for collection with ID {collection_id}"
            ) from e

    @staticmethod
    async def get_collection_file(
        collection_id: str, file_id: str, session: AsyncSession
    ):
        """
        Retrieve a specific file by its ID within a collection.

        Raises:
            RuntimeError: If database query fails.
        """
        try:
            stmt = select(File).where(
                File.id == file_id, File.collection_id == collection_id
            )
            result = await session.execute(stmt)
            file = result.scalar_one_or_none()

            if not file:
                raise ValueError(
                    f"File with id {file_id} not found in collection {collection_id}"
                )

            return file
        except Exception as e:
            raise RuntimeError("Failed to retrieve file from database") from e

    @classmethod
    async def upload_file_to_collection(
        cls, collection_id: str, file: ValidatedUploadFile, session: AsyncSession
    ):
        """
        Upload a file to a specific collection.

        Raises:
            ValueError: If the collection ID is not found.
            RuntimeError: If database operations fail.
        """

        # Check if the collection exists using the private method
        collection = await cls.get_collection_by_id(
            collection_id=collection_id, session=session
        )

        if not collection:
            raise ValueError(f"Collection with id {collection_id} not found")

        try:
            save_file_path = save_file(file)
            new_file = File(
                filename=file.filename,
                filesize=file.size,
                path=save_file_path,
                content_type=file.content_type,
                collection_id=collection_id,
            )
            session.add(new_file)
            await session.flush()

        except Exception as e:
            raise RuntimeError("Failed to upload file to collection") from e

        instance = cls()
        docs = instance.__extract_file(save_file_path)
        try:
            await instance.__store_documents_to_collection(
                docs=docs,
                collection_id=collection_id,
                embedding_model=collection.embedding_model,
                file_id=str(new_file.id),
                session=session,
            )
        except Exception as e:
            raise RuntimeError("Failed to store documents in collection") from e

        await session.commit()
        await session.refresh(new_file)

        return new_file

    @classmethod
    async def delete_file_from_collection(
        cls, collection_id: str, file_id: str, session: AsyncSession
    ):
        """
        Delete a file by its ID from a specific collection.

        Raises:
            ValueError: If the file ID is not found in the collection.
            RuntimeError: If database operations fail.
        """

        try:
            file = await cls.get_collection_file(
                collection_id=collection_id, file_id=file_id, session=session
            )
            if not file:
                raise ValueError(
                    f"File with id {file_id} not found in collection {collection_id}"
                )

            # Delete the vector row associated with the file
            instance = cls()
            VectorModel = await VectorStore.get_vector_model(
                session,
                table_name=instance.__generate_collection_vector_table_name(
                    file.collection_id
                ),
            )

            if VectorModel:
                smst = delete(VectorModel).where(
                    VectorModel.metadata["file_id"].astext == str(file.id)  # type: ignore
                )
                await session.execute(smst)

            # Delete the file record from the database
            stmt = delete(File).where(File.id == file_id)

            # TODO: avoid blocking I/O operation in async context
            # Delete the file from the filesystem
            delete_file(file.path)

            await session.execute(stmt)
            await session.commit()

            return f"File {file_id} deleted successfully."
        except Exception as e:
            raise RuntimeError(f"Failed to delete file, {e}") from e

    @classmethod
    async def delete_collection_files(cls, collection_id: str, session: AsyncSession):
        """
        Delete all files associated with a specific collection.

        Raises:
            ValueError: If the collection ID is not found.
            RuntimeError: If database operations fail.
        """
        try:
            collection = await cls.get_collection_by_id(
                collection_id=collection_id, session=session, with_files=True
            )
            if not collection:
                raise ValueError(f"Collection with ID {collection_id} not found")

            instance = cls()
            VectorModel = await VectorStore.get_vector_model(
                session,
                table_name=instance.__generate_collection_vector_table_name(
                    collection_id
                ),
            )

            if VectorModel:
                smst = delete(VectorModel).where(
                    VectorModel.metadata["collection_id"].astext == collection_id  # type: ignore
                )
                await session.execute(smst)

            for file in collection.files:
                await cls.delete_file_from_collection(
                    collection_id=collection_id, file_id=str(file.id), session=session
                )

        except Exception as e:
            raise RuntimeError(
                f"Failed to delete files in collection {collection_id}"
            ) from e

        return True
