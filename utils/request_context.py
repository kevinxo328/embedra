from contextvars import ContextVar


class RequestContext:
    """
    A context manager to handle request ID and sequence number.
    It allows you to set a request ID and manage sequence numbers within a request scope.
    """

    def __init__(self):
        self.request_id_contextvar: ContextVar[str] = ContextVar(
            "request_id", default="N/A"
        )
        self.seq_no_contextvar: ContextVar[int] = ContextVar("seq_no", default=0)

    def set_request_id(self, request_id: str):
        """
        Set the request ID for the current context.
        Args:
            request_id (str): The request ID to set
        """
        self.request_id_contextvar.set(request_id)

    def get_request_id(self) -> str:
        """
        Get the current request ID from context.
        Returns:
            str: The current request ID, or "N/A" if not available
        """
        return self.request_id_contextvar.get("N/A")

    def next_seq_no(self) -> int:
        """
        Get the next sequence number for the current request.
        Returns:
            int: The next sequence number, starting from 0
        """
        seq_no = self.seq_no_contextvar.get(0)
        seq_no += 1
        self.seq_no_contextvar.set(seq_no)
        return seq_no

    def reset(self):
        """
        Reset all context variables for the current request.
        This includes resetting the request ID and sequence number.
        """
        self.request_id_contextvar.set("N/A")
        self.seq_no_contextvar.set(0)
