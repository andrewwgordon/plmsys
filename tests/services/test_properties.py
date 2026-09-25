"""Typed property service: the PropertyDataType coercion matrix and rules."""

from datetime import date

import pytest

from app.models import BusinessObject, PropertyDataType, PropertyDefinition
from app.services import ServiceError, properties, revisions


def _requirement(session, number="REQ-0001"):
    return (
        session.query(BusinessObject)
        .filter_by(object_number=number)
        .one()
    )


def _definition(session, object_type, name, data_type, **kwargs):
    definition = PropertyDefinition(
        name=name, object_type=object_type, data_type=data_type, **kwargs
    )
    session.add(definition)
    session.flush()
    return definition


@pytest.mark.parametrize(
    "data_type, raw, expected, column",
    [
        (PropertyDataType.STRING, "hello", "hello", "string_value"),
        (PropertyDataType.INTEGER, "42", 42, "integer_value"),
        (PropertyDataType.FLOAT, "3.5", 3.5, "float_value"),
        (PropertyDataType.DATE, "2026-09-24", date(2026, 9, 24), "date_value"),
    ],
)
def test_coercion_matrix(session, data_type, raw, expected, column):
    """Every data type coerces to its Python type and its own column."""
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, f"matrix_{data_type.name.lower()}", data_type
    )

    value = properties.set_property(revision, definition, raw, session=session)

    assert getattr(value, column) == expected
    # No other typed column is populated.
    for other in ("string_value", "integer_value", "float_value", "date_value"):
        if other != column:
            assert getattr(value, other) is None
    assert properties.read_value(value) == expected


def test_coercion_accepts_native_and_iso_values(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    integer = _definition(
        session, requirement.object_type, "native_int", PropertyDataType.INTEGER
    )
    date_definition = _definition(
        session, requirement.object_type, "native_date", PropertyDataType.DATE
    )

    assert properties.set_property(revision, integer, 7, session=session).integer_value == 7
    assert (
        properties.set_property(
            revision, date_definition, date(2020, 1, 2), session=session
        ).date_value
        == date(2020, 1, 2)
    )


@pytest.mark.parametrize("raw", ["not-a-number", "1.5x"])
def test_invalid_coercion_raises(session, raw):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "bad_int", PropertyDataType.INTEGER
    )

    with pytest.raises(ServiceError):
        properties.set_property(revision, definition, raw, session=session)


def test_mandatory_cannot_be_cleared(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session,
        requirement.object_type,
        "must_have",
        PropertyDataType.STRING,
        mandatory=True,
    )

    with pytest.raises(ServiceError):
        properties.set_property(revision, definition, None, session=session)


def test_multi_value_uses_sequences(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session,
        requirement.object_type,
        "multi_tags",
        PropertyDataType.STRING,
        multi_value=True,
    )

    properties.set_property(revision, definition, "one", sequence_no=1, session=session)
    properties.set_property(revision, definition, "two", sequence_no=2, session=session)

    assert properties.get_properties(revision)["multi_tags"] == ["one", "two"]


def test_single_value_always_uses_sequence_one(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "single", PropertyDataType.STRING
    )

    properties.set_property(revision, definition, "old", sequence_no=5, session=session)

    stored = [pv for pv in revision.property_values if pv.property_definition_id == definition.id]
    assert len(stored) == 1
    assert stored[0].sequence_no == 1


def test_set_property_is_an_upsert(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "upserted", PropertyDataType.STRING
    )

    properties.set_property(revision, definition, "first", session=session)
    properties.set_property(revision, definition, "second", session=session)

    stored = [pv for pv in revision.property_values if pv.property_definition_id == definition.id]
    assert len(stored) == 1
    assert stored[0].string_value == "second"


def test_definition_must_match_object_type(session):
    requirement = _requirement(session)
    part = _requirement(session, "PART-1000")
    definition = _definition(
        session, part.object_type, "part_only", PropertyDataType.STRING
    )

    with pytest.raises(ServiceError):
        properties.set_property(
            requirement.current_revision, definition, "nope", session=session
        )


