from typing import Optional

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .factory import PgVectorOrmFactory


class PgVectorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.orm_factory = PgVectorOrmFactory()

    async def __validate_table_exists(self, table_name: str):
        """
        Validate if the table exists in the database.
        Raises an exception if the table does not exist.
        """

        sql = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = :table_name
        )
        """

        result = await self.session.execute(text(sql), {"table_name": table_name})
        result.scalar_one()

    async def create_table(self, table_name: str):
        """
        Create a new vector table with the specified name.
        """

        TableOrm = self.orm_factory.get_orm(table_name)

        def sync_check_create(sync_conn):
            """
            Check if the table exists in the database, and create it if not.
            """
            if not sync_conn.dialect.has_table(sync_conn, table_name):
                if table_name in self.orm_factory._metadata.tables:
                    self.orm_factory._metadata.tables[table_name].create(bind=sync_conn)
                else:
                    self.orm_factory._metadata.create_all(bind=sync_conn)

        conn = await self.session.connection()
        await conn.run_sync(sync_check_create)
        return TableOrm

    async def drop_table(self, table_name: str):
        """
        Drop the vector table with the specified name.
        """

        self.orm_factory.validate_table_name(table_name)

        def sync_drop_table(sync_conn):
            # Check if table exists before trying to drop
            if sync_conn.dialect.has_table(sync_conn, table_name):
                # Check if table is in metadata
                if table_name in self.orm_factory._metadata.tables:
                    # Use metadata to drop table
                    self.orm_factory._metadata.tables[table_name].drop(bind=sync_conn)
                else:
                    # Table name is already validated above
                    sync_conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

        conn = await self.session.connection()
        await conn.run_sync(sync_drop_table)

        return True

    async def get_documents_by_table_name(
        self,
        table_name: str,
        file_id: Optional[str] = None,
    ):
        """
        Retrieve documents from the specified vector table.
        If file_id is provided, filter documents by file_id.
        """
        TableOrm = self.orm_factory.get_orm(table_name)
        await self.__validate_table_exists(table_name)

        stmt = select(TableOrm)

        if file_id:
            stmt = stmt.where(TableOrm.file_id == file_id)

        result = await self.session.execute(stmt)

        return result.scalars().all()

    async def stage_delete_documents(
        self,
        table_name: str,
        file_id: Optional[str] = None,
    ):
        """
        Delete documents from the specified vector table.
        If file_id is provided, delete documents associated with that file_id.

        #### This method does not commit the transaction.
        """

        await self.__validate_table_exists(table_name)

        TableOrm = self.orm_factory.get_orm(table_name)

        stmt = delete(TableOrm)

        if file_id:
            stmt = stmt.where(TableOrm.file_id == file_id)
        await self.session.execute(stmt)

        return True

    async def cosine_similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
        threshold: Optional[float] = None,
    ):
        """
        Perform a cosine similarity search on the specified vector table.
        """

        TableOrm = self.orm_factory.get_orm(table_name)

        def sync_consine_similarity_search(sync_conn):
            """
            Execute the similarity search query.
            """

            similarity_exp = 1 - TableOrm.embedding.cosine_distance(query_vector)
            stmt = select(
                TableOrm,
                similarity_exp.label("cosine_similarity"),
            ).order_by(text("cosine_similarity DESC"))

            if threshold is not None:
                stmt = stmt.filter(similarity_exp >= threshold)

            stmt = stmt.limit(top_k)
            result = sync_conn.execute(stmt)
            # return result.scalars().fetchall()
            results = []
            for row in result.all():
                results.append(
                    {
                        "id": str(row.id),
                        "text": row.text,
                        "metadata": row.metadata,
                        "cosine_similarity": row.cosine_similarity,
                    }
                )
            return results

        conn = await self.session.connection()
        results = await conn.run_sync(sync_consine_similarity_search)
        return results
