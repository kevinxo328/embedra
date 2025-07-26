from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.db import init_db
from env import env
from middleware.logging_middleware import LoggingMiddleware
from routers import collections, embeddings
from settings import logger, request_context
from vector_database.pgvector.db import init_db as init_pgvector_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler to initialize the application.
    This can be used to set up database connections, load configurations, etc.
    """
    await init_db()
    await init_pgvector_db()
    yield


# Docs and ReDoc URLs are only available in non-production environments
app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs" if env.APP_ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if env.APP_ENVIRONMENT != "production" else None,
)


app.add_middleware(LoggingMiddleware, context=request_context, logger=logger)


app.include_router(collections.router, prefix="/api")
app.include_router(embeddings.router, prefix="/api")

# Include utils router only in non-production environment
if env.APP_ENVIRONMENT != "production":
    from routers import utils

    app.include_router(utils.router, prefix="/api")


@app.get("/")
def read_root():
    """
    Root endpoint that returns a simple greeting message.
    """
    return {"Hello": "World"}
