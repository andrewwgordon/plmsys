"""Custom Flask-AppBuilder security manager.

The schema is owned by Alembic (see ``migrations/``), so FAB must not create
tables. FAB's default ``SecurityManager.create_db`` does the opposite of what we
want: when ``FAB_CREATE_DB`` is true it creates the whole schema, and when it is
false it skips role/permission bootstrap entirely.

``PLMSecurityManager`` always runs the role/permission bootstrap (built-in
``Admin``/``Public`` roles and permission view menus) but never touches the
schema — it calls the base implementation that only manages security data.

Security models are imported here so they are present in the shared SQLAlchemy
metadata for Alembic autogeneration.
"""

from flask_appbuilder.security.manager import BaseSecurityManager
from flask_appbuilder.security.sqla import models as security_models  # noqa: F401
from flask_appbuilder.security.sqla.manager import SecurityManager


class PLMSecurityManager(SecurityManager):
    """Security manager that leaves schema creation to Alembic."""

    def create_db(self) -> None:
        """Bootstrap roles and permissions without creating tables."""
        BaseSecurityManager.create_db(self)
