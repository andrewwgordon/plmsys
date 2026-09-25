"""BOM service: product-structure traversal, roll-up, where-used and coverage.

BOM edges are ``parent revision --find_number--> child revision`` with a
quantity. All structure mutation goes through :func:`add_occurrence`, which
guards self-lines, duplicate find numbers, cycles, non-positive/non-finite
quantities and non-``Part`` revisions. Traversal is cycle-safe and fetches one
level of children/parents at a time (batched ``IN`` queries), so the cost is
O(depth) queries rather than O(nodes).
"""

import math
from collections import deque

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import BOMOccurrence, OccurrenceTrace, Revision
from . import ServiceError


def _session(session):
    return session if session is not None else db.session


def _object_type_name(revision) -> str:
    business_object = revision.business_object
    if business_object is None or business_object.object_type is None:
        return ""
    return business_object.object_type.name


def _require_part(revision, label: str) -> None:
    if _object_type_name(revision) != "Part":
        raise ServiceError(f"The {label} is not a Part revision.")


def _children_of(parent_ids, session) -> dict:
    """Return ``{parent_revision_id: [BOMOccurrence]}`` for the given parents."""
    ids = [parent_id for parent_id in parent_ids if parent_id is not None]
    if not ids:
        return {}
    occurrences = (
        session.query(BOMOccurrence)
        .filter(BOMOccurrence.parent_revision_id.in_(ids))
        .options(
            joinedload(BOMOccurrence.child_revision).joinedload(
                Revision.business_object
            )
        )
        .order_by(BOMOccurrence.parent_revision_id, BOMOccurrence.find_number)
        .all()
    )
    by_parent = {}
    for occurrence in occurrences:
        by_parent.setdefault(occurrence.parent_revision_id, []).append(occurrence)
    return by_parent


def _parents_of(child_ids, session) -> list:
    """Return the occurrences whose child is one of ``child_ids``."""
    ids = [child_id for child_id in child_ids if child_id is not None]
    if not ids:
        return []
    return (
        session.query(BOMOccurrence)
        .filter(BOMOccurrence.child_revision_id.in_(ids))
        .options(
            joinedload(BOMOccurrence.parent_revision).joinedload(
                Revision.business_object
            )
        )
        .order_by(BOMOccurrence.parent_revision_id, BOMOccurrence.find_number)
        .all()
    )


def would_create_cycle(parent, child, *, session=None) -> bool:
    """True when adding ``parent -> child`` would close a cycle."""
    session = _session(session)
    if parent.id == child.id:
        return True
    visited = set()
    frontier = {child.id}
    while frontier:
        if parent.id in frontier:
            return True
        visited.update(frontier)
        next_frontier = set()
        for occurrences in _children_of(frontier, session).values():
            for occurrence in occurrences:
                if occurrence.child_revision_id not in visited:
                    next_frontier.add(occurrence.child_revision_id)
        frontier = next_frontier
    return False


def add_occurrence(
    parent, child, find_number, quantity=1.0, *, session=None
):
    """Add a BOM line, guarding self-lines, duplicates, cycles and quantity."""
    session = _session(session)
    _require_part(parent, "parent")
    _require_part(child, "child")
    if parent.id == child.id:
        raise ServiceError("A part cannot be its own child.")

    find_number = (find_number or "").strip()
    if not find_number:
        raise ServiceError("A find number is required.")
    try:
        quantity = float(quantity)
    except (TypeError, ValueError) as exc:
        raise ServiceError("Quantity must be a number.") from exc
    if not math.isfinite(quantity) or quantity <= 0:
        raise ServiceError("Quantity must be a finite number greater than zero.")

    duplicate = (
        session.query(BOMOccurrence)
        .filter_by(parent_revision_id=parent.id, find_number=find_number)
        .first()
    )
    if duplicate is not None:
        raise ServiceError(
            f"Find number {find_number!r} already exists under this parent."
        )
    if would_create_cycle(parent, child, session=session):
        raise ServiceError("This occurrence would create a BOM cycle.")

    occurrence = BOMOccurrence(
        parent_revision=parent,
        child_revision=child,
        find_number=find_number,
        quantity=quantity,
    )
    session.add(occurrence)
    session.flush()
    return occurrence


def remove_occurrence(occurrence, *, session=None) -> bool:
    session = _session(session)
    session.delete(occurrence)
    session.flush()
    return True


