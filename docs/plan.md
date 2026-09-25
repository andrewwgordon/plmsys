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

### Phase 2 — Revision & lifecycle management — ✅ Complete

**Objective:** controlled revision creation and release lifecycle through the
UI.

> **Dependency:** the service layer already exists. `services/lifecycle.py`
> (`assign_release_state`, `submit_for_review`, `approve`, `release`,
> `obsolete`, `current_state_name`, `ensure_released`, and the state machine)
> and `services/revisions.py` (`create_revision`, `revert_to_revision`) landed
> in Phase 1; this phase wired them into FAB.

1. ✅ **`app/view_mixins.py`** adds a shared action base (`RevisionActionMixin`)
   plus two focused subclasses: `CreateRevisionMixin` (object views) and
   `RevisionLifecycleMixin` (`RevisionModelView`). Every action normalises its
   FAB single/list argument, calls the service, `commit`s on success,
   `rollback`s on `ServiceError`, flashes the outcome and redirects.
2. ✅ **Create Revision** on `BusinessObjectModelView` and
   `RequirementModelView` → `revisions.create_revision(obj)` (next label,
   lineage, property copy, `Draft` state). No action form: the service uses the
   object's name/description and copies properties by default.
3. ✅ **Set Current Revision** on `RevisionModelView` (single row) →
   `revisions.revert_to_revision(...)`, which validates ownership and re-syncs
   the status cache.
4. ✅ **Submit for Review / Approve / Release / Obsolete** on
   `RevisionModelView` → `services/lifecycle`. The service's transition table
   is the forward chain plus `Review → Draft`, `Approved → Review`, and any
   state → `Obsolete`.
5. ✅ **Release-state badge** — `Revision.release_state_badge`
   (`@renders("status")`, defined on the **model** where FAB expects it)
   renders the canonical state as a Bootstrap label with text, shown in the
   `RevisionModelView` list and show columns.
6. ✅ **Lifecycle bypass removed** — `status` removed from the add/edit columns
   of `RevisionModelView` and `BusinessObjectModelView`, `current_revision`
   removed from `BusinessObjectModelView.edit_columns`, and `can_add` dropped
   from `RevisionModelView.base_permissions` so creation goes through the
   action.
7. ✅ **Baseline guard** — `BaselineMemberModelView.pre_add`/`pre_update` call
   `lifecycle.ensure_released`; Phase 6's `create_baseline` must reuse it.
8. ✅ **Permissions** — actions register permissions named after the action
   (`create_revision`, `set_current_revision`, `release_revision`, …); Admin is
   auto-granted, Phase 12 maps them onto the Engineer/Reviewer roles.
9. ✅ **Tests** — `tests/views/` covers create/set-current/lifecycle actions,
   invalid-transition flash, viewer denial, badge rendering and the baseline
   guard. `test_all_list_views_render` stays green; the view tests isolate
   mutations with a commit→flush + rollback fixture.
10. ⏭️ **Seed item dropped** — the seed already records `RevisionLineage` for
    both multi-revision objects (`REQ-0001`, `PART-1001`), so no change was
    needed.

**Review follow-ups (applied):** actions call `update_redirect()` so they return
to the referring page, not Home; the baseline guard only detaches *transient*
items (never a persistent row); the Setup release-state view is read-only so it
cannot bypass the service; `Revision.release_states` eager-loads
(`lazy="selectin"`) to remove the badge N+1; revision identity and object
type/number are no longer editable; action handlers handle `None` inputs and
`IntegrityError`; and the badge escapes its state name. Covered by
`tests/views/test_phase2_regressions.py`.

**Deliverable:** ✅ users can branch, approve, release/obsolete and set the
current revision through the UI; invalid transitions and non-released baseline
members are rejected with a flash message.
**UI (UI-1/UI-7):** ✅ list/show release-state badges delivered; the Object-page
History tab (`RevisionLineage` + release-state changes) and the lifecycle
command bar are delivered with the Object page.

---

### Phase 3 — Property system (metadata-driven editing) — ✅ Complete

**Objective:** make properties first-class in the UI: view and edit typed,
multi-valued business data driven entirely by `PropertyDefinition` rows, with no
schema change.

