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

from datetime import timedelta

from ..extensions import db
from ..models import ReleaseState, RevisionReleaseState, utcnow
from . import ServiceError

DRAFT = "Draft"
REVIEW = "Review"
APPROVED = "Approved"
RELEASED = "Released"
OBSOLETE = "Obsolete"

STATE_ORDER = (DRAFT, REVIEW, APPROVED, RELEASED, OBSOLETE)

# Bootstrap 3 label class per state, used by ``Revision.release_state_badge``.
# Kept next to the state constants so adding a state is a single edit.
STATE_LABELS = {
    DRAFT: "label-default",
    REVIEW: "label-info",
    APPROVED: "label-warning",
    RELEASED: "label-success",
    OBSOLETE: "label-danger",
}

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


def current_state_name(revision) -> str:
    """Canonical current state name.

    Delegates to :attr:`Revision.release_state_name` (which falls back to the
    cached ``status``) so the model badge and the service cannot drift.
    """
    return revision.release_state_name


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

    Appends a :class:`RevisionReleaseState` row for the state, or refreshes the
    existing row's ``assigned_on`` when the state was visited before. The
    composite ``(revision_id, release_state_id)`` primary key allows only one
    row per state, so :meth:`Revision.release_state_name` (which selects the
    row with the latest ``assigned_on``) only stays correct if re-entering a
    state bumps its timestamp. Mirrors the name onto ``Revision.status`` and,
    when ``revision`` is its object's current revision, ``BusinessObject.status``.
    """
    session = _session(session)
    state = get_state(session, state_name)
    current = current_state_name(revision)

    if enforce_transition and not can_transition(revision, state_name):
        raise ServiceError(
            f"Cannot move revision {revision.revision_id!r} "
            f"from {current!r} to {state_name!r}"
        )

    recorded = next(
        (
            rel
            for rel in revision.release_states
            if rel.release_state_id == state.id
        ),
        None,
    )
    if recorded is None:
        session.add(RevisionReleaseState(revision=revision, release_state=state))
    else:
        # Re-entering a state (e.g. Review -> Draft): update the existing row so
        # it is the latest assignment and the canonical state follows the cache.
        # Keep ``assigned_on`` strictly greater than every other row so a same-
        # microsecond transition cannot tie-break on release_state_id.
        latest = max(
            (
                rel.assigned_on
                for rel in revision.release_states
                if rel is not recorded and rel.assigned_on is not None
            ),
            default=None,
        )
        now = utcnow()
        if latest is None or now > latest:
            recorded.assigned_on = now
        else:
            recorded.assigned_on = latest + timedelta(microseconds=1)
    session.flush()

    revision.status = state.name
    business_object = revision.business_object
    if business_object is not None and business_object.current_revision is revision:
        business_object.status = state.name
    session.flush()
    return state


def sync_status(revision, *, session=None) -> str:
    """Recompute the cached status from the canonical release states."""
    session = _session(session)
    state_name = current_state_name(revision)
    revision.status = state_name
    business_object = revision.business_object
    if business_object is not None and business_object.current_revision is revision:
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


def ensure_released(revision, *, session=None) -> None:
    """Guard for baseline membership: only released revisions qualify."""
    # ``no_autoflush`` keeps a pending BaselineMember (set by the form but not
    # yet added to the session) from being cascade-flushed while we lazy-load
    # the release states.
    with _session(session).no_autoflush:
        state = current_state_name(revision)
    if state != RELEASED:
        raise ServiceError(
            f"Revision {revision.revision_id!r} is {state!r}, not {RELEASED!r}"
        )


__all__ = [
    "DRAFT",
    "REVIEW",
    "APPROVED",
    "RELEASED",
    "OBSOLETE",
    "STATE_ORDER",
    "STATE_LABELS",
    "assign_release_state",
    "approve",
    "can_transition",
    "current_state_name",
    "ensure_released",
    "get_state",
    "is_released",
    "obsolete",
    "release",
    "submit_for_review",
    "sync_status",
]
