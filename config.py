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

# Seed representative business data once the schema is ready. Set
# PLMSYS_AUTO_SEED=0 to disable (e.g. while autogenerating a migration whose
# new column the seed already references).
AUTO_SEED = os.environ.get("PLMSYS_AUTO_SEED", "1").lower() not in (
    "0",
    "false",
    "no",
)

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
# Managed uploads are controlled content: they are stored OUTSIDE the
# web-served static tree (app/templates/static/) and reached only through the
# authenticated download route. Override with PLMSYS_UPLOAD_FOLDER.
UPLOAD_FOLDER = os.environ.get(
    "PLMSYS_UPLOAD_FOLDER", os.path.join(basedir, "instance", "uploads")
)

# The image upload folder, when using models with images (kept in sync with
# UPLOAD_FOLDER; only used if an ImageColumn is introduced).
IMG_UPLOAD_FOLDER = UPLOAD_FOLDER

# The image upload url, when using models with images
IMG_UPLOAD_URL = "/static/uploads/"
# Setup image size default is (300, 200, True)
# IMG_SIZE = (300, 200, True)

# Allowed upload extensions. FAB's FileManager accepts *every* extension when
# this is unset, so it must be defined. Active content (svg/html/js) is
# deliberately excluded.
FILE_ALLOWED_EXTENSIONS = {
    "pdf", "txt", "csv", "md",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff",
    "step", "stp", "iges", "igs",
    "zip",
}

# Cap the whole request body (uploads) to protect the server from disk fill.
MAX_CONTENT_LENGTH = 25 * 1024 * 1024

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
# Bootswatch themes are disabled: app/templates/static/plmsys.css is the sole
# theme layer for both the shell and FAB's inner views (docs/ui_plan.md UI-0c).
# Leave empty so FAB emits no `themes/<name>` link; FAB still loads Bootstrap 3
# core, Font Awesome and ab.css, and plmsys.css is loaded last.
APP_THEME = ""
# APP_THEME = "spacelab.css"
# APP_THEME = "united.css"
# APP_THEME = "yeti.css"

# ---------------------------------------------------
# PLMSys theme
# ---------------------------------------------------
# The palette, typography and Bootstrap 3 / FAB component overrides live in
# app/templates/static/plmsys.css (served at /static/plmsys.css) and are
# linked from app/templates/base_layout.html. They are kept out of Python
# config so the stylesheet can be edited, cached and linted as ordinary CSS.

# ---------------------------------------------------
# UI shell (see docs/ui_plan.md)
# ---------------------------------------------------
FAB_INDEX_VIEW = "app.ui.shell.PLMSysIndexView"
FAB_BASE_TEMPLATE = "base_layout.html"