def test_copy_properties(session):
    requirement = _requirement(session)
    source = requirement.revisions[0]
    target = requirement.revisions[1]

    copied = properties.copy_properties(source, target, session=session)

    assert copied > 0
    assert properties.get_properties(target)["req_text"] == properties.get_properties(source)["req_text"]


def test_validate_required_reports_missing(session):
    requirement = _requirement(session, "REQ-0003")
    # A branch that copies no properties has no req_text value.
    revision = revisions.create_revision(
        requirement, copy_properties=False, session=session
    )

    assert "req_text" in properties.validate_required(revision)


def test_delete_property_removes_row(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "deletable", PropertyDataType.STRING,
        multi_value=True,
    )
    properties.set_property(revision, definition, "a", sequence_no=1, session=session)
    properties.set_property(revision, definition, "b", sequence_no=2, session=session)

    assert properties.delete_property(revision, definition, 2, session=session)

    assert properties.get_properties(revision)["deletable"] == ["a"]


def test_delete_missing_property_returns_false(session):
    requirement = _requirement(session)
    definition = _definition(
        session, requirement.object_type, "absent", PropertyDataType.STRING
    )
    assert not properties.delete_property(
        requirement.current_revision, definition, session=session
    )


def test_delete_last_mandatory_value_rejected(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "must_keep", PropertyDataType.STRING,
        mandatory=True,
    )
    properties.set_property(revision, definition, "x", session=session)

    with pytest.raises(ServiceError):
        properties.delete_property(revision, definition, 1, session=session)


def test_mandatory_multi_value_per_definition(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "multi_mandatory",
        PropertyDataType.STRING, mandatory=True, multi_value=True,
    )
    properties.set_property(revision, definition, "a", sequence_no=1, session=session)
    properties.set_property(revision, definition, "b", sequence_no=2, session=session)

    # Clearing one sequence is allowed while another value remains.
    assert properties.delete_property(revision, definition, 2, session=session)
    assert properties.get_properties(revision)["multi_mandatory"] == ["a"]

    with pytest.raises(ServiceError):
        properties.delete_property(revision, definition, 1, session=session)


def test_clear_properties(session):
    requirement = _requirement(session)
    revision = requirement.current_revision
    definition = _definition(
        session, requirement.object_type, "clearable", PropertyDataType.STRING,
        multi_value=True,
    )
    properties.set_property(revision, definition, "a", sequence_no=1, session=session)
    properties.set_property(revision, definition, "b", sequence_no=2, session=session)

    assert properties.clear_properties(revision, definition, session=session) == 2
    assert "clearable" not in properties.get_properties(revision)


def test_clear_mandatory_properties_rejected(session):
    requirement = _requirement(session)
    definition = _definition(
        session, requirement.object_type, "clear_me", PropertyDataType.STRING,
        mandatory=True,
    )
    properties.set_property(
        requirement.current_revision, definition, "x", session=session
    )

    with pytest.raises(ServiceError):
        properties.clear_properties(
            requirement.current_revision, definition, session=session
        )


def test_matrix_returns_typed_cells(session):
    requirement = _requirement(session, "REQ-0001")
    revision = requirement.current_revision
    priority = properties.get_definition(requirement.object_type, "priority", session=session)
    risk = properties.get_definition(requirement.object_type, "risk_score", session=session)

    rows = properties.matrix([revision], [priority, risk])

    assert rows[0]["revision"] is revision
    assert rows[0]["cells"] == ["High", 7]


def test_copy_properties_skips_cross_type_definitions(session):
    """A Part definition/value must not be copied onto a Requirement revision."""
    part = _requirement(session, "PART-1000")
    part_revision = part.current_revision
    part_definition = _definition(
        session, part.object_type, "part_weight", PropertyDataType.STRING
    )
    properties.set_property(
        part_revision, part_definition, "12kg", session=session
    )

    target = _requirement(session, "REQ-0003").current_revision
    copied = properties.copy_properties(part_revision, target, session=session)

    assert copied == 0
    assert "part_weight" not in properties.get_properties(target)