> **Dependency:** `services/properties.py` (coercion, `set_property`,
> `get_properties`, `copy_properties`, `validate_required`) landed in Phase 1.
> This phase hardens that service, adds admin validation and builds the editing
> UI, reusing the Phase 2 patterns for guards, permissions and transactions.

1. **Harden the property service** (`app/services/properties.py`):
   - add `delete_property(revision, definition, sequence_no)` /
     `clear_properties(revision, definition)` so multi-valued rows can be
     removed (today a cleared value is left as an all-null row and
     `get_properties` returns `[None, …]`);
   - define `mandatory` as **per definition** (at least one non-null value), not
     per sequence, and enforce it in `set_property`;
   - add a `matrix(revisions, definitions)` helper returning typed cell values
     via `read_value`;
   - document that definitions are matched on the **exact** `object_type_id`
     (no `parent_type` inheritance) until ancestor lookup is added consistently
     to `get_definition`, `set_property`, `validate_required` and the form.
2. **Definition admin validation** (`PropertyDefinitionModelView.pre_add` /
   `pre_update`):
   - `name` matches `^[a-z][a-z0-9_]*$` **and** is not a reserved WTForms name
     (`data`, `errors`, `meta`, `validate`, `csrf_token`, `process`, …) — the
     dynamic form uses the property name as a field name (item 4);
   - changing `data_type`, `object_type` or `multi_value` is blocked once values
     exist. `pre_update` runs after `form.populate_obj`, so read the old value
     via `sqlalchemy.inspect(item).attrs.<attr>.history` (or a
     `db.session.no_autoflush` scalar query) before raising.
3. **Close the raw-value bypass:** make `PropertyValueModelView` read-only
   (`base_permissions = ["can_list", "can_show"]`) so every write goes through
   `properties.set_property` — the same rule applied to
   `RevisionReleaseStateModelView` (Phase 2, H3). Raw typed columns must never be
   edited directly.
4. **Dynamic property form** — `RevisionPropertiesView(BaseView)` at
   `/revision/<int:pk>/properties` (GET renders, POST saves):
   - build a WTForms class at runtime from the revision's definitions, mapping
     `STRING→StringField`, `INTEGER→IntegerField`, `FLOAT→FloatField`,
     `DATE→DateField`; `multi_value` definitions use
     `FieldList(field, min_entries=1)` with add/remove rows;
   - prefix generated fields (`prop_<name>`) to avoid WTForms reserved-name
     collisions, stripping the prefix before calling the service;
   - on POST call `properties.set_property` per value, catch `ServiceError` →
     `flash(..., "danger")`, then run `validate_required` for missing mandatory
     values; commit on success and roll back on error (Phase 2 mixin pattern);
   - guard with `@has_access` and an explicit permission so Phase 12 can grant
     it. **Do not use `SimpleFormView`**: its single `/form` route has no pk, so
     the revision id would have to be a spoofable form field.
5. **Object-page integration** — surface the form from the UI-1 Object page
   Details tab (with a revision selector), or at minimum link it from a
   `RevisionModelView` show action. The shell is the entry point, not the DB.
6. **Property Matrix** — a read-only `BaseView` +
   `templates/property_matrix.html` (not `GroupByChartView`, which is for
   aggregated charts): rows = revisions of a selectable object type (default
   Requirement), columns = selected definitions via a multi-select, cells =
   `read_value`; eager-load `property_values`/`property_definition` to avoid the
   badge-style N+1. Optional CSV export (UI-2).
7. **Seed typed and multi-valued data.** Add at least one
   `INTEGER`/`FLOAT`/`DATE` definition and one `multi_value=True` definition with
   values (all 8 current definitions are `STRING`, so the typed and multi-value
   paths are never exercised), and update `EXPECTED_COUNTS`.
8. **Tests** (`tests/services/`, `tests/views/`):
   - seed: every `PropertyValue` populates exactly one typed column matching its
     definition's `data_type`, others null;
   - service: `delete_property` and mandatory-per-definition semantics;
   - admin validation: regex, reserved names, the `data_type`/`object_type`/
     `multi_value` lock, and `PropertyValueModelView` read-only;
   - form: GET renders inputs by type; POST coerces and stores; invalid input
     and missing mandatory values flash; multi-value add/remove; wrong object
     type rejected;
   - matrix renders selected definitions with no N+1.
   Reuse the `tests/views/conftest.py` commit→flush isolation fixture.

