from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

import schemas.file
from database.session import get_db_session
from services.file import FileService
from utils.file_uploader import validate_upload_file

router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/collections/{collection_id}",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.file.File],
)
async def get_files_by_collection_id(
    collection_id: str, session: AsyncSession = Depends(get_db_session)
):
    """Retrieve all files associated with a specific collection."""
    try:
        return await FileService.get_files_by_collection_id(
            collection_id=collection_id, session=session
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{file_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.file.File,
)
async def get_file_by_id(file_id: str, session: AsyncSession = Depends(get_db_session)):
    """Retrieve a specific file by its ID."""
    try:
        return await FileService.get_file_by_id(file_id=file_id, session=session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/collection/{collection_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.file.File,
)
async def upload_file_to_collection(
    collection_id: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Upload a file to a specific collection.
    The file will be saved to the server and its metadata will be stored in the database.
    """

    # Validate the uploaded file
    try:
        validated_file = validate_upload_file(file)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        new_file = await FileService.upload_file_to_collection(
            collection_id=collection_id,
            file=validated_file,
            session=session,
        )
        return new_file
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file_by_id(
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a file by its ID."""
    try:
        await FileService.delete_file(file_id=file_id, session=session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
