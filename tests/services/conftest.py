"""Fixtures for the service-layer test suite.

The session-scoped ``app`` fixture (see ``tests/conftest.py``) is seeded once.
Each service test runs inside the app context and rolls back on teardown, so
tests may create rows freely without polluting one another.
"""

import pytest

from app.extensions import db


@pytest.fixture
def session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()
