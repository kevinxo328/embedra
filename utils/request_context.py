from contextvars import ContextVar

# Context variable to store request ID across the request lifecycle
request_id_contextvar: ContextVar[str] = ContextVar("request_id", default="N/A")


def get_request_id() -> str:
    """
    Get the current request ID from context.
    Returns:
        str: The current request ID, or "N/A" if not available
    """
    return request_id_contextvar.get("N/A")
