# Teamcenter-Inspired Domain Model for Flask-AppBuilder / SQLAlchemy

## Purpose

This specification defines a Teamcenter-inspired, database-agnostic domain model optimized for:

- Flask-AppBuilder
- SQLAlchemy
- SQLite / PostgreSQL / MySQL
- Requirements Engineering
- Systems Engineering
- Product Lifecycle Management (PLM)
- Digital Thread Traceability

Excluded from the model:

- Users
- Roles
- Permissions
- Authentication
- Authorization
- ACLs

These concerns are assumed to be managed by Flask-AppBuilder Security Manager.

---

# Design Principles

## Object-Centric Architecture

All business entities are represented using a common object model:

```text
ObjectType
    |
BusinessObject
    |
Revision
    |
Properties
    |
Relationships
```

## Revision-Controlled Data

Business objects represent stable identities.

Revisions represent versioned content.

## Metadata-Driven Properties

Business data is primarily stored via configurable property definitions and values.

## Relationship-Driven Traceability

Traceability is implemented through relationship objects.

---

# Core Meta-Model

## ObjectType

Represents a Teamcenter-style business object definition.

Fields:

- id (PK)
- name
- parent_type_id
- description

Examples:

- Requirement
- RequirementRevision
- Part
- PartRevision
- TestCase
- TestCaseRevision
- ChangeRequest
- Document

---

## BusinessObject

Represents stable identity.

Fields:

- id (PK)
- object_type_id (FK)
- object_number
- name
- description
- current_revision_id (FK)
- created_on
- modified_on
- status

Examples:

- REQ-0001
- PART-1000
- TEST-100

---

## Revision

Represents version-controlled content.

Fields:

- id (PK)
- object_id (FK)
- revision_id
- sequence_no
- title
- description
- created_on
- status

---

## RevisionLineage

Represents revision chains.

Fields:

- parent_revision_id
- child_revision_id

Supports:

```text
A -> B -> C
```

---

# Property Model

## PropertyDefinition

Defines metadata.

Fields:

- id (PK)
- name
- object_type_id (FK)
- data_type
- mandatory
- multi_value
- description

Examples:

- req_text
- priority
- safety_level
- verification_method
- compliance_class

---

## PropertyValue

Stores business data.

Fields:

- id (PK)
- revision_id (FK)
- property_definition_id (FK)
- string_value
- integer_value
- float_value
- date_value
- sequence_no

---

# Relationship Model

## RelationshipType

Fields:

- id (PK)
- name
- description

Examples:

- DERIVED_FROM
- SATISFIED_BY
- VERIFIED_BY
- ALLOCATED_TO
- IMPACTED_BY_CHANGE
- REFERENCES
- DEFINING
- COMPLYING

---

## Relationship

Fields:

- id (PK)
- relationship_type_id (FK)
- primary_revision_id (FK)
- secondary_revision_id (FK)
- created_on

---

# Requirements Model

Requirements are represented using:

```text
BusinessObject
+
Revision
+
PropertyValue
```

Requirement properties include:

- Requirement Number
- Requirement Text
- Priority
- Criticality
- Risk
- Source
- Verification Method
- Compliance Status
- Validation Status

---

# Product Architecture Model

Object types may include:

- Function
- FunctionRevision
- ArchitectureElement
- ArchitectureElementRevision
- SoftwareComponent
- SoftwareComponentRevision
- Part
- PartRevision

---

# Traceability Model

Requirement decomposition:

```text
Customer Requirement
      DEFINING
System Requirement
      DEFINING
Subsystem Requirement
      DEFINING
Component Requirement
```

Allocation:

```text
Requirement
    ALLOCATED_TO
Architecture Element
```

Verification:

```text
Requirement
    VERIFIED_BY
Test Case
```

Satisfaction:

```text
Requirement
    SATISFIED_BY
Part Revision
```

---

# BOM Model

## BOMOccurrence

Fields:

- id (PK)
- parent_revision_id
- child_revision_id
- find_number
- quantity

## OccurrenceTrace

Fields:

- id (PK)
- requirement_revision_id
- bom_occurrence_id

---

# Configuration Management

## RevisionRule

Fields:

- id (PK)
- name
- description

## ConfigurationContext

Fields:

- id (PK)
- revision_rule_id
- name
- description

## Baseline

Fields:

- id (PK)
- configuration_context_id
- name
- description
- created_on

## BaselineMember

Fields:

- baseline_id
- revision_id

---

# Dataset Model

## Dataset

Fields:

- id (PK)
- revision_id
- dataset_type
- name

## ManagedFile

Fields:

- id (PK)
- dataset_id
- file_name
- mime_type
- storage_path
- file_size

---

# Verification Model

## VerificationResult

Fields:

- id (PK)
- test_revision_id
- execution_date
- result
- summary

---

# Release Lifecycle

## ReleaseState

Fields:

- id (PK)
- name
- description

Examples:

- Draft
- Review
- Approved
- Released
- Obsolete

## RevisionReleaseState

Fields:

- revision_id
- release_state_id
- assigned_on

---

# Workflow Model

## WorkflowProcess

Fields:

- id (PK)
- name
- state
- started_on
- completed_on

## WorkflowTask

Fields:

- id (PK)
- process_id
- revision_id
- task_name
- task_state
- due_date

---

# Recommended SQLAlchemy Models

```text
ObjectType
BusinessObject
Revision
RevisionLineage
PropertyDefinition
PropertyValue
RelationshipType
Relationship
RevisionRule
ConfigurationContext
Baseline
BaselineMember
Dataset
ManagedFile
BOMOccurrence
OccurrenceTrace
ReleaseState
RevisionReleaseState
VerificationResult
WorkflowProcess
WorkflowTask
```
