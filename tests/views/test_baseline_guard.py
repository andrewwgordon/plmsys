"""The Phase 2 baseline guard: only Released revisions may join a baseline."""

from app.models import Baseline, BaselineMember, BusinessObject, ConfigurationContext


def _baseline(session):
    return session.query(Baseline).first()


def _member_count(session, baseline_id):
    return (
        session.query(BaselineMember)
        .filter_by(baseline_id=baseline_id)
        .count()
    )


def test_draft_revision_cannot_join_baseline(db_session, admin_client):
    baseline = _baseline(db_session)
    draft = (
        db_session.query(BusinessObject)
        .filter_by(object_number="REQ-0003")
        .one()
        .current_revision
    )
    before = _member_count(db_session, baseline.id)

    response = admin_client.post(
        "/baselinemembermodelview/add",
        data={"baseline": baseline.id, "revision": draft.id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Draft" in response.data  # flash: "... is 'Draft', not 'Released'"
    db_session.expire_all()
    assert _member_count(db_session, baseline.id) == before


def test_released_revision_can_join_baseline(db_session, admin_client):
    context = (
        db_session.query(ConfigurationContext)
        .filter_by(name="EV Program - Released")
        .one()
    )
    baseline = Baseline(
        configuration_context=context, name="Phase 2 guard test baseline"
    )
    db_session.add(baseline)
    db_session.flush()

    released = (
        db_session.query(BusinessObject)
        .filter_by(object_number="REQ-0001")
        .one()
        .revisions[-1]
    )

    response = admin_client.post(
        "/baselinemembermodelview/add",
        data={"baseline": baseline.id, "revision": released.id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert (
        db_session.query(BaselineMember)
        .filter_by(baseline_id=baseline.id, revision_id=released.id)
        .count()
        == 1
    )
