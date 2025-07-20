import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from database.db import init_db
from routers import collections, embeddings
from settings import APP_ENVIRONMENT
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler to initialize the application.
    This can be used to set up database connections, load configurations, etc.
    """
    await init_db()
    yield


# Docs and ReDoc URLs are only available in non-production environments
app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs" if APP_ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if APP_ENVIRONMENT != "production" else None,
)


@app.middleware("http")
async def middleware(request: Request, call_next):
    try:
        req_body = await request.body()
    except Exception:
        req_body = None

    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Unexpected error occurred during request processing: {e}")
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
        f"Processing Time: {process_time:.4f} seconds"
    )

    # Add custom headers to the response
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for the application.
    """
    try:
        body = await request.body()
    except Exception:
        body = None

    exception_message = f"Unhandled exception occurred: {exc}. Method: {request.method}, URL: {request.url}, Headers: {dict(request.headers)}, Query Params: {dict(request.query_params)}, Body: {body.decode('utf-8') if body else 'N/A'}"
    logger.exception(exception_message)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


app.include_router(collections.router, prefix="/api")
app.include_router(embeddings.router, prefix="/api")

# Include utils router only in non-production environment
if APP_ENVIRONMENT != "production":
    from routers import utils

    app.include_router(utils.router, prefix="/api")


@app.get("/")
def read_root():
    """
    Root endpoint that returns a simple greeting message.
    """
    return {"Hello": "World"}