**Delivered:** `services/properties.py` gained `delete_property` /
`clear_properties` (with `delete-orphan` collection consistency), per-definition
mandatory checks and `matrix`; `PropertyDefinitionModelView` validates the name
regex + reserved WTForms names and locks `data_type`/`object_type`/`multi_value`
once values exist (rolling back so a rejected edit cannot be autoflushed);
`PropertyValueModelView` is read-only; a dynamic
`RevisionPropertiesView(BaseView)` (runtime WTForms, `FieldList` multi-value,
prefixed fields) and a `PropertyMatrixView` landed, plus an **Edit Properties**
revision action; the seed now carries typed (`INTEGER`/`FLOAT`/`DATE`) and
multi-valued (`tags`) definitions/values; and `PropertyDefinitionModelView`
overrides the non-nullable booleans as optional so false values can be
submitted. Covered by `tests/services/test_properties.py` and
`tests/views/test_property_views.py`.

**Deliverable:** properties are viewed and edited through the UI for every
`PropertyDataType` (including multi-value add/remove) using only
`PropertyDefinition` rows; definition changes that would invalidate existing
data are rejected; raw `PropertyValue` editing is closed.
**UI (UI-1):** Summary/Details tabs on the Object page render and edit
`PropertyValue`s; the property form and matrix supply their data.

---

### Phase 4 — Traceability — ✅ Complete

**Objective:** rich, queryable, directional trace links, visible and clickable
in the UI.

> **Dependency:** `services/relationships.py` (`create_relationship` with
> self/duplicate guards, and `trace` BFS traversal) landed in Phase 1. This
> phase adds model integrity, relation forms and the matrix/relations UI,
> reusing the Phase 2 transaction/permission patterns and the Phase 3 `BaseView`
> pattern.

1. **Model and service integrity (do this first):**
   - add `UniqueConstraint(relationship_type_id, primary_revision_id,
     secondary_revision_id)` to `Relationship` plus an Alembic migration, so
     the seed/view/API cannot create duplicates and the check-then-insert race
     in `create_relationship` is closed;
   - keep the service self-reference guard (a portable DB CHECK is not
     available) and enforce it in any editable view;
   - add a `neighbours(revision, direction, type_names)` (and/or bulk helper)
     returning **typed edges** `(relationship, neighbour)`; `trace` stays for
     reachability. Relationships link **revisions**
     (`primary --type--> secondary`).
2. **Relation forms** (`BaseView`, service-backed, `@has_access`, using the
   Phase 2 mixin for `commit`/`rollback`/flash):
   - **Derive Requirement** — input number/name/description (optionally copy
     properties) → create the object/revision via `revisions.create_revision`,
     then `create_relationship("DEFINING", selected, new)`;
   - **Allocate to…** — pick a target object → `create_relationship(
     "ALLOCATED_TO", selected, target.current_revision)`;
   - **Verify by…** — pick a target object → `create_relationship(
     "VERIFIED_BY", selected, target.current_revision)`.
   State the direction explicitly in the labels.
3. **`TraceabilityMatrixView`** (read-only `BaseView` +
   `templates/traceability_matrix.html`):
   - rows = each requirement's **current revision** (query
     `ObjectType.name == "Requirement"` explicitly — `base_filters` is a
     `ModelView` concept and does not apply to `BaseView`);
   - columns = `DEFINING` levels (customer → system → subsystem → component)
     plus `ALLOCATED_TO`, `VERIFIED_BY`, `SATISFIED_BY`; cells are
     click-through links (multiple links shown as a short list);
   - define and highlight **coverage gaps** (e.g. a requirement with no
     `VERIFIED_BY` and no `ALLOCATED_TO`/`SATISFIED_BY` target);
   - bulk-load the relationships for the row set once and group in Python — do
     **not** call `trace` per row (`_neighbours` is N+1);
   - optional CSV export ([`ui_plan.md`](./ui_plan.md) UI-2).
4. **Relations section** on the revision (or the UI-1 Object page Relations
   tab): a custom read-only view listing **outbound and inbound** relationships
   grouped by type, with click-through links. FAB `related_views` cannot be
   scoped per parent for a two-FK model, so build it as a `BaseView` (or a
   section on the revision show). Make `RelationshipModelView` read-only (or
   Setup-only) and remove it from the primary nav
   ([`ui_plan.md`](./ui_plan.md) §6.2) so it cannot bypass the service guards.
