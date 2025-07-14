from collections import OrderedDict
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, Table, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import registry


class LRUCache:
    def __init__(self, max_size: int = 512):
        self.max_size = max_size
        self._cache = OrderedDict()

    def get(self, key):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def drop(self, key):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()


class PostgresVectorStore:
    def __init__(self, max_cache_size: int = 512):
        self._registry = registry()
        self._metadata = self._registry.metadata
        self._model_cache = LRUCache(max_cache_size)

    def __create_vector_table_class(self, table_name: str, dimension: int):
        """
        Create a new vector table class with the specified name and dimension.
        This method is used to dynamically create a table class for vector storage.
        """
        table = Table(
            table_name,
            self._metadata,
            Column(
                "id",
                UUID,
                primary_key=True,
                default=uuid4,
                comment="unique identifier for the vector",
            ),
            Column(
                "text",
                String,
                nullable=False,
                comment="text associated with the vector",
            ),
            Column("embedding", Vector(dimension), nullable=False, comment="vector embedding"),  # type: ignore
            Column(
                "metadata",
                JSONB,
                nullable=True,
                comment="additional metadata for the vector",
            ),
            extend_existing=True,
        )

        class VectorRow:
            def __init__(self, text, embedding, metadata=None):
                self.text = text
                self.embedding = embedding
                self.metadata = metadata

        self._registry.map_imperatively(VectorRow, table)
        self._model_cache.set(table_name, VectorRow)

        return VectorRow

    async def create_vector_table(
        self, session: AsyncSession, table_name: str, dimension: int
    ):
        # Check if the table already exists in the cache
        cached = self._model_cache.get(table_name)
        if cached is not None:
            return cached

        # Create a new table class and cache it
        vector_row_class = self.__create_vector_table_class(table_name, dimension)

        def sync_check_create(sync_conn):
            """
            Check if the table exists in the database, and create it if not.
            """
            if not sync_conn.dialect.has_table(sync_conn, table_name):
                if table_name in self._metadata.tables:
                    self._metadata.tables[table_name].create(bind=sync_conn)
                else:
                    # 如果表格不在 metadata 中，重新創建 metadata
                    self._metadata.create_all(bind=sync_conn)

        conn = await session.connection()
        await conn.run_sync(sync_check_create)

        return vector_row_class

    async def get_vector_model(self, session: AsyncSession, table_name: str):
        """
        Get the vector model for the specified table.
        """
        cached = self._model_cache.get(table_name)
        if cached:
            return cached

        def sync_inspect(sync_conn, embedding_column="embedding"):
            """
            Check if the table exists and get its vector dimension.
            """
            inspector = inspect(sync_conn)
            if not inspector.has_table(table_name):
                raise ValueError(f"Table '{table_name}' does not exist")

            columns = inspector.get_columns(table_name)
            for col in columns:
                if col["name"] == embedding_column:
                    col_type = col["type"]
                    if isinstance(col_type, Vector):
                        return col_type.dim

        conn = await session.connection()
        dimension = await conn.run_sync(sync_inspect)

        if dimension is None:
            raise ValueError(f"Could not determine dimension for table '{table_name}'")

        return self.__create_vector_table_class(table_name, int(dimension))

    async def drop_vector_table(self, session: AsyncSession, table_name: str):
        """
        Drop the vector table with the specified name.
        """
        cached = self._model_cache.get(table_name)
        if cached:
            self._model_cache.drop(table_name)

        def sync_drop_table(sync_conn):
            if sync_conn.dialect.has_table(sync_conn, table_name):
                self._metadata.tables[table_name].drop(bind=sync_conn)

        conn = await session.connection()
        await conn.run_sync(sync_drop_table)

        return True


class CollectionVectorStore(PostgresVectorStore):
    """
    A specialized vector store for collections, inheriting from PostgresVectorStore.
    This class can be extended with additional methods specific to collection management.
    """

    def __get_table_name(self, collection_id: str):
        """
        Generate a table name based on the collection ID.
        """
        return f"collection_{collection_id}"

    async def create_collection_vector_table(
        self, session: AsyncSession, collection_id: str, dimension: int
    ):
        """
        Create a vector table for a specific collection.
        """
        table_name = self.__get_table_name(collection_id)
        return await self.create_vector_table(session, table_name, dimension)

    async def get_collection_vector_model(
        self, session: AsyncSession, collection_id: str
    ):
        """
        Get the vector model for a specific collection.
        """
        table_name = self.__get_table_name(collection_id)
        return await self.get_vector_model(session, table_name)

    async def drop_collection_vector_table(
        self, session: AsyncSession, collection_id: str
    ):
        """
        Drop the vector table for a specific collection.
        """
        table_name = self.__get_table_name(collection_id)
        return await self.drop_vector_table(session, table_name)
