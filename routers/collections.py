import inspect
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

import schemas.collection
import schemas.common
import schemas.file
from database.session import get_db_session
from services.collection import (
    CollectionNotFoundException,
    CollectionService,
    CollectionServiceException,
)
from utils.file_uploader import delete_local_file, validate_upload_file

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=schemas.common.PaginatedResponse[schemas.collection.Collection],
    description=inspect.getdoc(CollectionService.get_collections),
)
async def get_collections(
    filter: schemas.collection.CollectionFilter = Depends(),
    pagination: schemas.collection.CollectionPaginationParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    return await CollectionService(session).get_collections(
        filter=filter, pagination=pagination
    )


@router.get(
    "/{collection_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.collection.Collection,
)
async def get_collection_by_id(
    collection_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve a specific collection by its ID.
    """

    collection = await CollectionService(session).get_collection_by_id_or_none(
        collection_id
    )

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(CollectionNotFoundException(collection_id)),
        )

    return collection


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.collection.Collection,
    description=inspect.getdoc(CollectionService.create_collection),
)
async def create_collection(
    collection: schemas.collection.CollectionCreate,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await CollectionService(session).create_collection(data=collection)
    except CollectionServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/{collection_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.collection.Collection,
)
async def update_collection(
    collection_id: str,
    collection: schemas.collection.CollectionUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """Update an existing collection by its ID."""
    try:
        return await CollectionService(session).update_collection(
            id=collection_id, data=collection
        )
    except CollectionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.common.DeleteResponse,
)
async def delete_collection_by_id(
    collection_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete a collection by its ID.
    This will also drop the vector table associated with the collection.
    """
    try:
        paths = await CollectionService(session).delete_collection_by_id(collection_id)

        # TODO: Handle file deletion in a more robust way. (e.g., Celery task + retry logic)
        # Schedule file deletion in the background
        for path in paths:
            background_tasks.add_task(delete_local_file, path)
        return schemas.common.DeleteResponse(deleted_ids=[collection_id])
    except CollectionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{collection_id}/files",
    status_code=status.HTTP_200_OK,
    response_model=schemas.common.PaginatedResponse[schemas.file.File],
)
async def get_collection_files(
    collection_id: str,
    filter: schemas.file.FileFilter = Depends(),
    pagination: schemas.file.FilePaginationParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve files associated with a specific collection.

       Returns:
           data: A paginated list of files in the collection.
           total: Total number of files in the collection before pagination.
           page: Current page number.
           page_size: Number of items per page.
    """
    try:
        return await CollectionService(session).get_collection_files(
            collection_id, filter, pagination
        )
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with ID {collection_id} not found",
        )


@router.post(
    "/{collection_id}/files",
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
        return await CollectionService(session).upload_file_to_collection(
            collection_id=collection_id,
            file=validated_file,
        )

    except CollectionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{collection_id}/files",
    status_code=status.HTTP_200_OK,
    response_model=schemas.common.DeleteResponse,
)
async def delete_files_in_collection(
    collection_id: str,
    request: schemas.common.DeleteRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete specific files in a specific collection.
    """
    try:
        result, delete_file_paths = await CollectionService(
            session
        ).delete_collection_files(
            collection_id=collection_id,
            file_ids=request.ids,
            all=request.all,
        )

    except CollectionNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CollectionServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # TODO: Handle file deletion in a more robust way. (e.g., Celery task + retry logic)
    for path in delete_file_paths:
        background_tasks.add_task(delete_local_file, path)

    return result


@router.get("/{collection_id}/cosine_similarity_search")
async def cosine_similarity_search(
    collection_id: str,
    query: str,
    k: int = 5,
    threshold: Optional[float] = None,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Perform a cosine similarity search in the specified collection.
    """
    try:
        return await CollectionService(session).cosine_similarity_search(
            collection_id=collection_id,
            query=query,
            top_k=k,
            threshold=threshold,
        )
    except CollectionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
