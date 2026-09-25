"""Flask-AppBuilder views for the PLMSys domain model.

Bootstraps one ``ModelView`` per domain entity, grouped into menu categories.
Views stay thin: revision/lifecycle actions delegate to ``app/services`` via
``app.view_mixins``; other entities provide CRUD over the scaffold.
"""

import re

from flask import g
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.filters import FilterEqual
from flask_appbuilder.models.sqla.interface import SQLAInterface
from sqlalchemy import inspect as sa_inspect
from wtforms import BooleanField
from wtforms.validators import Optional

from .extensions import db

from .models import (
    BOMOccurrence,
    Baseline,
    BaselineMember,
    BusinessObject,
    ConfigurationContext,
    Dataset,
    ManagedFile,
    ObjectType,
    OccurrenceTrace,
    PropertyDefinition,
    PropertyValue,
    Relationship,
    RelationshipType,
    ReleaseState,
    Revision,
    RevisionLineage,
    RevisionReleaseState,
    RevisionRule,
    VerificationResult,
    WorkflowProcess,
    WorkflowTask,
)
from .services import ServiceError, lifecycle
from .ui.properties import PropertyMatrixView, RevisionPropertiesView
from .ui.traceability import (
    DeriveRequirementView,
    RelationFormView,
    RevisionRelationsView,
    TraceabilityMatrixView,
)
from .view_mixins import CreateRevisionMixin, RevisionLifecycleMixin


# Property names become WTForms field names in the dynamic property form, so
# they must be lower-case identifiers and must not collide with WTForms' own
# attributes (plan §3.3).
_PROPERTY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RESERVED_WTFORMS_NAMES = frozenset(
    {"data", "errors", "meta", "validate", "csrf_token", "process"}
)


# ---------------------------------------------------------------------------
# Meta model
# ---------------------------------------------------------------------------


class ObjectTypeModelView(ModelView):
    datamodel = SQLAInterface(ObjectType)
    list_columns = ["name", "parent_type", "description"]
    show_columns = ["name", "parent_type", "subtypes", "description", "created_on"]
    add_columns = ["name", "parent_type", "description"]
    edit_columns = ["name", "parent_type", "description"]
    search_columns = ["name", "description"]
    order_columns = ["name"]
    label_columns = {"parent_type": "Parent Type", "subtypes": "Sub Types"}


class PropertyDefinitionModelView(ModelView):
    datamodel = SQLAInterface(PropertyDefinition)
    list_columns = ["object_type", "name", "data_type", "mandatory", "multi_value"]
    show_columns = [
        "object_type",
        "name",
        "data_type",
        "mandatory",
        "multi_value",
        "description",
    ]
    add_columns = ["object_type", "name", "data_type", "mandatory", "multi_value", "description"]
    edit_columns = ["object_type", "name", "data_type", "mandatory", "multi_value", "description"]
    search_columns = ["name"]
    order_columns = ["object_type", "name"]
    # Non-nullable booleans are generated as `required` checkboxes by FAB, so a
    # false value can never be submitted. Override them as optional booleans.
    add_form_extra_fields = {
        "mandatory": BooleanField("Mandatory", validators=[Optional()]),
        "multi_value": BooleanField("Multi Value", validators=[Optional()]),
    }
    edit_form_extra_fields = {
        "mandatory": BooleanField("Mandatory", validators=[Optional()]),
        "multi_value": BooleanField("Multi Value", validators=[Optional()]),
    }
    label_columns = {
        "object_type": "Object Type",
        "data_type": "Data Type",
        "mandatory": "Mandatory",
        "multi_value": "Multi Value",
    }

    def pre_add(self, item):
        self._validate_name(item)

    def pre_update(self, item):
        self._validate_name(item)
        self._lock_existing(item)

    def _validate_name(self, item):
        if not _PROPERTY_NAME_RE.match(item.name or ""):
            self._reject(
                "Property name must match ^[a-z][a-z0-9_]*$ "
                "(lower-case, with digits and underscores)"
            )
        if item.name in _RESERVED_WTFORMS_NAMES:
            self._reject(f"Property name {item.name!r} is reserved by WTForms")

    @staticmethod
    def _reject(message):
        # FAB flashes the exception but does not roll back; discard the pending
        # change so a later autoflush cannot persist a rejected edit.
        db.session.rollback()
        raise Exception(message)

    def _lock_existing(self, item):
        """Block changes that would invalidate stored values.

        ``pre_update`` runs after ``form.populate_obj``, so the old value is
        read from SQLAlchemy's attribute history rather than the instance.
        """
        if item.id is None:
            return
        changed = [
            attribute
            for attribute in ("data_type", "object_type_id", "multi_value")
            if sa_inspect(item).attrs[attribute].history.has_changes()
        ]
        if not changed:
            return
        with db.session.no_autoflush:
            has_values = (
                db.session.query(PropertyValue.id)
                .filter_by(property_definition_id=item.id)
                .first()
                is not None
            )
        if has_values:
            self._reject(
                "Cannot change "
                + ", ".join(changed)
                + " while property values exist"
            )


