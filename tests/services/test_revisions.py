"""Revision service: labelling, branching, lineage and reversion."""

import pytest

from app.models import BusinessObject, Revision, RevisionLineage
from app.services import ServiceError, lifecycle, revisions


def _object(session, number):
    return session.query(BusinessObject).filter_by(object_number=number).one()


def test_alpha_label():
    assert revisions.alpha_label(1) == "A"
    assert revisions.alpha_label(26) == "Z"
    assert revisions.alpha_label(27) == "AA"
    assert revisions.alpha_label(28) == "AB"


def test_next_revision_id(session):
    requirement = _object(session, "REQ-0003")  # single revision A
    assert revisions.next_revision_id(requirement) == "B"
    assert revisions.next_revision_id(requirement, numeric=True) == "02"


def test_create_revision_branches_and_copies(session):
    requirement = _object(session, "REQ-0003")
    previous = requirement.current_revision

    new_revision = revisions.create_revision(
        requirement, title="Branch", session=session
    )

    assert new_revision.revision_id == "B"
    assert new_revision.sequence_no == 2
    assert requirement.current_revision is new_revision
    # Lineage previous -> new.
    lineage = (
        session.query(RevisionLineage)
        .filter_by(child_revision_id=new_revision.id)
        .one()
    )
    assert lineage.parent_revision_id == previous.id
    # Starts life as Draft, with a matching canonical release-state row.
    assert new_revision.status == lifecycle.DRAFT
    assert lifecycle.current_state_name(new_revision) == lifecycle.DRAFT
    # Property values carried across.
    assert new_revision.property_values, "expected properties to be copied"


def test_create_revision_without_copy(session):
    requirement = _object(session, "REQ-0003")
    new_revision = revisions.create_revision(
        requirement, copy_properties=False, session=session
    )
    assert new_revision.property_values == []


def test_create_revision_rejects_duplicate_label(session):
    requirement = _object(session, "REQ-0001")
    with pytest.raises(ServiceError):
        revisions.create_revision(requirement, revision_id="A", session=session)


def test_revert_to_revision(session):
    requirement = _object(session, "REQ-0001")
    first = requirement.revisions[0]

    revisions.revert_to_revision(requirement, first, session=session)

    assert requirement.current_revision is first
    assert requirement.status == first.status


def test_revert_rejects_foreign_revision(session):
    requirement = _object(session, "REQ-0001")
    other = _object(session, "PART-1000").current_revision
    with pytest.raises(ServiceError):
        revisions.revert_to_revision(requirement, other, session=session)
