from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    This class uses DeclarativeBase from SQLAlchemy to define the base for all models.
    It can be extended by other model classes to inherit common properties and methods.
    """

    pass