class RelationshipTypeModelView(ModelView):
    datamodel = SQLAInterface(RelationshipType)
    list_columns = ["name", "description"]
    add_columns = ["name", "description"]
    edit_columns = ["name", "description"]
    search_columns = ["name", "description"]
    order_columns = ["name"]


# ---------------------------------------------------------------------------
# Objects & revisions
# ---------------------------------------------------------------------------


class RevisionModelView(RevisionLifecycleMixin, ModelView):
    datamodel = SQLAInterface(Revision)
    # `can_add` is intentionally omitted: revisions are created through the
    # "Create Revision" action so lineage and lifecycle are always recorded.
    base_permissions = ["can_list", "can_show", "can_edit", "can_delete"]
    list_columns = [
        "business_object",
        "revision_id",
        "sequence_no",
        "title",
        "release_state_badge",
    ]
    show_columns = [
        "business_object",
        "revision_id",
        "sequence_no",
        "title",
        "description",
        "release_state_badge",
        "created_on",
        "modified_on",
    ]
    add_columns = ["business_object", "revision_id", "sequence_no", "title", "description"]
    edit_columns = ["title", "description"]
    search_columns = ["revision_id", "title", "status"]
    order_columns = ["business_object", "sequence_no"]
    label_columns = {
        "business_object": "Business Object",
        "revision_id": "Revision",
        "sequence_no": "Sequence",
        "release_state_badge": "Status",
    }


class BusinessObjectModelView(CreateRevisionMixin, ModelView):
    datamodel = SQLAInterface(BusinessObject)
    related_views = [RevisionModelView]
    list_columns = [
        "object_number",
        "name",
        "object_type",
        "current_revision",
        "status",
        "modified_on",
    ]
    show_columns = [
        "object_number",
        "name",
        "object_type",
        "description",
        "current_revision",
        "status",
        "created_on",
        "modified_on",
    ]
    # Object identity/type are fixed at creation: changing object_type would
    # orphan property values (definitions are per type), and current_revision is
    # managed by the "Create Revision"/"Set Current Revision" actions.
    add_columns = [
        "object_type",
        "object_number",
        "name",
        "description",
    ]
    edit_columns = [
        "name",
        "description",
    ]
    search_columns = ["object_number", "name", "status"]
    order_columns = ["object_number"]
    label_columns = {
        "object_number": "Object Number",
        "object_type": "Object Type",
        "current_revision": "Current Revision",
    }


