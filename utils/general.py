def generate_collection_vector_table_name(collection_id: str) -> str:
    """
    Generate a vector table name for the collection.
    PostgreSQL doesn't allow hyphens in table names, so we replace them with underscores.

    Args:
        collection_id: The collection ID as string

    Returns:
        A valid PostgreSQL table name
    """
    return f"collection_{collection_id.replace('-', '_')}"