5. **Seed** the missing cross-domain links — requirement ↔ Function and
   requirement ↔ SoftwareComponent (e.g. `REQ-0002 --ALLOCATED_TO--> SWC-400`,
   `REQ-0001 --SATISFIED_BY--> FUNC-200`) — and update
   `EXPECTED_COUNTS["Relationship"]`.
6. **Tests** (`tests/services/`, `tests/views/`): relation forms
   (derive/allocate/verify, direction and target revision); DB duplicate/self
   guards; matrix rendering + coverage gaps + no N+1; the relations section;
   permission denial; and the new seed links. Reuse the
   `tests/views/conftest.py` commit→flush fixture.

**Delivered:** `Relationship` gained
`UniqueConstraint(relationship_type_id, primary_revision_id,
secondary_revision_id)` (migration `1bb38e525b37`), and
`services.relationships` gained the typed-edge `neighbours(...)` helper (with
`trace` refactored onto it). `app/ui/traceability.py` provides the
service-backed `RelationFormView` (Add Relation), `DeriveRequirementView` (new
object/revision via `revisions.create_revision` + optional property copy +
`DEFINING` link), the inbound/outbound `RevisionRelationsView`, and the
bulk-loaded `TraceabilityMatrixView` with coverage-gap rows. Revision actions
(Relations / Add Relation / Derive Requirement) link into them;
`RelationshipModelView` is read-only and moved to Setup. The seed adds
requirement ↔ Function and requirement ↔ SoftwareComponent links. Covered by
`tests/services/test_relationships.py` and `tests/views/test_traceability.py`.

**Review follow-ups (applied):** `properties.copy_properties` skips definitions
that do not belong to the target revision's object type (no cross-type copy on
derive); the relation/derive forms catch `IntegrityError` as well as
`ServiceError`; `relationships.neighbours` eager-loads its typed edges (no
N+1); the Add Relation form restricts target objects to type-appropriate ones
and rejects mismatches; derive is limited to requirement sources; the matrix
joins the current revision in SQL; and the migration documents the duplicate
cleanup needed before adding the unique constraint.

**Deliverable:** end-to-end requirement decomposition and cross-domain
traceability visible in the UI; duplicate and self links rejected at both the
service and DB level.
**UI (UI-5):** Traceability Matrix with coverage-gap highlighting and
click-through cells; Relations section cross-links.

---

### Phase 5 — BOM & occurrence trace — ✅ Complete

**Objective:** a cycle-safe product-structure explorer with quantity roll-up
and requirement-to-BOM coverage.

> **Dependency:** unlike Phases 1–4 there is no BOM service yet, so this phase
> builds `services/bom.py`. It reuses the Phase 2 action/transaction pattern,
> the Phase 3/4 `BaseView` page pattern, and the Phase 4 integrity lessons
> (unique constraints + `IntegrityError` handling).

1. **Model and service integrity (do this first):**
   - add `UniqueConstraint(parent_revision_id, find_number)` to
     `BOMOccurrence` and `UniqueConstraint(requirement_revision_id,
     bom_occurrence_id)` to `OccurrenceTrace`, plus an Alembic migration;
   - create `services/bom.py` with:
     - `add_occurrence(parent, child, find_number, quantity)` /
       `remove_occurrence(occurrence)` guarding self-lines, duplicates,
       **cycles** (`would_create_cycle(parent, child)`), `quantity <= 0`, and
       non-`Part` revisions; keep the guards in the service and handle
       `IntegrityError` in the form (Phase 4 pattern);
     - `explode(revision, max_depth=None)` → flat
       `[{occurrence, child_revision, depth, quantity}]`, cycle-safe with a
       visited set and depth cap;
     - `bom_rollup(revision)` → `{child_revision_id: aggregate_quantity}` (sum
       of products over all paths; define rounding);
     - `where_used(revision, transitive=False)` → immediate (default) or
       transitive reverse BOM.
   - bulk-load the structure (one query per level) and eager-load
     `child_revision`/`business_object` so `explode`/roll-up are not per-node
     N+1.