class RequirementModelView(CreateRevisionMixin, ModelView):
    """Business objects whose type is ``Requirement``."""

    datamodel = SQLAInterface(BusinessObject)
    base_filters = [["object_type.name", FilterEqual, "Requirement"]]
    list_columns = [
        "object_number",
        "name",
        "current_revision",
        "status",
        "modified_on",
    ]
    show_columns = [
        "object_number",
        "name",
        "description",
        "current_revision",
        "status",
        "created_on",
        "modified_on",
    ]
    search_columns = ["object_number", "name", "status"]
    order_columns = ["object_number"]
    # object_type is forced to Requirement in pre_add, so it is not editable and
    # a requirement cannot be silently retyped out of this filtered view.
    add_columns = [
        "object_number",
        "name",
        "description",
    ]
    edit_columns = [
        "name",
        "description",
    ]
    label_columns = {
        "object_number": "Requirement Number",
        "current_revision": "Current Revision",
    }

    def pre_add(self, item):
        item.object_type = (
            db.session.query(ObjectType)
            .filter_by(name="Requirement")
            .one()
        )


class RevisionLineageModelView(ModelView):
    datamodel = SQLAInterface(RevisionLineage)
    list_columns = ["parent_revision", "child_revision", "created_on"]
    add_columns = ["parent_revision", "child_revision"]
    edit_columns = ["parent_revision", "child_revision"]
    order_columns = ["parent_revision"]
    label_columns = {"parent_revision": "Parent", "child_revision": "Child"}


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class PropertyValueModelView(ModelView):
    """Read-only raw values.

    Every write must go through ``services.properties`` (the dynamic property
    form) so coercion, mandatory and multi-value rules are applied — an
    editable view here would bypass them and could store a value in the wrong
    typed column.
    """

    datamodel = SQLAInterface(PropertyValue)
    base_permissions = ["can_list", "can_show"]
    list_columns = [
        "revision",
        "property_definition",
        "string_value",
        "integer_value",
        "float_value",
        "date_value",
        "sequence_no",
    ]
    show_columns = [
        "revision",
        "property_definition",
        "string_value",
        "integer_value",
        "float_value",
        "date_value",
        "sequence_no",
        "created_on",
        "modified_on",
    ]
    search_columns = ["string_value", "sequence_no"]
    order_columns = ["revision", "property_definition"]
    label_columns = {
        "property_definition": "Property",
        "string_value": "Value",
        "integer_value": "Integer",
        "float_value": "Float",
        "date_value": "Date",
        "sequence_no": "Seq.",
    }


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


class RelationshipModelView(ModelView):
    """Read-only list of trace links.

    Links are created through ``services.relationships`` (the relation forms);
    an editable view here would bypass the duplicate/self guards and the new
    unique constraint would surface as a 500.
    """

    datamodel = SQLAInterface(Relationship)
    base_permissions = ["can_list", "can_show"]
    list_columns = [
        "relationship_type",
        "primary_revision",
        "secondary_revision",
        "modified_on",
    ]
    show_columns = [
        "relationship_type",
        "primary_revision",
        "secondary_revision",
        "created_on",
        "modified_on",
    ]
    search_columns = ["relationship_type", "primary_revision", "secondary_revision"]
    order_columns = ["relationship_type"]
    label_columns = {
        "relationship_type": "Type",
        "primary_revision": "Primary",
        "secondary_revision": "Secondary",
    }


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------


class BOMOccurrenceModelView(ModelView):
    datamodel = SQLAInterface(BOMOccurrence)
    list_columns = [
        "parent_revision",
        "child_revision",
        "find_number",
        "quantity",
    ]
    show_columns = [
        "parent_revision",
        "child_revision",
        "find_number",
        "quantity",
        "created_on",
    ]
    add_columns = ["parent_revision", "child_revision", "find_number", "quantity"]
    edit_columns = ["parent_revision", "child_revision", "find_number", "quantity"]
    order_columns = ["parent_revision", "find_number"]
    label_columns = {
        "parent_revision": "Parent",
        "child_revision": "Child",
        "find_number": "Find No.",
    }


