from enum import Enum
from typing import Union
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DocumentEmbeddingStatus(Enum):
    """
    Enum to represent the status of a document embedding.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

    @classmethod
    def pgtype(cls) -> str:
        """
        Return the name of the PostgreSQL type.
        """
        return "documentembeddingstatus"


class PgVectorOrmFactory:
    def __init__(self):
        pass

    def _create_orm(self, table_name: str):
        """
        Create a new ORM class with the specified name.
        """

        class DynamicOrm(Base):
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
                ENUM(
                    DocumentEmbeddingStatus,
                    create_type=False,
                    name=DocumentEmbeddingStatus.pgtype(),
                ),
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

    def _create_table_if_not_exists_sql(self, table_name: str):
        """
        Get the SQL statement for creating the ORM.
        """
        return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            text TEXT NOT NULL,
            embedding VECTOR,
            status {DocumentEmbeddingStatus.pgtype()} NOT NULL DEFAULT '{DocumentEmbeddingStatus.PENDING.name}',
            file_id UUID NOT NULL,
            metadata JSONB
        );
        """
