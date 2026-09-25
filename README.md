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
- **Domain services** (`app/services/`) — revision branching/lineage, typed
  metadata-driven properties, the release lifecycle state machine, and
  relationship traversal.
- **Revision lifecycle (Phase 2)** — FAB actions to create/branch revisions,
  set the current revision and move them through
  `Draft → Review → Approved → Released → Obsolete`, plus release-state badges,
  a baseline guard (only released revisions) and role-aware action
  permissions.
- **Property system (Phase 3)** — typed, multi-valued business data edited
  through a dynamic form generated from `PropertyDefinition` rows (with a
  Property Matrix report), validated definition admin and read-only raw values.
- **Traceability (Phase 4)** — relation forms (add relation, derive
  requirement), a revision relations section, a coverage-gap traceability
  matrix, typed-edge traversal, and a DB unique constraint on relationships.
- **BOM (Phase 5)** — a cycle-safe product-structure explorer with quantity
  roll-up, where-used, add-occurrence and requirement-trace forms, and a BOM
  coverage-gap report, backed by `services/bom.py` and DB constraints.
- **Configuration & baselines (Phase 6)** — rule-driven revision resolution,
  atomic baselines (Released-only, duplicate-guarded), a baseline detail and
  compare page, and a session-based header context selector.
- **Migration-first schema** — Alembic owns all tables; the app never creates
  tables at runtime. FAB security roles/permissions are bootstrapped on start.
- **Task-oriented UI shell (UI-0)** — global header, left navigation panel,
  location bar, Home page with KPI/entry tiles, and a config-driven Bootstrap
  colour schema.
- **Test suite** — 183 pytest tests covering seeds, the shell, the colour
  schema, the migration workflow, route-level access control, the service layer
  (including the `PropertyDataType` coercion matrix), the FAB revision
  actions/guards, the property form/matrix, traceability, the BOM and
  configuration/baselines.

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

- **Theme** — the palette, typography and FAB/Bootstrap component overrides live
  in `app/templates/static/plmsys.css` (served at `/static/plmsys.css`) and are
  linked from `app/templates/base_layout.html` after FAB's own stylesheets.
  `APP_THEME` is disabled, so no Bootswatch theme is loaded: `plmsys.css` is the
  sole theme layer and mirrors Bootstrap 3's design tokens. Changing the
  `--plmsys-*` custom properties re-themes both the shell and every FAB
  component. App static assets (including future uploads) live under
  `app/templates/static/`.
- **Schema ownership** — `FAB_CREATE_DB = False` and `AUTO_CREATE_SCHEMA = False`
  keep schema creation in Alembic. `AUTO_SEED = True` seeds business data once
  the schema is ready; set `PLMSYS_AUTO_SEED=0` to disable seeding (e.g. while
  autogenerating a migration whose column the seed already references).

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

- 8 object types; 13 business objects (`REQ-*`, `PART-*`, `FUNC-*`, `ARCH-*`,
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
UI shell/menu behaviour, route-level access control and the colour schema, and
unit-tests the domain services.

## Project layout

```
app/
├── __init__.py           # application factory (migration-first)
├── extensions.py         # db, appbuilder, migrate singletons
├── models.py             # 21 domain models
├── security.py           # PLMSecurityManager (roles without schema creation)
├── seed.py               # idempotent seed data
├── services/             # domain services (revisions, properties, lifecycle, …)
├── views.py              # ModelViews + task-oriented menu
├── ui/
│   └── shell.py          # PLMSysIndexView (Home)
└── templates/
    ├── base_layout.html  # global shell (header, nav panel, location bar)
    ├── index.html        # Home tiles + KPIs
    └── static/
        └── plmsys.css    # shared palette, typography + FAB overrides
migrations/               # Alembic (schema + FK indexes)
tests/                    # phase0, smoke, theme, security
└── services/             # service-layer unit tests
config.py                 # configuration (DB, auth, theme selection)
run.py                    # dev launcher (port 5001)
```

## Documentation

- Domain model: [`docs/PLMSys_FAB_Domain_Model.md`](docs/PLMSys_FAB_Domain_Model.md)
- Implementation plan: [`docs/plan.md`](docs/plan.md)
- UI / navigation plan: [`docs/ui_plan.md`](docs/ui_plan.md)
