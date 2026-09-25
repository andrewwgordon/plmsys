"""PLMSys domain model.

A Teamcenter-inspired, database-agnostic PLM domain model built on
Flask-AppBuilder's declarative ``Model`` base (SQLAlchemy 2.x).

Design:

* :class:`ObjectType` describes a business object definition (and revision
  definitions), forming a type hierarchy.
* :class:`BusinessObject` is a stable identity (e.g. ``REQ-0001``).
* :class:`Revision` holds version-controlled content for an object.
* Business data is stored as metadata-driven
  :class:`PropertyDefinition` / :class:`PropertyValue` pairs.
* Traceability is expressed through :class:`Relationship` objects.

Users/roles/permissions are intentionally out of scope and are handled by the
Flask-AppBuilder Security Manager.
"""

from datetime import datetime
from enum import StrEnum

from flask_appbuilder import Model
from flask_appbuilder.models.decorators import renders
from markupsafe import Markup, escape
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

__all__ = [
    "ObjectType",
    "BusinessObject",
    "Revision",
    "RevisionLineage",
    "PropertyDefinition",
    "PropertyValue",
    "RelationshipType",
    "Relationship",
    "BOMOccurrence",
    "OccurrenceTrace",
    "RevisionRule",
    "ConfigurationContext",
    "Baseline",
    "BaselineMember",
    "Dataset",
    "ManagedFile",
    "ReleaseState",
    "RevisionReleaseState",
    "VerificationResult",
    "WorkflowProcess",
    "WorkflowTask",
]


def utcnow() -> datetime:
    """Timezone-naive timestamp helper (portable across DB backends)."""
    return datetime.now()


class TimestampMixin:
    """Adds ``created_on`` / ``modified_on`` audit timestamps."""

    created_on = Column(DateTime, default=utcnow, nullable=False)
    modified_on = Column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class PropertyDataType(StrEnum):
    """Supported scalar types for :class:`PropertyValue`."""

    STRING = "String"
    INTEGER = "Integer"
    FLOAT = "Float"
    DATE = "Date"


# ---------------------------------------------------------------------------
# Core meta-model
# ---------------------------------------------------------------------------


