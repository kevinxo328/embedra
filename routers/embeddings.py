from typing import Annotated, Union

from fastapi import APIRouter, Body, HTTPException, status

from schemas.embedding import EmbeddingModelMetadata
from settings import AZURE_OPENAI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY
from utils.embeddings import (
    EmbeddingModelProvider,
    get_embedding_model_by_provider_name,
)

router = APIRouter(
    prefix="/embeddings",
    tags=["embeddings"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/providers",
    status_code=status.HTTP_200_OK,
    response_model=list[str],
)
async def get_embedding_providers():
    """
    Get a list of available embedding providers.
    """
    providers = []

    if GOOGLE_API_KEY:
        providers.append(EmbeddingModelProvider.GOOGLE.value)

    if AZURE_OPENAI_API_KEY:
        providers.append(EmbeddingModelProvider.AZURE_OPENAI.value)

    if OPENAI_API_KEY:
        providers.append(EmbeddingModelProvider.OPENAI.value)

    return providers


@router.post("/", status_code=status.HTTP_200_OK)
async def create_text_embedding(
    text: Annotated[str, Body()],
    model_name: Annotated[str, Body()],
    provider_name: Annotated[str, Body()],
    metadata: Annotated[Union[EmbeddingModelMetadata, None], Body()] = None,
):
    """
    Create the embedding for a given text using the specified embedding model.

    ### Args:
    - provider_name: The provider of the embedding model (e.g., "google", "azure_openai", "openai").
    - model_name: The name of the embedding model to use.
    - metadata: Optional metadata for the embedding model. For example, it can include the endpoint and dimensions.
    - text: The text to embed.

    ### Returns:
    - embeddings: A list of floats representing the embedding of the text.
    - dimensions: The number of dimensions in the embedding.
    """
    try:
        provider = get_embedding_model_by_provider_name(
            provider_name,
            model_name,
            metadata,
        )
        embeddings = provider.embed_query(text)

        return {
            "embeddings": embeddings,
            "dimensions": len(embeddings),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
