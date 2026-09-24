import os

from flask_appbuilder.security.manager import (
    AUTH_DB,
)

basedir = os.path.abspath(os.path.dirname(__file__))

# Your App secret key
SECRET_KEY = "9e52852b-5466-4173-81bb-5360b700b91d"

# The SQLAlchemy connection string. Override with PLMSYS_DATABASE_URI (e.g. for
# tests, CI or a PostgreSQL deployment).
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "PLMSYS_DATABASE_URI", "sqlite:///" + os.path.join(basedir, "app.db")
)
# SQLALCHEMY_DATABASE_URI = 'mysql://myapp@localhost/myapp'
# SQLALCHEMY_DATABASE_URI = 'postgresql://root:password@localhost/myapp'

# Schema is owned by Alembic migrations (see migrations/). FAB must not create
# tables; app.security.PLMSecurityManager still bootstraps the built-in roles
# and permissions once the schema exists.
FAB_CREATE_DB = False
FAB_SECURITY_MANAGER_CLASS = "app.security.PLMSecurityManager"

# Create tables from metadata at startup instead of running migrations.
# Intended for tests and throwaway local bootstraps only; use `flask db upgrade`.
AUTO_CREATE_SCHEMA = False

# Seed representative business data once the schema is ready.
AUTO_SEED = True

# Flask-WTF flag for CSRF  
CSRF_ENABLED = True

# ------------------------------
# GLOBALS FOR APP Builder
# ------------------------------
# Uncomment to setup Your App name
APP_NAME = "PLMSys"

# Uncomment to setup Setup an App icon
# APP_ICON = "static/img/logo.jpg"

# ----------------------------------------------------
# AUTHENTICATION CONFIG
# ----------------------------------------------------
# The authentication type
# AUTH_OID : Is for OpenID
# AUTH_DB : Is for database (username/password()
# AUTH_LDAP : Is for LDAP
# AUTH_REMOTE_USER : Is for using REMOTE_USER from web server
AUTH_TYPE = AUTH_DB

# Uncomment to setup Full admin role name
# AUTH_ROLE_ADMIN = 'Admin'

# Uncomment to setup Public role name, no authentication needed
# AUTH_ROLE_PUBLIC = 'Public'

# Will allow user self registration
# AUTH_USER_REGISTRATION = True

# Recaoptcha settings for user self registration
# RECAPTCHA_USE_SSL = False
# RECAPTCHA_PUBLIC_KEY = 'public'
# RECAPTCHA_PRIVATE_KEY = 'private'
# RECAPTCHA_OPTIONS = {'theme': 'white'}

# The default user self registration role
AUTH_USER_REGISTRATION_ROLE = "Public"

# When using LDAP Auth, setup the ldap server
# AUTH_LDAP_SERVER = "ldap://ldapserver.new"

# Uncomment to setup OpenID providers example for OpenID authentication
# OPENID_PROVIDERS = [
#    { 'name': 'Yahoo', 'url': 'https://me.yahoo.com' },
#    { 'name': 'AOL', 'url': 'http://openid.aol.com/<username>' },
#    { 'name': 'Flickr', 'url': 'http://www.flickr.com/<username>' },
#    { 'name': 'MyOpenID', 'url': 'https://www.myopenid.com' }]
# ---------------------------------------------------
# Babel config for translations
# ---------------------------------------------------
# Setup default language
BABEL_DEFAULT_LOCALE = "en"
# Your application default translation path
BABEL_DEFAULT_FOLDER = "translations"
# The allowed translation for you app
LANGUAGES = {
    "en": {"flag": "gb", "name": "English"},
    "pt": {"flag": "pt", "name": "Portuguese"},
    "pt_BR": {"flag": "br", "name": "Pt Brazil"},
    "es": {"flag": "es", "name": "Spanish"},
    "de": {"flag": "de", "name": "German"},
    "pl": {"flag": "pl", "name": "Polish"}
}
# ---------------------------------------------------
# Image and file configuration
# ---------------------------------------------------
# The file upload folder, when using models with files
UPLOAD_FOLDER = basedir + "/app/static/uploads/"