2. **BOM UI:**
   - `BomTreeView` (read-only `BaseView` + `templates/bom_tree.html`) for a
     `Part` revision's current revision: recursive tree with per-line
     find_number, child object/revision, quantity and status, plus a data pane
     (requirement traces, status); enforce Part-only and a depth cap.
   - **Add child occurrence** — a `BaseView` **form** (an `@action` cannot pick
     the child): pick a child `Part` object, `find_number`, `quantity` →
     `services.bom.add_occurrence`. Link it from the revision show.
   - make `BOMOccurrenceModelView` read-only (or Setup-only) and remove it from
     the primary nav ([`ui_plan.md`](./ui_plan.md) §6.2) so raw rows cannot
     bypass the guards.
3. **Occurrence trace UI:**
   - a `BaseView` form to link a requirement's **current revision** to a BOM
     occurrence via a new service helper (`link_requirement(occurrence,
     revision)`) with a duplicate guard;
   - per-line pane "requirements traced to this BOM line";
   - report "BOM lines without requirement coverage" (an occurrence with no
     `OccurrenceTrace`), mirroring the Phase 4 coverage-gap wording;
   - make `OccurrenceTraceModelView` read-only (or Setup-only) and remove it
     from the primary nav.
4. **Seed** a 3-level structure with a shared subassembly and non-unit
   quantities, several `OccurrenceTrace` rows, and at least one **uncovered**
   BOM line so the coverage report has output; update `EXPECTED_COUNTS`.
5. **Tests** (`tests/services/`, `tests/views/`): `explode` (depth + cycle
   safety), `bom_rollup`, `where_used`, `add_occurrence` guards
   (self/duplicate/cycle/quantity/type), the DB unique constraints, the tree
   render, the add form, the per-line traces, the coverage report, and the seed
   counts. Reuse the `tests/views/conftest.py` isolation fixture.

**Delivered:** `BOMOccurrence` and `OccurrenceTrace` gained unique constraints
(migration `b82bd12c1ba6`); `app/services/bom.py` provides
`add_occurrence`/`remove_occurrence` (self/duplicate/cycle/quantity/Part
guards), `would_create_cycle`, `explode` (cycle-safe, depth-capped, accumulated
quantity), `bom_rollup`, `where_used`, `link_requirement` and
`uncovered_occurrences` — all bulk-loaded. `app/ui/bom.py` provides the
read-only `BomTreeView` (+ data pane), `AddOccurrenceView`,
`LinkRequirementView` and `BomCoverageView`; a **BOM** revision action links in.
`BOMOccurrenceModelView`/`OccurrenceTraceModelView` are read-only and moved to
Setup. The seed has a 3-level structure (with a shared plate) and one uncovered
line. Covered by `tests/services/test_bom.py` and
`tests/views/test_bom_views.py`.

**Review follow-ups (applied):** traversal fetches one level at a time
(batched `IN` queries, O(depth) not O(nodes)); `bom_rollup` reuses the exploded
rows instead of re-walking; quantities must be finite and positive; a back-edge
is marked as `cycle` in the tree; the BOM tree shows a **Where used** panel and
supports deleting a line (`RemoveOccurrenceView`); and tests cover the DB
constraints, non-requirement traces, `remove_occurrence`, non-finite quantities
and the batched query count.

**Deliverable:** a cycle-safe BOM explorer with roll-up quantity, plus
requirement-to-BOM coverage (per line and gap report); self/duplicate/cycle/
quantity violations rejected at the service and DB level.
**UI (UI-4):** Phase 5 ships the read-only tree + data pane (interactive
expand/collapse, search/filter, status symbols and the change context are added
by UI-4).

---

### Phase 6 — Configuration management & baselines — ✅ Complete

**Objective:** rule-driven configuration resolution, atomic baselines, and a
baseline diff.

> **Dependency:** no configuration service exists yet, so this phase builds
> `services/configuration.py`. It reuses the Phase 2 lifecycle
> (`current_state_name`, `ensure_released`), the Phase 3/4/5 `BaseView` form/page
> pattern, and the Phase 4/5 `IntegrityError` handling.

