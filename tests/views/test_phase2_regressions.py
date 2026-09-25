"""Regression coverage for the Phase 2 review findings.

Each test pins one of the fixes: action redirect target, list-action branch,
disabled revision add, read-only release-state view, CSRF-safe show actions,
the transient-only baseline guard, and the lifecycle fields that must not be
editable.
"""

import pytest

from app.extensions import appbuilder, db
from app.models import BaselineMember, BusinessObject
from app.services import ServiceError
from app.views import (
    BusinessObjectModelView,
    RequirementModelView,
    RevisionModelView,
    RevisionReleaseStateModelView,
)


def _object(session, number):
    return session.query(BusinessObject).filter_by(object_number=number).one()


# ---------------------------------------------------------------------------
# H2 — redirect goes back to the referring page, not Home
# ---------------------------------------------------------------------------


def test_action_redirects_to_referring_list(db_session, admin_client):
    obj = _object(db_session, "REQ-0002")
    admin_client.get("/businessobjectmodelview/list/")

    response = admin_client.post(
        f"/businessobjectmodelview/action/create_revision/{obj.id}"
    )

    assert response.status_code == 302
    # Without update_redirect() this was "/" (Home).
    assert "businessobjectmodelview" in response.headers["Location"]


# ---------------------------------------------------------------------------
# M4 — the list-action (action_post) branch
# ---------------------------------------------------------------------------


def test_list_action_post_runs_the_list_branch(db_session, admin_client):
    obj = _object(db_session, "REQ-0002")
    before = {r.revision_id for r in obj.revisions}

    response = admin_client.post(
        "/businessobjectmodelview/action_post",
        data={"action": "create_revision", "rowid": str(obj.id)},
    )

    assert response.status_code == 302
    db_session.expire_all()
    after = {r.revision_id for r in db_session.get(BusinessObject, obj.id).revisions}
    assert after - before == {"B"}


# ---------------------------------------------------------------------------
# H3 — lifecycle bypass closed
# ---------------------------------------------------------------------------


def test_revision_add_route_is_disabled(admin_client):
    assert admin_client.get("/revisionmodelview/add").status_code == 403


def test_release_state_view_is_read_only(admin_client):
    assert (
        admin_client.get("/revisionreleasestatemodelview/add").status_code == 403
    )
    assert RevisionReleaseStateModelView.base_permissions == [
        "can_list",
        "can_show",
    ]


def test_show_actions_use_a_csrf_safe_post_form(db_session, admin_client):
    revision = _object(db_session, "REQ-0003").current_revision

    body = admin_client.get(
        f"/revisionmodelview/show/{revision.id}"
    ).get_data(as_text=True)

    assert 'method="POST"' in body
    assert "action/release_revision/" in body


# ---------------------------------------------------------------------------
# H1 — the baseline guard must not corrupt a persistent row
# ---------------------------------------------------------------------------


def test_pre_update_guard_does_not_corrupt_persistent_member(db_session):
    view = next(
        v
        for v in appbuilder.baseviews
        if v.__class__.__name__ == "BaselineMemberModelView"
    )
    member = db_session.query(BaselineMember).first()
    member.revision = _object(db_session, "REQ-0003").current_revision

    with pytest.raises(ServiceError):
        view.pre_update(member)

    # The guard must leave the persistent row intact (not detach/null the FK).
    assert member.revision is not None
    db_session.flush()  # would raise if the PK/FK had been blanked


# ---------------------------------------------------------------------------
# M2/M3 — lifecycle/identity fields are not editable
# ---------------------------------------------------------------------------


def test_lifecycle_and_identity_fields_are_not_editable():
    for view in (RevisionModelView, BusinessObjectModelView, RequirementModelView):
        assert "status" not in view.add_columns
        assert "status" not in view.edit_columns

    assert RevisionModelView.edit_columns == ["title", "description"]
    assert "current_revision" not in BusinessObjectModelView.add_columns
    assert "current_revision" not in BusinessObjectModelView.edit_columns
    assert "object_type" not in BusinessObjectModelView.edit_columns
    assert "object_type" not in RequirementModelView.add_columns
    assert "object_type" not in RequirementModelView.edit_columns


def test_requirement_pre_add_forces_object_type(db_session):
    view = next(
        v
        for v in appbuilder.baseviews
        if v.__class__.__name__ == "RequirementModelView"
    )
    item = BusinessObject(object_number="REQ-NEW", name="New requirement")

    view.pre_add(item)

    assert item.object_type.name == "Requirement"
