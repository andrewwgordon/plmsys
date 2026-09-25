"""Configuration service: resolution, baselines and diffs."""

import pytest

from app.models import (
    Baseline,
    BaselineMember,
    BusinessObject,
    ConfigurationContext,
    Revision,
)
from app.services import ServiceError, configuration, lifecycle


def _context(session, name):
    return session.query(ConfigurationContext).filter_by(name=name).one()


def _object(session, number):
    return session.query(BusinessObject).filter_by(object_number=number).one()


def _revision(session, number, index=-1):
    return _object(session, number).revisions[index]


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_resolve_latest_released(session):
    context = _context(session, "EV Program - Released")

    resolved = configuration.resolve(context, session=session)

    # REQ-0001/B is Released and is the highest revision.
    assert resolved[_object(session, "REQ-0001").id].id == _revision(session, "REQ-0001", 1).id
    # REQ-0003 is only Draft -> not in a Released configuration.
    assert _object(session, "REQ-0003").id not in resolved
    for revision in resolved.values():
        assert lifecycle.current_state_name(revision) == lifecycle.RELEASED


def test_resolve_latest_working(session):
    context = _context(session, "EV Program - Working")

    resolved = configuration.resolve(context, session=session)

    # Working picks the highest non-Obsolete revision, e.g. REQ-0001/B.
    assert resolved[_object(session, "REQ-0001").id].id == _revision(session, "REQ-0001", 1).id
    assert _object(session, "REQ-0003").id in resolved
    # All seeded revisions are non-Obsolete, so every object resolves.
    assert len(resolved) == session.query(BusinessObject).count()


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def test_create_baseline_atomic_snapshot(session):
    context = _context(session, "EV Program - Released")
    expected = configuration.resolve(context, session=session)

    baseline = configuration.create_baseline(
        context, "Test Baseline", created_by="tester", session=session
    )

    assert baseline.created_by == "tester"
    assert len(baseline.members) == len(expected)
    for member in baseline.members:
        assert lifecycle.is_released(member.revision)


def test_create_baseline_stores_description(session):
    context = _context(session, "EV Program - Released")

    baseline = configuration.create_baseline(
        context,
        "Described Baseline",
        description="Captured for the audit trail.",
        session=session,
    )

    assert baseline.description == "Captured for the audit trail."


def test_create_baseline_rejects_duplicate_name(session):
    context = _context(session, "EV Program - Released")
    configuration.create_baseline(context, "Duplicated", session=session)
    with pytest.raises(ServiceError):
        configuration.create_baseline(context, "Duplicated", session=session)


def test_create_baseline_working_context_rejected(session):
    context = _context(session, "EV Program - Working")
    with pytest.raises(ServiceError):
        configuration.create_baseline(context, "Working Baseline", session=session)


def test_seeded_baseline_members_are_released(session):
    baseline = session.query(Baseline).first()
    assert baseline.members
    for member in baseline.members:
        assert lifecycle.is_released(member.revision)


def test_add_and_remove_baseline_member(session):
    context = _context(session, "EV Program - Released")
    baseline = Baseline(configuration_context=context, name="Member test")
    session.add(baseline)
    session.flush()
    released = _revision(session, "PART-1001", 1)  # B, Released

    configuration.add_baseline_member(baseline, released, session=session)

    assert (
        session.query(BaselineMember)
        .filter_by(baseline_id=baseline.id, revision_id=released.id)
        .count()
        == 1
    )
    with pytest.raises(ServiceError):
        configuration.add_baseline_member(baseline, released, session=session)

    assert configuration.remove_baseline_member(
        baseline, released, session=session
    )
    assert not configuration.remove_baseline_member(
        baseline, released, session=session
    )


def test_add_baseline_member_rejects_draft(session):
    baseline = session.query(Baseline).first()
    draft = _revision(session, "REQ-0003")  # Draft
    with pytest.raises(ServiceError):
        configuration.add_baseline_member(baseline, draft, session=session)


def test_add_baseline_member_rejects_second_revision_of_object(session):
    """Regression: a baseline captures one revision per object, otherwise
    ``compare_baselines`` (keyed by object_id) silently drops a member."""
    context = _context(session, "EV Program - Released")
    baseline = Baseline(configuration_context=context, name="Object-unique test")
    session.add(baseline)
    session.flush()

    req1_a = _revision(session, "REQ-0001", 0)  # Draft
    req1_b = _revision(session, "REQ-0001", 1)  # Released
    lifecycle.submit_for_review(req1_a, session=session)
    lifecycle.approve(req1_a, session=session)
    lifecycle.release(req1_a, session=session)

    configuration.add_baseline_member(baseline, req1_b, session=session)
    with pytest.raises(ServiceError):
        configuration.add_baseline_member(baseline, req1_a, session=session)


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


def _make_baseline(session, context, name, revisions):
    baseline = Baseline(configuration_context=context, name=name)
    session.add(baseline)
    session.flush()
    for revision in revisions:
        session.add(BaselineMember(baseline=baseline, revision=revision))
    session.flush()
    return baseline


def test_compare_baselines(session):
    context = _context(session, "EV Program - Released")
    req1_a = _revision(session, "REQ-0001", 0)
    req1_b = _revision(session, "REQ-0001", 1)
    req2 = _revision(session, "REQ-0002")
    plate_b = _revision(session, "PART-1001", 1)

    baseline_a = _make_baseline(session, context, "A", [req1_b, plate_b])
    baseline_b = _make_baseline(session, context, "B", [req1_a, req2])

    result = configuration.compare_baselines(baseline_a, baseline_b)

    assert [revision.id for revision in result["added"]] == [req2.id]
    assert [revision.id for revision in result["removed"]] == [plate_b.id]
    assert len(result["changed"]) == 1
    assert result["changed"][0]["before"].id == req1_b.id
    assert result["changed"][0]["after"].id == req1_a.id
