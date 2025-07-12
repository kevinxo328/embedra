from io import BytesIO

from fastapi import APIRouter, UploadFile, status
from langchain_core.documents import Document

import schemas.utils
import settings
import utils.doc_processor as doc_processor

router = APIRouter(
    prefix="/utils",
    tags=["utils"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/markitdown/path",
    status_code=status.HTTP_200_OK,
    response_model=schemas.utils.MarkdownResponse,
)
async def convert_markdown_by_path(path: str):
    """
    Convert to markdown by file path or url.

    Args:
        path: Path to the file or URL to fetch the markdown content. For local files, use absolute or relative paths.
    """
    return doc_processor.markitdown_converter(source=path)


@router.post(
    "/markitdown/file",
    status_code=status.HTTP_200_OK,
    response_model=schemas.utils.MarkdownResponse,
)
async def convert_markdown_by_file(file: UploadFile):
    """
    Convert to markdown by file.
    """

    content = await file.read()
    bio = BytesIO(content)
    return doc_processor.markitdown_converter(source=bio)


@router.post(
    "/splitter/markdown", status_code=status.HTTP_200_OK, response_model=list[Document]
)
async def split_markdown(markdown: str, chunk_size: int = 300, chunk_overlap: int = 50):
    """
    Split markdown text into chunks.

    Args:
        markdown: The markdown text to split.
        chunk_size: The size of each chunk.
        chunk_overlap: The overlap between chunks.
    """
    return doc_processor.split_markdown(
        markdown=markdown, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
