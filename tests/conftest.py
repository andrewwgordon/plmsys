"""Shared pytest fixtures for the PLMSys test suite.

The suite builds a single application against a temporary SQLite file and
creates the schema from metadata (``AUTO_CREATE_SCHEMA``), which is the
supported test-only alternative to running Alembic migrations.
"""

import pytest

from app import create_app
from app.extensions import appbuilder


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("plmsys") / "test.db"
    application = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "AUTO_CREATE_SCHEMA": True,
            "AUTO_SEED": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + db_path.as_posix(),
        }
    )
    yield application


@pytest.fixture(scope="session")
def client(app):
    """Anonymous test client."""
    return app.test_client()


def _login(application, username, password):
    test_client = application.test_client()
    response = test_client.post(
        "/login/",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return test_client


@pytest.fixture(scope="session")
def admin_client(app):
    """Logged-in administrator test client."""
    with app.app_context():
        sm = appbuilder.sm
        if not sm.find_user("admin"):
            sm.add_user(
                "admin",
                "Ada",
                "Admin",
                "admin@example.com",
                sm.find_role("Admin"),
                "password",
            )
    return _login(app, "admin", "password")


@pytest.fixture(scope="session")
def viewer_client(app):
    """Logged-in non-administrator test client (Public role)."""
    with app.app_context():
        sm = appbuilder.sm
        if not sm.find_user("viewer"):
            sm.add_user(
                "viewer",
                "Vic",
                "Viewer",
                "viewer@example.com",
                sm.find_role("Public"),
                "password",
            )
    return _login(app, "viewer", "password")
