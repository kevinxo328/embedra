import re
from collections import OrderedDict
from typing import Union
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, Table, inspect, select, text
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

    def __validate_table_name(self, table_name: str):
        """
        Validate the table name to prevent SQL injection.
        Only alphanumeric characters and underscores are allowed.
        """
        return re.match(r"^[a-zA-Z0-9_]+$", table_name)

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

        self._registry.map_imperatively(
            VectorRow,
            table,
            properties={
                "id": table.c.id,
                "text": table.c.text,
                "embedding": table.c.embedding,
                "metadata": table.c.metadata,
            },
        )
        self._model_cache.set(table_name, VectorRow)

        return VectorRow

    async def create_vector_table(
        self, table_name: str, dimension: int, session: AsyncSession
    ):
        if not self.__validate_table_name(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

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
                    self._metadata.create_all(bind=sync_conn)

        conn = await session.connection()
        await conn.run_sync(sync_check_create)
        return vector_row_class

    async def get_vector_model(self, session: AsyncSession, table_name: str):
        """
        Get the vector model for the specified table.
        """
        if not self.__validate_table_name(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

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

    async def drop_vector_table(
        self,
        table_name: str,
        session: AsyncSession,
    ):
        """
        Drop the vector table with the specified name.
        """
        if not self.__validate_table_name(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        # Remove from cache first
        cached = self._model_cache.get(table_name)
        if cached:
            self._model_cache.drop(table_name)

        def sync_drop_table(sync_conn):
            # Check if table exists before trying to drop
            if sync_conn.dialect.has_table(sync_conn, table_name):
                # Check if table is in metadata
                if table_name in self._metadata.tables:
                    # Use metadata to drop table
                    self._metadata.tables[table_name].drop(bind=sync_conn)
                else:
                    # Table name is already validated above
                    sync_conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

        conn = await session.connection()
        await conn.run_sync(sync_drop_table)

        return True

    async def similarity_search(
        self,
        session: AsyncSession,
        table_name: str,
        query_vector: list[float],
        top_k=5,
        threshold: Union[float, None] = None,
    ):
        """
        Perform a similarity search in the specified vector table.
        """
        if not self.__validate_table_name(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        VectorModel = await self.get_vector_model(session, table_name)
        if not VectorModel:
            raise ValueError(f"Vector model for table '{table_name}' not found")

        def sync_similarity_search(sync_conn):
            """
            Execute the similarity search query.
            """
            stmt = select(
                VectorModel,
                (1 - VectorModel.embedding.cosine_distance(query_vector)).label(  # type: ignore
                    "similarity_score"
                ),
            ).order_by(
                VectorModel.embedding.cosine_distance(query_vector)  # type: ignore
            )

            if threshold is not None:
                stmt = stmt.filter(
                    VectorModel.embedding.cosine_distance(query_vector) < threshold  # type: ignore
                )

            stmt = stmt.limit(top_k)
            result = sync_conn.execute(stmt)
            # return result.scalars().fetchall()
            results = []
            for row in result.all():
                results.append(
                    {
                        "id": str(row.id),
                        "text": row.text,
                        # "embedding": row.embedding.tolist(),
                        "metadata": row.metadata,
                        "similarity_score": row.similarity_score,
                    }
                )
            return results

        conn = await session.connection()
        results = await conn.run_sync(sync_similarity_search)
        return results
