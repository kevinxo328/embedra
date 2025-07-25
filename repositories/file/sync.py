from sqlalchemy.orm import Session

from domains.file import SelectFilter

from .core import FileRepositoryCore


class FileRepositorySync(FileRepositoryCore):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

    def select_one(self, select_filter: SelectFilter):
        """Retrieve a file."""
        stmt = self._select_expression(select_filter)

        result = self.session.execute(stmt)
        return result.scalar_one()
