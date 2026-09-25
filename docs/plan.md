# PLMSys — Implementation Plan

A step-by-step plan to take the current Flask-AppBuilder scaffold to a working,
Teamcenter-inspired Product Lifecycle Management application, based on
[`PLMSys_FAB_Domain_Model.md`](./PLMSys_FAB_Domain_Model.md) and the UI/UX
design in [`ui_plan.md`](./ui_plan.md).

The core plan (this document) owns the domain, service, data and integration
work. [`ui_plan.md`](./ui_plan.md) owns the interface and navigation design;
this plan **references and schedules that design as part of the roadmap** so
that UI is delivered with the functionality it depends on.

The project path is: /c/users/andre/workspace/plmsys in Git Bash on Windows 11.

---

## 1. Goals & scope

Build a database-agnostic PLM system on Flask-AppBuilder (FAB) / SQLAlchemy that
supports:

- **Object-centric identity** — stable `BusinessObject` records (e.g. `REQ-0001`).
- **Revision control** — versioned `Revision` content with lineage.
- **Metadata-driven properties** — configurable `PropertyDefinition` /
  `PropertyValue`, so new attributes need no schema migration.
- **Relationship-driven traceability** — typed links between revisions
  (derivation, allocation, verification, satisfaction).
- **Configuration management** — revision rules, configuration contexts,
  baselines.
- **BOM** — parent/child occurrences and requirement-to-occurrence traceability.
- **Datasets, verification, workflow** — files attached to revisions, test
  results, and process tracking.
- **Intuitive, task-oriented UI** — an object-centric shell with a personal
  Home, global search, persistent context, an Object page, and a Structure
  Manager, designed in [`ui_plan.md`](./ui_plan.md).

Out of scope (delegated to FAB Security Manager): users, roles, permissions,
authentication, ACLs.

---

## 2. Current baseline (what already exists)

| Artifact | Purpose | Status |
|---|---|---|
| `app/models.py` | 21 domain models + `TimestampMixin` + `PropertyDataType` | Done |
| `app/seed.py` | Idempotent `seed_data()` with representative business data | Done |
| `app/services/` | Phase 1 domain services (`ServiceError`, revisions, properties, lifecycle, relationships) + unit tests | Done |
| `app/views.py` | 21 `ModelView`s + task-oriented `register_views()` | Done |
| `app/__init__.py` | Application factory: init db/migrate/appbuilder, seed | Done |
| `app/security.py` | `PLMSecurityManager` — role bootstrap without schema creation | Done |
| `app/ui/` + `app/templates/` | UI-0 shell: base layout, Home page, colour schema | Done |
| `migrations/` | Alembic; initial schema creates all 33 tables | Done |
| `tests/` | pytest suite (conftest, smoke, phase-0, theme) | Done |
| `config.py` | App config (migration-first, theme, colour schema, i18n) | Done |
| `run.py` | Dev launcher (port 5001) | Existing |

**Verified:** schema creation, seeding (118 rows), idempotent re-seed, all 28
list views and the application's own add forms render, and create/edit POSTs
succeed (including the `PropertyDataType` enum round-trip). `app.db` is now
gitignored. **Phase 0 is complete — see §5.** The Phase 1 service layer and its
tests are also in place (74 pytest tests pass; `flask db check` reports no
schema drift), with foreign-key indexes added by migration `26f349ed091f`. The
theme CSS now lives in `app/templates/static/plmsys.css` (UI-0b).

**UI baseline:** the UI-0 shell is in place — a global header, left navigation
panel, location bar, config-driven Home page and a Bootstrap colour schema. The
Object page, global search, personal context and Structure Manager are still to
come; see [`ui_plan.md`](./ui_plan.md) §4–§9.

### Models delivered

Core meta-model: `ObjectType`, `BusinessObject`, `Revision`, `RevisionLineage`.
Properties: `PropertyDefinition`, `PropertyValue`.
Relationships: `RelationshipType`, `Relationship`.
BOM: `BOMOccurrence`, `OccurrenceTrace`.
Configuration: `RevisionRule`, `ConfigurationContext`, `Baseline`,
`BaselineMember`.
Datasets: `Dataset`, `ManagedFile`.
Lifecycle: `ReleaseState`, `RevisionReleaseState`.
Verification: `VerificationResult`.
Workflow: `WorkflowProcess`, `WorkflowTask`.

