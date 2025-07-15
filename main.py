from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.db import init_db
from routers import collections
from settings import APP_ENVIRONMENT


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

app.include_router(collections.router, prefix="/api")

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
