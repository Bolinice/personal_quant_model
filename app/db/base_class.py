"""SQLAlchemy declarative base — no dependencies on app.core to avoid circular imports."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