---

## 3. Conventions & lessons learned (apply throughout)

1. **Every model needs an explicit `__tablename__`** (FAB 5.x requirement).
2. **Circular FK** (`BusinessObject.current_revision_id` ↔ `Revision.object_id`)
   is resolved with `post_update=True` on `BusinessObject.current_revision`.
   SQLite tolerated the plain cycle; keep the relationship flag for portability.
3. **Never name a model attribute `process`** (or any reserved WTForms name:
   `data`, `errors`, `meta`, `validate`, `csrf_token`). `WorkflowTask.process`
   shadowed `Form.process()` and broke all forms — it is now
   `workflow_process`.
4. **SQLAlchemy `Enum` columns must not use `values_callable`** if FAB forms
   are used. FAB's `EnumField` expects `column.type.enums` to be the enum
   *member names* (`list(enum_class.__members__)`); it then renders member
   values as labels. The current `PropertyDataType` follows this.
5. **Composite primary keys** are used for link tables
   (`RevisionLineage`, `BaselineMember`, `RevisionReleaseState`).
6. **Relationships with two FKs to the same table** always declare
   `foreign_keys=[...]` (`RevisionLineage`, `BOMOccurrence`, `Relationship`).
7. **Business data goes in `PropertyValue`, not new columns.** New attributes
   should be seed rows in `PropertyDefinition`, not schema changes.
8. **Seeding is idempotent** — `seed_data()` returns early when `ObjectType`
   rows already exist. Keep this contract for future seed additions.

### UI conventions (from [`ui_plan.md`](./ui_plan.md))

9. **Navigation is task-oriented, not table-oriented.** Menu categories follow
   business domains (Products, Requirements, Changes, …); entities such as
   `PropertyValue`, `Relationship` and `BOMOccurrence` are reached through
   object pages, not menus ([`ui_plan.md`](./ui_plan.md) §6).
10. **The Object page is the centre of gravity.** Every `BusinessObject` has one
    page with Summary / Details / Relations / Structure / Verification /
    Attachments / History tabs, and every object reference is a link
    ([`ui_plan.md`](./ui_plan.md) §7.3).
11. **Configuration context is always visible.** The active `RevisionRule` /
    `Baseline` is shown and selectable in the global frame
    ([`ui_plan.md`](./ui_plan.md) §7.7).
12. **Personal context is persisted.** Favorites, Recent, Worklist and Saved
    Searches use thin app-level tables keyed to `ab_user`; they are not part of
    the domain model ([`ui_plan.md`](./ui_plan.md) §8).
13. **Extend FAB's base layout; don't fork it.** Override only the needed Jinja
    blocks in a `base_layout.html` derived from `appbuilder/baselayout.html`
    ([`ui_plan.md`](./ui_plan.md) §10).
14. **One lifecycle source of truth.** `RevisionReleaseState`/`ReleaseState`
    is canonical; `Revision.status` and `BusinessObject.status` are
    denormalised caches kept in sync by `app/services/lifecycle.py`. Never
    write `status` directly from a view or seed — route it through the service.
15. **FK columns are indexed.** Traversal-heavy foreign keys carry
    `index=True`; new FKs must ship with an Alembic migration.

---

## 4. Target module layout

