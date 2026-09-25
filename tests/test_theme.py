"""Tests for the shared external stylesheet.

The stylesheet lives at ``app/templates/static/plmsys.css`` and is served at
``/static/plmsys.css``. It is the *only* theme layer: ``APP_THEME`` is disabled
so no Bootswatch theme is loaded, and this file is linked last from
``base_layout.html`` (see ``docs/ui_plan.md`` UI-0c).
"""

import re
from pathlib import Path

import config

CSS_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "templates"
    / "static"
    / "plmsys.css"
)

STYLESHEET_LINK = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
STYLESHEET_HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)
STYLESHEET_REL = re.compile(r'rel="stylesheet"', re.IGNORECASE)


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _stylesheet_hrefs(html: str) -> list:
    hrefs = []
    for tag in STYLESHEET_LINK.findall(html):
        if STYLESHEET_REL.search(tag):
            match = STYLESHEET_HREF.search(tag)
            if match:
                hrefs.append(match.group(1))
    return hrefs


# ---------------------------------------------------------------------------
# File / tokens
# ---------------------------------------------------------------------------


def test_stylesheet_exists():
    assert CSS_PATH.is_file(), f"missing stylesheet: {CSS_PATH}"


def test_bootswatch_theme_is_disabled():
    assert config.APP_THEME == ""


def test_palette_and_typography_are_defined():
    css = _css()
    for token in (
        "--plmsys-primary: #1f6feb;",
        "--plmsys-success: #2e7d32;",
        "--plmsys-info: #0b7285;",
        "--plmsys-warning: #b26a00;",
        "--plmsys-danger: #c62828;",
        "--plmsys-nav-bg: #2a3542;",
        "--plmsys-font-family:",
        "--plmsys-font-family-mono:",
        "--plmsys-radius-base:",
    ):
        assert token in css, f"missing token: {token}"


def test_full_bootstrap3_and_fab_component_coverage():
    css = _css()
    for selector in (
        # buttons + states
        ".btn-primary",
        ".btn-success",
        ".btn-info",
        ".btn-warning",
        ".btn-danger",
        ".btn-default",
        ".btn-link",
        # tables
        ".table",
        ".table-striped",
        ".table-bordered",
        ".table-hover",
        # forms + widgets
        ".form-control:focus",
        ".input-group-addon",
        ".has-error .form-control",
        ".select2-container--default",
        ".datepicker",
        # panels
        ".panel-primary > .panel-heading",
        ".panel-success > .panel-heading",
        # navigation
        ".navbar-default",
        ".navbar-inverse",
        ".nav-tabs",
        ".nav-pills",
        ".dropdown-menu",
        # feedback
        ".pagination",
        ".pager",
        ".label-success",
        ".badge",
        ".progress-bar-success",
        ".alert-success",
        ".alert-link",
        ".list-group-item",
        ".breadcrumb",
        ".modal-content",
        ".popover",
        ".tooltip-inner",
        ".well",
        # FAB helpers
        ".fixed-footer",
        ".action_checkboxes",
        # utilities
        ".text-primary",
        ".bg-danger",
    ):
        assert selector in css, f"missing component override: {selector}"


def test_stylesheet_uses_palette_variables_not_bootstrap_defaults():
    """Component rules reference custom properties, not Bootstrap defaults."""
    # Ignore comments (the header documents the defaults we must not leak).
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.DOTALL)
    overrides = css.split("}", 1)[1]
    assert "var(--plmsys-primary)" in overrides
    # None of Bootstrap's default brand colours may survive.
    for default in ("#337ab7", "#5cb85c", "#5bc0de", "#f0ad4e", "#d9534f"):
        assert default not in overrides, f"Bootstrap default leaked: {default}"


# ---------------------------------------------------------------------------
# Serving & cascade
# ---------------------------------------------------------------------------


def test_stylesheet_is_served(client):
    response = client.get("/static/plmsys.css")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "--plmsys-primary: #1f6feb;" in body
    assert ".btn-primary" in body


def test_shell_does_not_request_bootswatch(client):
    body = client.get("/").get_data(as_text=True)
    hrefs = _stylesheet_hrefs(body)
    assert not any("flatly.css" in href for href in hrefs)
    assert not any("/themes/" in href for href in hrefs)
    assert hrefs[-1].endswith("/static/plmsys.css"), hrefs


def test_fab_list_page_uses_plmsys_theme(admin_client):
    body = admin_client.get("/businessobjectmodelview/list/").get_data(as_text=True)
    hrefs = _stylesheet_hrefs(body)
    assert not any("flatly.css" in href for href in hrefs)
    assert not any("/themes/" in href for href in hrefs)
    # plmsys.css must be the last stylesheet so it wins the cascade.
    assert hrefs[-1].endswith("/static/plmsys.css"), hrefs


def test_fab_show_page_uses_plmsys_theme(admin_client, app):
    from app.extensions import db
    from app.models import BusinessObject

    with app.app_context():
        object_id = (
            db.session.query(BusinessObject)
            .filter_by(object_number="REQ-0001")
            .one()
            .id
        )
    body = admin_client.get(
        f"/businessobjectmodelview/show/{object_id}"
    ).get_data(as_text=True)
    hrefs = _stylesheet_hrefs(body)
    assert not any("/themes/" in href for href in hrefs)
    assert hrefs[-1].endswith("/static/plmsys.css"), hrefs