1. **Model integrity first:**
   - add `RevisionRule.rule_type` (e.g. `LATEST_WORKING` / `LATEST_RELEASED`),
     plus a migration and seed update — resolution must dispatch on the type,
     **not** the rule `name`;
   - add `UniqueConstraint(configuration_context_id, name)` to `Baseline` plus a
     migration;
   - fix the seed so every baseline member is `Released` (today the seeded
     baseline contains Draft/Approved revisions, contradicting both the Phase 2
     guard and the `Latest Released` rule), or build it via the service.
2. **`services/configuration.py`:**
   - `resolve(context)` — apply `context.revision_rule.rule_type` and pick, per
     object, the highest `sequence_no` revision that satisfies the rule
     (`LATEST_WORKING`: highest non-Obsolete; `LATEST_RELEASED`: highest with a
     `Released` state, read via the canonical lifecycle); document which
     objects are considered (all objects with a matching revision; skip those
     without) and eager-load so it is not N+1;
   - `create_baseline(context, name, created_by=None)` — resolve, call
     `lifecycle.ensure_released` for every member, and create `Baseline` +
     `BaselineMember` **atomically** (roll back on any guard failure); reject
     duplicate names per context; `created_by` is a plain string (the domain
     model has no user FK) — drop the `user` argument or add the column;
   - `compare_baselines(a, b)` — structured additions / removals / changes
     (same `BusinessObject`, different revision), returning a documented shape;
   - `add_baseline_member` / `remove_baseline_member` so the `ensure_released`
     guard lives in the service, not only in the view.
3. **Baseline UI:**
   - a `BaseView` **Create Baseline** form at
     `/configuration/<context_id>/baseline/new` (the context is fixed in the
     URL — do **not** use `SimpleFormView`, whose single `/form` route cannot
     scope the context): name input → `create_baseline`, `@has_access`,
     `ServiceError`/`IntegrityError` → flash;
   - a read-only `BaselineDetailView` grouping members by `object_type.name`
     (object number, revision, release state);
   - a `BaselineCompareView` taking two baseline ids (query args) with an
     added/removed/changed legend;
   - make `BaselineModelView`/`BaselineMemberModelView` read-only (or
     Setup-only) so raw rows cannot bypass atomic creation, and register the
     configuration views under the existing **Configuration** category.
4. **Context persistence:** UI-6's header selector is backed by
   `UserPreference`, which UI-3 schedules for Phases 9 & 12. Move the
   `UserPreference` model + migration into this phase, **or** explicitly scope
   UI-6 to a session-only selector and defer persistence. State which.
5. **Tests** (`tests/services/`, `tests/views/`): `resolve` per rule type;
   `create_baseline` release guard, duplicate-name rejection and atomicity;
   `compare_baselines` additions/removals/changes; the `RevisionRule.rule_type`
   and `Baseline` unique constraints; the create/detail/compare views; and a
   seed invariant that all baseline members are Released. Reuse the
   `tests/views/conftest.py` isolation fixture.

**Delivered:** `RevisionRule.rule_type` and `Baseline`'s
`UniqueConstraint(configuration_context_id, name)` + `created_by` (migration
`eb8e40076f38`); the seed now releases every baseline member (plus one Approved
example). `services/configuration.py` provides `resolve` (rule-type dispatch on
the canonical lifecycle), atomic `create_baseline` (`ensure_released` +
duplicate-name guard), `compare_baselines` (added/removed/changed) and
`add_baseline_member`/`remove_baseline_member`. `app/ui/configuration.py`
provides the context-scoped Create Baseline form, the grouped
`BaselineDetailView`, `BaselineCompareView`, and a session-based `SetContextView`
with a header context selector (persistence deferred — `UserPreference` is not
introduced). Baseline/member ModelViews are read-only and moved to Setup. A
`PLMSYS_AUTO_SEED=0` env override was added so migrations can autogenerate when
the seed already references a new column. Covered by
`tests/services/test_configuration.py` and
`tests/views/test_configuration_views.py`.

**Deliverable:** rule-driven configuration resolution, reusable atomic
baselines and a baseline diff, with non-Released members and duplicate names
rejected.
**UI (UI-6):** a header configuration-context selector (persisted via
`UserPreference` or explicitly session-only); a baseline detail page and a
compare page.

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
> complete; Phase 2 revision/lifecycle ✅ complete; Phase 3 properties ✅
> complete; Phase 4 traceability ✅ complete; Phase 5 BOM ✅ complete; Phase 6
> configuration ✅ complete; Phase 7 pending.

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
