"""Application factory for PLMSys.

Schema creation is delegated to Alembic (see ``migrations/``). Setting
``AUTO_CREATE_SCHEMA`` (used by the test suite) creates tables from metadata
instead, so the app can be built without running migrations.
"""

from flask import Flask
from flask_appbuilder import Model

from . import models  # noqa: F401  (register domain models with the metadata)
from . import security  # noqa: F401  (register security models + manager)
from .extensions import appbuilder, db, migrate
from .seed import seed_data


def _schema_ready(engine) -> bool:
    """Return True when the migrated schema (domain + security) is present."""
    from sqlalchemy import inspect

    try:
        tables = set(inspect(engine).get_table_names())
    except Exception:
        return False
    return {"ab_user", "business_object"}.issubset(tables)


def create_app(config_overrides=None) -> Flask:
    # App static assets (the shared stylesheet, uploads, favicons…) live under
    # app/templates/static and are served at /static/. FAB serves its own
    # assets from its separate /appbuilder blueprint, so this does not affect
    # the framework. See docs/ui_plan.md UI-0b.
    app = Flask(__name__, static_folder="templates/static")
    app.config.from_object("config")
    if config_overrides:
        app.config.update(config_overrides)

    with app.app_context():
        db.init_app(app)
        migrate.init_app(app, db, compare_type=True, render_as_batch=True)

        if app.config.get("AUTO_CREATE_SCHEMA"):
            Model.metadata.create_all(db.engine)

        # FAB (and the security bootstrap) needs the schema to exist. During
        # `flask db upgrade` on a fresh database it does not yet, so the app is
        # built in a minimal state that Alembic can import.
        if _schema_ready(db.engine):
            from .views import register_views

            appbuilder.init_app(app, db.session)
            register_views(appbuilder)
            if app.config.get("AUTO_SEED", True):
                seed_data(db.session)

    return app


__all__ = ["create_app"]
