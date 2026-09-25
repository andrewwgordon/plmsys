"""Configuration service: revision resolution, baselines and diffs.

A :class:`RevisionRule` has an explicit ``rule_type``; :func:`resolve` applies it
per business object using the canonical lifecycle (never the cached ``status``).
Baselines are created atomically and only from Released revisions, and
:func:`compare_baselines` reports additions, removals and revision changes.
"""

from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    Baseline,
    BaselineMember,
    BusinessObject,
    Revision,
    RevisionRuleType,
)
from . import ServiceError, lifecycle


def _session(session):
    return session if session is not None else db.session


def _rule_type(context) -> RevisionRuleType:
    rule_type = context.revision_rule.rule_type
    if isinstance(rule_type, RevisionRuleType):
        return rule_type
    try:
        return RevisionRuleType(rule_type)
    except ValueError as exc:
        raise ServiceError(
            f"Unknown revision rule type: {rule_type!r}"
        ) from exc


def resolve(context, *, session=None) -> dict:
    """Return ``{business_object_id: Revision}`` chosen by the context's rule.

    ``LATEST_WORKING`` picks the highest-sequence revision that is not
    ``Obsolete``; ``LATEST_RELEASED`` picks the highest ``Released`` one.
    Objects with no matching revision are skipped.
    """
    session = _session(session)
    rule_type = _rule_type(context)
    objects = (
        session.query(BusinessObject)
        .options(
            selectinload(BusinessObject.revisions).selectinload(
                Revision.release_states
            )
        )
        .all()
    )

    resolved = {}
    for business_object in objects:
        candidate = None
        for revision in business_object.revisions:
            state = lifecycle.current_state_name(revision)
            if rule_type == RevisionRuleType.LATEST_RELEASED:
                if state != lifecycle.RELEASED:
                    continue
            elif state == lifecycle.OBSOLETE:
                continue
            if candidate is None or (revision.sequence_no or 0) > (
                candidate.sequence_no or 0
            ):
                candidate = revision
        if candidate is not None:
            resolved[business_object.id] = candidate
    return resolved


def create_baseline(context, name, created_by=None, *, session=None):
    """Atomically snapshot the resolved configuration into a baseline.

    Only Released revisions may enter a baseline; the name must be unique within
    the context. Any failure rolls the whole operation back.
    """
    session = _session(session)
    name = (name or "").strip()
    if not name:
        raise ServiceError("A baseline name is required.")

    duplicate = (
        session.query(Baseline)
        .filter_by(configuration_context_id=context.id, name=name)
        .first()
    )
    if duplicate is not None:
        raise ServiceError(
            f"Baseline {name!r} already exists in this context."
        )

    resolved = resolve(context, session=session)
    if not resolved:
        raise ServiceError("No revisions match this configuration rule.")
    for revision in resolved.values():
        lifecycle.ensure_released(revision)

    baseline = Baseline(
        configuration_context=context,
        name=name,
        created_by=created_by,
    )
    session.add(baseline)
    session.flush()
    for revision in resolved.values():
        session.add(BaselineMember(baseline=baseline, revision=revision))
    session.flush()
    return baseline


def add_baseline_member(baseline, revision, *, session=None):
    """Add a released revision to a baseline (duplicate-guarded)."""
    session = _session(session)
    lifecycle.ensure_released(revision)
    existing = (
        session.query(BaselineMember)
        .filter_by(baseline_id=baseline.id, revision_id=revision.id)
        .first()
    )
    if existing is not None:
        raise ServiceError("This revision is already in the baseline.")
    member = BaselineMember(baseline=baseline, revision=revision)
    session.add(member)
    session.flush()
    return member


def remove_baseline_member(baseline, revision, *, session=None) -> bool:
    session = _session(session)
    member = (
        session.query(BaselineMember)
        .filter_by(baseline_id=baseline.id, revision_id=revision.id)
        .first()
    )
    if member is None:
        return False
    session.delete(member)
    session.flush()
    return True


def compare_baselines(a, b, *, session=None) -> dict:
    """Return ``{"added", "removed", "changed"}`` between two baselines.

    ``added``/``removed`` are revisions; ``changed`` entries are
    ``{"object_id", "before", "after"}`` for the same business object.
    """
    def _by_object(baseline):
        result = {}
        for member in baseline.members:
            result[member.revision.object_id] = member.revision
        return result

    a_members = _by_object(a)
    b_members = _by_object(b)

    added = []
    removed = []
    changed = []
    for object_id, revision in b_members.items():
        before = a_members.get(object_id)
        if before is None:
            added.append(revision)
        elif before.id != revision.id:
            changed.append(
                {"object_id": object_id, "before": before, "after": revision}
            )
    for object_id, revision in a_members.items():
        if object_id not in b_members:
            removed.append(revision)

    return {"added": added, "removed": removed, "changed": changed}


__all__ = [
    "add_baseline_member",
    "compare_baselines",
    "create_baseline",
    "remove_baseline_member",
    "resolve",
]