class ObjectType(TimestampMixin, Model):
    """A Teamcenter-style business object definition."""

    __tablename__ = "object_type"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    parent_type_id = Column(Integer, ForeignKey("object_type.id"), index=True)
    description = Column(Text)

    parent_type = relationship(
        "ObjectType", remote_side=[id], backref="subtypes"
    )
    business_objects = relationship(
        "BusinessObject", back_populates="object_type"
    )
    property_definitions = relationship(
        "PropertyDefinition",
        back_populates="object_type",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return self.name


class BusinessObject(TimestampMixin, Model):
    """Stable identity of a business object (e.g. ``REQ-0001``)."""

    __tablename__ = "business_object"

    id = Column(Integer, primary_key=True)
    object_type_id = Column(
        Integer, ForeignKey("object_type.id"), nullable=False, index=True
    )
    object_number = Column(String(120), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    current_revision_id = Column(Integer, ForeignKey("revision.id"), index=True)
    # Denormalised mirror of the *current revision's* lifecycle state. The
    # canonical lifecycle state lives in RevisionReleaseState / ReleaseState;
    # this column is kept in sync by ``services.lifecycle`` and is safe to read
    # for cheap list rendering.
    status = Column(String(40), default="Draft", nullable=False)

    object_type = relationship(
        "ObjectType", back_populates="business_objects"
    )
    # ``post_update`` breaks the insert-order cycle on current_revision_id.
    current_revision = relationship(
        "Revision",
        foreign_keys=[current_revision_id],
        post_update=True,
    )
    revisions = relationship(
        "Revision",
        foreign_keys="Revision.object_id",
        back_populates="business_object",
        cascade="all, delete-orphan",
        order_by="Revision.sequence_no",
    )

    def __repr__(self) -> str:
        return f"{self.object_number} - {self.name}"


class Revision(TimestampMixin, Model):
    """Version-controlled content for a :class:`BusinessObject`."""

    __tablename__ = "revision"
    __table_args__ = (
        UniqueConstraint(
            "object_id", "revision_id", name="uq_revision_object_rev"
        ),
    )

    id = Column(Integer, primary_key=True)
    object_id = Column(
        Integer, ForeignKey("business_object.id"), nullable=False, index=True
    )
    revision_id = Column(String(40), nullable=False)
    sequence_no = Column(Integer, default=1, nullable=False)
    title = Column(String(255))
    description = Column(Text)
    # Denormalised cache of the latest ``RevisionReleaseState``/``ReleaseState``
    # (see ``services.lifecycle``); never mutate directly outside that service.
    status = Column(String(40), default="Draft", nullable=False)

    business_object = relationship(
        "BusinessObject",
        foreign_keys=[object_id],
        back_populates="revisions",
    )
    property_values = relationship(
        "PropertyValue",
        back_populates="revision",
        cascade="all, delete-orphan",
    )
    release_states = relationship(
        "RevisionReleaseState",
        back_populates="revision",
        cascade="all, delete-orphan",
        # selectin avoids an N+1 when list/show render the status badge.
        lazy="selectin",
    )
    datasets = relationship(
        "Dataset", back_populates="revision", cascade="all, delete-orphan"
    )

    @property
    def release_state_name(self) -> str:
        """Canonical current lifecycle state name.

        Mirrors ``services.lifecycle.current_state_name`` without importing the
        service (which would be circular). The denormalised ``status`` column is
        the fallback when the revision has no release-state assignment.
        """
        if not self.release_states:
            return self.status or "Draft"
        latest = max(
            self.release_states,
            key=lambda rel: (rel.assigned_on, rel.release_state_id),
        )
        return latest.release_state.name

    @renders("status")
    def release_state_badge(self):
        """Coloured, labelled lifecycle badge for FAB list/show columns."""
        # Local import avoids a models <-> services circular import. The label
        # map lives with the state constants in services.lifecycle.
        from .services.lifecycle import STATE_LABELS

        state = self.release_state_name
        css = STATE_LABELS.get(state, "label-default")
        return Markup(f'<span class="label {css}">{escape(state)}</span>')

    def __repr__(self) -> str:
        number = self.business_object.object_number if self.business_object else self.object_id
        return f"{number}/{self.revision_id}"


class RevisionLineage(Model):
    """Directed edge in a revision chain (``A -> B -> C``)."""

    __tablename__ = "revision_lineage"

    parent_revision_id = Column(
        Integer, ForeignKey("revision.id"), primary_key=True
    )
    child_revision_id = Column(
        Integer, ForeignKey("revision.id"), primary_key=True
    )
    created_on = Column(DateTime, default=utcnow, nullable=False)

    parent_revision = relationship(
        "Revision", foreign_keys=[parent_revision_id], backref="child_links"
    )
    child_revision = relationship(
        "Revision", foreign_keys=[child_revision_id], backref="parent_links"
    )

    def __repr__(self) -> str:
        return f"{self.parent_revision_id} -> {self.child_revision_id}"


# ---------------------------------------------------------------------------
# Property model
# ---------------------------------------------------------------------------


class PropertyDefinition(TimestampMixin, Model):
    """Metadata describing a business property on an object type."""

    __tablename__ = "property_definition"
    __table_args__ = (
        UniqueConstraint(
            "object_type_id", "name", name="uq_propdef_type_name"
        ),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    object_type_id = Column(
        Integer, ForeignKey("object_type.id"), nullable=False, index=True
    )
    data_type = Column(
        SAEnum(
            PropertyDataType,
            native_enum=False,
            length=32,
        ),
        default=PropertyDataType.STRING,
        nullable=False,
    )
    mandatory = Column(Boolean, default=False, nullable=False)
    multi_value = Column(Boolean, default=False, nullable=False)
    description = Column(Text)

    object_type = relationship(
        "ObjectType", back_populates="property_definitions"
    )
    values = relationship(
        "PropertyValue",
        back_populates="property_definition",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"{self.object_type.name}.{self.name}"


class PropertyValue(TimestampMixin, Model):
    """Stores a single business data value against a revision."""

    __tablename__ = "property_value"
    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "property_definition_id",
            "sequence_no",
            name="uq_propvalue_rev_def_seq",
        ),
    )

    id = Column(Integer, primary_key=True)
    revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    property_definition_id = Column(
        Integer, ForeignKey("property_definition.id"), nullable=False, index=True
    )
    string_value = Column(Text)
    integer_value = Column(Integer)
    float_value = Column(Float)
    date_value = Column(Date)
    sequence_no = Column(Integer, default=1, nullable=False)

    revision = relationship("Revision", back_populates="property_values")
    property_definition = relationship(
        "PropertyDefinition", back_populates="values"
    )

    def __repr__(self) -> str:
        value = (
            self.string_value
            if self.string_value is not None
            else self.integer_value
            if self.integer_value is not None
            else self.float_value
            if self.float_value is not None
            else self.date_value
        )
        return f"{self.property_definition.name}={value}"


# ---------------------------------------------------------------------------
# Relationship model
# ---------------------------------------------------------------------------


class RelationshipType(TimestampMixin, Model):
    """Named, typed link between revisions (e.g. ``VERIFIED_BY``)."""

    __tablename__ = "relationship_type"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(Text)

    relationships = relationship(
        "Relationship", back_populates="relationship_type"
    )

    def __repr__(self) -> str:
        return self.name


class Relationship(TimestampMixin, Model):
    """Traceability edge: ``primary`` --type--> ``secondary``."""

    __tablename__ = "relationship"
    __table_args__ = (
        UniqueConstraint(
            "relationship_type_id",
            "primary_revision_id",
            "secondary_revision_id",
            name="uq_relationship_type_primary_secondary",
        ),
    )

    id = Column(Integer, primary_key=True)
    relationship_type_id = Column(
        Integer, ForeignKey("relationship_type.id"), nullable=False, index=True
    )
    primary_revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    secondary_revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )

    relationship_type = relationship(
        "RelationshipType", back_populates="relationships"
    )
    primary_revision = relationship(
        "Revision",
        foreign_keys=[primary_revision_id],
        backref="outgoing_relationships",
    )
    secondary_revision = relationship(
        "Revision",
        foreign_keys=[secondary_revision_id],
        backref="incoming_relationships",
    )

    def __repr__(self) -> str:
        return f"{self.primary_revision} {self.relationship_type} {self.secondary_revision}"


# ---------------------------------------------------------------------------
# BOM model
# ---------------------------------------------------------------------------


class BOMOccurrence(TimestampMixin, Model):
    """A parent/child occurrence in a bill of materials."""

    __tablename__ = "bom_occurrence"
    __table_args__ = (
        UniqueConstraint(
            "parent_revision_id", "find_number", name="uq_bom_parent_find"
        ),
    )

    id = Column(Integer, primary_key=True)
    parent_revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    child_revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    find_number = Column(String(40))
    quantity = Column(Float, default=1.0, nullable=False)

    parent_revision = relationship(
        "Revision", foreign_keys=[parent_revision_id], backref="bom_lines"
    )
    child_revision = relationship(
        "Revision", foreign_keys=[child_revision_id], backref="used_in"
    )
    traces = relationship(
        "OccurrenceTrace",
        back_populates="bom_occurrence",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"{self.parent_revision} -> {self.child_revision} (x{self.quantity})"


class OccurrenceTrace(Model):
    """Links a requirement revision to a BOM occurrence."""

    __tablename__ = "occurrence_trace"
    __table_args__ = (
        UniqueConstraint(
            "requirement_revision_id",
            "bom_occurrence_id",
            name="uq_occurrence_trace_req_occ",
        ),
    )

    id = Column(Integer, primary_key=True)
    requirement_revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    bom_occurrence_id = Column(
        Integer, ForeignKey("bom_occurrence.id"), nullable=False, index=True
    )
    created_on = Column(DateTime, default=utcnow, nullable=False)

    requirement_revision = relationship(
        "Revision", foreign_keys=[requirement_revision_id]
    )
    bom_occurrence = relationship(
        "BOMOccurrence", back_populates="traces"
    )

    def __repr__(self) -> str:
        return f"{self.requirement_revision} @ {self.bom_occurrence}"


# ---------------------------------------------------------------------------
# Configuration management
# ---------------------------------------------------------------------------


class RevisionRule(TimestampMixin, Model):
    """Rule selecting which revision of each object to configure."""

    __tablename__ = "revision_rule"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text)

    configuration_contexts = relationship(
        "ConfigurationContext", back_populates="revision_rule"
    )

    def __repr__(self) -> str:
        return self.name


class ConfigurationContext(TimestampMixin, Model):
    """A named application of a revision rule."""

    __tablename__ = "configuration_context"

    id = Column(Integer, primary_key=True)
    revision_rule_id = Column(
        Integer, ForeignKey("revision_rule.id"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False)
    description = Column(Text)

    revision_rule = relationship(
        "RevisionRule", back_populates="configuration_contexts"
    )
    baselines = relationship(
        "Baseline",
        back_populates="configuration_context",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return self.name


class Baseline(TimestampMixin, Model):
    """Frozen configuration captured from a context."""

    __tablename__ = "baseline"

    id = Column(Integer, primary_key=True)
    configuration_context_id = Column(
        Integer, ForeignKey("configuration_context.id"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False)
    description = Column(Text)

    configuration_context = relationship(
        "ConfigurationContext", back_populates="baselines"
    )
    members = relationship(
        "BaselineMember",
        back_populates="baseline",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return self.name


class BaselineMember(Model):
    """A revision captured by a baseline."""

    __tablename__ = "baseline_member"

    baseline_id = Column(
        Integer, ForeignKey("baseline.id"), primary_key=True
    )
    revision_id = Column(
        Integer, ForeignKey("revision.id"), primary_key=True, index=True
    )
    created_on = Column(DateTime, default=utcnow, nullable=False)

    baseline = relationship("Baseline", back_populates="members")
    revision = relationship("Revision", backref="baseline_memberships")

    def __repr__(self) -> str:
        return f"{self.baseline} <{self.revision}>"


# ---------------------------------------------------------------------------
# Dataset model
# ---------------------------------------------------------------------------


class Dataset(TimestampMixin, Model):
    """A named collection of managed files attached to a revision."""

    __tablename__ = "dataset"

    id = Column(Integer, primary_key=True)
    revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    dataset_type = Column(String(80))
    name = Column(String(255), nullable=False)

    revision = relationship("Revision", back_populates="datasets")
    files = relationship(
        "ManagedFile",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return self.name


class ManagedFile(TimestampMixin, Model):
    """A physical file stored behind a dataset."""

    __tablename__ = "managed_file"

    id = Column(Integer, primary_key=True)
    dataset_id = Column(
        Integer, ForeignKey("dataset.id"), nullable=False, index=True
    )
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(120))
    storage_path = Column(Text)
    file_size = Column(Integer)

    dataset = relationship("Dataset", back_populates="files")

    def __repr__(self) -> str:
        return self.file_name


# ---------------------------------------------------------------------------
# Release lifecycle
# ---------------------------------------------------------------------------


class ReleaseState(TimestampMixin, Model):
    """A lifecycle state (Draft, Review, Approved, Released, Obsolete)."""

    __tablename__ = "release_state"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(Text)

    revision_states = relationship(
        "RevisionReleaseState",
        back_populates="release_state",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return self.name


class RevisionReleaseState(Model):
    """Assignment of a release state to a revision."""

    __tablename__ = "revision_release_state"

    revision_id = Column(
        Integer, ForeignKey("revision.id"), primary_key=True
    )
    release_state_id = Column(
        Integer, ForeignKey("release_state.id"), primary_key=True, index=True
    )
    assigned_on = Column(DateTime, default=utcnow, nullable=False)

    revision = relationship("Revision", back_populates="release_states")
    release_state = relationship(
        "ReleaseState", back_populates="revision_states", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"{self.revision} = {self.release_state}"


# ---------------------------------------------------------------------------
# Verification model
# ---------------------------------------------------------------------------


class VerificationResult(TimestampMixin, Model):
    """Outcome of executing a test revision."""

    __tablename__ = "verification_result"

    id = Column(Integer, primary_key=True)
    test_revision_id = Column(
        Integer, ForeignKey("revision.id"), nullable=False, index=True
    )
    execution_date = Column(Date)
    result = Column(String(40))
    summary = Column(Text)

    test_revision = relationship(
        "Revision", foreign_keys=[test_revision_id], backref="verification_results"
    )

    def __repr__(self) -> str:
        return f"{self.test_revision}: {self.result}"


# ---------------------------------------------------------------------------
# Workflow model
# ---------------------------------------------------------------------------


class WorkflowProcess(TimestampMixin, Model):
    """A workflow process instance."""

    __tablename__ = "workflow_process"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    state = Column(String(40), default="Not Started", nullable=False)
    started_on = Column(DateTime)
    completed_on = Column(DateTime)

    tasks = relationship(
        "WorkflowTask",
        back_populates="workflow_process",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"{self.name} [{self.state}]"


class WorkflowTask(TimestampMixin, Model):
    """A single task within a workflow process."""

    __tablename__ = "workflow_task"

    id = Column(Integer, primary_key=True)
    process_id = Column(
        Integer, ForeignKey("workflow_process.id"), nullable=False, index=True
    )
    revision_id = Column(Integer, ForeignKey("revision.id"), index=True)
    task_name = Column(String(255), nullable=False)
    task_state = Column(String(40), default="Open", nullable=False)
    due_date = Column(Date)

    workflow_process = relationship(
        "WorkflowProcess", back_populates="tasks"
    )
    revision = relationship("Revision", backref="workflow_tasks")

    def __repr__(self) -> str:
        return f"{self.task_name} [{self.task_state}]"
