import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logger import logger
from utils.request_context import request_id_contextvar


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
            )
            raise e

        process_time = time.perf_counter() - start_time
        method = request.method
        url = request.url.path
        query_params = dict(request.query_params)

        # Handle request body logging
        if req_body:
            try:
                body_str = req_body.decode("utf-8")
            except UnicodeDecodeError:
                body_str = f"<binary {len(req_body)} bytes>"
        else:
            body_str = "N/A"

        logger.info(
            f"Request processed: Method: {method}, URL: {url}, "
            f"Query Params: {query_params}, "
            f"Body: {body_str}, "
            f"Response Status Code: {response.status_code}, "
            f"Processing Time: {process_time:.4f} seconds",
        )

        response.headers[self.header_name] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        request_id_contextvar.reset(token)
        return response