class OccurrenceTraceModelView(ModelView):
    datamodel = SQLAInterface(OccurrenceTrace)
    list_columns = ["requirement_revision", "bom_occurrence", "created_on"]
    add_columns = ["requirement_revision", "bom_occurrence"]
    edit_columns = ["requirement_revision", "bom_occurrence"]
    order_columns = ["requirement_revision"]
    label_columns = {
        "requirement_revision": "Requirement",
        "bom_occurrence": "BOM Occurrence",
    }


# ---------------------------------------------------------------------------
# Configuration management
# ---------------------------------------------------------------------------


class RevisionRuleModelView(ModelView):
    datamodel = SQLAInterface(RevisionRule)
    list_columns = ["name", "description"]
    add_columns = ["name", "description"]
    edit_columns = ["name", "description"]
    search_columns = ["name", "description"]
    order_columns = ["name"]


class ConfigurationContextModelView(ModelView):
    datamodel = SQLAInterface(ConfigurationContext)
    list_columns = ["name", "revision_rule", "description"]
    show_columns = ["name", "revision_rule", "description", "created_on"]
    add_columns = ["name", "revision_rule", "description"]
    edit_columns = ["name", "revision_rule", "description"]
    search_columns = ["name"]
    order_columns = ["name"]
    label_columns = {"revision_rule": "Revision Rule"}


class BaselineModelView(ModelView):
    datamodel = SQLAInterface(Baseline)
    related_views = []
    list_columns = ["name", "configuration_context", "description"]
    show_columns = [
        "name",
        "configuration_context",
        "description",
        "created_on",
    ]
    add_columns = ["name", "configuration_context", "description"]
    edit_columns = ["name", "configuration_context", "description"]
    search_columns = ["name"]
    order_columns = ["name"]
    label_columns = {"configuration_context": "Configuration Context"}


class BaselineMemberModelView(ModelView):
    datamodel = SQLAInterface(BaselineMember)
    list_columns = ["baseline", "revision", "created_on"]
    add_columns = ["baseline", "revision"]
    edit_columns = ["baseline", "revision"]
    order_columns = ["baseline", "revision"]

    def pre_add(self, item):
        """Only released revisions may enter a baseline (Phase 2 guard)."""
        self._ensure_released(item)

    def pre_update(self, item):
        self._ensure_released(item)

    @staticmethod
    def _ensure_released(item):
        try:
            lifecycle.ensure_released(item.revision)
        except ServiceError:
            # A rejected pre_add item is transient; unhook it so a later
            # autoflush cannot cascade it. Never mutate a persistent row.
            if item not in db.session:
                item.revision = None
                item.baseline = None
            raise


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


class ManagedFileModelView(ModelView):
    datamodel = SQLAInterface(ManagedFile)
    list_columns = ["file_name", "dataset", "mime_type", "file_size"]
    show_columns = [
        "file_name",
        "dataset",
        "mime_type",
        "storage_path",
        "file_size",
        "created_on",
    ]
    add_columns = ["dataset", "file_name", "mime_type", "storage_path", "file_size"]
    edit_columns = ["dataset", "file_name", "mime_type", "storage_path", "file_size"]
    search_columns = ["file_name", "mime_type"]
    order_columns = ["file_name"]
    label_columns = {
        "file_name": "File Name",
        "mime_type": "MIME Type",
        "storage_path": "Storage Path",
        "file_size": "Size",
    }


class DatasetModelView(ModelView):
    datamodel = SQLAInterface(Dataset)
    related_views = [ManagedFileModelView]
    list_columns = ["name", "dataset_type", "revision"]
    show_columns = ["name", "dataset_type", "revision", "created_on"]
    add_columns = ["revision", "dataset_type", "name"]
    edit_columns = ["revision", "dataset_type", "name"]
    search_columns = ["name", "dataset_type"]
    order_columns = ["name"]
    label_columns = {"dataset_type": "Type", "revision": "Revision"}


