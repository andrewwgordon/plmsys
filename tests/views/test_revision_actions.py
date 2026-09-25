"""Phase 2 revision lifecycle actions (show-route FAB actions)."""

from app.models import BusinessObject, Revision
from app.services import lifecycle


def _object(session, number):
    return session.query(BusinessObject).filter_by(object_number=number).one()


def _current_revision(session, number):
    return _object(session, number).current_revision


# ---------------------------------------------------------------------------
# Create revision
# ---------------------------------------------------------------------------


def test_create_revision_action(db_session, admin_client):
    obj = _object(db_session, "REQ-0002")
    obj_id = obj.id
    before = {revision.revision_id for revision in obj.revisions}

    response = admin_client.post(
        f"/businessobjectmodelview/action/create_revision/{obj_id}",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Created revision" in response.data
    db_session.expire_all()
    obj = db_session.get(BusinessObject, obj_id)
    assert {r.revision_id for r in obj.revisions} - before == {"B"}
    assert obj.current_revision.revision_id == "B"
    # The new revision is Draft and carries copied properties.
    assert obj.current_revision.status == lifecycle.DRAFT


def test_create_revision_action_via_requirements_view(db_session, admin_client):
    obj = _object(db_session, "REQ-0003")
    obj_id = obj.id

    response = admin_client.post(
        f"/requirementmodelview/action/create_revision/{obj_id}"
    )

    assert response.status_code == 302
    db_session.expire_all()
    assert db_session.get(BusinessObject, obj_id).current_revision.revision_id == "B"


# ---------------------------------------------------------------------------
# Set current revision
# ---------------------------------------------------------------------------


def test_set_current_revision_action(db_session, admin_client):
    obj = _object(db_session, "PART-1001")
    target = obj.revisions[0]  # A; current is B
    assert obj.current_revision.revision_id == "B"

    response = admin_client.post(
        f"/revisionmodelview/action/set_current_revision/{target.id}",
        follow_redirects=True,
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(BusinessObject, obj.id).current_revision_id == target.id


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


def test_lifecycle_happy_path(db_session, admin_client):
    revision = _current_revision(db_session, "REQ-0004")
    revision_id = revision.id

    for action_name in ("submit_for_review", "approve_revision", "release_revision"):
        response = admin_client.post(
            f"/revisionmodelview/action/{action_name}/{revision_id}"
        )
        assert response.status_code == 302

    db_session.expire_all()
    assert (
        lifecycle.current_state_name(db_session.get(Revision, revision_id))
        == lifecycle.RELEASED
    )


def test_release_rejects_draft_and_flashes(db_session, admin_client):
    revision = _current_revision(db_session, "REQ-0003")  # Draft
    revision_id = revision.id

    response = admin_client.post(
        f"/revisionmodelview/action/release_revision/{revision_id}",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Cannot move" in response.data
    db_session.expire_all()
    assert (
        lifecycle.current_state_name(db_session.get(Revision, revision_id))
        == lifecycle.DRAFT
    )


def test_obsolete_action(db_session, admin_client):
    revision = _current_revision(db_session, "ARCH-300")  # Draft
    revision_id = revision.id

    response = admin_client.post(
        f"/revisionmodelview/action/obsolete_revision/{revision_id}"
    )

    assert response.status_code == 302
    db_session.expire_all()
    assert (
        lifecycle.current_state_name(db_session.get(Revision, revision_id))
        == lifecycle.OBSOLETE
    )


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_viewer_cannot_create_revision(db_session, viewer_client):
    obj = _object(db_session, "REQ-0002")
    obj_id = obj.id
    before = len(obj.revisions)

    viewer_client.post(
        f"/businessobjectmodelview/action/create_revision/{obj_id}",
        follow_redirects=True,
    )

    db_session.expire_all()
    assert len(db_session.get(BusinessObject, obj_id).revisions) == before