```
app/
├── __init__.py            # factory (extend: blueprint registration, errors)
├── extensions.py          # db, appbuilder singletons
├── models.py              # (done) domain models
├── seed.py                # (done) seed data; may split into seed/ package later
├── views.py               # bootstrap views; to be split per domain area
├── views/                 # (later) one module per domain area
│   ├── meta.py
│   ├── objects.py
│   ├── requirements.py
│   ├── relationships.py
│   ├── bom.py
│   ├── configuration.py
│   ├── datasets.py
│   ├── verification.py
│   └── workflow.py
├── ui/                    # UI shell & custom pages (see ui_plan.md)
│   ├── shell.py           # Home (IndexView), Object page, breadcrumb/nav helpers
│   ├── search.py          # Global search + saved searches
│   ├── context.py         # Favorites, Recent, Worklist, UserPreference
│   ├── structure.py       # Structure Manager (BOM explorer)
│   ├── traceability.py    # Traceability matrix + Impact Analysis
│   └── components.py      # config-driven tabs, command bar, tiles, badges
├── services/              # domain/business logic (no HTTP concerns)
│   ├── revisions.py
│   ├── properties.py
│   ├── relationships.py
│   ├── bom.py
│   ├── configuration.py
│   ├── lifecycle.py
│   ├── datasets.py
│   ├── verification.py
│   └── workflow.py
├── api/                   # ModelRestApi + BaseApi endpoints
├── templates/             # custom templates (extend appbuilder/baselayout.html)
│   ├── base_layout.html   # global frame: header, nav panel, location bar
│   ├── index.html         # Home tiles
│   ├── object_detail.html # Object page with tabs
│   ├── structure.html     # BOM tree + data panes
│   ├── traceability.html  # Traceability matrix
│   └── static/            # app static assets (served at /static/)
│       ├── plmsys.css     # shared palette, typography + FAB/Bootstrap overrides
│       └── uploads/       # managed files (Phase 7)
migrations/                # Alembic
tests/
```

---

## 5. Implementation roadmap

The roadmap runs two interleaved tracks:

- **Functional track** — Phases 0–13 below: services, data and features.
- **UI track** — UI-0 … UI-9: the Teamcenter-inspired shell, Object page,
  search, personal context, Structure Manager, traceability, and configuration
  context. Wireframes, information architecture and component detail live in
  [`ui_plan.md`](./ui_plan.md); the table below sequences that work against the
  functional phases.

> **Rule:** a UI phase must not start before the functional phase supplying its
> data/services is complete. UI work is part of each phase's definition of done,
> not a follow-up.

### UI track summary (full detail in [`ui_plan.md`](./ui_plan.md) §9)

| UI phase | Scope | Lands with |
|---|---|---|
| UI-0 ✅ | Global shell, theme, task-oriented menu, Home skeleton | Phase 0 |
| UI-0b ✅ | External stylesheet; align all FAB core components (colours + fonts) with the shell | Phase 0 follow-up |
| UI-0c ✅ | Disable Bootswatch `flatly.css`; make `plmsys.css` the FAB theme with complete Bootstrap 3/FAB token + component coverage | UI-0b follow-up |
| UI-1 | Object page: Summary / Details / Relations / History | Phases 1–3 |
| UI-2 | Global search, advanced/saved searches | Phase 11 |
| UI-3 | Favorites, Recent, Worklist, user context prefs | Phases 9, 12 |
| UI-4 | Structure Manager (BOM tree + data panes) | Phase 5 |
| UI-5 | Traceability Matrix + Impact Analysis | Phases 4, 6 |
| UI-6 | Configuration-context selector + baseline compare | Phase 6 |
| UI-7 | Attachments viewer, verification tab, lifecycle command bar | Phases 2, 7, 8 |
| UI-8 | Home tiles, KPIs, reporting charts | Phase 11 |
| UI-9 | Responsive, accessibility, role-tailored UI | Phases 12–13 |

### Phase 0 — Foundation — ✅ Complete

**Objective:** stable, repeatable dev environment. **Status: complete.**

1. ✅ App factory, config, models, seed and bootstrap views.
2. ✅ `pytest` fixtures (`tests/conftest.py`): temporary SQLite `app` fixture
   plus anonymous, `admin` and non-admin test clients.
3. ✅ Smoke tests asserting full seed counts and idempotency
   (`tests/test_smoke.py`).
4. ✅ `flask fab create-admin` documented in `README.md` (with scriptable flags).
5. ✅ Alembic (`flask-migrate`) owns the schema; `FAB_CREATE_DB=False` and
   `metadata.create_all` removed from the runtime path:
   - `app/security.py` bootstraps roles without creating tables.
   - `migrations/env.py` targets FAB's shared `Model.metadata`.
   - Initial migration `05a62086ca6d_initial_schema.py` creates all 33 tables.
   - `AUTO_CREATE_SCHEMA` remains a test-only fallback.

