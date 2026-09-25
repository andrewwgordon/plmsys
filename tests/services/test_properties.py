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
        "tags",
        PropertyDataType.STRING,
        multi_value=True,
    )

    properties.set_property(revision, definition, "one", sequence_no=1, session=session)
    properties.set_property(revision, definition, "two", sequence_no=2, session=session)

    assert properties.get_properties(revision)["tags"] == ["one", "two"]


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
