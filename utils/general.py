import uuid
from typing import Union


def generate_collection_vector_table_name(collection_id: Union[uuid.UUID, str]) -> str:
    """
    Generate a vector table name for the collection.
    PostgreSQL doesn't allow hyphens in table names, so we replace them with underscores.

    Args:
        collection_id: The collection ID as UUID or string

    Returns:
        A valid PostgreSQL table name
    """
    return f"collection_{str(collection_id).replace('-', '_')}"
