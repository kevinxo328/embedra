from typing import Optional

from pydantic import BaseModel


class EmbeddingModelMetadata(BaseModel):
    endpoint: Optional[str] = None
    dimensions: Optional[int] = None


class EmbeddingModel(BaseModel):
    embedding_model: str
    embedding_model_provider: str
    embedding_model_metadata: Optional[EmbeddingModelMetadata] = None
