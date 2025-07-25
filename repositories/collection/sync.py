from sqlalchemy.orm import Session

from domains.collection import SelectFilter

from .core import CollectionRepositoryCore


class CollectionRepositorySync(CollectionRepositoryCore):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

    def select_one(self, filter: SelectFilter):
        """Retrieve a collection."""
        stmt = self._select_expression(filter)
        result = self.session.execute(stmt)
        return result.scalar_one()
