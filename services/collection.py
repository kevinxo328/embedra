from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.collection import Collection
from schemas.collection import CollectionCreate, CollectionUpdate
from settings import VectorStore
from utils.embeddings import GoogleEmbeddingModel
from utils.file_uploader import delete_file
from utils.general import generate_collection_vector_table_name


class CollectionService:
    def __init__(self):
        pass

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

        Args:
            collection_id: The UUID string of the collection to retrieve
            session: Database session

        Returns:
            Collection object if found, None if not found

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
        vector_table_name = generate_collection_vector_table_name(collection.id)
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
        vector_table_name = generate_collection_vector_table_name(collection.id)

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
