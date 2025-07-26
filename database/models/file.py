import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from schemas.file import FileStatus

if TYPE_CHECKING:
    from .collection import CollectionModel

from .base import Base


class FileModel(Base):

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=uuid.uuid4,
        comment="unique identifier for the file",
    )
    filename: Mapped[str] = mapped_column(
        String(80), nullable=False, comment="original name of the file"
    )
    size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="size of the file in bytes"
    )
    content_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="MIME type of the file"
    )
    path: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="path where the file is stored on disk or cloud storage",
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="timestamp when the file was created",
    )
    status: Mapped[FileStatus] = mapped_column(
        ENUM(FileStatus),
        nullable=False,
        default=FileStatus.UPLOADED,
        comment="current processing status of the file",
    )

    # Relationship to collection
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id"))
    collection: Mapped["CollectionModel"] = relationship(
        "Collection",
        back_populates="files",
    )

    def __repr__(self) -> str:
        return f"<File(id={self.id}, filename={self.filename}, size={self.size}, content_type={self.content_type})>"
