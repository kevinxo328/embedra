import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from utils.request_context import RequestContext


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a unique request ID for each incoming request,
    logs request/response info, and adds request ID to response headers.
    """

    def __init__(
        self,
        app,
        context: RequestContext,
        logger: logging.Logger,
        header_name: str = "X-Request-ID",
    ):
        super().__init__(app)
        self.header_name = header_name
        self.context = context
        self.logger = logger

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate a unique request ID if not provided in headers
        request_id = request.headers.get(
            self.header_name.lower()
        ) or request.headers.get(self.header_name)

        if not request_id:
            request_id = str(uuid.uuid4())

        self.context.reset()

        # Store request ID in context variable for use in logging
        self.context.set_request_id(request_id)

        start_time = time.perf_counter()

        try:
            req_body = await request.body()
        except Exception:
            req_body = None

        try:
            response = await call_next(request)
        except IntegrityError as e:
            self.logger.error(
                f"Integrity error occurred during request processing: {e}",
            )
            response = JSONResponse(
                status_code=400,
                content={"detail": f"Integrity error occurred: {e.orig}"},
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error occurred during request processing: {e}",
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )

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

        log_str = (
            f"Request ID: {request_id}, "
            f"Method: {method}, URL: {url}, "
            f"Query Params: {query_params}, "
            f"Body: {body_str}, "
            f"Response Status Code: {response.status_code}, "
            f"Processing Time: {process_time:.4f} seconds"
        )

        if response.status_code >= 400:
            self.logger.error(log_str)
        else:
            self.logger.info(log_str)

        response.headers[self.header_name] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        return response