**Deliverable:** ✅ `flask run` boots (verified end-to-end from a clean DB),
`pytest` passes (**20 tests**), and migrations own the schema (`flask db migrate`
reports "No changes in schema detected").
**UI (UI-0):** ✅ global shell (`base_layout.html`), task-oriented menu, Home
skeleton and a Bootstrap colour schema
([`ui_plan.md`](./ui_plan.md) §6, §7.1, §9–10).

**UI (UI-0b — ✅ complete):** the theme was externalised from `config.py` to
`app/templates/static/plmsys.css` (served at `/static/plmsys.css`) and the
overrides were extended to every core FAB/Bootstrap 3 component, with shared
colour and font custom properties so the shell and FAB render identically. See
[`ui_plan.md`](./ui_plan.md) UI-0b.

**UI (UI-0c — ✅ complete):** `APP_THEME` is now `""`, so FAB no longer loads
`flatly.css`; `plmsys.css` is the sole theme layer and was expanded into a full
Bootstrap 3 theme (mirrored design tokens + the complete component/state
matrix), including FAB's `ab.css` helpers. Tests assert no Bootswatch theme is
requested and that `plmsys.css` is last. Detail in
[`ui_plan.md`](./ui_plan.md) UI-0c.

---

### Phase 1 — Domain services layer — ✅ Complete

**Objective:** move business rules out of views/models into testable services.

1. ✅ Create `app/services/` with a shared `ServiceError` exception.
2. ✅ `revisions.py`:
   - `next_revision_id(obj, numeric=False)` — compute the next revision label
     (`A→B→…`, `01→02`).
   - `create_revision(obj, title, description, user)` — insert `Revision`, add
     `RevisionLineage` from the previous current revision, copy properties,
     advance `current_revision_id`, start in the `Draft` lifecycle state.
   - `revert_to_revision(obj, revision)`.
3. ✅ `properties.py`:
   - `get_definition(object_type, name)`.
   - `set_property(revision, definition, value, sequence_no=1)` — coerce to the
     correct column based on `PropertyDataType`; enforce `mandatory` and
     `multi_value`; upsert.
   - `get_properties(revision)` — typed dict.
   - `copy_properties(source_revision, target_revision)` — used when branching a
     revision.
   - `validate_required(revision, object_type)`.
4. ✅ `relationships.py`:
   - `create_relationship(type_name, primary, secondary)` with duplicate and
     self-reference guards.
   - `trace(revision, direction, type_names=None, max_depth=None)` — transitive
     traversal for traceability reports.
5. ✅ `lifecycle.py` (added during review to reconcile the dual status/cache
   representation): `assign_release_state`, `release`, `obsolete`,
   `current_state_name`, `ensure_released`, with the state machine
   `Draft → Review → Approved → Released → Obsolete`.
6. ✅ Unit tests under `tests/services/`, including a `PropertyDataType`
   coercion matrix.

**Deliverable:** ✅ services with thorough unit coverage, ready for views to
call. **UI (UI-1):** Object page tabs can now consume the
`properties`/`relationships` services.

---

### Phase 2 — Revision & lifecycle management

**Objective:** controlled revision creation and release lifecycle through the
UI.

> **Dependency:** the service layer already exists. `services/lifecycle.py`
> (`assign_release_state`, `submit_for_review`, `approve`, `release`,
> `obsolete`, `current_state_name`, `ensure_released`, and the state machine)
> and `services/revisions.py` (`create_revision`, `revert_to_revision`) landed
> in Phase 1. This phase **wires those services into FAB**; do not reimplement
> business logic here.

1. Create a shared **`RevisionActionsMixin`** (e.g. `app/views/revisions.py`)
   used by `BusinessObjectModelView`, `RequirementModelView` and
   `RevisionModelView`. Every action must:
   - normalise its argument (a single model on the show route, a list on
     `POST /action_post`);
   - call the service, `commit` on success and `rollback` on `ServiceError`;
   - `flash(...)` the outcome (invalid transitions as `"danger"`) and
     `redirect(self.get_redirect())`.
2. **"Create Revision"** action on `BusinessObjectModelView` and
   `RequirementModelView` (single row) → `revisions.create_revision(obj)`.
   The service computes the next label, records `RevisionLineage`, copies
   property values and starts the revision in `Draft`. If a title/description
   or a copy/no-copy choice is wanted, use an action form; otherwise document
   that the object's name/description and copy-by-default are used.
