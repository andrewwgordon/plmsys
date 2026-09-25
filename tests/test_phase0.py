"""Phase 0 acceptance tests: migration-first schema and security bootstrap."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect

from app import models  # noqa: F401
from app.extensions import appbuilder, db

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _flask_db_upgrade(env):
    return subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_shipped_config_is_migration_first():
    """The shipped configuration must not let FAB or create_all own the schema."""
    import config

    assert config.FAB_CREATE_DB is False
    assert config.AUTO_CREATE_SCHEMA is False
    assert config.FAB_SECURITY_MANAGER_CLASS == "app.security.PLMSecurityManager"


def test_schema_is_present(app):
    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())
    assert {
        "business_object",
        "revision",
        "property_value",
        "relationship",
        "baseline",
        "ab_user",
        "ab_role",
        "ab_permission",
    } <= tables


def test_security_roles_are_bootstrapped(app):
    with app.app_context():
        assert appbuilder.sm.find_role("Admin") is not None
        assert appbuilder.sm.find_role("Public") is not None


def test_alembic_migration_creates_schema(tmp_path):
    """`flask db upgrade` alone must produce the full schema."""
    db_file = tmp_path / "migrated.db"
    env = os.environ.copy()
    env["PLMSYS_DATABASE_URI"] = "sqlite:///" + db_file.as_posix()
    env["FLASK_APP"] = "run.py"

    result = _flask_db_upgrade(env)
    assert result.returncode == 0, result.stderr

    connection = sqlite3.connect(db_file)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        managed_file_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(managed_file)")
        }
    finally:
        connection.close()

    assert {
        "business_object",
        "revision",
        "property_value",
        "relationship",
        "baseline",
        "ab_user",
        "alembic_version",
    } <= tables
    assert {"file", "checksum"} <= managed_file_columns
    assert "storage_path" not in managed_file_columns


def test_alembic_upgrade_is_idempotent(tmp_path):
    db_file = tmp_path / "migrated_twice.db"
    env = os.environ.copy()
    env["PLMSYS_DATABASE_URI"] = "sqlite:///" + db_file.as_posix()
    env["FLASK_APP"] = "run.py"

    for _ in range(2):
        result = _flask_db_upgrade(env)
        assert result.returncode == 0, result.stderr
