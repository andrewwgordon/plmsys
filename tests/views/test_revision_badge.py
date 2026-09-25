"""The @renders release-state badge on RevisionModelView."""

from app.models import BusinessObject


def _released_revision(session):
    obj = session.query(BusinessObject).filter_by(object_number="REQ-0001").one()
    return obj.revisions[-1]  # B, seeded Released


def test_release_state_badge_renders_states(db_session, admin_client):
    body = admin_client.get("/revisionmodelview/list/").get_data(as_text=True)

    # Colour class plus the state text (never colour alone).
    assert "label-success" in body and "Released" in body
    assert "label-warning" in body and "Approved" in body


def test_release_state_badge_on_show(db_session, admin_client):
    revision = _released_revision(db_session)

    body = admin_client.get(
        f"/revisionmodelview/show/{revision.id}"
    ).get_data(as_text=True)

    assert "label-success" in body
    assert "Released" in body


def test_release_state_badge_uses_canonical_state(db_session):
    revision = _released_revision(db_session)
    html = str(revision.release_state_badge())
    assert "label-success" in html
    assert "Released" in html