3. **"Set Current Revision"** action on `RevisionModelView` (single row —
   **not** on the object, since a FAB action there cannot choose a revision) →
   `revisions.revert_to_revision(revision.business_object, revision)`, which
   validates ownership and re-syncs the status cache.
4. **Lifecycle actions** on `RevisionModelView` (single row, with confirmation
   for Release/Obsolete): Submit for Review, Approve, Release, Obsolete →
   `lifecycle.submit_for_review/approve/release/obsolete`. Document the actual
   transition table: in addition to the forward chain
   `Draft → Review → Approved → Released → Obsolete`, the implementation allows
   `Review → Draft`, `Approved → Review`, and any state → `Obsolete`.
5. **Release-state badges** via `@renders` on `RevisionModelView`: a
   `release_state_badge` accessor reading `lifecycle.current_state_name(revision)`,
   mapped to Bootstrap labels (`Draft=label-default`, `Review=label-info`,
   `Approved=label-warning`, `Released=label-success`,
   `Obsolete=label-danger`). Include the state **text**, not colour alone
   ([`ui_plan.md`](./ui_plan.md) UI-9).
6. **Stop bypassing the lifecycle.** Remove `status` from the add/edit columns
   of `RevisionModelView` and `BusinessObjectModelView` (it is a cache owned by
   `services/lifecycle` — convention §3.14), and remove `current_revision` from
   `BusinessObjectModelView.edit_columns` so it changes only via the "Set
   Current Revision" action. Make the `Revision` add form read-only or route
   creation through the action.
7. **Enforce the baseline guard.** Add `pre_add` (or `on_model_change`)
   validation to `BaselineMemberModelView` calling
   `lifecycle.ensure_released(revision)`; Phase 6's `create_baseline` service
   must call the same guard.
8. **Permissions.** New actions register permissions named after the action
   (`create_revision`, `set_current_revision`, `release`, …). Admin is
   auto-granted; Phase 12 maps them onto the Engineer/Reviewer roles.
9. **Tests** (`tests/views/`): actions through the show route *and*
   `/action_post`; invalid transition flashes and leaves state unchanged;
   viewer denied; badge rendering; the baseline guard rejects a `Draft`
   revision. Keep `test_all_list_views_render` green.
10. **Seed.** Replace the vague "additional lineage chains" with: branch the
    seeded multi-revision objects through `revisions.create_revision(...)` so
    lineage and release-state rows are produced by the service, or drop the
    item.

**Deliverable:** users can branch, approve, release/obsolete and set the
current revision through the UI; invalid transitions and non-released baseline
members are rejected with a flash message.
**UI (UI-1/UI-7):** list/show release-state badges land in this phase; the
Object-page History tab (`RevisionLineage` + release-state changes) and the
lifecycle command bar are delivered with the Object page.

---

### Phase 3 — Property system (metadata-driven editing)

**Objective:** make properties first-class in the UI.

1. Custom `PropertyDefinition` admin already exists; add validation:
   - `name` matches `^[a-z][a-z0-9_]*$`.
   - Changing `data_type` after values exist is blocked.
2. Build a **dynamic property form** on the `Revision` show page:
   - `BaseView` or a custom `show_template` that lists
     `PropertyDefinition`s for the revision's object type and renders inputs by
     `data_type`.
   - Multi-valued definitions render repeatable rows.
3. `SimpleFormView`/POST handler to submit values through
   `properties.set_property`.
4. Add a **Property Matrix** report (`GroupByChartView` or a custom
   `BaseView` table): rows = requirements, columns = selected property
   definitions.
5. Seed verification: every seeded `PropertyValue` matches its definition's
   `data_type`.

**Deliverable:** properties can be viewed/edited without touching the DB or
schema.
**UI (UI-1):** Summary/Details tabs render and edit `PropertyValue`s on the
Object page.

---

### Phase 4 — Traceability

**Objective:** rich, queryable trace links.

1. Add FAB `@action`s on `RequirementModelView`:
   - "Derive requirement" (creates object + `DEFINING` relationship).
   - "Allocate to…" (`ALLOCATED_TO`).
   - "Verify by…" (`VERIFIED_BY`).
