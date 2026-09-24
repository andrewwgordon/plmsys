"""Tests for the config-driven Bootstrap colour schema."""

import config


def test_palette_and_base_theme():
    assert config.PLMSYS_COLORS["primary"] == "#1f6feb"
    assert config.PLMSYS_COLORS["nav_bg"] == "#2a3542"
    # The shell is light content + dark chrome, so the base theme is light.
    assert config.APP_THEME == "flatly.css"


def test_theme_css_emits_a_variable_for_every_colour():
    for name, value in config.PLMSYS_COLORS.items():
        variable = "--plmsys-" + name.replace("_", "-")
        assert f"{variable}: {value};" in config.PLMSYS_THEME_CSS


def test_theme_css_overrides_bootstrap_components():
    for selector in (
        ".btn-primary",
        ".panel-primary > .panel-heading",
        ".table",
        ".form-control:focus",
        ".pagination",
        ".dropdown-menu",
    ):
        assert selector in config.PLMSYS_THEME_CSS


def test_theme_css_recolours_via_custom_properties():
    # Everything after the :root block must reference custom properties.
    overrides = config.PLMSYS_THEME_CSS.split("}", 1)[1]
    assert "var(--plmsys-primary)" in overrides


def test_theme_is_injected_into_rendered_pages(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "--plmsys-primary: #1f6feb;" in body
    assert ".btn-primary" in body
    assert "var(--plmsys-nav-bg)" in body
