"""Revision service: create/branch revisions and move the current pointer.

Revision labels default to the Teamcenter-style alpha scheme (``A``, ``B``, …,
``Z``, ``AA``); pass ``numeric=True`` for ``01``, ``02``. Creating a revision
records lineage from the previous current revision, optionally copies property
values, and starts the new revision in the ``Draft`` lifecycle state.
"""

from ..extensions import db
from ..models import Revision, RevisionLineage
from . import ServiceError, lifecycle, properties

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def alpha_label(n: int) -> str:
    """Return the 1-based spreadsheet-style label: 1->A, 26->Z, 27->AA."""
    if n < 1:
        raise ServiceError("Revision sequence must be >= 1")
    label = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        label = _ALPHABET[remainder] + label
    return label


def next_revision_id(business_object, *, numeric: bool = False) -> str:
    """Compute the next revision label for an object."""
    next_sequence = (
        max((revision.sequence_no or 0 for revision in business_object.revisions), default=0)
        + 1
    )
    return f"{next_sequence:02d}" if numeric else alpha_label(next_sequence)


def create_revision(
    business_object,
    title=None,
    description=None,
    user=None,
    *,
    revision_id=None,
    copy_properties: bool = True,
    session=None,
):
    """Branch ``business_object``'s current revision into a new ``Draft``.

    ``user`` is accepted for call-site compatibility and future audit use.
    """
    session = session if session is not None else db.session
    previous = business_object.current_revision

    revision_id = revision_id or next_revision_id(business_object)
    if any(
        revision.revision_id == revision_id
        for revision in business_object.revisions
    ):
        raise ServiceError(
            f"Revision {revision_id!r} already exists on "
            f"{business_object.object_number!r}"
        )

    next_sequence = (
        max((revision.sequence_no or 0 for revision in business_object.revisions), default=0)
        + 1
    )
    revision = Revision(
        business_object=business_object,
        revision_id=revision_id,
        sequence_no=next_sequence,
        title=title or business_object.name,
        description=description
        if description is not None
        else business_object.description,
        status=lifecycle.DRAFT,
    )
    session.add(revision)
    session.flush()

    if previous is not None:
        session.add(
            RevisionLineage(parent_revision=previous, child_revision=revision)
        )
        if copy_properties:
            properties.copy_properties(previous, revision, session=session)

    business_object.current_revision = revision
    lifecycle.assign_release_state(
        revision, lifecycle.DRAFT, enforce_transition=False, session=session
    )
    session.flush()
    return revision


def revert_to_revision(business_object, revision, *, session=None):
    """Point ``business_object.current_revision`` back at ``revision``."""
    session = session if session is not None else db.session
    if revision.object_id != business_object.id:
        raise ServiceError(
            f"Revision {revision.revision_id!r} does not belong to "
            f"{business_object.object_number!r}"
        )
    business_object.current_revision = revision
    lifecycle.sync_status(revision, session=session)
    session.flush()
    return revision


__all__ = [
    "alpha_label",
    "create_revision",
    "next_revision_id",
    "revert_to_revision",
]
