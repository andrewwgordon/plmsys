"""BOM service: traversal, roll-up, where-used, guards and coverage."""

import pytest

from app.models import BOMOccurrence, BusinessObject, OccurrenceTrace
from app.services import ServiceError, bom


def _revision(session, number):
    return (
        session.query(BusinessObject)
        .filter_by(object_number=number)
        .one()
        .current_revision
    )


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


def test_explode_with_accumulated_quantity(session):
    module = _revision(session, "PART-1000")

    rows = bom.explode(module)

    lines = [
        (r["occurrence"].find_number, r["child_revision"].business_object.object_number,
         r["depth"], r["quantity"])
        for r in rows
    ]
    assert ("10", "PART-1001", 1, 12.0) in lines
    assert ("20", "PART-1002", 1, 1.0) in lines
    assert ("30", "PART-1003", 1, 4.0) in lines
    # Plate shared through the interconnect: 4 x 1 at depth 2.
    assert ("10", "PART-1002", 2, 4.0) in lines
    assert len(rows) == 4


def test_explode_respects_max_depth(session):
    module = _revision(session, "PART-1000")

    rows = bom.explode(module, max_depth=1)

    assert len(rows) == 3
    assert all(row["depth"] == 1 for row in rows)


def test_explode_is_cycle_safe(session):
    module = _revision(session, "PART-1000").business_object.current_revision
    interconnect = _revision(session, "PART-1003")
    # Insert a cycle directly (bypassing the service guard).
    session.add(
        BOMOccurrence(
            parent_revision=interconnect,
            child_revision=module,
            find_number="99",
            quantity=1.0,
        )
    )
    session.flush()

    rows = bom.explode(module)  # must terminate

    # The cycle edge is listed once but not expanded (no depth 3).
    assert max(row["depth"] for row in rows) <= 2
    assert module.id in [row["occurrence"].child_revision_id for row in rows]


def test_bom_rollup(session):
    module = _revision(session, "PART-1000")

    totals = bom.bom_rollup(module)
    by_number = {
        revision_id: total for revision_id, total in totals.items()
    }
    cell_id = _revision(session, "PART-1001").id
    plate_id = _revision(session, "PART-1002").id
    interconnect_id = _revision(session, "PART-1003").id

    assert by_number[cell_id] == 12.0
    assert by_number[plate_id] == 5.0        # 1 direct + 4 through the subassembly
    assert by_number[interconnect_id] == 4.0


def test_where_used_immediate_and_transitive(session):
    plate = _revision(session, "PART-1002")

    immediate = {
        row["parent_revision"].business_object.object_number
        for row in bom.where_used(plate)
    }
    transitive = [
        row["parent_revision"].business_object.object_number
        for row in bom.where_used(plate, transitive=True)
    ]

    assert immediate == {"PART-1000", "PART-1003"}
    # Distinct ancestors, no duplicates.
    assert transitive == ["PART-1000", "PART-1003"]


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_add_occurrence_rejects_self_line(session):
    part = _revision(session, "PART-1001")
    with pytest.raises(ServiceError):
        bom.add_occurrence(part, part, "99", 1)


def test_add_occurrence_rejects_duplicate_find_number(session):
    module = _revision(session, "PART-1000")
    cell = _revision(session, "PART-1001")
    with pytest.raises(ServiceError):
        bom.add_occurrence(module, cell, "10", 1)


def test_add_occurrence_rejects_non_positive_quantity(session):
    module = _revision(session, "PART-1000")
    cell = _revision(session, "PART-1001")
    with pytest.raises(ServiceError):
        bom.add_occurrence(module, cell, "40", 0)


def test_add_occurrence_rejects_non_part(session):
    requirement = _revision(session, "REQ-0001")
    part = _revision(session, "PART-1001")
    with pytest.raises(ServiceError):
        bom.add_occurrence(requirement, part, "40", 1)


def test_add_occurrence_rejects_cycle(session):
    module = _revision(session, "PART-1000")
    interconnect = _revision(session, "PART-1003")
    with pytest.raises(ServiceError):
        bom.add_occurrence(interconnect, module, "99", 1)


def test_add_occurrence_creates_line(session):
    module = _revision(session, "PART-1000")
    cell = _revision(session, "PART-1001")

    occurrence = bom.add_occurrence(module, cell, "40", 2, session=session)

    assert occurrence.find_number == "40"
    assert occurrence.quantity == 2.0


# ---------------------------------------------------------------------------
# Occurrence trace & coverage
# ---------------------------------------------------------------------------


def test_link_requirement_duplicate_rejected(session):
    plate_line = (
        session.query(BOMOccurrence).filter_by(find_number="20").first()
    )
    req4 = _revision(session, "REQ-0004")
    # REQ-0004 -> plate line already exists from the seed.
    with pytest.raises(ServiceError):
        bom.link_requirement(plate_line, req4, session=session)


def test_uncovered_occurrences_reports_gap(session):
    uncovered = bom.uncovered_occurrences()

    find_numbers = {occurrence.find_number for occurrence in uncovered}
    # PART-1003/find 10 (interconnect plate) is intentionally untraced.
    assert "10" in find_numbers
    assert len(uncovered) == 1
