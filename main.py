from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.db import init_db
from routers import collections, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler to initialize the application.
    This can be used to set up database connections, load configurations, etc.
    """
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(collections.router)
app.include_router(files.router)


@app.get("/")
def read_root():
    """
    Root endpoint that returns a simple greeting message.
    """
    return {"Hello": "World"}