# ---------------------------------------------------------------------------
# Release lifecycle
# ---------------------------------------------------------------------------


class ReleaseStateModelView(ModelView):
    datamodel = SQLAInterface(ReleaseState)
    list_columns = ["name", "description"]
    add_columns = ["name", "description"]
    edit_columns = ["name", "description"]
    search_columns = ["name"]
    order_columns = ["name"]


class RevisionReleaseStateModelView(ModelView):
    """Read-only state history.

    Assignments must go through ``services.lifecycle`` (the revision actions)
    so the status cache stays in sync; an editable view here would bypass the
    state machine and re-introduce drift.
    """

    datamodel = SQLAInterface(RevisionReleaseState)
    base_permissions = ["can_list", "can_show"]
    list_columns = ["revision", "release_state", "assigned_on"]
    order_columns = ["revision"]
    label_columns = {
        "release_state": "Release State",
        "assigned_on": "Assigned On",
    }


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


class VerificationResultModelView(ModelView):
    datamodel = SQLAInterface(VerificationResult)
    list_columns = ["test_revision", "execution_date", "result", "summary"]
    show_columns = [
        "test_revision",
        "execution_date",
        "result",
        "summary",
        "created_on",
    ]
    add_columns = ["test_revision", "execution_date", "result", "summary"]
    edit_columns = ["test_revision", "execution_date", "result", "summary"]
    search_columns = ["result", "summary"]
    order_columns = ["execution_date"]
    label_columns = {
        "test_revision": "Test Revision",
        "execution_date": "Execution Date",
    }


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class WorkflowTaskModelView(ModelView):
    datamodel = SQLAInterface(WorkflowTask)
    list_columns = ["task_name", "workflow_process", "revision", "task_state", "due_date"]
    show_columns = [
        "task_name",
        "workflow_process",
        "revision",
        "task_state",
        "due_date",
        "created_on",
    ]
    add_columns = ["workflow_process", "revision", "task_name", "task_state", "due_date"]
    edit_columns = ["workflow_process", "revision", "task_name", "task_state", "due_date"]
    search_columns = ["task_name", "task_state"]
    order_columns = ["task_name"]
    label_columns = {
        "task_name": "Task",
        "workflow_process": "Process",
        "task_state": "State",
        "due_date": "Due Date",
    }


class WorkflowProcessModelView(ModelView):
    datamodel = SQLAInterface(WorkflowProcess)
    related_views = [WorkflowTaskModelView]
    list_columns = ["name", "state", "started_on", "completed_on"]
    show_columns = ["name", "state", "started_on", "completed_on", "created_on"]
    add_columns = ["name", "state", "started_on", "completed_on"]
    edit_columns = ["name", "state", "started_on", "completed_on"]
    search_columns = ["name", "state"]
    order_columns = ["name"]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _is_admin() -> bool:
    """Menu guard: show administration items only to administrators.

    Used as ``menu_cond`` on the Setup views. The custom shell evaluates
    ``MenuItem.should_render()`` (which invokes this) in addition to FAB's
    ``menu_access`` permission check, so this is defence in depth: the Setup
    *routes* are already protected by FAB permissions (non-admins receive 403),
    and this keeps the menu itself free of the heading for non-admins.
    """
    try:
        return bool(
            g.user
            and g.user.is_authenticated
            and any(role.name == "Admin" for role in g.user.roles)
        )
    except Exception:
        return False


