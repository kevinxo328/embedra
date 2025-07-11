from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import schemas.file
import settings
from database.models.collection import Collection
from database.models.file import File
from database.session import get_db_session
from utils.file_uploader import delete_file, save_file, validate_upload_file

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
async def get_collection_files(
    collection_id: str, session: AsyncSession = Depends(get_db_session)
):
    """Retrieve all files associated with a specific collection."""
    stmt = (
        select(Collection)
        .where(Collection.id == collection_id)
        .options(selectinload(Collection.files))
    )
    result = await session.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    return [schemas.file.File.model_validate(file) for file in collection.files]


@router.get(
    "/{file_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.file.File,
)
async def get_file(file_id: str, session: AsyncSession = Depends(get_db_session)):
    """Retrieve a specific file by its ID."""
    stmt = select(File).where(File.id == file_id)
    result = await session.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return schemas.file.File.model_validate(file)


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

    # Check if the collection exists
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await session.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    try:
        save_file_path = save_file(validated_file)

        new_file = File(
            filename=validated_file.filename,
            filesize=validated_file.size,
            content_type=validated_file.content_type,
            collection_id=collection.id,
            path=save_file_path,
        )

        session.add(new_file)
        await session.commit()
        await session.refresh(new_file)

        return schemas.file.File.model_validate(new_file)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={str(e)},
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
    stmt = select(File).where(File.id == file_id)
    result = await session.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete the file
    delete_file(file.path)

    # Delete the file record from the database
    await session.delete(file)
    await session.commit()

    return "File deleted successfully"
