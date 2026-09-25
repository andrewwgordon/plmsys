"""Tests for the shared external stylesheet.

The stylesheet lives at ``app/templates/static/plmsys.css`` and is served at
``/static/plmsys.css``. It owns the palette, typography and the Bootstrap 3 /
FAB component overrides (see ``docs/ui_plan.md`` UI-0b).
"""

from pathlib import Path

CSS_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "templates"
    / "static"
    / "plmsys.css"
)


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def test_stylesheet_exists():
    assert CSS_PATH.is_file(), f"missing stylesheet: {CSS_PATH}"


def test_palette_and_typography_are_defined():
    css = _css()
    assert "--plmsys-primary: #1f6feb;" in css
    assert "--plmsys-nav-bg: #2a3542;" in css
    assert "--plmsys-font-family:" in css
    assert "--plmsys-font-family-mono:" in css


def test_fab_and_bootstrap_components_are_overridden():
    css = _css()
    for selector in (
        ".btn-primary",
        ".panel-primary > .panel-heading",
        ".table",
        ".form-control:focus",
        ".nav-tabs",
        ".dropdown-menu",
        ".pagination",
        ".list-group-item",
        ".modal-content",
        ".label-success",
        ".progress-bar",
    ):
        assert selector in css, f"missing component override: {selector}"


def test_stylesheet_uses_palette_variables_not_colour_literals():
    """Component rules should reference custom properties, not hex literals."""
    overrides = _css().split("}", 1)[1]
    assert "var(--plmsys-primary)" in overrides
    assert "#1f6feb" not in overrides


def test_stylesheet_is_served(client):
    response = client.get("/static/plmsys.css")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "--plmsys-primary: #1f6feb;" in body
    assert ".btn-primary" in body


def test_page_links_stylesheet_after_fab_base(client):
    body = client.get("/").get_data(as_text=True)
    assert "plmsys.css" in body
    # FAB's base theme must load before the PLMSys overrides win the cascade.
    fab = body.find("bootstrap.min.css")
    ours = body.find("plmsys.css")
    assert fab != -1, "FAB base CSS not found"
    assert ours != -1, "PLMSys stylesheet link not found"
    assert fab < ours
