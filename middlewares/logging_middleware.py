import time
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logger import logger

# Context variable to store request ID across the request lifecycle
request_id_contextvar: ContextVar[str] = ContextVar("request_id", default="N/A")


def get_request_id() -> str:
    """
    Get the current request ID from context.
    Returns:
        str: The current request ID, or empty string if not available
    """
    return request_id_contextvar.get("N/A")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a unique request ID for each incoming request,
    logs request/response info, and adds request ID to response headers.
    """

    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(
            self.header_name.lower()
        ) or request.headers.get(self.header_name)

        if not request_id:
            request_id = str(uuid.uuid4())

        # Store request ID in context variable for use in logging
        token = request_id_contextvar.set(request_id)

        start_time = time.perf_counter()
        try:
            req_body = await request.body()
        except Exception:
            req_body = None

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                f"Unexpected error occurred during request processing: {e}",
                extra={"request_id": get_request_id()},
            )
            raise e

        process_time = time.perf_counter() - start_time
        method = request.method
        url = request.url.path
        query_params = dict(request.query_params)

        logger.info(
            f"Request processed: Method: {method}, URL: {url}, "
            f"Query Params: {query_params}, "
            f"Body: {req_body.decode('utf-8') if req_body else 'N/A'}, "
            f"Response Status Code: {response.status_code}, "
            f"Processing Time: {process_time:.4f} seconds",
            extra={"request_id": get_request_id()},
        )

        response.headers[self.header_name] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        request_id_contextvar.reset(token)
        return response
