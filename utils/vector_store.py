import re
from enum import Enum
from typing import Union
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, select, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, registry


class DocumentEmbeddingStatus(Enum):
    """
    Enum to represent the status of a document embedding.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# TODO: Implement similarity search and hybrid search
# TODO: Add logging for vector store operations
class PostgresVectorStore:
    def __init__(self):
        self._registry = registry()
        self._metadata = self._registry.metadata

    def __validate_table_name(self, table_name: str):
        """
        Validate the table name to prevent SQL injection.
        Only alphanumeric characters and underscores are allowed.
        """
        if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
            raise ValueError(
                f"Invalid table name: {table_name}. Only alphanumeric characters and underscores are allowed."
            )
        return True

    def __create_orm(self, table_name: str):
        """
        Create a new ORM class with the specified name.
        """

        @self._registry.mapped
        class DynamicOrm:
            __tablename__ = table_name
            __table_args__ = {"extend_existing": True}
            id: Mapped[str] = mapped_column(
                UUID(as_uuid=False),
                primary_key=True,
                default=uuid4,
                comment="unique identifier for the document",
            )
            text: Mapped[str] = mapped_column(
                String, nullable=False, comment="text associated with the document"
            )
            embedding: Mapped[list[float]] = mapped_column(
                Vector(), nullable=True, comment="document embedding"  # type: ignore
            )
            status: Mapped[DocumentEmbeddingStatus] = mapped_column(
                ENUM(DocumentEmbeddingStatus),
                nullable=False,
                default=DocumentEmbeddingStatus.PENDING,
                comment="status of the document embedding",
            )
            # TODO: Create ForeignKey to File table.
            file_id: Mapped[str] = mapped_column(
                UUID(as_uuid=False),
                nullable=False,
                comment="ID of the file associated with the document",
            )
            meta: Mapped[Union[dict, None]] = mapped_column(
                "metadata",
                JSONB,
                nullable=True,
                comment="additional metadata for the document",
            )

        return DynamicOrm

    def get_orm(self, table_name: str):
        """
        Get the vector model for the specified table.
        """
        self.__validate_table_name(table_name)

        return self.__create_orm(table_name)

    async def create_vector_table(self, table_name: str, session: AsyncSession):
        self.__validate_table_name(table_name)
        # Create a new vector ORM and cache it
        VectorOrm = self.__create_orm(table_name)

        def sync_check_create(sync_conn):
            """
            Check if the table exists in the database, and create it if not.
            """
            if not sync_conn.dialect.has_table(sync_conn, table_name):
                if table_name in self._metadata.tables:
                    self._metadata.tables[table_name].create(bind=sync_conn)
                else:
                    self._metadata.create_all(bind=sync_conn)

        conn = await session.connection()
        await conn.run_sync(sync_check_create)
        return VectorOrm

    async def drop_vector_table(
        self,
        table_name: str,
        session: AsyncSession,
    ):
        """
        Drop the vector table with the specified name.
        """
        self.__validate_table_name(table_name)

        def sync_drop_table(sync_conn):
            # Check if table exists before trying to drop
            if sync_conn.dialect.has_table(sync_conn, table_name):
                # Check if table is in metadata
                if table_name in self._metadata.tables:
                    # Use metadata to drop table
                    self._metadata.tables[table_name].drop(bind=sync_conn)
                else:
                    # Table name is already validated above
                    sync_conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

        conn = await session.connection()
        await conn.run_sync(sync_drop_table)

        return True

    async def consine_similarity_search(
        self,
        session: AsyncSession,
        table_name: str,
        query_vector: list[float],
        top_k=5,
        threshold: Union[float, None] = None,
    ):
        """
        Perform a similarity search in the specified vector table.
        """
        self.__validate_table_name(table_name)

        VectorOrm = self.get_orm(table_name)
        if not VectorOrm:
            raise ValueError(f"Vector model for table '{table_name}' not found")

        def sync_consine_similarity_search(sync_conn):
            """
            Execute the similarity search query.
            """

            similarity_exp = 1 - VectorOrm.embedding.cosine_distance(query_vector)
            stmt = select(
                VectorOrm,
                similarity_exp.label("cosine_similarity"),
            ).order_by(text("cosine_similarity DESC"))

            if threshold is not None:
                stmt = stmt.filter(similarity_exp >= threshold)

            stmt = stmt.limit(top_k)
            result = sync_conn.execute(stmt)
            # return result.scalars().fetchall()
            results = []
            for row in result.all():
                results.append(
                    {
                        "id": str(row.id),
                        "text": row.text,
                        "metadata": row.metadata,
                        "cosine_similarity": row.cosine_similarity,
                    }
                )
            return results

        conn = await session.connection()
        results = await conn.run_sync(sync_consine_similarity_search)
        return results
