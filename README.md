# plmsys

PoC Product Life Cycle Management application built with
[Flask-AppBuilder](https://flask-appbuilder.readthedocs.io/).

A Teamcenter-inspired PLM system: object-centric identities, revision control,
metadata-driven properties, relationship-driven traceability, BOM,
configuration management, datasets, verification and workflow.

## Status

**Phase 0 — Foundation is complete.** See
[`docs/plan.md`](docs/plan.md) for the roadmap and
[`docs/ui_plan.md`](docs/ui_plan.md) for the UI design.

Delivered so far:

- 21 domain models, an idempotent seed data set (118 rows) and 21 bootstrap
  `ModelView`s.
- **Migration-first schema** — Alembic owns all tables; the app never creates
  tables at runtime. FAB security roles/permissions are bootstrapped on start.
- **Task-oriented UI shell (UI-0)** — global header, left navigation panel,
  location bar, Home page with KPI/entry tiles, and a config-driven Bootstrap
  colour schema.
- **Test suite** — 20 pytest tests covering seeds, the shell, the colour schema
  and the migration workflow.

The Object page, global search, personal context and Structure Manager arrive in
later phases.

## Requirements

- Python 3.14+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Quick start

The examples below use a Git Bash shell on Windows.

```bash
uv sync                      # install dependencies into .venv

export FLASK_APP=run.py

flask db upgrade             # create the schema (Alembic migrations)
flask fab create-admin       # create your first administrator
flask run                    # http://localhost:5000
```

Alternatively, run the development server with the built-in launcher (port
5001, debug on):

```bash
python run.py                # http://localhost:5001
```

`flask fab create-admin` is interactive. It can also be scripted:

```bash
flask fab create-admin --username admin --firstname Ada --lastname Admin \
    --email admin@example.com --password changeme
```

Sign in at `/login/` with the account you created.

## Configuration

All application config lives in `config.py`.

- **Database URL** — override without editing code:

  ```bash
  export PLMSYS_DATABASE_URI="postgresql://user:password@localhost/plmsys"
  ```

- **Colour schema** — `PLMSYS_COLORS` is the single source of truth for the UI
  palette. `PLMSYS_THEME_CSS` turns it into CSS custom properties plus Bootstrap
  overrides, injected by `app/templates/base_layout.html`. `APP_THEME` selects
  the light Bootswatch base (`flatly.css`) that the schema recolours. Changing
  the palette re-themes both the shell and the FAB components.
- **Schema ownership** — `FAB_CREATE_DB = False` and `AUTO_CREATE_SCHEMA = False`
  keep schema creation in Alembic. `AUTO_SEED = True` seeds business data once
  the schema is ready.

## UI shell

The shell (`app/ui/shell.py`, `app/templates/base_layout.html`) wraps every page:

- **Header** — brand, object search, active configuration-context badge and the
  user/language menu.
- **Navigation panel** — business domains: Products, Requirements,
  Relationships, BOM, Documents, Verification, Configuration and Workflow.
  Meta-model and link-table views live under **Setup**, visible to
  administrators only.
- **Location bar** and **application pane** for page content.
- **Home page** (`/`) — KPI tiles, quick-entry tiles and a basic object lookup.

## Schema & migrations

The schema is **owned by Alembic** (`flask-migrate`). After `flask db upgrade`,
the first application start bootstraps the FAB security roles/permissions and
seeds representative data (seeding is idempotent).

```bash
flask db migrate -m "describe your change"   # autogenerate a migration
flask db upgrade                             # apply migrations
flask db downgrade                           # roll back one migration
```

## Seed data

`app/seed.py` populates a representative EV-battery programme and is safe to run
repeatedly. Highlights:

- 16 object types; 13 business objects (`REQ-*`, `PART-*`, `FUNC-*`, `ARCH-*`,
  `SWC-*`, `TEST-*`, `CR-*`, `DOC-*`) with 15 revisions.
- 8 property definitions and 15 typed property values.
- 8 relationship types and 11 traceability links (decomposition, allocation,
  verification, satisfaction).
- BOM occurrences, occurrence traces, a released baseline, verification result,
  dataset/file and a workflow with tasks.

## Tests

```bash
uv run pytest
```

The suite builds a temporary database and creates the schema from metadata
(`AUTO_CREATE_SCHEMA`), and separately verifies that `flask db upgrade` alone
produces the full schema and is idempotent. It also checks the seed counts, the
UI shell/menu behaviour and the colour schema.

## Project layout

```
app/
├── __init__.py           # application factory (migration-first)
├── extensions.py         # db, appbuilder, migrate singletons
├── models.py             # 21 domain models
├── seed.py               # idempotent seed data
├── security.py           # PLMSecurityManager (roles without schema creation)
├── views.py              # ModelViews + task-oriented menu
├── ui/
│   └── shell.py          # PLMSysIndexView (Home)
└── templates/
    ├── base_layout.html  # global shell (header, nav panel, location bar)
    └── index.html        # Home tiles + KPIs
migrations/               # Alembic (initial schema: 33 tables)
tests/                    # conftest, test_phase0, test_smoke, test_theme
config.py                 # configuration + colour schema
run.py                    # dev launcher (port 5001)
```

## Documentation

- Domain model: [`docs/PLMSys_FAB_Domain_Model.md`](docs/PLMSys_FAB_Domain_Model.md)
- Implementation plan: [`docs/plan.md`](docs/plan.md)
- UI / navigation plan: [`docs/ui_plan.md`](docs/ui_plan.md)
