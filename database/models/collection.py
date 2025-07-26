import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from schemas.embedding import EmbeddingModelMetadata

if TYPE_CHECKING:
    from .file import FileModel

from .base import Base


class CollectionModel(Base):
    """
    Represents a collection of files.
    Each collection can have multiple files associated with it.
    """

    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=uuid.uuid4,
        comment="unique identifier for the collection",
    )
    name: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="name of the collection", unique=True
    )
    description: Mapped[str] = mapped_column(
        String(255), nullable=True, comment="description of the collection"
    )
    embedding_model_provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="embedding provider used for the collection",
    )
    embedding_model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="embedding model used for the collection",
    )
    _embedding_model_metadata: Mapped[Optional[dict]] = mapped_column(
        "embedding_model_metadata",
        JSONB,
        nullable=True,
        comment="metadata for the embedding model used in the collection",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="timestamp when the collection was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="timestamp when the collection was last updated",
    )

    # Relationship to files
    files: Mapped[list["FileModel"]] = relationship(
        "FileModel",
        back_populates="collection",
        cascade="all, delete-orphan",
        single_parent=True,
    )

    @property
    def embedding_model_metadata(self) -> Optional[EmbeddingModelMetadata]:
        if self._embedding_model_metadata is None:
            return None
        return EmbeddingModelMetadata(**self._embedding_model_metadata)

    @embedding_model_metadata.setter
    def embedding_model_metadata(self, value: Optional[EmbeddingModelMetadata]):
        if value is None:
            self._embedding_model_metadata = None
        elif isinstance(value, EmbeddingModelMetadata):
            self._embedding_model_metadata = value.model_dump()
        elif isinstance(value, dict):
            self._embedding_model_metadata = EmbeddingModelMetadata(
                **value
            ).model_dump()
        else:
            raise TypeError("Invalid type for embedding_model_metadata")

    @validates("embedding_model_metadata")
    def validate_embedding_model_metadata(self, key, value):
        """
        Validate the embedding model metadata to ensure that only valid keys are present.
        """
        if value is None:
            return None
        validated = EmbeddingModelMetadata(**value)
        return validated.model_dump()

    def __repr__(self) -> str:
        return f"<CollectionModel(id={self.id}, name={self.name}, description={self.description})>"
