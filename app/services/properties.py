"""Metadata-driven property service.

Property *definitions* describe typed attributes on an object type; property
*values* store the data against a revision. This module owns the coercion
between Python values and the four typed columns on
:class:`~app.models.PropertyValue`, plus mandatory/multi-value enforcement
(``docs/plan.md`` §7: "always coerce via PropertyDataType").

Definitions are matched on the **exact** ``object_type_id``: ``ObjectType``
parent types are not traversed (documented behaviour, not an oversight).
"""

from datetime import date, datetime
from enum import Enum

from ..extensions import db
from ..models import PropertyDataType, PropertyDefinition, PropertyValue
from . import ServiceError

# Maps a data type to its backing column.
_COLUMNS = {
    PropertyDataType.STRING: "string_value",
    PropertyDataType.INTEGER: "integer_value",
    PropertyDataType.FLOAT: "float_value",
    PropertyDataType.DATE: "date_value",
}

# Column read order used when projecting a stored value back to Python.
_VALUE_COLUMNS = ("string_value", "integer_value", "float_value", "date_value")


def _session(session):
    return session if session is not None else db.session


def data_type_of(definition) -> PropertyDataType:
    """Return ``definition.data_type`` as the enum, tolerating raw strings."""
    value = definition.data_type
    if isinstance(value, PropertyDataType):
        return value
    if isinstance(value, Enum):
        return PropertyDataType(value.value)
    return PropertyDataType(value)


def get_definition(object_type, name: str, *, session=None):
    """Return the definition ``name`` on ``object_type``, or ``None``."""
    return (
        _session(session)
        .query(PropertyDefinition)
        .filter_by(object_type_id=object_type.id, name=name)
        .one_or_none()
    )


def coerce_value(definition, value):
    """Coerce ``value`` to the Python type implied by ``definition``.

    ``None``/empty means "no value" and returns ``None``. Invalid input raises
    :class:`ServiceError`.
    """
    if value is None or value == "":
        return None

    data_type = data_type_of(definition)
    label = definition.name

    if data_type == PropertyDataType.STRING:
        return str(value)
    if data_type == PropertyDataType.INTEGER:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ServiceError(f"Property {label!r} expects an integer") from exc
    if data_type == PropertyDataType.FLOAT:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ServiceError(f"Property {label!r} expects a number") from exc
    if data_type == PropertyDataType.DATE:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ServiceError(
                f"Property {label!r} expects an ISO date (YYYY-MM-DD)"
            ) from exc
    raise ServiceError(f"Unsupported data type for {label!r}: {data_type!r}")


def read_value(property_value):
    """Project a stored :class:`PropertyValue` back to a Python value."""
    for column in _VALUE_COLUMNS:
        value = getattr(property_value, column)
        if value is not None:
            return value
    return None


def _has_other_value(revision, definition, sequence_no) -> bool:
    """True when the revision holds another non-null value for the definition."""
    return any(
        pv.property_definition_id == definition.id
        and pv.sequence_no != sequence_no
        and read_value(pv) is not None
        for pv in revision.property_values
    )


def set_property(
    revision,
    definition,
    value,
    sequence_no: int = 1,
    *,
    session=None,
):
    """Create/update a typed property value (upsert).

    Non-multi-valued definitions are always stored at sequence 1. An empty
    value clears the property; a mandatory property cannot be cleared.
    """
    session = _session(session)

    if (
        revision.business_object is not None
        and definition.object_type_id
        != revision.business_object.object_type_id
    ):
        raise ServiceError(
            f"Property {definition.name!r} does not apply to this object type"
        )

    if not definition.multi_value:
        sequence_no = 1
    elif sequence_no < 1:
        raise ServiceError("sequence_no must be >= 1")

    coerced = coerce_value(definition, value)
    if (
        coerced is None
        and definition.mandatory
        and not _has_other_value(revision, definition, sequence_no)
    ):
        raise ServiceError(f"Property {definition.name!r} is mandatory")

    property_value = (
        session.query(PropertyValue)
        .filter_by(
            revision_id=revision.id,
            property_definition_id=definition.id,
            sequence_no=sequence_no,
        )
        .one_or_none()
    )
    if property_value is None:
        if coerced is None:
            return None
        property_value = PropertyValue(
            revision=revision,
            property_definition=definition,
            sequence_no=sequence_no,
        )
        session.add(property_value)

    for column in _VALUE_COLUMNS:
        setattr(property_value, column, None)
    if coerced is not None:
        setattr(property_value, _COLUMNS[data_type_of(definition)], coerced)

    session.flush()
    return property_value


