from langchain_core.documents import Document
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.collection import Collection
from database.models.file import File
from schemas.file import ValidatedUploadFile
from settings import VectorStore
from utils.doc_processor import markitdown_converter, split_markdown
from utils.embeddings import get_google_embeddings
from utils.file_uploader import delete_file, save_file
from utils.general import generate_collection_vector_table_name


class FileService:
    def __init__(self):
        pass

    async def __get_collecion(
        self, collection_id: str, session: AsyncSession, with_files: bool = False
    ):
        """
        Check if the collection exists in the database.
        Raises ValueError if not found.
        """
        stmt = select(Collection).where(Collection.id == collection_id)

        if with_files:
            stmt = stmt.options(selectinload(Collection.files))

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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
        vector_table_name = generate_collection_vector_table_name(collection_id)
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

    @classmethod
    async def get_files_by_collection_id(
        cls, collection_id: str, session: AsyncSession
    ):
        """
        Retrieve all files associated with a specific collection ID.

        Raises:
            ValueError: If the collection ID is not found.
            RuntimeError: If database query fails.
        """

        try:
            instance = cls()
            collection = await instance.__get_collecion(
                collection_id=collection_id, session=session, with_files=True
            )

            if not collection:
                raise ValueError(f"Collection with id {collection_id} not found")

            return collection.files
        except Exception as e:
            raise RuntimeError("Failed to retrieve files from database") from e

    @staticmethod
    async def get_file_by_id(file_id: str, session: AsyncSession):
        """
        Retrieve a specific file by its ID.

        Raises:
            RuntimeError: If database query fails.
        """

        try:
            stmt = select(File).where(File.id == file_id)
            result = await session.execute(stmt)
            file = result.scalar_one_or_none()

            if not file:
                raise ValueError(f"File with id {file_id} not found")

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
        instance = cls()
        collection = await instance.__get_collecion(
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
    async def delete_file(cls, file_id: str, session: AsyncSession):
        """
        Delete a file by its ID.

        Raises:
            ValueError: If the file ID is not found.
            RuntimeError: If database operations fail.
        """

        try:
            file = await cls.get_file_by_id(file_id=file_id, session=session)
            if not file:
                raise ValueError(f"File with id {file_id} not found")

            # Delete the vector row associated with the file
            VectorModel = await VectorStore.get_vector_model(
                session,
                table_name=generate_collection_vector_table_name(file.collection_id),
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
