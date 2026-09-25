"""BOM service: product-structure traversal, roll-up, where-used and coverage.

BOM edges are ``parent revision --find_number--> child revision`` with a
quantity. All structure mutation goes through :func:`add_occurrence`, which
guards self-lines, duplicate find numbers, cycles, non-positive quantities and
non-``Part`` revisions. Traversal is cycle-safe and bulk-loads the structure so
it never issues a query per node.
"""

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


def _occurrences_by_parent(session):
    """Load the whole BOM once and index it by parent revision id."""
    occurrences = (
        session.query(BOMOccurrence)
        .options(
            joinedload(BOMOccurrence.parent_revision).joinedload(
                Revision.business_object
            ),
            joinedload(BOMOccurrence.child_revision).joinedload(
                Revision.business_object
            ),
        )
        .all()
    )
    by_parent = {}
    for occurrence in occurrences:
        by_parent.setdefault(occurrence.parent_revision_id, []).append(occurrence)
    return by_parent


def would_create_cycle(parent, child, *, session=None) -> bool:
    """True when adding ``parent -> child`` would close a cycle."""
    session = _session(session)
    if parent.id == child.id:
        return True
    by_parent = _occurrences_by_parent(session)
    stack = [child.id]
    visited = set()
    while stack:
        current = stack.pop()
        if current == parent.id:
            return True
        if current in visited:
            continue
        visited.add(current)
        for occurrence in by_parent.get(current, []):
            stack.append(occurrence.child_revision_id)
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
    if quantity <= 0:
        raise ServiceError("Quantity must be greater than zero.")

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

    Returns ``[{"occurrence", "child_revision", "depth", "quantity"}, …]`` in
    depth-first order; ``quantity`` is accumulated along the path. Cycle-safe
    and depth-capped (``max_depth=None`` = full structure).
    """
    session = _session(session)
    if max_depth is not None and max_depth < 1:
        raise ServiceError("max_depth must be >= 1")
    by_parent = _occurrences_by_parent(session)

    results = []
    stack = [
        (occurrence, 1, occurrence.quantity, (revision.id,))
        for occurrence in reversed(by_parent.get(revision.id, []))
    ]
    while stack:
        occurrence, depth, quantity, path = stack.pop()
        results.append(
            {
                "occurrence": occurrence,
                "child_revision": occurrence.child_revision,
                "depth": depth,
                "quantity": quantity,
            }
        )
        if max_depth is not None and depth >= max_depth:
            continue
        if occurrence.child_revision_id in path:
            continue  # cycle guard
        new_path = path + (occurrence.child_revision_id,)
        for child_occurrence in reversed(
            by_parent.get(occurrence.child_revision_id, [])
        ):
            stack.append(
                (
                    child_occurrence,
                    depth + 1,
                    quantity * child_occurrence.quantity,
                    new_path,
                )
            )
    return results


def bom_rollup(revision, *, session=None) -> dict:
    """Aggregate quantity per child revision across the whole structure."""
    totals = {}
    for row in explode(revision, session=session):
        child_id = row["child_revision"].id
        totals[child_id] = round(totals.get(child_id, 0.0) + row["quantity"], 6)
    return totals


def where_used(revision, transitive=False, *, session=None) -> list:
    """Return the parents that use ``revision``.

    Each entry is ``{"occurrence", "parent_revision", "depth"}``; with
    ``transitive`` the walk continues up the structure.
    """
    session = _session(session)
    occurrences = (
        session.query(BOMOccurrence)
        .options(
            joinedload(BOMOccurrence.parent_revision).joinedload(
                Revision.business_object
            )
        )
        .all()
    )
    by_child = {}
    for occurrence in occurrences:
        by_child.setdefault(occurrence.child_revision_id, []).append(occurrence)

    results = []
    if not transitive:
        for occurrence in by_child.get(revision.id, []):
            results.append(
                {
                    "occurrence": occurrence,
                    "parent_revision": occurrence.parent_revision,
                    "depth": 1,
                }
            )
        return results

    visited = {revision.id}
    queue = deque([(revision.id, 0)])
    while queue:
        current, depth = queue.popleft()
        for occurrence in by_child.get(current, []):
            parent = occurrence.parent_revision
            if parent.id in visited:
                continue
            visited.add(parent.id)
            results.append(
                {
                    "occurrence": occurrence,
                    "parent_revision": parent,
                    "depth": depth + 1,
                }
            )
            queue.append((parent.id, depth + 1))
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