def delete_property(revision, definition, sequence_no: int = 1, *, session=None) -> bool:
    """Delete one stored value. Returns ``True`` when a row was removed.

    Deleting the last non-null value of a mandatory definition is rejected.
    """
    session = _session(session)
    property_value = (
        session.query(PropertyValue)
        .filter_by(
            revision_id=revision.id,
            property_definition_id=definition.id,
            sequence_no=sequence_no,
        )
        .one_or_none()
    )
    if property_value is None:
        return False
    if (
        definition.mandatory
        and read_value(property_value) is not None
        and not _has_other_value(revision, definition, sequence_no)
    ):
        raise ServiceError(f"Property {definition.name!r} is mandatory")
    if property_value in revision.property_values:
        # delete-orphan: removing from the parent schedules the DELETE and keeps
        # the in-memory collection consistent for subsequent reads.
        revision.property_values.remove(property_value)
    else:
        session.delete(property_value)
    session.flush()
    return True


def clear_properties(revision, definition, *, session=None) -> int:
    """Delete every value for a definition. Rejects clearing a mandatory one."""
    session = _session(session)
    values = [
        pv
        for pv in revision.property_values
        if pv.property_definition_id == definition.id
    ]
    if definition.mandatory and any(read_value(pv) is not None for pv in values):
        raise ServiceError(f"Property {definition.name!r} is mandatory")
    for property_value in values:
        if property_value in revision.property_values:
            revision.property_values.remove(property_value)
        else:
            session.delete(property_value)
    session.flush()
    return len(values)


def get_properties(revision) -> dict:
    """Return a typed ``{name: value}`` mapping for a revision.

    Multi-valued definitions map to a list of values, ordered by sequence.
    """
    result: dict = {}
    for property_value in sorted(
        revision.property_values, key=lambda pv: (pv.property_definition_id, pv.sequence_no)
    ):
        name = property_value.property_definition.name
        value = read_value(property_value)
        if property_value.property_definition.multi_value:
            result.setdefault(name, []).append(value)
        else:
            result[name] = value
    return result


def matrix(revisions, definitions) -> list:
    """Return ``[{"revision": rev, "cells": [cell, ...]}, ...]``.

    Cells are typed values; multi-valued definitions yield a list.
    """
    rows = []
    for revision in revisions:
        values = get_properties(revision)
        rows.append(
            {
                "revision": revision,
                "cells": [values.get(definition.name) for definition in definitions],
            }
        )
    return rows


def copy_properties(source, target, *, overwrite: bool = True, session=None):
    """Copy every value from ``source`` to ``target`` revision.

    Returns the number of values copied. When ``overwrite`` is false, existing
    target values at the same ``(definition, sequence_no)`` are left alone.
    """
    session = _session(session)
    existing = {
        (pv.property_definition_id, pv.sequence_no): pv
        for pv in target.property_values
    }

    copied = 0
    for source_value in source.property_values:
        key = (source_value.property_definition_id, source_value.sequence_no)
        target_value = existing.get(key)
        if target_value is not None and not overwrite:
            continue
        if target_value is None:
            target_value = PropertyValue(
                revision=target,
                property_definition=source_value.property_definition,
                sequence_no=source_value.sequence_no,
            )
            session.add(target_value)
            existing[key] = target_value
        for column in _VALUE_COLUMNS:
            setattr(target_value, column, getattr(source_value, column))
        copied += 1

    session.flush()
    return copied


def validate_required(revision, object_type=None) -> list:
    """Return the names of mandatory definitions that have no value."""
    if object_type is None:
        object_type = revision.business_object.object_type
    present = {
        pv.property_definition_id
        for pv in revision.property_values
        if read_value(pv) is not None
    }
    return [
        definition.name
        for definition in object_type.property_definitions
        if definition.mandatory and definition.id not in present
    ]


__all__ = [
    "clear_properties",
    "coerce_value",
    "copy_properties",
    "data_type_of",
    "delete_property",
    "get_definition",
    "get_properties",
    "matrix",
    "read_value",
    "set_property",
    "validate_required",
]