# The image upload folder, when using models with images
IMG_UPLOAD_FOLDER = basedir + "/app/static/uploads/"

# The image upload url, when using models with images
IMG_UPLOAD_URL = "/static/uploads/"
# Setup image size default is (300, 200, True)
# IMG_SIZE = (300, 200, True)

# Theme configuration
# these are located on static/appbuilder/css/themes
# you can create your own and easily use them placing them on the same dir structure to override
# APP_THEME = "bootstrap-theme.css"  # default bootstrap
# APP_THEME = "cerulean.css"
# APP_THEME = "amelia.css"
# APP_THEME = "cosmo.css"
# APP_THEME = "cyborg.css"
# APP_THEME = "flatly.css"
# APP_THEME = "journal.css"
# APP_THEME = "readable.css"
# APP_THEME = "simplex.css"
APP_THEME = "flatly.css"  # light base; recoloured by the PLMSys schema below
# APP_THEME = "spacelab.css"
# APP_THEME = "united.css"
# APP_THEME = "yeti.css"

# ---------------------------------------------------
# PLMSys colour schema (Bootstrap 3 / FAB)
# ---------------------------------------------------
# Single source of truth for the UI palette. `PLMSYS_THEME_CSS` turns this
# dictionary into CSS custom properties and Bootstrap 3 component overrides.
# The shell in app/templates/base_layout.html consumes the same properties, so
# the global shell and the FAB-generated components share one colour scheme.
PLMSYS_COLORS = {
    "primary": "#1f6feb",
    "primary_hover": "#1a5fd0",
    "primary_soft": "rgba(31, 111, 235, 0.15)",
    "nav_bg": "#2a3542",
    "nav_bg_dark": "#22303f",
    "nav_hover": "#2f4054",
    "nav_text": "#cdd7e0",
    "nav_text_strong": "#ffffff",
    "nav_heading": "#7f8fa0",
    "header_search_bg": "#3b4859",
    "header_search_text": "#eef3f8",
    "header_search_muted": "#9aa7b4",
    "body_bg": "#f4f6f9",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "text": "#1f2933",
    "muted": "#7c8794",
    "border": "#e2e8f0",
    "success": "#2e7d32",
    "info": "#0b7285",
    "warning": "#b26a00",
    "danger": "#c62828",
}

