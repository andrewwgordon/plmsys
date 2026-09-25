"""Phase 0 smoke tests: seeding, idempotency and bootstrapped UI views."""

from app.extensions import db
from app.seed import seed_data

EXPECTED_COUNTS = {
    "ObjectType": 8,
    "BusinessObject": 14,
    "Revision": 16,
    "RevisionLineage": 2,
    "PropertyDefinition": 12,
    "PropertyValue": 21,
    "RelationshipType": 8,
    "Relationship": 13,
    "BOMOccurrence": 4,
    "OccurrenceTrace": 3,
    "RevisionRule": 2,
    "ConfigurationContext": 2,
    "Baseline": 1,
    "BaselineMember": 7,
    "Dataset": 1,
    "ManagedFile": 1,
    "ReleaseState": 5,
    "RevisionReleaseState": 4,
    "VerificationResult": 1,
    "WorkflowProcess": 1,
    "WorkflowTask": 2,
}


def test_seed_counts(app):
    from app import models

    with app.app_context():
        for name, expected in EXPECTED_COUNTS.items():
            model = getattr(models, name)
            actual = db.session.query(model).count()
            assert actual == expected, f"{name}: expected {expected}, got {actual}"


def test_seed_is_idempotent(app):
    from app import models

    with app.app_context():
        assert seed_data(db.session) is False
        assert db.session.query(models.ObjectType).count() == 8


def test_seed_property_values_match_their_data_type(app):
    """Every seeded value populates exactly the column for its definition."""
    from app import models

    columns = {
        models.PropertyDataType.STRING: "string_value",
        models.PropertyDataType.INTEGER: "integer_value",
        models.PropertyDataType.FLOAT: "float_value",
        models.PropertyDataType.DATE: "date_value",
    }
    with app.app_context():
        values = db.session.query(models.PropertyValue).all()
        assert values
        for value in values:
            populated = [
                column
                for column in columns.values()
                if getattr(value, column) is not None
            ]
            assert len(populated) == 1, (value, populated)
            data_type = models.PropertyDataType(value.property_definition.data_type)
            assert populated[0] == columns[data_type], (value, data_type)


def test_home_page_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"PLMSys" in response.data


def test_home_page_has_shell(admin_client):
    body = admin_client.get("/").get_data(as_text=True)
    assert "plmsys-header" in body
    assert "plmsys-nav" in body


def test_home_kpis_render(admin_client):
    body = admin_client.get("/").get_data(as_text=True)
    assert "Business Objects" in body
    assert "Baselines" in body


def test_home_search_finds_objects(admin_client):
    response = admin_client.get("/?q=REQ-0001")
    assert response.status_code == 200
    assert "REQ-0001" in response.get_data(as_text=True)


def test_requirement_list_is_filtered(admin_client):
    response = admin_client.get("/requirementmodelview/list/")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "REQ-0001" in body
    assert "PART-1000" not in body


def test_admin_sees_setup_menu(admin_client):
    body = admin_client.get("/").get_data(as_text=True)
    assert "Setup" in body
    assert "Object Types" in body


def test_viewer_does_not_see_setup_menu(viewer_client):
    body = viewer_client.get("/").get_data(as_text=True)
    assert "Setup" not in body


def test_all_list_views_render(admin_client, app):
    rules = sorted(
        str(rule)
        for rule in app.url_map.iter_rules()
        if str(rule).endswith("/list/") and "ModelView" in rule.endpoint
    )
    assert rules, "no list views were registered"

    failures = []
    for rule in rules:
        response = admin_client.get(rule, follow_redirects=True)
        if response.status_code != 200:
            failures.append((rule, response.status_code))
    assert not failures, failures
