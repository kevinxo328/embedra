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