2. Add a **Traceability Matrix** view:
   - Rows: requirements (via `base_filters` on `object_type.name`), columns:
     child/allocated/verified revisions.
   - Implement as a read-only `BaseView` querying `Relationship`.
   - Support depth traversal via `relationships.trace(...)`.
3. Add "Relationships" related view tab on `RevisionModelView` (note: two FKs
   to `Revision`, so scope with `base_filters` or a custom read-only view).
4. Seed a deeper decomposition chain and cross-domain links
   (requirement ↔ software component, requirement ↔ function).

**Deliverable:** end-to-end requirement decomposition visible in the UI.
**UI (UI-5):** Traceability Matrix with coverage-gap highlighting; Relations
tab cross-links.

---

### Phase 5 — BOM & occurrence trace

1. Add a **BOM tree** view for a `Part` revision:
   - Recursive `BOMOccurrence` traversal with roll-up quantity.
   - Read-only `BaseView` rendering `templates/bom_tree.html`.
2. Add "Add child occurrence" action on `RevisionModelView` (Part revisions).
3. `services/bom.py`: `where_used(revision)`, `bom_rollup(revision)`,
   `explode(revision, depth)`.
4. Occurrence trace:
   - UI to link a requirement revision to a BOM occurrence
     (`OccurrenceTrace`).
   - Report: "requirements traced to this BOM line" and
     "BOM lines without requirement coverage" (coverage gap report).

**Deliverable:** BOM explorer + requirement coverage report.
**UI (UI-4):** Structure Manager — tree, data panes, search area, status.

---

### Phase 6 — Configuration management & baselines

1. `services/configuration.py`:
   - `resolve(context)` — apply a `RevisionRule` to pick a revision per object.
   - `create_baseline(context, name, user)` — snapshot resolved revisions into
     `Baseline` + `BaselineMember`.
   - `compare_baselines(a, b)` — additions/removals/revision changes.
2. Add a **"Create Baseline"** form (`SimpleFormView`) under a configuration
   context.
3. Baseline detail view: members grouped by object type with revision IDs.
4. Wire `RevisionRule` implementations:
   - `Latest Working` → highest `sequence_no`, status ≠ Obsolete.
   - `Latest Released` → highest `sequence_no` with a `Released` state.

**Deliverable:** reusable baselines and baseline diff.
**UI (UI-6):** header configuration-context selector; baseline compare page.

---

### Phase 7 — Datasets & file uploads

1. Replace the `ManagedFile.storage_path` string with a FAB `FileColumn`, or add
   a `file` column alongside it.
2. Configure `UPLOAD_FOLDER`, `FILE_ALLOWED_EXTENSIONS` in `config.py`.
3. `DatasetModelView`: file upload/download via FAB's file manager.
4. `ManagedFile` show page: download link, size, mime type, thumbnail for images
   (`ImageColumn` + Pillow if needed).
5. `services/datasets.py`: attach file, checksum, delete on dataset removal.
6. Seed a dataset with a small placeholder file under `app/static/uploads/`.

**Deliverable:** files attachable to revisions and downloadable.
**UI (UI-7):** Attachments tab and viewer on the Object page.

---

### Phase 8 — Verification

1. `services/verification.py`:
   - `record_result(test_revision, result, summary, execution_date)`.
   - Automatically create/refresh a `VERIFIED_BY` relationship from each
     requirement linked to the test.
2. UI: "Record verification result" action on `TestCase`-type objects.
3. Requirement show page: verification status derived from linked
   `VerificationResult`s (Passed/Failed/Not Run).
4. Report: verification coverage per requirement.

**Deliverable:** requirements traceable to test outcomes.
**UI (UI-1/UI-8):** Verification tab with pass/fail indicators and coverage
chart.

---

### Phase 9 — Workflow

1. `services/workflow.py`:
   - `start_process(name, revision)`, `complete_task(task)`,
     `advance_state(process)`.
   - Task states: `Open → In Progress → Done / Cancelled`.
2. Actions on `WorkflowProcessModelView`: start, complete, cancel.
3. Auto-create workflow tasks from release-state transitions (e.g. entering
   `Review` creates a review task).
4. Notifications hook (email via Flask-Mail) — optional, later.