def explode(revision, max_depth=None, *, session=None) -> list:
    """Flatten the structure below ``revision``.

    Returns ``[{"occurrence", "child_revision", "depth", "quantity", "cycle"},
    …]`` in breadth-first order; ``quantity`` is accumulated along the path and
    ``cycle`` marks a back-edge that was listed but not expanded. Cycle-safe,
    depth-capped (``max_depth=None`` = full structure), and batched one level at
    a time.
    """
    session = _session(session)
    if max_depth is not None and max_depth < 1:
        raise ServiceError("max_depth must be >= 1")

    results = []
    # frontier entries: (parent_revision_id, accumulated_quantity, path)
    frontier = [(revision.id, 1.0, (revision.id,))]
    depth = 0
    while frontier:
        depth += 1
        if max_depth is not None and depth > max_depth:
            break
        children = _children_of({entry[0] for entry in frontier}, session)
        next_frontier = []
        for parent_id, quantity, path in frontier:
            for occurrence in children.get(parent_id, []):
                child_id = occurrence.child_revision_id
                accumulated = quantity * occurrence.quantity
                cycle = child_id in path
                results.append(
                    {
                        "occurrence": occurrence,
                        "child_revision": occurrence.child_revision,
                        "depth": depth,
                        "quantity": accumulated,
                        "cycle": cycle,
                    }
                )
                if not cycle:
                    next_frontier.append(
                        (child_id, accumulated, path + (child_id,))
                    )
        frontier = next_frontier
    return results


def bom_rollup(revision, rows=None, *, session=None) -> dict:
    """Aggregate quantity per child revision across the whole structure.

    Pass ``rows`` (the result of :func:`explode`) to reuse an existing
    traversal instead of walking the structure again.
    """
    if rows is None:
        rows = explode(revision, session=session)
    totals = {}
    for row in rows:
        child_id = row["child_revision"].id
        totals[child_id] = round(totals.get(child_id, 0.0) + row["quantity"], 6)
    return totals


def where_used(revision, transitive=False, *, session=None) -> list:
    """Return the parents that use ``revision``.

    Each entry is ``{"occurrence", "parent_revision", "depth"}``; with
    ``transitive`` the walk continues up the structure (batched, distinct
    ancestors).
    """
    session = _session(session)
    if not transitive:
        return [
            {
                "occurrence": occurrence,
                "parent_revision": occurrence.parent_revision,
                "depth": 1,
            }
            for occurrence in _parents_of([revision.id], session)
        ]

    results = []
    visited = {revision.id}
    frontier = {revision.id}
    depth = 0
    while frontier:
        depth += 1
        next_frontier = set()
        for occurrence in _parents_of(frontier, session):
            parent = occurrence.parent_revision
            if parent.id in visited:
                continue
            visited.add(parent.id)
            results.append(
                {
                    "occurrence": occurrence,
                    "parent_revision": parent,
                    "depth": depth,
                }
            )
            next_frontier.add(parent.id)
        frontier = next_frontier
    return results


def link_requirement(occurrence, revision, *, session=None):
    """Trace a requirement revision to a BOM occurrence (duplicate-guarded)."""
    session = _session(session)
    if _object_type_name(revision) != "Requirement":
        raise ServiceError(
            "Only requirement revisions can be traced to a BOM line."
        )
    duplicate = (
        session.query(OccurrenceTrace)
        .filter_by(
            requirement_revision_id=revision.id,
            bom_occurrence_id=occurrence.id,
        )
        .first()
    )
    if duplicate is not None:
        raise ServiceError(
            "This requirement is already traced to the BOM line."
        )
    trace = OccurrenceTrace(
        requirement_revision=revision, bom_occurrence=occurrence
    )
    session.add(trace)
    session.flush()
    return trace


def uncovered_occurrences(*, session=None) -> list:
    """BOM lines with no requirement trace (coverage gaps)."""
    session = _session(session)
    return (
        session.query(BOMOccurrence)
        .outerjoin(
            OccurrenceTrace,
            OccurrenceTrace.bom_occurrence_id == BOMOccurrence.id,
        )
        .filter(OccurrenceTrace.id.is_(None))
        .options(
            joinedload(BOMOccurrence.parent_revision).joinedload(
                Revision.business_object
            ),
            joinedload(BOMOccurrence.child_revision).joinedload(
                Revision.business_object
            ),
        )
        .order_by(BOMOccurrence.parent_revision_id, BOMOccurrence.find_number)
        .all()
    )


__all__ = [
    "add_occurrence",
    "bom_rollup",
    "explode",
    "link_requirement",
    "remove_occurrence",
    "uncovered_occurrences",
    "where_used",
    "would_create_cycle",
]