# Static Bootstrap overrides. They reference the CSS custom properties emitted
# from PLMSYS_COLORS (no colour literals here), so changing the palette above
# re-themes the whole application.
_plmsys_bootstrap_overrides = """
/* Base */
body { background-color: var(--plmsys-body-bg); color: var(--plmsys-text); }
a { color: var(--plmsys-primary); }
a:hover, a:focus { color: var(--plmsys-primary-hover); }
h1, h2, h3, h4, h5, h6 { color: var(--plmsys-text); }

/* Buttons */
.btn-primary { background-color: var(--plmsys-primary); border-color: var(--plmsys-primary); }
.btn-primary:hover, .btn-primary:focus, .btn-primary:active, .btn-primary.active,
.open > .dropdown-toggle.btn-primary {
    background-color: var(--plmsys-primary-hover); border-color: var(--plmsys-primary-hover);
}
.btn-primary.disabled, .btn-primary[disabled], fieldset[disabled] .btn-primary {
    background-color: var(--plmsys-primary); border-color: var(--plmsys-primary); opacity: .65;
}
.btn-link { color: var(--plmsys-primary); }
.btn-link:hover, .btn-link:focus { color: var(--plmsys-primary-hover); }

/* Utilities */
.text-primary { color: var(--plmsys-primary) !important; }
.bg-primary { background-color: var(--plmsys-primary) !important; }

/* Panels */
.panel { background-color: var(--plmsys-surface); border-color: var(--plmsys-border); }
.panel-default > .panel-heading {
    background-color: var(--plmsys-surface-alt); border-color: var(--plmsys-border);
    color: var(--plmsys-text);
}
.panel-primary { border-color: var(--plmsys-primary); }
.panel-primary > .panel-heading {
    background-color: var(--plmsys-primary); border-color: var(--plmsys-primary); color: #fff;
}
.panel-title > a { color: inherit; }

/* Navbar (FAB's own, when rendered) */
.navbar-default { background-color: var(--plmsys-nav-bg); border-color: var(--plmsys-nav-bg-dark); }
.navbar-default .navbar-brand, .navbar-default .navbar-nav > li > a { color: var(--plmsys-nav-text); }
.navbar-default .navbar-nav > li > a:hover, .navbar-default .navbar-nav > li > a:focus {
    color: var(--plmsys-nav-text-strong); background-color: var(--plmsys-nav-hover);
}
.navbar-default .navbar-nav > .active > a,
.navbar-default .navbar-nav > .open > a { background-color: var(--plmsys-nav-bg-dark); color: var(--plmsys-nav-text-strong); }

/* Dropdowns */
.dropdown-menu { background-color: var(--plmsys-surface); border-color: var(--plmsys-border); }
.dropdown-menu > li > a { color: var(--plmsys-text); }
.dropdown-menu > li > a:hover, .dropdown-menu > li > a:focus {
    background-color: var(--plmsys-surface-alt); color: var(--plmsys-primary);
}
.dropdown-menu > .active > a, .dropdown-menu > .active > a:hover {
    background-color: var(--plmsys-primary); color: #fff;
}

/* Tables */
.table { color: var(--plmsys-text); }
.table > thead > tr > th { border-bottom-color: var(--plmsys-border); }
.table > tbody > tr > td, .table > tbody > tr > th, .table > tfoot > tr > td,
.table > tfoot > tr > th, .table > thead > tr > td { border-top-color: var(--plmsys-border); }
.table-striped > tbody > tr:nth-of-type(odd) { background-color: var(--plmsys-surface-alt); }
.table-hover > tbody > tr:hover { background-color: var(--plmsys-surface-alt); }

/* Forms */
.form-control { border-color: var(--plmsys-border); color: var(--plmsys-text); }
.form-control:focus { border-color: var(--plmsys-primary); box-shadow: 0 0 0 2px var(--plmsys-primary-soft); }
.help-block { color: var(--plmsys-muted); }

/* Pagination */
.pagination > li > a, .pagination > li > span {
    color: var(--plmsys-primary); background-color: var(--plmsys-surface); border-color: var(--plmsys-border);
}
.pagination > li > a:hover { background-color: var(--plmsys-surface-alt); color: var(--plmsys-primary-hover); }
.pagination > .active > a, .pagination > .active > a:hover {
    background-color: var(--plmsys-primary); border-color: var(--plmsys-primary); color: #fff;
}

/* Labels, badges, progress */
.label-primary, .badge { background-color: var(--plmsys-primary); }
.label-success { background-color: var(--plmsys-success); }
.label-info { background-color: var(--plmsys-info); }
.label-warning { background-color: var(--plmsys-warning); }
.label-danger { background-color: var(--plmsys-danger); }
.progress-bar { background-color: var(--plmsys-primary); }

/* List groups, wells */
.list-group-item.active, .list-group-item.active:hover {
    background-color: var(--plmsys-primary); border-color: var(--plmsys-primary);
}
.well { background-color: var(--plmsys-surface); border-color: var(--plmsys-border); }
blockquote { border-left-color: var(--plmsys-border); }
""".strip()


def _plmsys_theme_css(colors):
    """Build CSS custom properties + Bootstrap overrides from the palette."""
    variables = "\n".join(
        f"  --plmsys-{name.replace('_', '-')}: {value};"
        for name, value in colors.items()
    )
    return ":root {\n" + variables + "\n}\n" + _plmsys_bootstrap_overrides


PLMSYS_THEME_CSS = _plmsys_theme_css(PLMSYS_COLORS)

# ---------------------------------------------------
# UI shell (see docs/ui_plan.md)
# ---------------------------------------------------
FAB_INDEX_VIEW = "app.ui.shell.PLMSysIndexView"
FAB_BASE_TEMPLATE = "base_layout.html"