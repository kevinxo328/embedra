import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .file import File

from .base import Base


class Collection(Base):
    """
    Represents a collection of files.
    Each collection can have multiple files associated with it.
    """

    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
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
    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="collection",
        cascade="all, delete-orphan",
        single_parent=True,
    )

    def __repr__(self) -> str:
        return f"<Collection(id={self.id}, name={self.name}, description={self.description})>"
