from enum import Enum
from typing import Union

from langchain_core.embeddings.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
from pydantic import SecretStr

from schemas.embedding import EmbeddingModelMetadata
from settings import AZURE_OPENAI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY


class EmbeddingModelProvider(Enum):
    """
    Enum for Embedding Model Providers.
    Each provider has a name and a list of supported models.
    """

    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"


def get_embedding_model_by_provider_name(
    provider_name: str,
    model_name: str,
    metadata: Union[EmbeddingModelMetadata, None] = None,
) -> Embeddings:
    """
    Get the embedding model provider by its name.

    ### Args:
    - provider_name: The name of the embedding model provider.
    - model_name: The name of the model to use.
    - metadata: Optional metadata for the embedding model.

    ### Returns:
    An instance of the specified embedding model.

    ### Raises:
    ValueError: If the provider name is invalid or required parameters are missing.
    """
    try:
        provider = EmbeddingModelProvider(provider_name)
    except ValueError:
        raise ValueError(
            f"Invalid embedding model provider '{provider_name}'. Must be one of {[p.value for p in EmbeddingModelProvider]}"
        )

    if provider == EmbeddingModelProvider.GOOGLE:
        if not GOOGLE_API_KEY:
            raise ValueError("Google API key must be provided for Google embeddings.")

        return GoogleGenerativeAIEmbeddings(
            model=model_name, google_api_key=SecretStr(GOOGLE_API_KEY)
        )

    elif provider == EmbeddingModelProvider.AZURE_OPENAI:
        if not metadata or not metadata.endpoint:
            raise ValueError("Endpoint must be provided for Azure OpenAI embeddings.")
        if not AZURE_OPENAI_API_KEY:
            raise ValueError(
                "Azure OpenAI API key must be provided for Azure OpenAI embeddings."
            )
        return AzureOpenAIEmbeddings(
            model=model_name,
            azure_endpoint=metadata.endpoint,
            dimensions=metadata.dimensions if metadata else None,
            api_key=SecretStr(AZURE_OPENAI_API_KEY),
        )

    elif provider == EmbeddingModelProvider.OPENAI:
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key must be provided for OpenAI embeddings.")
        return OpenAIEmbeddings(
            model=model_name,
            dimensions=metadata.dimensions if metadata else None,
            api_key=SecretStr(OPENAI_API_KEY),
            base_url=metadata.endpoint if metadata else None,
        )

    else:
        raise ValueError(
            f"Unsupported embedding model provider '{provider_name}'. Must be one of {[p.value for p in EmbeddingModelProvider]}."
        )
