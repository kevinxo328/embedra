import re
from typing import Optional

from sqlalchemy import text

from ..exception import TableNameValidationError
from ..model.factory import PgVectorOrmFactory


class PgVectorRepositoryCore:
    def __init__(self):
        self.orm_factory = PgVectorOrmFactory()

    """
    This class provides core functionalities and is not intended to be used directly.
    It is meant to be extended by synchronous and asynchronous repository classes.
    """

    @staticmethod
    def _validate_table_name(table_name: str):
        """
        Validate the table name to prevent SQL injection.
        Only alphanumeric characters and underscores are allowed.

        ### Raises
        - TableNameValidationError: If the table name contains invalid characters.
        """
        if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
            raise TableNameValidationError(table_name)
        return True

    def _check_table_exists_clause(self, table_name: str):
        sql = f"""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = '{table_name}'
        )
        """
        return text(sql)

    def _create_table_if_not_exists_clause(self, table_name: str):
        return text(self.orm_factory._create_table_if_not_exists_sql(table_name))

    def _drop_table_if_exists_clause(self, table_name: str):
        sql = f"DROP TABLE IF EXISTS {table_name};"
        return text(sql)

    def _cosine_similarity_search_clause(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
        threshold: Optional[float] = None,
    ):
        """
        Get the SQL clause to perform a cosine similarity search on the specified table.
        """
        sql = f"SELECT *, 1 - (embedding <=> '{query_vector}') AS cosine_similarity FROM {table_name}"

        if threshold is not None:
            sql += f" WHERE 1 - (embedding <=> '{query_vector}') >= {threshold}"

        sql += f" ORDER BY cosine_similarity DESC LIMIT {top_k};"
        return text(sql)
