from enum import Enum

from langchain_google_genai import GoogleGenerativeAIEmbeddings

import settings


class GoogleEmbeddingModel(Enum):
    """
    Enum for Google Embedding Models.
    Each model has a name, input dimension, and output dimension.

    References:
    - https://ai.google.dev/gemini-api/docs/models#gemini-embedding
    """

    EMBEDDING_004 = (
        "models/text-embedding-004",
        2048,
        768,
    )

    def __init__(self, name: str, input_dim: int, output_dim: int):
        self._name = name
        self._input_dim = input_dim
        self._output_dim = output_dim

    @property
    def name(self) -> str:
        """Return the model name."""
        return self._name

    @property
    def input_dim(self) -> int:
        """Return the input dimension of the model."""
        return self._input_dim

    @property
    def output_dim(self) -> int:
        """Return the output dimension of the model."""
        return self._output_dim

    @classmethod
    def from_name(cls, name: str):
        """
        Get the embedding model by its name.
        """

        for model in cls:
            if model.name == name:
                return model
        raise ValueError(f"Model {name} not found in GoogleEmbeddingModel enum.")


def get_google_embeddings(
    model_name: str = GoogleEmbeddingModel.EMBEDDING_004.name,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> GoogleGenerativeAIEmbeddings:
    # Check model should be one of the GoogleEmbeddingModel enum's name
    try:
        GoogleEmbeddingModel.from_name(model_name)
    except ValueError:
        raise ValueError(
            f"Invalid embedding model '{model_name}'. Must be one of {[m.name for m in GoogleEmbeddingModel]}"
        )

    return GoogleGenerativeAIEmbeddings(model=model_name, task_type=task_type)
