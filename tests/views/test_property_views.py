"""Phase 3 property pages: dynamic form, matrix, validation and read-only rules."""

from datetime import date

from app.models import (
    BusinessObject,
    ObjectType,
    PropertyDataType,
    PropertyDefinition,
)
from app.services import properties
from app.views import PropertyValueModelView


def _revision(session, number):
    return (
        session.query(BusinessObject)
        .filter_by(object_number=number)
        .one()
        .current_revision
    )


def _requirement_type_id(session):
    return session.query(ObjectType).filter_by(name="Requirement").one().id


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def test_edit_properties_action_redirects_to_form(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    response = admin_client.post(
        f"/revisionmodelview/action/edit_properties/{revision.id}"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/revision/{revision.id}/properties"
    )


# ---------------------------------------------------------------------------
# Dynamic form
# ---------------------------------------------------------------------------


def test_property_form_renders_inputs_by_type(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    body = admin_client.get(
        f"/revision/{revision.id}/properties"
    ).get_data(as_text=True)

    assert 'name="prop_req_text"' in body       # string
    assert 'name="prop_risk_score"' in body     # integer
    assert 'name="prop_mass_kg"' in body        # float
    assert 'name="prop_due_date"' in body       # date
    assert 'name="prop_tags-0"' in body         # multi-value FieldList
    assert 'name="add_field"' in body           # add-value control


def test_property_form_saves_typed_and_multi_values(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    response = admin_client.post(
        f"/revision/{revision.id}/properties",
        data={
            "prop_req_text": "Cells shall use NMC 811 chemistry.",
            "prop_priority": "Medium",
            "prop_risk_score": "9",
            "prop_mass_kg": "3.25",
            "prop_due_date": "2027-06-30",
            "prop_tags-0": "thermal",
            "prop_tags-1": "chemistry",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Properties saved" in response.data

    db_session.expire_all()
    values = properties.get_properties(
        db_session.get(type(revision), revision.id)
    )
    assert values["risk_score"] == 9
    assert values["mass_kg"] == 3.25
    assert values["due_date"] == date(2027, 6, 30)
    assert values["tags"] == ["thermal", "chemistry"]


def test_property_form_flashes_invalid_input(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    response = admin_client.post(
        f"/revision/{revision.id}/properties",
        data={"prop_req_text": "ok", "prop_risk_score": "not-a-number"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"correct the errors" in response.data


def test_property_form_flashes_missing_mandatory(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    response = admin_client.post(
        f"/revision/{revision.id}/properties",
        data={},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"mandatory" in response.data.lower()


def test_property_form_add_value_extends_fieldlist(db_session, admin_client):
    revision = _revision(db_session, "REQ-0003")

    body = admin_client.post(
        f"/revision/{revision.id}/properties",
        data={"add_field": "prop_tags"},
    ).get_data(as_text=True)

    assert body.count('name="prop_tags-') >= 2


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------


def test_property_matrix_renders_definitions(db_session, admin_client):
    response = admin_client.get("/property-matrix/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "REQ-0003" in body
    assert ">tags<" in body
    assert ">risk_score<" in body


# ---------------------------------------------------------------------------
# Raw-value bypass closed
# ---------------------------------------------------------------------------


def test_property_value_view_is_read_only(admin_client):
    assert admin_client.get("/propertyvaluemodelview/add").status_code == 403
    assert PropertyValueModelView.base_permissions == ["can_list", "can_show"]


# ---------------------------------------------------------------------------
# Definition validation
# ---------------------------------------------------------------------------


def test_definition_rejects_bad_name(db_session, admin_client):
    type_id = _requirement_type_id(db_session)

    response = admin_client.post(
        "/propertydefinitionmodelview/add",
        data={"object_type": type_id, "name": "Bad Name", "data_type": "STRING"},
        follow_redirects=True,
    )

    assert b"must match" in response.data
    db_session.expire_all()
    assert (
        db_session.query(PropertyDefinition).filter_by(name="Bad Name").count()
        == 0
    )


def test_definition_rejects_reserved_wtforms_name(db_session, admin_client):
    type_id = _requirement_type_id(db_session)

    response = admin_client.post(
        "/propertydefinitionmodelview/add",
        data={"object_type": type_id, "name": "data", "data_type": "STRING"},
        follow_redirects=True,
    )

    assert b"reserved" in response.data


def test_definition_optional_booleans_are_creatable(db_session, admin_client):
    type_id = _requirement_type_id(db_session)

    response = admin_client.post(
        "/propertydefinitionmodelview/add",
        data={"object_type": type_id, "name": "new_optional", "data_type": "STRING"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    db_session.expire_all()
    created = (
        db_session.query(PropertyDefinition)
        .filter_by(name="new_optional")
        .one_or_none()
    )
    assert created is not None
    assert created.mandatory is False
    assert created.multi_value is False


def test_definition_data_type_locked_when_values_exist(db_session, admin_client):
    definition = (
        db_session.query(PropertyDefinition).filter_by(name="req_text").one()
    )

    response = admin_client.post(
        f"/propertydefinitionmodelview/edit/{definition.id}",
        data={
            "object_type": definition.object_type_id,
            "name": "req_text",
            "data_type": "INTEGER",
        },
        follow_redirects=True,
    )

    assert b"Cannot change" in response.data
    db_session.expire_all()
    assert (
        db_session.get(PropertyDefinition, definition.id).data_type
        == PropertyDataType.STRING
    )


def test_definition_data_type_change_allowed_without_values(
    db_session, admin_client
):
    definition = (
        db_session.query(PropertyDefinition).filter_by(name="risk").one()
    )

    admin_client.post(
        f"/propertydefinitionmodelview/edit/{definition.id}",
        data={
            "object_type": definition.object_type_id,
            "name": "risk",
            "data_type": "INTEGER",
        },
        follow_redirects=True,
    )

    db_session.expire_all()
    assert (
        db_session.get(PropertyDefinition, definition.id).data_type
        == PropertyDataType.INTEGER
    )
