import re
from enum import Enum
from typing import Union
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, registry


class DocumentEmbeddingStatus(Enum):
    """
    Enum to represent the status of a document embedding.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PgVectorOrmFactory:
    def __init__(self):
        self._registry = registry()
        self._metadata = self._registry.metadata

    def __validate_table_name(self, table_name: str):
        """
        Validate the table name to prevent SQL injection.
        Only alphanumeric characters and underscores are allowed.

        ### Raises
        ValueError: If the table name contains invalid characters.
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

            # TODO: `extend_existing` is used to allow __create_orm to be called multiple times.
            # However, if the table schema changes unexpectedly, this may cause issues.
            # Ideally, a caching layer should be implemented to avoid redefining the same ORM type.
            # For now, it's not implemented because defining dynamic ORM types is somewhat complex.
            # This may be revisited once a clean dynamic ORM definition pattern is established.
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
        Get the ORM class for the specified table name.
        """
        self.__validate_table_name(table_name)

        return self.__create_orm(table_name)
