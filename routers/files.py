from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db_session
from schemas.common import DeleteRequest
from services.collection import CollectionService
from services.file import FileService

router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)


@router.get("/{file_id}/download", status_code=status.HTTP_200_OK)
async def download_file(file_id: str, session: AsyncSession = Depends(get_db_session)):
    file = await FileService(session).get_file(file_id)
    return FileResponse(file.path, media_type=file.content_type)


@router.post("/{file_id}/retry", status_code=status.HTTP_200_OK)
async def retry_file_task(
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Retry the embedding task for a specific file.
    """
    return await FileService(session).retry_file_task(file_id)
