"""Phase 5 BOM pages: tree, add form, trace form, coverage and guards."""

from app.models import BOMOccurrence, BusinessObject, OccurrenceTrace
from app.views import BOMOccurrenceModelView, OccurrenceTraceModelView


def _revision(session, number):
    return (
        session.query(BusinessObject)
        .filter_by(object_number=number)
        .one()
        .current_revision
    )


def _object_id(session, number):
    return session.query(BusinessObject).filter_by(object_number=number).one().id


# ---------------------------------------------------------------------------
# Structure tree
# ---------------------------------------------------------------------------


def test_bom_tree_renders_structure(db_session, admin_client):
    module = _revision(db_session, "PART-1000")

    body = admin_client.get(f"/bom/{module.id}/").get_data(as_text=True)

    assert "PART-1001" in body
    assert "PART-1002" in body
    assert "PART-1003" in body           # third level
    assert "uncovered" in body           # the untraced interconnect-plate line
    assert "/bom-coverage/" in body


def test_bom_tree_rejects_non_part(db_session, admin_client):
    requirement = _revision(db_session, "REQ-0001")

    response = admin_client.get(f"/bom/{requirement.id}/")

    assert response.status_code == 302  # flashed + back to the revision


# ---------------------------------------------------------------------------
# Add occurrence
# ---------------------------------------------------------------------------


def test_add_occurrence_creates_line(db_session, admin_client):
    module = _revision(db_session, "PART-1000")
    cell_id = _object_id(db_session, "PART-1001")
    before = db_session.query(BOMOccurrence).count()

    response = admin_client.post(
        f"/bom/{module.id}/add",
        data={"child": str(cell_id), "find_number": "40", "quantity": "2"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"BOM line added" in response.data
    db_session.expire_all()
    assert db_session.query(BOMOccurrence).count() == before + 1


def test_add_occurrence_duplicate_find_flashes(db_session, admin_client):
    module = _revision(db_session, "PART-1000")
    cell_id = _object_id(db_session, "PART-1001")

    response = admin_client.post(
        f"/bom/{module.id}/add",
        data={"child": str(cell_id), "find_number": "10", "quantity": "1"},
        follow_redirects=True,
    )

    assert b"already exists" in response.data


# ---------------------------------------------------------------------------
# Occurrence trace
# ---------------------------------------------------------------------------


def test_link_requirement_creates_trace(db_session, admin_client):
    interconnect = _revision(db_session, "PART-1003")
    occurrence = (
        db_session.query(BOMOccurrence)
        .filter_by(parent_revision_id=interconnect.id, find_number="10")
        .one()
    )
    requirement_id = _object_id(db_session, "REQ-0003")
    before = db_session.query(OccurrenceTrace).count()

    response = admin_client.post(
        f"/bom/occurrence/{occurrence.id}/trace",
        data={"requirement": str(requirement_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"traced to the BOM line" in response.data
    db_session.expire_all()
    assert db_session.query(OccurrenceTrace).count() == before + 1


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------


def test_bom_coverage_reports_uncovered_line(db_session, admin_client):
    response = admin_client.get("/bom-coverage/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "PART-1003" in body            # parent of the untraced line
    assert "PART-1002" in body            # child of the untraced line


# ---------------------------------------------------------------------------
# Raw editing closed + actions
# ---------------------------------------------------------------------------


def test_bom_model_views_are_read_only(admin_client):
    assert admin_client.get("/bomoccurrencemodelview/add").status_code == 403
    assert admin_client.get("/occurrencetracemodelview/add").status_code == 403
    assert BOMOccurrenceModelView.base_permissions == ["can_list", "can_show"]
    assert OccurrenceTraceModelView.base_permissions == ["can_list", "can_show"]


def test_view_bom_action_redirects(db_session, admin_client):
    module = _revision(db_session, "PART-1000")

    response = admin_client.post(
        f"/revisionmodelview/action/view_bom/{module.id}"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/bom/{module.id}/")


def test_bom_views_deny_viewer(db_session, viewer_client):
    module = _revision(db_session, "PART-1000")

    assert viewer_client.get(f"/bom/{module.id}/").status_code == 403
    assert viewer_client.get(f"/bom/{module.id}/add").status_code == 403
    assert viewer_client.get("/bom-coverage/").status_code == 403
