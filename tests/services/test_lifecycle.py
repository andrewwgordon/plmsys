"""Lifecycle service: state machine and status-cache reconciliation."""

import pytest

from app.models import BusinessObject, Revision
from app.services import ServiceError, lifecycle


def _object(session, number):
    return session.query(BusinessObject).filter_by(object_number=number).one()


def test_seeded_status_matches_canonical_state(session):
    """Seeded revisions must not have a cached status that contradicts the
    RevisionReleaseState history."""
    for revision in session.query(Revision).all():
        assert revision.status == lifecycle.current_state_name(revision), (
            f"{revision} cached status {revision.status!r} != "
            f"canonical {lifecycle.current_state_name(revision)!r}"
        )


def test_happy_path_transitions_sync_status(session):
    requirement = _object(session, "REQ-0003")  # Draft, single revision A
    revision = requirement.current_revision

    lifecycle.submit_for_review(revision, session=session)
    assert revision.status == lifecycle.REVIEW

    lifecycle.approve(revision, session=session)
    assert revision.status == lifecycle.APPROVED
    assert requirement.status == lifecycle.APPROVED

    lifecycle.release(revision, session=session)
    assert revision.status == lifecycle.RELEASED
    assert requirement.status == lifecycle.RELEASED
    assert lifecycle.is_released(revision)
    lifecycle.ensure_released(revision)  # does not raise


def test_invalid_transition_is_rejected(session):
    requirement = _object(session, "REQ-0003")
    revision = requirement.current_revision  # Draft

    with pytest.raises(ServiceError):
        lifecycle.release(revision, session=session)


def test_obsolete_is_terminal(session):
    requirement = _object(session, "REQ-0003")
    revision = requirement.current_revision

    lifecycle.obsolete(revision, session=session)
    assert revision.status == lifecycle.OBSOLETE

    with pytest.raises(ServiceError):
        lifecycle.assign_release_state(revision, lifecycle.DRAFT, session=session)


def test_ensure_released_rejects_draft(session):
    requirement = _object(session, "REQ-0003")
    with pytest.raises(ServiceError):
        lifecycle.ensure_released(requirement.current_revision)


def test_back_transition_review_to_draft(session):
    requirement = _object(session, "REQ-0003")
    revision = requirement.current_revision

    lifecycle.submit_for_review(revision, session=session)
    lifecycle.assign_release_state(revision, lifecycle.DRAFT, session=session)

    assert revision.status == lifecycle.DRAFT
