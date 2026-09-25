"""Initial seed data for the PLMSys domain model.

``seed_data`` is idempotent: it is a no-op whenever any :class:`ObjectType`
already exists. It is intended to be called once from the application factory
after the schema has been created.
"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

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
    PropertyDataType,
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


# --- helpers ---------------------------------------------------------------


# Maps PropertyDataType to its backing column on PropertyValue.
_PROPERTY_COLUMNS = {
    PropertyDataType.STRING: "string_value",
    PropertyDataType.INTEGER: "integer_value",
    PropertyDataType.FLOAT: "float_value",
    PropertyDataType.DATE: "date_value",
}


def _release_states(session: Session) -> dict[str, ReleaseState]:
    states = {}
    for name, description in (
        ("Draft", "Work in progress, not yet reviewed."),
        ("Review", "Under review by stakeholders."),
        ("Approved", "Reviewed and approved, not yet released."),
        ("Released", "Released and under configuration control."),
        ("Obsolete", "Superseded or withdrawn."),
    ):
        state = ReleaseState(name=name, description=description)
        session.add(state)
        states[name] = state
    return states


def _object_types(session: Session) -> dict[str, ObjectType]:
    # (name, parent name, description)
    #
    # Only the *base* business object types are seeded. Earlier revisions of
    # this file also created paired ``*Revision`` object types
    # (``RequirementRevision`` etc.), but nothing referenced them: a revision is
    # typed by its business object's type and carries its attributes through
    # PropertyValue. They were removed to avoid dead seed data (see the Phase 1
    # review); reintroduce them together with a real Revision.type FK if a
    # distinct revision-type hierarchy is ever needed.
    definitions = [
        ("Requirement", None, "A requirement business object."),
        ("Function", None, "A functional element."),
        ("ArchitectureElement", None, "A logical/physical architecture element."),
        ("SoftwareComponent", None, "A software component."),
        ("Part", None, "A physical part."),
        ("TestCase", None, "A verification test case."),
        ("ChangeRequest", None, "An engineering change request."),
        ("Document", None, "A controlled document."),
    ]
    types: dict[str, ObjectType] = {}
    for name, parent_name, description in definitions:
        parent = types.get(parent_name) if parent_name else None
        obj_type = ObjectType(name=name, description=description, parent_type=parent)
        session.add(obj_type)
        types[name] = obj_type
    session.flush()
    return types


def _property_definitions(
    session: Session, object_types: dict[str, ObjectType]
) -> dict[str, PropertyDefinition]:
    requirement = object_types["Requirement"]
    # (name, data_type, mandatory, multi_value, description)
    definitions = [
        ("req_text", PropertyDataType.STRING, True, False, "The normative requirement statement."),
        ("priority", PropertyDataType.STRING, False, False, "Priority classification (High/Medium/Low)."),
        ("criticality", PropertyDataType.STRING, False, False, "Criticality classification."),
        ("risk", PropertyDataType.STRING, False, False, "Associated risk level."),
        ("risk_score", PropertyDataType.INTEGER, False, False, "Quantified risk score (0-100)."),
        ("mass_kg", PropertyDataType.FLOAT, False, False, "Estimated mass in kilograms."),
        ("due_date", PropertyDataType.DATE, False, False, "Target completion date."),
        ("source", PropertyDataType.STRING, False, False, "Origin of the requirement."),
        ("verification_method", PropertyDataType.STRING, False, False, "Inspection/Analysis/Demonstration/Test."),
        ("compliance_status", PropertyDataType.STRING, False, False, "Compliance status."),
        ("validation_status", PropertyDataType.STRING, False, False, "Validation status."),
        ("tags", PropertyDataType.STRING, False, True, "Free-form classification tags."),
    ]
    props: dict[str, PropertyDefinition] = {}
    for name, data_type, mandatory, multi_value, description in definitions:
        prop = PropertyDefinition(
            name=name,
            object_type=requirement,
            data_type=data_type,
            mandatory=mandatory,
            multi_value=multi_value,
            description=description,
        )
        session.add(prop)
        props[name] = prop
    session.flush()
    return props


def _relationship_types(session: Session) -> dict[str, RelationshipType]:
    definitions = [
        ("DERIVED_FROM", "The primary is derived from the secondary."),
        ("SATISFIED_BY", "The requirement is satisfied by the secondary."),
        ("VERIFIED_BY", "The requirement is verified by the secondary."),
        ("ALLOCATED_TO", "The requirement is allocated to the secondary."),
        ("IMPACTED_BY_CHANGE", "The primary is impacted by a change request."),
        ("REFERENCES", "A general reference link."),
        ("DEFINING", "The primary defines the secondary."),
        ("COMPLYING", "The primary complies with the secondary."),
    ]
    types: dict[str, RelationshipType] = {}
    for name, description in definitions:
        rel_type = RelationshipType(name=name, description=description)
        session.add(rel_type)
        types[name] = rel_type
    session.flush()
    return types


def _create_object(
    session: Session,
    object_type: ObjectType,
    object_number: str,
    name: str,
    description: str,
    revision_ids: list[str],
    status: str = "Draft",
) -> tuple[BusinessObject, list[Revision]]:
    business_object = BusinessObject(
        object_type=object_type,
        object_number=object_number,
        name=name,
        description=description,
        status=status,
    )
    session.add(business_object)
    session.flush()

    revisions = []
    for sequence_no, revision_id in enumerate(revision_ids, start=1):
        revision = Revision(
            business_object=business_object,
            revision_id=revision_id,
            sequence_no=sequence_no,
            title=name,
            description=description,
            status=status,
        )
        session.add(revision)
        revisions.append(revision)
    session.flush()

    business_object.current_revision = revisions[-1]
    session.flush()
    return business_object, revisions


def _set_property(
    session: Session,
    revision: Revision,
    definition: PropertyDefinition,
    value,
    sequence_no: int = 1,
) -> PropertyValue:
    """Store a typed property value in its data-type column."""
    column = _PROPERTY_COLUMNS[PropertyDataType(definition.data_type)]
    prop_value = PropertyValue(
        revision=revision,
        property_definition=definition,
        sequence_no=sequence_no,
        **{column: value},
    )
    session.add(prop_value)
    return prop_value


# --- entry point -----------------------------------------------------------


def seed_data(session: Session) -> bool:
    """Populate the database with a representative initial data set.

    Returns ``True`` when data was inserted, ``False`` when the database
    already contained seeded data.
    """
    if session.query(ObjectType).count() > 0:
        return False

    states = _release_states(session)
    object_types = _object_types(session)
    properties = _property_definitions(session, object_types)
    relation_types = _relationship_types(session)

    # -- revision rules & configuration contexts ---------------------------
    latest_working = RevisionRule(
        name="Latest Working",
        description="Select the latest working revision of every object.",
    )
    latest_released = RevisionRule(
        name="Latest Released",
        description="Select the latest released revision of every object.",
    )
    session.add_all([latest_working, latest_released])
    session.flush()

    context_working = ConfigurationContext(
        revision_rule=latest_working,
        name="EV Program - Working",
        description="Working configuration for the EV battery program.",
    )
    context_released = ConfigurationContext(
        revision_rule=latest_released,
        name="EV Program - Released",
        description="Released configuration for the EV battery program.",
    )
    session.add_all([context_working, context_released])
    session.flush()

    # -- requirement objects & revisions -----------------------------------
    req1, req1_revs = _create_object(
        session,
        object_types["Requirement"],
        "REQ-0001",
        "Customer Requirement: Vehicle Range",
        "The vehicle shall achieve a certified range of at least 400 km (WLTP).",
        ["A", "B"],
    )
    req2, req2_revs = _create_object(
        session,
        object_types["Requirement"],
        "REQ-0002",
        "System Requirement: Battery Capacity",
        "The traction battery shall provide at least 75 kWh of usable energy.",
        ["A"],
    )
    req3, req3_revs = _create_object(
        session,
        object_types["Requirement"],
        "REQ-0003",
        "Subsystem Requirement: Cell Chemistry",
        "The cells shall use a nickel-rich NMC cathode chemistry.",
        ["A"],
    )
    req4, req4_revs = _create_object(
        session,
        object_types["Requirement"],
        "REQ-0004",
        "Component Requirement: Module Thermal Management",
        "Each module shall maintain cell temperature within 5 K of the pack average.",
        ["A"],
    )

    # requirement property values
    _set_property(
        session, req1_revs[0], properties["req_text"],
        "The vehicle shall achieve a certified range of at least 400 km (WLTP).",
    )
    _set_property(session, req1_revs[0], properties["priority"], "High")
    _set_property(session, req1_revs[0], properties["source"], "Marketing")
    _set_property(session, req1_revs[0], properties["verification_method"], "Test")

    _set_property(
        session, req1_revs[1], properties["req_text"],
        "The vehicle shall achieve a certified range of at least 420 km (WLTP).",
    )
    _set_property(session, req1_revs[1], properties["priority"], "High")
    _set_property(session, req1_revs[1], properties["criticality"], "Safety")
    _set_property(session, req1_revs[1], properties["verification_method"], "Test")
    _set_property(session, req1_revs[1], properties["risk_score"], 7)
    _set_property(session, req1_revs[1], properties["mass_kg"], 12.5)
    _set_property(session, req1_revs[1], properties["due_date"], date(2027, 3, 31))
    _set_property(session, req1_revs[1], properties["tags"], "safety", sequence_no=1)
    _set_property(session, req1_revs[1], properties["tags"], "range", sequence_no=2)

    _set_property(
        session, req2_revs[0], properties["req_text"],
        "The traction battery shall provide at least 75 kWh of usable energy.",
    )
    _set_property(session, req2_revs[0], properties["priority"], "High")
    _set_property(session, req2_revs[0], properties["source"], "Systems Engineering")
    _set_property(session, req2_revs[0], properties["risk_score"], 4)

    _set_property(
        session, req3_revs[0], properties["req_text"],
        "The cells shall use a nickel-rich NMC cathode chemistry.",
    )
    _set_property(session, req3_revs[0], properties["compliance_status"], "Pending")

    _set_property(
        session, req4_revs[0], properties["req_text"],
        "Each module shall maintain cell temperature within 5 K of the pack average.",
    )
    _set_property(session, req4_revs[0], properties["validation_status"], "Validated")

    # -- other object types -------------------------------------------------
    part_module, part_module_revs = _create_object(
        session, object_types["Part"], "PART-1000", "Battery Module",
        "A 12-cell battery module assembly.", ["A"],
    )
    part_cell, part_cell_revs = _create_object(
        session, object_types["Part"], "PART-1001", "Battery Cell",
        "Prismatic NMC battery cell.", ["A", "B"],
    )
    part_plate, part_plate_revs = _create_object(
        session, object_types["Part"], "PART-1002", "Thermal Plate",
        "Liquid-cooled thermal management plate.", ["A"],
    )
    part_interconnect, part_interconnect_revs = _create_object(
        session, object_types["Part"], "PART-1003", "Cell Interconnect",
        "Busbar interconnect between cells.", ["A"],
    )
    func_traction, func_traction_revs = _create_object(
        session, object_types["Function"], "FUNC-200", "Provide Traction Power",
        "Supply tractive power to the drivetrain.", ["A"],
    )
    arch_pack, arch_pack_revs = _create_object(
        session, object_types["ArchitectureElement"], "ARCH-300",
        "High Voltage Battery Pack", "The complete high-voltage traction battery.",
        ["A"],
    )
    swc_bms, swc_bms_revs = _create_object(
        session, object_types["SoftwareComponent"], "SWC-400",
        "BMS State Estimator", "Battery state-of-charge and health estimator.",
        ["A"],
    )
    test_range, test_range_revs = _create_object(
        session, object_types["TestCase"], "TEST-100", "Range Verification Test",
        "WLTP range measurement on a dynamometer.", ["A"],
    )
    change_density, change_density_revs = _create_object(
        session, object_types["ChangeRequest"], "CR-500",
        "Increase Pack Energy Density", "Request to increase usable energy density.",
        ["A"],
    )
    doc_arch, doc_arch_revs = _create_object(
        session, object_types["Document"], "DOC-600",
        "Battery Pack Architecture Description",
        "Architecture description document for the battery pack.", ["A"],
    )

    # -- relationships ------------------------------------------------------
    def rel(type_name: str, primary: Revision, secondary: Revision) -> Relationship:
        relationship = Relationship(
            relationship_type=relation_types[type_name],
            primary_revision=primary,
            secondary_revision=secondary,
        )
        session.add(relationship)
        return relationship

    rel("DEFINING", req1_revs[1], req2_revs[0])   # customer -> system
    rel("DEFINING", req2_revs[0], req3_revs[0])   # system -> subsystem
    rel("DEFINING", req3_revs[0], req4_revs[0])   # subsystem -> component
    rel("ALLOCATED_TO", req2_revs[0], arch_pack_revs[0])
    rel("ALLOCATED_TO", req4_revs[0], part_plate_revs[0])
    rel("VERIFIED_BY", req1_revs[1], test_range_revs[0])
    rel("SATISFIED_BY", req3_revs[0], part_cell_revs[1])
    rel("SATISFIED_BY", req4_revs[0], part_plate_revs[0])
    rel("IMPACTED_BY_CHANGE", req2_revs[0], change_density_revs[0])
    rel("REFERENCES", doc_arch_revs[0], arch_pack_revs[0])
    rel("COMPLYING", req2_revs[0], arch_pack_revs[0])
    rel("ALLOCATED_TO", req2_revs[0], swc_bms_revs[0])       # requirement <-> software component
    rel("SATISFIED_BY", req1_revs[1], func_traction_revs[0])  # requirement <-> function

    # -- revision lineage ---------------------------------------------------
    session.add(
        RevisionLineage(
            parent_revision=req1_revs[0], child_revision=req1_revs[1]
        )
    )
    session.add(
        RevisionLineage(
            parent_revision=part_cell_revs[0], child_revision=part_cell_revs[1]
        )
    )

    # -- BOM ----------------------------------------------------------------
    bom_cell = BOMOccurrence(
        parent_revision=part_module_revs[0],
        child_revision=part_cell_revs[1],
        find_number="10",
        quantity=12.0,
    )
    bom_plate = BOMOccurrence(
        parent_revision=part_module_revs[0],
        child_revision=part_plate_revs[0],
        find_number="20",
        quantity=1.0,
    )
    bom_interconnect = BOMOccurrence(
        parent_revision=part_module_revs[0],
        child_revision=part_interconnect_revs[0],
        find_number="30",
        quantity=4.0,
    )
    bom_interconnect_plate = BOMOccurrence(
        parent_revision=part_interconnect_revs[0],
        child_revision=part_plate_revs[0],
        find_number="10",
        quantity=1.0,
    )
    session.add_all(
        [bom_cell, bom_plate, bom_interconnect, bom_interconnect_plate]
    )
    session.flush()

    session.add_all(
        [
            OccurrenceTrace(
                requirement_revision=req4_revs[0], bom_occurrence=bom_plate
            ),
            OccurrenceTrace(
                requirement_revision=req3_revs[0], bom_occurrence=bom_cell
            ),
            OccurrenceTrace(
                requirement_revision=req2_revs[0],
                bom_occurrence=bom_interconnect,
            ),
        ]
    )
    # bom_interconnect_plate is intentionally left without a requirement trace
    # so the coverage report has output.

    # -- baseline -----------------------------------------------------------
    baseline = Baseline(
        configuration_context=context_released,
        name="EV Program Baseline v1.0",
        description="First released baseline of the EV battery program.",
    )
    session.add(baseline)
    session.flush()
    for revision in (
        req1_revs[1],
        req2_revs[0],
        part_module_revs[0],
        part_cell_revs[1],
        part_plate_revs[0],
        arch_pack_revs[0],
        test_range_revs[0],
    ):
        session.add(BaselineMember(baseline=baseline, revision=revision))

    # -- release states -----------------------------------------------------
    # Reconcile the canonical lifecycle (RevisionReleaseState) with the
    # denormalised `status` caches on Revision/BusinessObject so the seeded data
    # does not start out inconsistent (see `app/services/lifecycle.py`).
    for revision, state_name in (
        (req1_revs[1], "Released"),
        (req2_revs[0], "Approved"),
        (part_cell_revs[1], "Released"),
        (test_range_revs[0], "Approved"),
    ):
        session.add(
            RevisionReleaseState(
                revision=revision, release_state=states[state_name]
            )
        )
        revision.status = state_name
        business_object = revision.business_object
        if business_object.current_revision is revision:
            business_object.status = state_name

    # -- verification -------------------------------------------------------
    session.add(
        VerificationResult(
            test_revision=test_range_revs[0],
            execution_date=date.today(),
            result="Pass",
            summary="Measured WLTP range 428 km, exceeding the 420 km target.",
        )
    )

    # -- datasets & files ---------------------------------------------------
    dataset = Dataset(
        revision=doc_arch_revs[0],
        dataset_type="Document",
        name="Battery Pack Architecture Description",
    )
    session.add(dataset)
    session.flush()
    session.add(
        ManagedFile(
            dataset=dataset,
            file_name="battery_pack_architecture.pdf",
            mime_type="application/pdf",
            storage_path="/static/uploads/battery_pack_architecture.pdf",
            file_size=248_320,
        )
    )

    # -- workflow -----------------------------------------------------------
    process = WorkflowProcess(
        name="Requirement Review",
        state="In Progress",
        started_on=datetime.now() - timedelta(days=3),
    )
    session.add(process)
    session.flush()
    session.add_all(
        [
            WorkflowTask(
                workflow_process=process,
                revision=req1_revs[1],
                task_name="Review customer requirement",
                task_state="Open",
                due_date=date.today() + timedelta(days=4),
            ),
            WorkflowTask(
                workflow_process=process,
                revision=req2_revs[0],
                task_name="Review system requirement",
                task_state="Open",
                due_date=date.today() + timedelta(days=7),
            ),
        ]
    )

    session.commit()
    return True
