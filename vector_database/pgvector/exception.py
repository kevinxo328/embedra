class TableNameValidationError(Exception):
    """
    Exception raised when a table name does not meet the validation criteria.
    """

    def __init__(self, table_name: str):
        super().__init__(
            f"Invalid table name: '{table_name}'. "
            "Table names must contain only alphanumeric characters and underscores."
        )


class TableNotFoundError(Exception):
    """
    Exception raised when a table is not found in the database.
    """

    def __init__(self, table_name: str):
        super().__init__(f"Table '{table_name}' does not exist in the database.")
