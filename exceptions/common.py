class ResourceNotFoundError(Exception):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource_name: str, resource_id: str):
        super().__init__(
            f"Resource '{resource_name.capitalize()}' with ID '{resource_id}' not found."
        )
        self.resource_name = resource_name
        self.resource_id = resource_id


class FileStatusNotRetryableError(Exception):
    """Exception raised when a file's status is not retryable."""

    def __init__(self, file_id: str, status: str, retryable_statuses: list[str]):
        super().__init__(
            f"File {file_id} is not in a retryable state. "
            f"Current status: {status}. "
            f"Only files with status {', '.join(retryable_statuses)} can be retried."
        )
        self.file_id = file_id
        self.status = status
        self.retryable_statuses = retryable_statuses
