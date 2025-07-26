from typing import Optional, Union

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vector_database.pgvector.exception import TableNotFoundError

from ..model.factory import DocumentEmbeddingStatus
from .core import PgVectorRepositoryCore


class PgVectorRepositoryAsync(PgVectorRepositoryCore):
    """
    Asynchronous repository for managing vector data in PostgreSQL using pgvector.
    """

    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session

    async def _validate_table_exists(self, table_name: str):
        """
        Validate if the table exists in the database.

        #### Raises
        - TableNameValidationError: If the table name does not meet validation criteria.
        - TableNotFoundError: If the table does not exist.
        """
        self._validate_table_name(table_name)
        sql = self._check_table_exists_clause(table_name)
        result = await self.session.execute(sql)
        if not bool(result.scalar_one()):
            raise TableNotFoundError(table_name)

        return True

    async def _get_model(self, table_name: str):
        """
        Get the Model class for the specified table name.

        #### Raises
        - TableNameValidationError: If the table name does not meet validation criteria.
        - TableNotFoundError: If the table does not exist.
        """

        await self._validate_table_exists(table_name)
        return self.model_factory._create_model(table_name)

    async def stage_create_table_if_not_exists(self, table_name: str):
        """
        Create a new vector table with the specified name.
        This method does not commit the transaction.

        #### Raises
        - TableNameValidationError: If the table name does not meet validation criteria.
        """

        self._validate_table_name(table_name)
        syntax = self._create_table_if_not_exists_clause(table_name)
        await self.session.execute(syntax)
        return self.model_factory._create_model(table_name)

    async def stage_drop_table_if_exists(self, table_name: str):
        """
        Drop the specified table if it exists.
        This method does not commit the transaction.

        #### Raises
        - TableNameValidationError: If the table name does not meet validation criteria.
        """

        self._validate_table_name(table_name)
        syntax = self._drop_table_if_exists_clause(table_name)
        await self.session.execute(syntax)
        return True

    async def get_documents(
        self,
        table_name: str,
        file_id: Optional[str] = None,
        embedding_filter: Union[bool, None] = None,
    ):
        """
        Retrieve documents from the specified vector table.

        #### Args
        - table_name: Name of the table to query.
        - file_id: ID of the file to filter documents by.
        - embedding_filter: Whether to filter by documents with or without embeddings.
            - None: No filter on embedding field. (Default)
            - True: Only documents with non-null embedding are returned.
            - False: Only documents with null embedding are returned.

        #### Raises
        - TableNameValidationError: If the table name does not meet validation criteria.
        - TableNotFoundError: If the table does not exist.
        """

        Model = await self._get_model(table_name)

        stmt = select(Model)

        if file_id:
            stmt = stmt.where(Model.file_id == file_id)

        if embedding_filter:
            stmt = stmt.where(Model.embedding != None)  # noqa: E711
        elif embedding_filter == False:  # noqa: E712
            stmt = stmt.where(Model.embedding == None)  # noqa: E711

        result = await self.session.execute(stmt)

        return result.scalars().all()

    async def get_document_by_id(self, table_name: str, id: str):
        """
        Retrieve document by its ID.

        #### Raises
        - TableNameValidationError: If the table name does not meet validation criteria.
        - TableNotFoundError: If the table does not exist.
        """

        Model = await self._get_model(table_name)

        stmt = select(Model).where(Model.id == id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def stage_add_document(
        self,
        table_name: str,
        text: str,
        file_id: str,
        embedding: Optional[list[float]] = None,
        status: Optional[DocumentEmbeddingStatus] = None,
        meta: Optional[dict] = None,
    ):
        """
        Add a new document to the specified vector table.
        This method does not commit the transaction.
        """

        await self._validate_table_exists(table_name)

        Model = await self._get_model(table_name)

        new_document = Model(
            text=text,
            embedding=embedding,
            status=status,
            file_id=file_id,
            meta=meta,
        )

        self.session.add(new_document)
        await self.session.flush()
        return new_document

    async def stage_delete_documents(
        self, table_name: str, file_id: Optional[str] = None
    ):
        """
        Delete documents from the specified vector table.
        If file_id is provided, delete documents associated with that file_id.

        #### This method does not commit the transaction.
        """

        await self._validate_table_exists(table_name)

        Model = await self._get_model(table_name)

        stmt = delete(Model)

        if file_id:
            stmt = stmt.where(Model.file_id == file_id)

        await self.session.execute(stmt)

        return True

    async def cosine_similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
        threshold: Optional[float] = None,
    ):
        """
        Perform a cosine similarity search on the specified vector table.
        """

        clause = self._cosine_similarity_search_clause(
            table_name, query_vector, top_k, threshold
        )
        result = await self.session.execute(clause)

        results = []

        for row in result.mappings().all():
            results.append(
                {
                    "id": row.id,
                    "text": row.text,
                    "file_id": row.file_id,
                    "status": getattr(DocumentEmbeddingStatus, row.status, None),
                    "metadata": row.metadata,
                    "cosine_similarity": row.cosine_similarity,
                }
            )

        return results
