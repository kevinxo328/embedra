from io import BytesIO

from fastapi import APIRouter, UploadFile, status

import schemas.utils
import settings
from utils.doc_processor import markitdown_converter

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
    return markitdown_converter(source=path)


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
    return markitdown_converter(source=bio)
