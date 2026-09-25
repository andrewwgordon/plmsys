"""Fixtures for the FAB view/action tests.

The app is seeded once for the whole session. These tests exercise actions that
call ``db.session.commit()``; to keep them isolated we hold an app context open
and turn ``Session.commit`` into ``Session.flush`` so every change is rolled
back at teardown instead of leaking into the shared database.
"""

import pytest
from sqlalchemy.orm import Session

from app.extensions import db


@pytest.fixture
def db_session(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(Session, "commit", Session.flush)
        try:
            yield db.session
        finally:
            db.session.rollback()
