from typing import Union

from pydantic import BaseModel


class EmbeddingModelMetadata(BaseModel):
    endpoint: Union[str, None] = None
    dimensions: Union[int, None] = None


class EmbeddingModel(BaseModel):
    embedding_model: str
    embedding_model_provider: str
    embedding_model_metadata: Union[EmbeddingModelMetadata, None] = None
