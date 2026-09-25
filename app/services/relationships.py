"""Relationship service: typed trace links and transitive traversal.

Relationships are directed edges ``primary --type--> secondary``. :func:`trace`
walks them breadth-first for traceability reports (``docs/plan.md`` Phase 1 and
Phase 4).
"""

from collections import deque

from ..extensions import db
from ..models import Relationship, RelationshipType
from . import ServiceError

_DIRECTIONS = ("out", "in", "both")


def _session(session):
    return session if session is not None else db.session


def get_type(session, name: str):
    relationship_type = (
        _session(session)
        .query(RelationshipType)
        .filter(RelationshipType.name == name)
        .one_or_none()
    )
    if relationship_type is None:
        raise ServiceError(f"Unknown relationship type: {name!r}")
    return relationship_type


def create_relationship(
    type_name: str,
    primary,
    secondary,
    *,
    allow_self: bool = False,
    session=None,
):
    """Create a typed link, guarding self-references and duplicates."""
    session = _session(session)
    if primary.id == secondary.id and not allow_self:
        raise ServiceError("A revision cannot be related to itself")

    relationship_type = get_type(session, type_name)
    duplicate = (
        session.query(Relationship)
        .filter_by(
            relationship_type_id=relationship_type.id,
            primary_revision_id=primary.id,
            secondary_revision_id=secondary.id,
        )
        .first()
    )
    if duplicate is not None:
        raise ServiceError(
            f"Duplicate relationship: {primary} --{type_name}--> {secondary}"
        )

    relationship = Relationship(
        relationship_type=relationship_type,
        primary_revision=primary,
        secondary_revision=secondary,
    )
    session.add(relationship)
    session.flush()
    return relationship


def _neighbours(revision, direction: str, type_names, session):
    query = session.query(Relationship)
    if direction == "out":
        query = query.filter(Relationship.primary_revision_id == revision.id)
    elif direction == "in":
        query = query.filter(Relationship.secondary_revision_id == revision.id)
    else:
        from sqlalchemy import or_

        query = query.filter(
            or_(
                Relationship.primary_revision_id == revision.id,
                Relationship.secondary_revision_id == revision.id,
            )
        )

    for relationship in query.all():
        if type_names and relationship.relationship_type.name not in type_names:
            continue
        if relationship.primary_revision_id == revision.id:
            neighbour = relationship.secondary_revision
        else:
            neighbour = relationship.primary_revision
        if neighbour.id != revision.id:
            yield neighbour


def trace(
    revision,
    direction: str = "out",
    type_names=None,
    max_depth=None,
    *,
    session=None,
):
    """Breadth-first transitive traversal from ``revision``.

    Returns the reachable revisions (excluding the start), in BFS order. Set
    ``max_depth`` to cap traversal (``1`` = immediate neighbours only).
    """
    if direction not in _DIRECTIONS:
        raise ServiceError(
            f"direction must be one of {_DIRECTIONS}, got {direction!r}"
        )
    session = _session(session)
    if type_names is not None:
        type_names = set(type_names)

    visited = {revision.id}
    results = []
    queue = deque([(revision, 0)])
    while queue:
        current, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for neighbour in _neighbours(current, direction, type_names, session):
            if neighbour.id in visited:
                continue
            visited.add(neighbour.id)
            results.append(neighbour)
            queue.append((neighbour, depth + 1))
    return results


__all__ = ["create_relationship", "get_type", "trace"]