def register_views(appbuilder) -> None:
    """Register views under the task-oriented navigation.

    Operational entities are grouped by business domain (see
    ``docs/ui_plan.md`` §6.2). Meta-model and link tables live under the
    admin-only "Setup" category.
    """
    # Products
    appbuilder.add_view(
        BusinessObjectModelView,
        "Business Objects",
        icon="fa-cube",
        category="Products",
        category_icon="fa-cube",
    )
    appbuilder.add_view(
        RevisionModelView,
        "Revisions",
        icon="fa-code-fork",
        category="Products",
    )

    # Requirements
    appbuilder.add_view(
        RequirementModelView,
        "Requirements",
        icon="fa-list-alt",
        category="Requirements",
        category_icon="fa-list-alt",
    )
    appbuilder.add_view(
        PropertyMatrixView,
        "Property Matrix",
        icon="fa-table",
        category="Requirements",
    )
    appbuilder.add_view(
        TraceabilityMatrixView,
        "Traceability Matrix",
        icon="fa-sitemap",
        category="Requirements",
    )
    # Reached from revision actions; no menu entries.
    appbuilder.add_view_no_menu(RevisionPropertiesView)
    appbuilder.add_view_no_menu(RevisionRelationsView)
    appbuilder.add_view_no_menu(RelationFormView)
    appbuilder.add_view_no_menu(DeriveRequirementView)

    # BOM
    appbuilder.add_view(
        BOMOccurrenceModelView,
        "BOM Occurrences",
        icon="fa-sitemap",
        category="BOM",
        category_icon="fa-sitemap",
    )
    appbuilder.add_view(
        OccurrenceTraceModelView,
        "Occurrence Traces",
        icon="fa-crosshairs",
        category="BOM",
    )

    # Documents / datasets
    appbuilder.add_view(
        DatasetModelView,
        "Datasets",
        icon="fa-folder-open",
        category="Documents",
        category_icon="fa-file",
    )
    appbuilder.add_view(
        ManagedFileModelView,
        "Managed Files",
        icon="fa-file-o",
        category="Documents",
    )

    # Verification
    appbuilder.add_view(
        VerificationResultModelView,
        "Verification Results",
        icon="fa-flask",
        category="Verification",
        category_icon="fa-flask",
    )

    # Configuration management
    appbuilder.add_view(
        ConfigurationContextModelView,
        "Configuration Contexts",
        icon="fa-sliders",
        category="Configuration",
        category_icon="fa-random",
    )
    appbuilder.add_view(
        BaselineModelView,
        "Baselines",
        icon="fa-flag-checkered",
        category="Configuration",
    )

    # Workflow
    appbuilder.add_view(
        WorkflowProcessModelView,
        "Workflow Processes",
        icon="fa-tasks",
        category="Workflow",
        category_icon="fa-tasks",
    )
    appbuilder.add_view(
        WorkflowTaskModelView,
        "Workflow Tasks",
        icon="fa-check-square",
        category="Workflow",
    )

    # Setup (administrators only): meta-model and link tables
    setup = dict(category="Setup", category_icon="fa-cogs", menu_cond=_is_admin)
    appbuilder.add_view(
        ObjectTypeModelView, "Object Types", icon="fa-sitemap", **setup
    )
    appbuilder.add_view(
        PropertyDefinitionModelView,
        "Property Definitions",
        icon="fa-tags",
        **setup,
    )
    appbuilder.add_view(
        RelationshipTypeModelView,
        "Relationship Types",
        icon="fa-random",
        **setup,
    )
    appbuilder.add_view(
        RelationshipModelView, "Relationships", icon="fa-link", **setup
    )
    appbuilder.add_view(
        RevisionRuleModelView, "Revision Rules", icon="fa-filter", **setup
    )
    appbuilder.add_view(
        ReleaseStateModelView,
        "Release States",
        icon="fa-check-circle",
        **setup,
    )
    appbuilder.add_view(
        RevisionLineageModelView, "Revision Lineage", icon="fa-chain", **setup
    )
    appbuilder.add_view(
        PropertyValueModelView, "Property Values", icon="fa-tag", **setup
    )
    appbuilder.add_view(
        BaselineMemberModelView,
        "Baseline Members",
        icon="fa-flag-o",
        **setup,
    )
    appbuilder.add_view(
        RevisionReleaseStateModelView,
        "Revision Release States",
        icon="fa-check-square-o",
        **setup,
    )
