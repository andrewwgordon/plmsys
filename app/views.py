"""Flask-AppBuilder views for the PLMSys domain model.

Bootstraps one ``ModelView`` per domain entity, grouped into menu categories.
Business logic (revision creation, workflow transitions, etc.) is intentionally
out of scope here -- these views provide initial CRUD over the scaffold.
"""

from flask import g
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.filters import FilterEqual
from flask_appbuilder.models.sqla.interface import SQLAInterface

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
    label_columns = {
        "object_type": "Object Type",
        "data_type": "Data Type",
        "mandatory": "Mandatory",
        "multi_value": "Multi Value",
    }


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


class RevisionModelView(ModelView):
    datamodel = SQLAInterface(Revision)
    list_columns = [
        "business_object",
        "revision_id",
        "sequence_no",
        "title",
        "status",
    ]
    show_columns = [
        "business_object",
        "revision_id",
        "sequence_no",
        "title",
        "description",
        "status",
        "created_on",
        "modified_on",
    ]
    add_columns = ["business_object", "revision_id", "sequence_no", "title", "description", "status"]
    edit_columns = ["business_object", "revision_id", "sequence_no", "title", "description", "status"]
    search_columns = ["revision_id", "title", "status"]
    order_columns = ["business_object", "sequence_no"]
    label_columns = {
        "business_object": "Business Object",
        "revision_id": "Revision",
        "sequence_no": "Sequence",
    }


class BusinessObjectModelView(ModelView):
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
    add_columns = [
        "object_type",
        "object_number",
        "name",
        "description",
        "current_revision",
        "status",
    ]
    edit_columns = [
        "object_type",
        "object_number",
        "name",
        "description",
        "current_revision",
        "status",
    ]
    search_columns = ["object_number", "name", "status"]
    order_columns = ["object_number"]
    label_columns = {
        "object_number": "Object Number",
        "object_type": "Object Type",
        "current_revision": "Current Revision",
    }


class RequirementModelView(ModelView):
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
    label_columns = {
        "object_number": "Requirement Number",
        "current_revision": "Current Revision",
    }


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
    datamodel = SQLAInterface(PropertyValue)
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
    add_columns = [
        "revision",
        "property_definition",
        "string_value",
        "integer_value",
        "float_value",
        "date_value",
        "sequence_no",
    ]
    edit_columns = [
        "revision",
        "property_definition",
        "string_value",
        "integer_value",
        "float_value",
        "date_value",
        "sequence_no",
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
    datamodel = SQLAInterface(Relationship)
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
    add_columns = ["relationship_type", "primary_revision", "secondary_revision"]
    edit_columns = ["relationship_type", "primary_revision", "secondary_revision"]
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
    datamodel = SQLAInterface(RevisionReleaseState)
    list_columns = ["revision", "release_state", "assigned_on"]
    add_columns = ["revision", "release_state", "assigned_on"]
    edit_columns = ["revision", "release_state", "assigned_on"]
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

    # Relationships
    appbuilder.add_view(
        RelationshipModelView,
        "Relationships",
        icon="fa-link",
        category="Relationships",
        category_icon="fa-link",
    )

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
