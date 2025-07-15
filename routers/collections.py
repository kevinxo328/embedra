from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import schemas.collection
from database.session import get_db_session
from services.collection import CollectionService

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[schemas.collection.Collection],
)
async def get_collections(
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieve all collections from the database."""
    return await CollectionService.get_collections(session)


@router.get(
    "/{collection_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.collection.Collection,
)
async def get_collection_by_id(
    collection_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieve a specific collection by its ID."""
    collection = await CollectionService.get_collection_by_id(
        collection_id=collection_id, session=session
    )
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection id {collection_id} not found",
        )
    return collection


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.collection.Collection,
)
async def create_collection(
    collection: schemas.collection.CollectionCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Create a new collection in the database.
    This will also create a vector table for the collection in the vector store.
    """
    try:
        new_collection = await CollectionService.create_collection(
            collection_data=collection, session=session
        )

        return new_collection
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
        updated_collection = await CollectionService.update_collection(
            collection_id=collection_id,
            collection_data=collection,
            session=session,
        )
        return updated_collection
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


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete a collection by its ID.
    This will also drop the vector table associated with the collection.
    """
    try:
        await CollectionService.delete_collection(
            collection_id=collection_id, session=session
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

    return "Collection deleted successfully"
