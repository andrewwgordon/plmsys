"""Relationship service: typed links and transitive trace traversal."""

import pytest

from app.models import BusinessObject
from app.services import ServiceError, relationships


def _revision(session, number, index=-1):
    business_object = (
        session.query(BusinessObject).filter_by(object_number=number).one()
    )
    return business_object.revisions[index]


def test_create_relationship(session):
    req3 = _revision(session, "REQ-0003")
    test = _revision(session, "TEST-100")

    relationship = relationships.create_relationship(
        "VERIFIED_BY", req3, test, session=session
    )

    assert relationship.primary_revision is req3
    assert relationship.secondary_revision is test


def test_duplicate_relationship_is_rejected(session):
    req1 = _revision(session, "REQ-0001", 1)
    test = _revision(session, "TEST-100")  # already VERIFIED_BY in the seed

    with pytest.raises(ServiceError):
        relationships.create_relationship("VERIFIED_BY", req1, test, session=session)


def test_self_relationship_is_rejected(session):
    req3 = _revision(session, "REQ-0003")
    with pytest.raises(ServiceError):
        relationships.create_relationship("REFERENCES", req3, req3, session=session)


def test_trace_out_follows_decomposition_chain(session):
    req1 = _revision(session, "REQ-0001", 1)
    traced = relationships.trace(req1, "out", ["DEFINING"], session=session)

    numbers = [revision.business_object.object_number for revision in traced]
    assert numbers == ["REQ-0002", "REQ-0003", "REQ-0004"]


def test_trace_in_reverses_the_chain(session):
    req4 = _revision(session, "REQ-0004")
    traced = relationships.trace(req4, "in", ["DEFINING"], session=session)

    numbers = [revision.business_object.object_number for revision in traced]
    assert numbers == ["REQ-0003", "REQ-0002", "REQ-0001"]


def test_trace_respects_type_filter(session):
    req1 = _revision(session, "REQ-0001", 1)
    traced = relationships.trace(req1, "out", ["VERIFIED_BY"], session=session)

    assert [revision.business_object.object_number for revision in traced] == ["TEST-100"]


def test_trace_respects_max_depth(session):
    req1 = _revision(session, "REQ-0001", 1)
    traced = relationships.trace(
        req1, "out", ["DEFINING"], max_depth=1, session=session
    )

    assert [revision.business_object.object_number for revision in traced] == ["REQ-0002"]


def test_trace_rejects_bad_direction(session):
    req1 = _revision(session, "REQ-0001", 1)
    with pytest.raises(ServiceError):
        relationships.trace(req1, "sideways", session=session)