**Deliverable:** process/task tracking with state transitions.
**UI (UI-3):** My Worklist view with Start/Complete actions.

---

### Phase 10 — REST API

1. Add `app/api/` with `ModelRestApi`s for the main entities:
   - `object`, `revision`, `property`, `relationship`, `baseline`,
     `dataset`, `verification`, `workflow`.
2. Global read-only API base with `class_permission_name` compression.
3. Custom `BaseApi` endpoints:
   - `GET /api/v1/trace/<revision_id>` — traceability traversal.
   - `GET /api/v1/bom/<revision_id>` — exploded BOM.
   - `POST /api/v1/revisions/<id>/release`.
4. Enable Swagger UI (`FAB_API_SWAGGER_UI = True`) and document endpoints with
   OpenAPI docstrings.
5. Tests using a JWT obtained from `/api/v1/security/login`.

**Deliverable:** documented, tested JSON API.
**UI:** headless; supplies data to UI-2 search and external clients.

---

### Phase 11 — Search & reporting

1. Global search view across `BusinessObject` (number/name) and `PropertyValue`
   (string values), respecting property definitions.
2. Charts (`GroupByChartView`):
   - Requirements by status / priority.
   - BOM occurrences by parent part.
   - Verification results by outcome.
3. Dashboard `IndexView` with key counts and traceability coverage.

**Deliverable:** dashboard + search + charts.
**UI (UI-2/UI-8):** global search with saved searches; Home tiles and KPIs.

---

### Phase 12 — Security & roles

1. Define FAB roles (`app/security.py`):
   - **Engineer** — create/edit objects/revisions/properties.
   - **Reviewer** — approve/review, read-only elsewhere.
   - **Viewer** — read-only (`can_list`, `can_show`).
   - **Admin** — full.
2. `base_permissions` / `class_permission_name` per view; write a
   `security-converge` migration note.
3. Row-level scoping example (e.g. limit by programme) using
   `base_filters` + `FilterEqualFunction`.
4. Harden config: rotate `SECRET_KEY` from env, `AUTH_USER_REGISTRATION=False`
   in production, rate limiting on login.

**Deliverable:** least-privilege roles and production-safe config.
**UI (UI-9):** role-tailored tiles and menu via `menu_cond`; `Setup` hidden
from non-admins.

---

### Phase 13 — Quality, migrations & release

1. **Testing tiers:**
   - Unit: services (`tests/services/`).
   - Integration: views via logged-in test client (`tests/views/`).
   - API: `tests/api/`.
   - Property-coercion matrix test for all `PropertyDataType`s.
2. **Migrations:** every model change accompanied by an Alembic revision;
   add a `flask db upgrade` step to CI.
3. **CI:** lint (`ruff`), type check (`mypy` optional), `pytest`, migration
   autogenerate diff check.
4. **i18n:** run `flask fab babel-extract` / `babel-compile`; label new strings
   with `lazy_gettext`.
5. **Docs:** update README, add `docs/architecture.md`, `docs/erd.md`.
6. **Packaging:** pin deps in `pyproject.toml`, tag `v0.1.0`.

**Deliverable:** reproducible, tested, migratable release.
**UI (UI-9):** responsive + accessibility audit; UI regression tests via the
logged-in test client.

---

## 6. Milestone sequencing

| Milestone | Functional | UI | Outcome |
|---|---|---|---|
| M1 — Foundation & shell | 0–2 | UI-0 | Services, revision/release, migrations, task-oriented shell + Home |
| M2 — Metadata & traceability | 3–4 | UI-1, UI-5 | Metadata-driven properties, Object page, traceability matrix |
| M3 — Product structure | 5–6 | UI-4, UI-6 | Structure Manager, configuration context + baselines |
| M4 — Data & quality | 7–9 | UI-3, UI-7 | Datasets, verification, workflow, Object-page completion, Worklist |
| M5 — Integration | 10–12 | UI-2, UI-8, UI-9 | REST API, search/dashboard, responsive/role-tailored UI |
| M6 — Hardening | 13 | UI-9 | CI, docs, accessibility audit, release |

> **Progress:** M1 in progress — Phase 0 + UI-0 ✅ complete; Phase 1 services ✅
> complete; Phase 2 pending.

