"""Phase 6 configuration pages: baseline create/detail/compare and context."""

from app.models import (
    Baseline,
    ConfigurationContext,
    RevisionRule,
    RevisionRuleType,
)
from app.views import BaselineMemberModelView, BaselineModelView


def _context(session, name):
    return session.query(ConfigurationContext).filter_by(name=name).one()


# ---------------------------------------------------------------------------
# Read-only model views
# ---------------------------------------------------------------------------


def test_baseline_model_views_are_read_only(admin_client):
    assert admin_client.get("/baselinemodelview/add").status_code == 403
    assert admin_client.get("/baselinemembermodelview/add").status_code == 403
    assert BaselineModelView.base_permissions == ["can_list", "can_show"]
    assert BaselineMemberModelView.base_permissions == ["can_list", "can_show"]


# ---------------------------------------------------------------------------
# Create baseline
# ---------------------------------------------------------------------------


def test_create_baseline_view(db_session, admin_client):
    context = _context(db_session, "EV Program - Released")
    before = db_session.query(Baseline).count()

    response = admin_client.post(
        f"/configuration/{context.id}/baseline/new",
        data={"name": "Phase 6 Baseline"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Baseline created" in response.data
    db_session.expire_all()
    assert db_session.query(Baseline).count() == before + 1


def test_create_baseline_view_stores_description(db_session, admin_client):
    context = _context(db_session, "EV Program - Released")

    response = admin_client.post(
        f"/configuration/{context.id}/baseline/new",
        data={
            "name": "Described Baseline",
            "description": "Captured for the audit trail.",
        },
        follow_redirects=True,
    )

    assert b"Baseline created" in response.data
    db_session.expire_all()
    baseline = (
        db_session.query(Baseline)
        .filter_by(name="Described Baseline")
        .one()
    )
    assert baseline.description == "Captured for the audit trail."


def test_create_baseline_duplicate_name_flashes(db_session, admin_client):
    context = _context(db_session, "EV Program - Released")

    response = admin_client.post(
        f"/configuration/{context.id}/baseline/new",
        data={"name": "EV Program Baseline v1.0"},  # seeded name
        follow_redirects=True,
    )

    assert b"already exists" in response.data


def test_create_baseline_working_context_flashes(db_session, admin_client):
    context = _context(db_session, "EV Program - Working")

    response = admin_client.post(
        f"/configuration/{context.id}/baseline/new",
        data={"name": "Working Baseline"},
        follow_redirects=True,
    )

    assert b"Released" in response.data


# ---------------------------------------------------------------------------
# Detail & compare
# ---------------------------------------------------------------------------


def test_baseline_detail_groups_by_object_type(db_session, admin_client):
    baseline = db_session.query(Baseline).first()

    body = admin_client.get(f"/baseline/{baseline.id}/").get_data(as_text=True)

    assert baseline.name in body
    assert "Requirement" in body   # grouped by object type
    assert "Part" in body
    # Members are Released, so the shared badge renders as a success label.
    assert "label-success" in body


def test_context_view_create_baseline_action(db_session, admin_client):
    context = _context(db_session, "EV Program - Released")

    response = admin_client.post(
        f"/configurationcontextmodelview/action/create_baseline/{context.id}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert f"/configuration/{context.id}/baseline/new" in response.headers[
        "Location"
    ]


def test_baseline_compare_page(db_session, admin_client):
    baseline = db_session.query(Baseline).first()

    response = admin_client.get(
        f"/baseline/compare?a={baseline.id}&b={baseline.id}"
    )

    assert response.status_code == 200
    assert b"Compare Baselines" in response.data


# ---------------------------------------------------------------------------
# Context selector
# ---------------------------------------------------------------------------


def test_set_context(db_session, admin_client):
    context = _context(db_session, "EV Program - Released")

    response = admin_client.post(
        "/context/set", data={"context_id": context.id, "next": "/"}
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_set_context_rejects_protocol_relative_redirect(db_session, admin_client):
    context = _context(db_session, "EV Program - Released")

    response = admin_client.post(
        "/context/set",
        data={"context_id": context.id, "next": "//evil.example.com"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_viewer_can_set_context(db_session, viewer_client):
    context = _context(db_session, "EV Program - Released")

    response = viewer_client.post(
        "/context/set", data={"context_id": context.id, "next": "/"}
    )

    assert response.status_code == 302


def test_revision_rule_view_exposes_and_sets_rule_type(db_session, admin_client):
    response = admin_client.get("/revisionrulemodelview/add")
    assert response.status_code == 200

    response = admin_client.post(
        "/revisionrulemodelview/add",
        data={
            "name": "Released Only",
            "rule_type": "LATEST_RELEASED",
            "description": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    db_session.expire_all()
    rule = db_session.query(RevisionRule).filter_by(name="Released Only").one()
    assert rule.rule_type == RevisionRuleType.LATEST_RELEASED


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_configuration_views_deny_viewer(db_session, viewer_client):
    baseline = db_session.query(Baseline).first()
    context = _context(db_session, "EV Program - Released")

    assert (
        viewer_client.get(
            f"/configuration/{context.id}/baseline/new"
        ).status_code
        == 403
    )
    assert viewer_client.get(f"/baseline/{baseline.id}/").status_code == 403
    assert viewer_client.get("/baseline/compare").status_code == 403


def test_anonymous_cannot_set_context(client):
    assert client.post("/context/set", data={"context_id": "1"}).status_code == 401
