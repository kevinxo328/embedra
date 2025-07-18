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
from utils.file_uploader import save_file


class CollectionServiceException(Exception):
    pass


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
        """
        stmt = select(Collection).order_by(Collection.created_at.desc())
        result = await session.execute(stmt)
        collections = result.scalars().all()
        return collections

    @staticmethod
    async def get_collection_by_id(
        collection_id: str, session: AsyncSession, with_files: bool = False
    ):
        """
        Retrieve a specific collection by its ID.

        Raises:
            NoResultFound: If the collection ID is not found
        """
        stmt = select(Collection).where(Collection.id == collection_id)

        if with_files:
            stmt = stmt.options(selectinload(Collection.files))

        result = await session.execute(stmt)
        return result.scalar_one()

    @classmethod
    async def create_collection(
        cls, collection_data: CollectionCreate, session: AsyncSession
    ):
        """
        Create a new collection in the database.
        This also creates a vector table for the collection in the vector store.

        Raises:
            ValueError: If the embedding model is invalid
        """
        # Validate the embedding model and get its dimension
        try:
            dimension = GoogleEmbeddingModel.from_name(
                collection_data.embedding_model
            ).output_dim
        except ValueError as e:
            raise CollectionServiceException(
                f"Invalid embedding model '{collection_data.embedding_model}'. "
            ) from e

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
            dimension,
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

        Raises:
            NoResultFound: If the collection ID is not found
        """

        collection = await cls.get_collection_by_id(collection_id, session)

        # Update collection fields
        for key, value in collection_data.model_dump().items():
            if value is not None:
                setattr(collection, key, value)

        await session.commit()
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

        Returns:
            List of file paths that require deletion to complete cleanup.

        Raises:
            NoResultFound: If the collection ID is not found
        """
        collection = await cls.get_collection_by_id(
            collection_id, session, with_files=True
        )
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
    async def get_collection_files(cls, collection_id: str, session: AsyncSession):
        """
        Retrieve all files associated with a specific collection.

        Raises:
            NoResultFound: If the collection ID is not found
        """
        collection = await cls.get_collection_by_id(
            collection_id, session, with_files=True
        )
        return collection.files

    @staticmethod
    async def get_collection_file(
        collection_id: str, file_id: str, session: AsyncSession
    ):
        """
        Retrieve a specific file by its ID within a collection.

        Raises:
            NoResultFound: If the file ID is not found in the collection.
        """
        stmt = select(File).where(
            File.id == file_id, File.collection_id == collection_id
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    @classmethod
    async def upload_file_to_collection(
        cls, collection_id: str, file: ValidatedUploadFile, session: AsyncSession
    ):
        """
        Upload a file to a specific collection.

        Raises:
            NoResultFound: If the collection ID is not found.
        """
        # TODO: Digest the file content and store it in the vector store in the background.

        # Check if the collection exists using the private method
        collection = await cls.get_collection_by_id(
            collection_id=collection_id, session=session
        )

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

        await session.refresh(new_file)
        return new_file

    @classmethod
    async def delete_file_from_collection(
        cls, collection_id: str, file_id: str, session: AsyncSession
    ):
        """
        Delete a file by its ID from a specific collection.
        This will delete the file record from the database and return the file path for cleanup avoiding blocking I/O operations.

        Raises:
            NoResultFound: If the file ID is not found in the collection.
        """
        file = await cls.get_collection_file(collection_id, file_id, session)
        delete_file_path = file.path

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
        await session.execute(stmt)

        return delete_file_path

    # @classmethod
    # async def delete_collection_files(cls, collection_id: str, session: AsyncSession):
    #     """
    #     Delete all files associated with a specific collection.

    #     Raises:
    #         NoResultFound: If the collection ID is not found.
    #     """

    #     collection = await cls.get_collection_by_id(
    #         collection_id=collection_id, session=session, with_files=True
    #     )

    #     instance = cls()
    #     VectorModel = await VectorStore.get_vector_model(
    #         session,
    #         table_name=instance.__generate_collection_vector_table_name(collection_id),
    #     )

    #     if VectorModel:
    #         smst = delete(VectorModel).where(
    #             VectorModel.metadata["collection_id"].astext == collection_id  # type: ignore
    #         )
    #         await session.execute(smst)

    #     for file in collection.files:
    #         await cls.delete_file_from_collection(
    #             collection_id=collection_id, file_id=str(file.id), session=session
    #         )

    #     return True

    @classmethod
    async def similarity_search(
        cls,
        collection_id: Union[uuid.UUID, str],
        query: str,
        session: AsyncSession,
        top_k: int = 5,
        threshold: Union[float, None] = None,
    ):
        """
        Perform a similarity search in the specified collection.

        Raises:
            NoResultFound: If the collection ID is not found.
        """
        instance = cls()
        vector_table_name = instance.__generate_collection_vector_table_name(
            collection_id
        )
        collection = await cls.get_collection_by_id(
            collection_id=str(collection_id), session=session
        )

        # Get the embedding model for the collection
        embedding_model = collection.embedding_model
        embeddings = get_google_embeddings(embedding_model)

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