---

## 7. Cross-cutting concerns

- **Migrations over `create_all`.** Keep `metadata.create_all` only for tests.
- **Service layer owns invariants**; views stay thin and call services.
- **Property values are typed** — always coerce via `PropertyDataType`; never
  stuff everything into `string_value`.
- **Traceability is directional.** `primary --type--> secondary`; document the
  meaning of each `RelationshipType` (already in seed descriptions).
- **Idempotent seeding** must remain true as seed grows; consider moving to
  Alembic data migrations or a `seed/` package with per-domain modules.
- **Database portability.** Avoid DB-specific types; the models are already
  SQLite/PostgreSQL/MySQL compatible.
- **Reserved WTForms names** must never be used as model attributes (see §3.3).
- **UI conforms to [`ui_plan.md`](./ui_plan.md).** Navigation is task-oriented,
  not table-oriented; the Object page is the primary surface; every object
  reference is a link ("1-click-away").
- **One stylesheet for the shell and FAB.** App CSS lives in
  `app/templates/static/plmsys.css` (loaded after FAB's base theme); colours and
  fonts are `--plmsys-*` custom properties. Target Bootstrap 3 class names and
  never put CSS back into `config.py`
  ([`ui_plan.md`](./ui_plan.md) UI-0b).
- **Custom pages stay thin.** `BaseView`/UI code queries through
  `app/services/`, uses FAB's `SQLAInterface` where possible, and never issues
  ad-hoc SQL.
- **Configuration context is globally visible** and selectable; the UI reads it
  from `UserPreference` ([`ui_plan.md`](./ui_plan.md) §8).
- **Extend, don't fork, the FAB shell.** Override only the required
  `appbuilder/baselayout.html` blocks; re-verify overrides on every FAB upgrade.
- **Accessibility is part of done** for every UI phase (landmarks, keyboard
  navigation, non-colour status cues).

---

## 8. Acceptance criteria (overall)

1. `flask run` → login → all menu categories render without errors.
2. A user can create an object, branch a revision, edit metadata-driven
   properties, link revisions, and release the revision — all through the UI.
3. Baselines can be created and compared.
4. BOM can be exploded and traced to requirements.
5. Test results update requirement verification status.
6. REST endpoints return correct data with JWT auth and appear in Swagger.
7. `pytest` passes in CI; schema is owned by Alembic migrations.
8. `/` lands on a personalized Home with tiles, worklist and recents; global
   search is reachable from every page and supports saved searches.
9. Every `BusinessObject` has an Object page with Summary/Details/Relations/
   Structure/Verification/Attachments/History tabs, and all object references
   are clickable.
10. The active configuration context is visible and selectable; Favorites,
    Recent, Worklist and Saved Searches persist per user.
11. Structure Manager supports expand/collapse, quantities and status symbols;
    the Traceability Matrix highlights coverage gaps.
12. Setup/meta-model views are hidden from non-admins; the UI is
    keyboard-navigable and passes a basic accessibility audit.
13. UI behaviour matches the acceptance criteria in
    [`ui_plan.md`](./ui_plan.md) §12.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Metadata-driven properties weaken DB constraints | Validate in `properties.set_property`; add service tests; optional typed CHECK constraints later |
| Recursive BOM/trace traversal performance | Cache roll-ups; cap depth; add indexes on FK columns |
| FAB form field name collisions | Lint/checklist against reserved WTForms names (§3.3) |
| `Enum` + FAB incompatibility | Keep member names as `enums`; never use `values_callable` with FAB forms |
| Circular FK across DB backends | Keep `post_update=True`; test on PostgreSQL before production |
| Schema drift from `create_all` | Switch to Alembic in Phase 0 |
| UI shell drifts from FAB upgrades | Override only needed blocks in `base_layout.html`; pin FAB; add a visual smoke test |
| Custom `BaseView` pages bypass FAB CRUD conventions | Route queries through `app/services`; reuse `SQLAInterface`; keep FAB list views as fallback |
| Structure/trace tree performance at scale | Lazy loading, depth caps, FK indexes ([`ui_plan.md`](./ui_plan.md) §11) |
| UI scope creep delays core functionality | Gate each UI phase on its backing functional phase; ship shell + Object page first |
