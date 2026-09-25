"""Revision lifecycle service.

Single source of truth for a revision's lifecycle state. The canonical record
is the set of :class:`~app.models.RevisionReleaseState` rows (a history of
assignments); :attr:`Revision.status` and :attr:`BusinessObject.status` are
denormalised caches. Every mutation goes through :func:`assign_release_state`,
which keeps the cache in sync, so the two representations cannot drift.

State machine (``docs/plan.md`` Phase 2)::

    Draft -> Review -> Approved -> Released -> Obsolete

with the usual back-steps (``Review -> Draft``, ``Approved -> Review``) and an
escape hatch to ``Obsolete`` from any non-obsolete state.
"""

from ..extensions import db
from ..models import ReleaseState, RevisionReleaseState
from . import ServiceError

DRAFT = "Draft"
REVIEW = "Review"
APPROVED = "Approved"
RELEASED = "Released"
OBSOLETE = "Obsolete"

STATE_ORDER = (DRAFT, REVIEW, APPROVED, RELEASED, OBSOLETE)

# Allowed forward/backward transitions. ``Obsolete`` is terminal.
_TRANSITIONS = {
    DRAFT: {REVIEW, OBSOLETE},
    REVIEW: {DRAFT, APPROVED, OBSOLETE},
    APPROVED: {REVIEW, RELEASED, OBSOLETE},
    RELEASED: {OBSOLETE},
    OBSOLETE: frozenset(),
}


def _session(session):
    return session if session is not None else db.session


def get_state(session, name):
    """Return the :class:`ReleaseState` called ``name`` or raise."""
    state = (
        _session(session)
        .query(ReleaseState)
        .filter(ReleaseState.name == name)
        .one_or_none()
    )
    if state is None:
        raise ServiceError(f"Unknown release state: {name!r}")
    return state


def current_release_state(revision):
    """Return the most recently assigned :class:`ReleaseState`, or ``None``."""
    if not revision.release_states:
        return None
    return max(
        revision.release_states,
        key=lambda rel: (rel.assigned_on, rel.release_state_id),
    ).release_state


def current_state_name(revision) -> str:
    """Canonical current state name, falling back to the cached ``status``."""
    state = current_release_state(revision)
    if state is not None:
        return state.name
    return revision.status or DRAFT


def can_transition(revision, state_name: str) -> bool:
    current = current_state_name(revision)
    if state_name == current:
        return True
    return state_name in _TRANSITIONS.get(current, frozenset())


def assign_release_state(
    revision,
    state_name: str,
    *,
    enforce_transition: bool = True,
    session=None,
):
    """Assign ``state_name`` to ``revision`` and keep the status cache in sync.

    Appends a :class:`RevisionReleaseState` history row (unless the revision is
    already in that exact state) and mirrors the name onto
    ``Revision.status`` and, when ``revision`` is its object's current
    revision, ``BusinessObject.status``.
    """
    session = _session(session)
    state = get_state(session, state_name)
    current = current_state_name(revision)

    if enforce_transition and not can_transition(revision, state_name):
        raise ServiceError(
            f"Cannot move revision {revision.revision_id!r} "
            f"from {current!r} to {state_name!r}"
        )

    already_recorded = any(
        rel.release_state_id == state.id for rel in revision.release_states
    )
    if not already_recorded:
        session.add(RevisionReleaseState(revision=revision, release_state=state))
        session.flush()

    revision.status = state.name
    business_object = revision.business_object
    if (
        business_object is not None
        and business_object.current_revision_id == revision.id
    ):
        business_object.status = state.name
    session.flush()
    return state


def sync_status(revision, *, session=None) -> str:
    """Recompute the cached status from the canonical release states."""
    session = _session(session)
    state_name = current_state_name(revision)
    revision.status = state_name
    business_object = revision.business_object
    if (
        business_object is not None
        and business_object.current_revision_id == revision.id
    ):
        business_object.status = state_name
    session.flush()
    return state_name


def submit_for_review(revision, **kwargs):
    return assign_release_state(revision, REVIEW, **kwargs)


def approve(revision, **kwargs):
    return assign_release_state(revision, APPROVED, **kwargs)


def release(revision, **kwargs):
    """Move a revision to ``Released`` (only from ``Approved``)."""
    return assign_release_state(revision, RELEASED, **kwargs)


def obsolete(revision, **kwargs):
    return assign_release_state(revision, OBSOLETE, **kwargs)


def is_released(revision) -> bool:
    return current_state_name(revision) == RELEASED


def ensure_released(revision) -> None:
    """Guard for baseline membership: only released revisions qualify."""
    if not is_released(revision):
        raise ServiceError(
            f"Revision {revision.revision_id!r} is "
            f"{current_state_name(revision)!r}, not {RELEASED!r}"
        )


__all__ = [
    "DRAFT",
    "REVIEW",
    "APPROVED",
    "RELEASED",
    "OBSOLETE",
    "STATE_ORDER",
    "assign_release_state",
    "approve",
    "can_transition",
    "current_release_state",
    "current_state_name",
    "ensure_released",
    "get_state",
    "is_released",
    "obsolete",
    "release",
    "submit_for_review",
    "sync_status",
]
