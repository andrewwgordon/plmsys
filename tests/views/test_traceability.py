"""Phase 4 traceability: relation forms, relations section and matrix."""

from app.models import BusinessObject, ObjectType, Relationship
from app.services import properties, revisions
from app.views import RelationshipModelView


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
# Relations section
# ---------------------------------------------------------------------------


def test_relations_section_groups_outbound_and_inbound(db_session, admin_client):
    revision = _revision(db_session, "REQ-0001")

    body = admin_client.get(
        f"/revision/{revision.id}/relations"
    ).get_data(as_text=True)

    assert "DEFINING" in body
    assert "REQ-0002" in body            # outbound DEFINING
    assert "FUNC-200" in body            # outbound SATISFIED_BY
    assert "Outgoing" in body
    assert "Incoming" in body


# ---------------------------------------------------------------------------
# Relation form
# ---------------------------------------------------------------------------


def test_add_relation_creates_link(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")
    target_id = _object_id(db_session, "SWC-400")
    before = db_session.query(Relationship).count()

    response = admin_client.post(
        f"/relation/{revision.id}/",
        data={"relationship_type": "ALLOCATED_TO", "target": str(target_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Relationship created" in response.data
    db_session.expire_all()
    assert db_session.query(Relationship).count() == before + 1


def test_add_relation_duplicate_flashes(db_session, admin_client):
    # REQ-0001 --VERIFIED_BY--> TEST-100 already exists in the seed.
    revision = _revision(db_session, "REQ-0001")
    target_id = _object_id(db_session, "TEST-100")

    response = admin_client.post(
        f"/relation/{revision.id}/",
        data={"relationship_type": "VERIFIED_BY", "target": str(target_id)},
        follow_redirects=True,
    )

    assert b"Duplicate" in response.data


def test_derive_requirement_creates_object_and_link(db_session, admin_client):
    source = _revision(db_session, "REQ-0001")

    response = admin_client.post(
        f"/relation/{source.id}/derive",
        data={
            "object_number": "REQ-0900",
            "name": "Derived Range Requirement",
            "description": "Derived from REQ-0001.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"created and derived" in response.data

    db_session.expire_all()
    new_object = (
        db_session.query(BusinessObject)
        .filter_by(object_number="REQ-0900")
        .one()
    )
    assert new_object.current_revision is not None
    link = (
        db_session.query(Relationship)
        .filter_by(secondary_revision_id=new_object.current_revision_id)
        .one()
    )
    assert link.primary_revision_id == source.id
    assert link.relationship_type.name == "DEFINING"


def test_derive_rejects_duplicate_object_number(db_session, admin_client):
    source = _revision(db_session, "REQ-0001")

    response = admin_client.post(
        f"/relation/{source.id}/derive",
        data={"object_number": "REQ-0002", "name": "Clash"},
        follow_redirects=True,
    )

    assert b"already exists" in response.data


def test_derive_copies_requirement_properties(db_session, admin_client):
    source = _revision(db_session, "REQ-0001")
    source_text = properties.get_properties(source)["req_text"]

    response = admin_client.post(
        f"/relation/{source.id}/derive",
        data={
            "object_number": "REQ-0901",
            "name": "Derived Copy",
            "copy_properties": "y",
        },
        follow_redirects=True,
    )

    assert b"created and derived" in response.data
    db_session.expire_all()
    new_object = (
        db_session.query(BusinessObject).filter_by(object_number="REQ-0901").one()
    )
    assert properties.get_properties(new_object.current_revision)["req_text"] == source_text


def test_derive_rejects_non_requirement_source(db_session, admin_client):
    part_revision = _revision(db_session, "PART-1000")

    assert admin_client.get(f"/relation/{part_revision.id}/derive").status_code == 404
    assert (
        admin_client.post(
            f"/relation/{part_revision.id}/derive",
            data={"object_number": "REQ-X", "name": "X"},
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Traceability matrix
# ---------------------------------------------------------------------------


def test_matrix_renders_requirements(db_session, admin_client):
    response = admin_client.get("/traceability/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "REQ-0001" in body
    assert "DEFINING" in body
    assert "VERIFIED_BY" in body


def test_matrix_highlights_uncovered_requirement(db_session, admin_client):
    requirement_type = (
        db_session.query(ObjectType).filter_by(name="Requirement").one()
    )
    business_object = BusinessObject(
        object_type=requirement_type, object_number="REQ-GAP", name="Uncovered"
    )
    db_session.add(business_object)
    db_session.flush()
    revisions.create_revision(business_object, session=db_session)

    body = admin_client.get("/traceability/").get_data(as_text=True)

    assert "REQ-GAP" in body
    assert '<tr class="danger">' in body   # coverage-gap row
    assert '<tr class="">' in body         # covered rows remain unmarked


def test_add_relation_rejects_wrong_target_type(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")
    part_id = _object_id(db_session, "PART-1000")

    response = admin_client.post(
        f"/relation/{revision.id}/",
        data={"relationship_type": "VERIFIED_BY", "target": str(part_id)},
        follow_redirects=True,
    )

    assert b"cannot target" in response.data
    db_session.expire_all()
    assert (
        db_session.query(Relationship)
        .filter_by(secondary_revision_id=_revision(db_session, "PART-1000").id)
        .count()
        == 0
    )


def test_add_relation_handles_integrity_error(monkeypatch, db_session, admin_client):
    from sqlalchemy.exc import IntegrityError

    from app.ui import traceability

    def _boom(*args, **kwargs):
        raise IntegrityError("stmt", {}, Exception("duplicate"))

    monkeypatch.setattr(traceability.relationships, "create_relationship", _boom)

    revision = _revision(db_session, "REQ-0003")
    target_id = _object_id(db_session, "SWC-400")
    response = admin_client.post(
        f"/relation/{revision.id}/",
        data={"relationship_type": "ALLOCATED_TO", "target": str(target_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"conflicts with existing data" in response.data


# ---------------------------------------------------------------------------
# Raw relationship editing closed
# ---------------------------------------------------------------------------


def test_relationship_view_is_read_only(admin_client):
    assert admin_client.get("/relationshipmodelview/add").status_code == 403
    assert RelationshipModelView.base_permissions == ["can_list", "can_show"]


# ---------------------------------------------------------------------------
# Revision actions
# ---------------------------------------------------------------------------


def test_relation_actions_redirect(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    expected = {
        "view_relations": f"/revision/{revision.id}/relations",
        "add_relation": f"/relation/{revision.id}/",
        "derive_requirement": f"/relation/{revision.id}/derive",
    }
    for action_name, path in expected.items():
        response = admin_client.post(
            f"/revisionmodelview/action/{action_name}/{revision.id}"
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith(path)


def test_traceability_views_deny_viewer(db_session, viewer_client):
    revision = _revision(db_session, "REQ-0003")

    assert viewer_client.get(f"/relation/{revision.id}/").status_code == 403
    assert viewer_client.get(f"/relation/{revision.id}/derive").status_code == 403
    assert viewer_client.get(f"/revision/{revision.id}/relations").status_code == 403
    assert viewer_client.get("/traceability/").status_code == 403
