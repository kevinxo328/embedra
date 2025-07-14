from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import schemas.collection
from database.models.collection import Collection
from database.session import get_db_session
from settings import VectorStore
from utils.embeddings import GoogleEmbeddingModel
from utils.file_uploader import delete_file

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

    stmt = (
        select(Collection)
        .options(selectinload(Collection.files))
        .order_by(Collection.created_at.desc())
    )
    result = await session.execute(stmt)
    collections = result.scalars().all()

    return [
        schemas.collection.Collection.model_validate(collection)
        for collection in collections
    ]


@router.get(
    "/{collection_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.collection.Collection,
)
async def get_collection(
    collection_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieve a specific collection by its ID."""

    stmt = (
        select(Collection)
        .options(selectinload(Collection.files))
        .where(Collection.id == collection_id)
    )
    result = await session.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    return schemas.collection.Collection.model_validate(collection)


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

    # Validate the embedding model and get its dimension
    model_output_map = {
        model.value["name"]: model.value["output"] for model in GoogleEmbeddingModel
    }
    dimension = model_output_map.get(collection.embedding_model)
    if not dimension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid embedding model '{collection.embedding_model}'. "
            f"Must be one of {[m.value['name'] for m in GoogleEmbeddingModel]}",
        )

    # Create a new collection instance
    new_collection = Collection(
        name=collection.name,
        description=collection.description,
        embedding_model=collection.embedding_model,
    )

    session.add(new_collection)
    await session.flush()  # Ensure the collection ID is generated before creating the vector table

    try:
        # Create a vector table for the new collection
        await VectorStore.create_collection_vector_table(
            session=session,
            collection_id=str(new_collection.id),
            dimension=dimension,
        )

        # Commit the session to save the collection and vector table
        await session.commit()
        await session.refresh(new_collection)

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create collection: {str(e)}",
        )

    return schemas.collection.Collection.model_validate(new_collection)


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
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await session.execute(stmt)
    existing_collection = result.scalar_one_or_none()

    if not existing_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    # Update the collection fields
    existing_collection.name = collection.name
    existing_collection.description = (
        collection.description
        if collection.description is not None
        else existing_collection.description
    )

    await session.commit()
    await session.refresh(existing_collection)

    return schemas.collection.Collection.model_validate(existing_collection)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete a collection by its ID.
    This will also drop the vector table associated with the collection.
    """
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await session.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    try:
        await VectorStore.drop_collection_vector_table(
            session=session,
            collection_id=str(collection.id),
        )
        await session.delete(collection)
        await session.commit()

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete collection: {str(e)}",
        )

    # TODO: remove files without blocking
    for file in collection.files:
        delete_file(file.path)

    return "Collection deleted successfully"
