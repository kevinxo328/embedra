import enum

from langchain_google_genai import GoogleGenerativeAIEmbeddings

import settings


class GoogleEmbeddingModel(enum.Enum):
    """
    Enum for Google Embedding Models.
    Each model has a name, input dimension, and output dimension.

    References:
    - https://ai.google.dev/gemini-api/docs/models#gemini-embedding
    """

    EMBEDDING_001 = {
        "name": "models/embedding-001",
        "input": 2048,
        "output": 768,
    }
    EMBEDDING_004 = {
        "name": "models/embedding-004",
        "input": 2048,
        "output": 768,
    }


def get_google_embeddings(
    model: str = GoogleEmbeddingModel.EMBEDDING_004.name,
) -> GoogleGenerativeAIEmbeddings:
    if model not in [m.name for m in GoogleEmbeddingModel]:
        raise ValueError(
            f"Invalid model name: {model}. Must be one of {[m.name for m in GoogleEmbeddingModel]}."
        )

    return GoogleGenerativeAIEmbeddings(model=model)
