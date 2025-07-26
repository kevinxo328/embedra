from enum import Enum
from typing import Optional
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


class PgVectorModelFactory:
    def __init__(self):
        pass

    def _create_model(self, table_name: str):
        """
        Create a new ORM class with the specified name.
        """

        class VectorModel(Base):
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
            meta: Mapped[Optional[dict]] = mapped_column(
                "metadata",
                JSONB,
                nullable=True,
                comment="additional metadata for the document",
            )

        return VectorModel

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

    def _create_enum_if_not_exists_sql(self):
        """
        Create the ENUM type in the database if it does not exist.
        """
        return f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{DocumentEmbeddingStatus.pgtype()}') THEN
                CREATE TYPE {DocumentEmbeddingStatus.pgtype()} AS ENUM (
                    {', '.join([f"'{status.name}'" for status in DocumentEmbeddingStatus])}
                );
            END IF;
        END $$;
        """
