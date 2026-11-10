"""SQLAlchemy declarative base and shared naming convention.

A single :class:`Base` is shared by every ORM model in the application so
that Alembic's ``target_metadata`` reflects the full schema and
``create_all()`` (used only in disposable test databases, never in
production) creates every table at once.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

#: Shared naming convention so Alembic-generated constraint names are
#: deterministic across environments (important for migration reproducibility).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all PEIARS ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
