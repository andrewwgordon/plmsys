# PLMSys — UI & Navigation Refactor Plan

A plan to rework the current Flask-AppBuilder (FAB) scaffold's user interface and
navigation into an intuitive, task-oriented PLM experience, informed by an
analysis of Siemens Teamcenter's user interface.

Companion documents:

- [`PLMSys_FAB_Domain_Model.md`](./PLMSys_FAB_Domain_Model.md) — domain model spec.
- [`plan.md`](./plan.md) — functional/backend implementation roadmap.
- This document — **UI/UX and navigation**.

---

## 1. Purpose

The current scaffold exposes a **model-centric** menu: one flat entry per
database entity, grouped by technical domain (`Meta Model`, `Objects`,
`Properties`, `Relationships`, `BOM`, `Configuration`, `Lifecycle`, `Datasets`,
`Verification`, `Workflow`). This mirrors the schema rather than the way a PLM
user works. End users think in terms of *"Find my part → open its structure →
see what it satisfies → release it"*, not *"which table holds this row?"*.

This plan defines a **task- and object-centric** information architecture and
screen design, adapted from Teamcenter, and a phased way to implement it in FAB.

---

## 2. Research method & sources

Web sources consulted (September 2026):

| # | Source | Used for |
|---|---|---|
| S1 | Siemens Teamcenter blog — *What's New in Teamcenter and Active Workspace* — <https://blogs.sw.siemens.com/teamcenter/whats-new-in-teamcenter-and-active-workspace/> | AWC layout/styling updates, navigation "that does not require users to understand the underlying data model", advanced search & analytics, faster tree table |
| S2 | PLM is Everything — *Active Workspace (AWC): How Teamcenter UI Really Works* — <https://plmiseverything.com/blog/active-workspace-awc-foundation> | AWC as the interaction layer; declarative UI, `ctx`, services; panels/commands/tables/forms/object pages |
| S3 | PLM Coach — *Siemens Teamcenter PLM Guide* — <https://plmcoach.com/siemens-teamcenter-plm-guide> | Rich Client layout: application banner, search box, navigation pane, application pane, perspectives; Structure Manager layout; Summary/Details/Viewer/Impact Analysis views; My Worklist, Home, Saved Searches, My Links |
| S4 | Wikipedia — *Teamcenter* — <https://en.wikipedia.org/wiki/Teamcenter> | Product background, client/architecture context |
| S5 | Siemens — *Teamcenter PLM* product page — <https://plm.sw.siemens.com/en-US/teamcenter/> | Positioning: single source of product data across the lifecycle |

> Note: live searches were performed with `curl` against Wikipedia, the Siemens
> blog/product site, and search-engine result pages. Some vendor documentation is
> behind a login; the analysis below triangulates the public sources with the
> documented product terminology.

---

## 3. Findings — how Teamcenter presents itself

### 3.1 Two clients, one interaction model

- **Active Workspace (AWC)** is the modern, HTML5 web client and Siemens'
  *preferred* UI. It is described as the *interaction layer* through which users
  **search, open, edit, review, and navigate** product data (S1, S2).
- **Rich Client (RAC / "My Teamcenter")** is the classic thick client. Its styling
  has been aligned with AWC to minimise retraining (S1).

Key takeaway for PLMSys: a **web-first, single shell** is the right target; FAB
already gives us this.

### 3.2 Active Workspace layout & navigation patterns

Synthesised from S1 and S2:

1. **Global header / top bar**
   - Application switcher and active-application banner.
   - **Global search** (predefined quick searches + advanced search).
   - User/role identity, settings, notifications.
2. **Left navigation panel**
   - Entry points such as **Home**, **Recent**, **Favorites**,
     **My Worklist**, saved searches.
   - Navigation is deliberately **decoupled from the data model** — users pick
     concepts (parts, changes, requirements), not tables (S1).
3. **Home page with configurable tiles**
   - Navigation tiles and search tiles; personalized per user.
4. **Object pages with tabs**
   - Typically **Summary** (key properties), **Details**, **Relations**,
     **Structure**, **Viewer/Attachments**, and history.
   - Commands are grouped in a **command bar** near the object context.
5. **"1-click-away" navigation**
   - From any search result or relation, the next relevant object is one click
     away; carried into architecture/relations views (S1).
6. **Global search & saved searches**
   - Execute, save, filter, mark as *preferred*; export results (S1).
7. **Structure/tree table**
   - Fast, expandable product-structure tree; a major performance and usability
     focus (S1).
8. **Declarative UI (`ctx`, ViewModels, services)** (S2)
   - The UI is configured, not hard-coded: panels, commands, and visibility are
     driven by definitions and the current application context. **This is the
     architectural pattern PLMSys should imitate** with FAB views/templates.

### 3.3 Rich Client layout & navigation patterns

From S3:

- **Back / Forward** between loaded applications.
- **Application Banner** — active app + current user/role.
- **Search Box** — predefined quick search.
- **Navigation Pane** — quick access to day-to-day data. Its upper section
  contains: **Quick Search, Quick Links, Open Items, History, Favorite,
  I Want to, Primary Applications, Secondary Applications, Configure
  Application**.
- **Application Pane** — the active "perspective".
- **Getting Started** button; **Clipboard** for cut/copied objects; server/UI
  status symbols.
- **Perspectives** — primary/secondary applications selected from a navigation
  pane (e.g. My Teamcenter, Structure Manager); opened via *Window → Open
  Perspective*.
- **Search** — quick search + **Saved Queries** grouped into *My Saved
  Searches*, *System Defined Searches*, *Search History*.
- **Object presentation views**:
  - **Summary view** — properties of the selected object, editable attributes.
  - **Details view** — tabular properties of children of the selection.
  - **Viewer view** — content depends on object type (2D/3D/doc).
  - **Impact Analysis view** — impact of the current component/change.
- **Structure Manager** interface (S3):
  1. **Structure navigation tree** — navigate product structure.
  2. **Data panes** — data about the selected line.
  3. **Search area** — find/configure a structure.
  4. **Incremental change management area** — current change context.
  5. **Status symbol** — status of the selected line.
- **Folders / Home folder / My Worklist / My Saved Searches / My Links.**
- **Tasks and workflow**: perform and track tasks; send/receive mail.

### 3.4 Cross-cutting UX principles observed

| Principle | Teamcenter evidence | Implication for PLMSys |
|---|---|---|
| Object-centric, not table-centric | Object pages with tabs; app switcher | Lead with BusinessObject/Revision pages, not ModelView tables |
| Navigation independent of the data model | S1 explicitly | Task-based menu labels ("Products", "Requirements") |
| Persistent personal context | Favorites, Recent, History, Worklist, Saved Searches | Add Favorites/Recent/Saved Searches |
| Context is first-class | Revision rule / configuration context shown beside the structure; `ctx` in AWC | Show active configuration context + revision rule in the global frame |
| One-click-away browsing | Relations/links everywhere | Rich cross-links between objects and relations |
| Search is a primary workflow | Global + advanced + saved search | Global search as a top-level entry |
| Command bar near context | Commands grouped by object | FAB `@action`s and view actions grouped per object |
| Configurable/declarative UI | AWC ViewModels | Drive panels/tabs/columns from configuration |
| Progressive disclosure | Summary → Details → Structure | Tabs instead of dumping all columns |
| Status visibility | Status symbols, lifecycle badges | Release-state badges on every object row/page |

---

## 4. Current PLMSys UI — gap analysis

### 4.1 What exists today

- FAB's default layout: top navbar with menu categories, no global search box,
  no object-centric home, no persistent personal context.
- ~21 `ModelView`s registered in `app/views.py` under technical categories
  (`Meta Model`, `Objects`, `Properties`, …). Tables are the primary (often only)
  way to reach data.
- Simple `related_views` (e.g. `BusinessObject → Revisions`) and a
  `RequirementModelView` scoped by `base_filters`.
- No Home/dashboard, no global search, no Favorites/Recent/Worklist, no
  breadcrumb, no structure/traceability visualisation, no active configuration
  context indicator.

### 4.2 Problems

1. **Schema-shaped navigation** — users must know that requirements are
   `BusinessObject` rows of type `Requirement`.
2. **No entry point / landing experience** — the index is generic; no "what
   should I work on?".
3. **Everything is a list** — no object page that unifies summary, properties,
   relations, structure, verification and history.
4. **No cross-navigation** — relationships, BOM and traces are separate tables
   with no links, so traceability cannot be followed.
5. **No personal context** — no favorites, recents, saved searches, or task list.
6. **No configuration-context awareness** — users cannot tell which revision
   rule/baseline they are viewing.
7. **Technical labels** — "Business Objects", "Property Definitions",
   "Revision Release States" mean little to business users.
8. **Admin mixed with daily work** — meta-model setup sits beside operational
   views.

### 4.3 Mapping Teamcenter concepts to PLMSys

| Teamcenter concept | PLMSys domain entity | Primary UI surface |
|---|---|---|
| Item / Item Revision | `BusinessObject` / `Revision` | Object page |
| Item properties / Summary | `PropertyDefinition` + `PropertyValue` | Summary & Details tabs |
| BOM View Revision / product structure | `BOMOccurrence` | Structure tab / Structure Manager |
| Relations (trace links) | `Relationship` + `RelationshipType` | Relations tab, Traceability matrix |
| Revision Rule / configuration context | `RevisionRule`, `ConfigurationContext`, `Baseline`, `BaselineMember` | Global context selector; Configuration workspace |
| Release status / lifecycle | `ReleaseState`, `RevisionReleaseState` | Status badges, Release command |
| Dataset / file | `Dataset`, `ManagedFile` | Attachments tab / Viewer |
| Change | `ChangeRequest` (+ `IMPACTED_BY_CHANGE`) | Changes workspace, Impact Analysis |
| Workflow task | `WorkflowProcess`, `WorkflowTask` | My Worklist |
| Object type / classification | `ObjectType` | Icons, filters, admin |
| Favorites / Recent / Saved search | *(new app-level tables)* | Navigation panel |
| Folder / Home | *(derived)* | Home page |

---

## 5. Target UX vision & principles

**Vision:** *"Every user lands on a personal home, searches or browses by
business concept, opens an object page, and follows relationships one click at a
time — always knowing which configuration context they are in."*

Design principles (derived from §3.4):

1. **Task-oriented navigation** — label menus by what users do, not what the DB
   stores.
2. **Object page is the centre of gravity** — one page per BusinessObject with
   tabs.
3. **Follow the thread** — every referenced object is a link ("1-click-away").
4. **Persistent personal context** — Favorites, Recent, Worklist, Saved Search.
5. **Configuration context is always visible** — revision rule + baseline in the
   global frame.
6. **Search first** — global search in the header, with saved/advanced searches.
7. **Progressive disclosure** — Summary → Details → Structure/Relations.
8. **Status at a glance** — lifecycle badges, coverage/verification indicators.
9. **Admin is separate** — a "Setup" area, hidden from non-admins via
   `menu_cond`/permissions.
10. **Declarative, configurable panels** — imitate AWC's ViewModel idea by
    driving tabs/columns from configuration/templates rather than hard-coding.

---

## 6. Target information architecture

### 6.1 Global frame (present on every page)

```
+--------------------------------------------------------------------------------------+
|  ☰  PLMSys   [ Global search........................................ ]   Ctx: Latest   |
|                                                          Released ▾   🔔  👤 admin ▾  |
+--------------+-----------------------------------------------------------------------+
| NAV PANEL    |  LOCATION BAR:  Home / Products / PART-1000 / Battery Module / A       |
|              +-----------------------------------------------------------------------+
| ⌂ Home       |                                                                       |
| 🔎 Search    |                     APPLICATION PANE                                  |
| ✅ Worklist  |                     (Home | Object page | Structure | Matrix | ...)   |
| ⭐ Favorites |                                                                       |
| 🕘 Recent    |                                                                       |
| ─────────    |                                                                       |
| 📦 Products  |                                                                       |
| 📋 Requirem. |                                                                       |
| 🔧 Changes   |                                                                       |
| 📄 Documents |                                                                       |
| ─────────    |                                                                       |
| ⚙ Setup      |                                                                       |
+--------------+-----------------------------------------------------------------------+
| FOOTER: status / server symbols                                                      |
+--------------------------------------------------------------------------------------+
```

- **Header**: brand, global search, **configuration-context selector** (revision
  rule / baseline), notifications, user menu.
- **Navigation panel** (left): personal entries (Home, Search, Worklist,
  Favorites, Recent) then business domains, then Setup.
- **Location bar**: breadcrumb trail of the current navigation path with
  in-place context actions.
- **Application pane**: the current perspective/page.

### 6.2 Primary navigation (menu restructure)

| New category | Menu label | Backing view(s) | Notes |
|---|---|---|---|
| *(top)* | Home | `PLMSysIndexView` | Dashboard with tiles |
| *(top)* | Search | `GlobalSearchView` | Advanced + saved searches |
| *(top)* | My Worklist | `WorklistView` | Open `WorkflowTask`s |
| *(top)* | Favorites | `FavoritesView` | New `Favorite` rows |
| *(top)* | Recent | `RecentView` | New `RecentView` rows |
| **Products** | Parts | `PartModelView` (filtered) | `BusinessObject` type = Part |
| **Products** | Product Structure | `StructureManagerView` | BOM explorer |
| **Products** | Where Used | `WhereUsedView` | Reverse BOM |
| **Requirements** | Requirements | `RequirementModelView` | existing filter |
| **Requirements** | Traceability Matrix | `TraceabilityMatrixView` | requirement ↔ targets |
| **Changes** | Change Requests | `ChangeRequestModelView` | filtered |
| **Changes** | Impact Analysis | `ImpactAnalysisView` | uses `IMPACTED_BY_CHANGE` |
| **Documents** | Documents | `DocumentModelView` | filtered |
| **Documents** | Datasets | `DatasetModelView` | existing |
| **Verification** | Test Cases | `TestCaseModelView` | filtered |
| **Verification** | Verification Results | `VerificationResultModelView` | existing |
| **Configuration** | Configuration Contexts | `ConfigurationContextModelView` | existing |
| **Configuration** | Baselines | `BaselineModelView` | existing |
| **Setup** *(admin)* | Object Types | `ObjectTypeModelView` | existing |
| **Setup** *(admin)* | Property Definitions | `PropertyDefinitionModelView` | existing |
| **Setup** *(admin)* | Relationship Types | `RelationshipTypeModelView` | existing |
| **Setup** *(admin)* | Revision Rules | `RevisionRuleModelView` | existing |
| **Setup** *(admin)* | Release States | `ReleaseStateModelView` | existing |
| **Setup** *(admin)* | Workflow Processes | `WorkflowProcessModelView` | existing |

Removed from primary nav (moved into object pages/tabs or Setup):
`Revisions`, `Business Objects`, `Revision Lineage`, `Property Values`,
`Relationships`, `BOM Occurrences`, `Occurrence Traces`, `Baseline Members`,
`Revision Release States`, `Managed Files`, `Workflow Tasks`.

> These remain reachable as **related views/tabs** on their parent object, or via
> "Setup" for administrators. This is the key change: **tables stop being the
> navigation model**.

### 6.3 Menu implementation notes (FAB)

- Reorganise `register_views(appbuilder)` categories to the table above.
- Use `appbuilder.add_link(...)` for computed pages and `add_separator(...)`
  between blocks.
- Hide `Setup` with `menu_cond=lambda: "Admin" in g.user.roles` (guard the
  views too via `base_permissions`).
- Set `FAB_INDEX_VIEW = "app.views.PLMSysIndexView"` so `/` is the new Home.

---

## 7. Screen designs (wireframe level)

### 7.1 Home / dashboard (`PLMSysIndexView`)

```
+-- Home ------------------------------------------------------------------+
|  [Search tile: Requirements..............] [Search tile: Parts.........]  |
|                                                                          |
|  My Worklist (5)            Recent                                      |
|   • Review REQ-0001/B        • PART-1000/A   (Structure)                |
|   • Approve TEST-100/A       • REQ-0002/A    (Summary)                  |
|                                                                          |
|  Favorites                  Lifecycle Overview (chart)                  |
|   • PART-1000 Battery Module   Draft ▇▇  Review ▇  Released ▇▇▇▇       |
|                                                                          |
|  Coverage: 82% requirements traced   |  3 baselines   |  12 open tasks  |
+--------------------------------------------------------------------------+
```

- Configurable tiles per role (later phase): engineers see assigned work;
  reviewers see approval queues.
- KPI cards: requirement coverage, verification pass rate, open changes, open
  tasks.

### 7.2 Global search (`GlobalSearchView`)

- Big search box, quick-search presets by type (Parts, Requirements, Tests,
  Documents).
- Filter rail: object type, status, configuration context, owner, date.
- Result list with type icon, ID, name, revision, status badge, context menu.
- Actions: **Save search**, **Mark preferred**, export.
- Saved searches sidebar grouped as *My Saved Searches* / *System Searches* /
  *Search History* (mirrors Rich Client, S3).
- Every result links to the object page (1-click-away).

### 7.3 Object page (`ObjectDetailView`, per `BusinessObject`)

Tabs (mirroring Summary/Details/Relations/Structure/Viewer, S3):

```
+ PART-1000  Battery Module            [Released]   Ctx: Latest Released ▾   +
| Summary | Details | Structure | Relations | Where Used | Verification |    |
| Attachments | History                                                    |
+--------------------------------------------------------------------------+
| Summary: key properties (from PropertyValue), current revision, owner,   |
| lifecycle state, configuration context, coverage/verification indicators |
+--------------------------------------------------------------------------+
```

| Tab | Contents | Backing data |
|---|---|---|
| **Summary** | Identity, current revision, key properties, status, KPIs | `BusinessObject`, `Revision`, `PropertyValue` |
| **Details** | All properties, editable; revision selector | `PropertyDefinition`/`PropertyValue` |
| **Structure** | BOM tree, quantities, find numbers (parts only) | `BOMOccurrence` |
| **Relations** | Grouped inbound/outbound typed links | `Relationship` |
| **Where Used** | Reverse BOM / reverse relations | `BOMOccurrence`, `Relationship` |
| **Verification** | Linked tests + results + pass/fail | `VerificationResult`, `VERIFIED_BY` |
| **Attachments** | Datasets/files, viewer, download | `Dataset`, `ManagedFile` |
| **History** | Revisions, lineage, release-state changes, who/when | `RevisionLineage`, `RevisionReleaseState`, timestamps |

Commands (command bar, contextual): Create Revision, Set Current Revision,
Release, Obsolete, Add to Favorites, Add to Worklist, Add Relation, Add to
Baseline, Check Out/In (later), Delete.

### 7.4 Structure Manager (`StructureManagerView`) — BOM

Mirrors the Rich Client Structure Manager (S3):

```
+ Structure: PART-1000 Battery Module      Ctx: Latest Released   Rule: Latest |
+------------------------------------------------------------------------------+
| Structure tree            | Data panes (selected line)                       |
|  ▸ PART-1000 Battery Mod  |  Find 10  PART-1001 Battery Cell   x12  Rev B  ●|
|    ▸ 10 PART-1001 Cell    |  Properties | BOM properties | Occurrence        |
|    ▸ 20 PART-1002 Plate   |  Requirement traces: REQ-0004                    |
|                           |  Status: Released                                |
+---------------------------+--------------------------------------------------+
| Search area: [ filter structure............ ]  [ Expand all ] [ Export ]     |
+------------------------------------------------------------------------------+
```

Features: expand/collapse, multilevel mode, column configuration, quantity
roll-up, packing, filtering, status symbols, and an **incremental change area**
showing the active `ChangeRequest` context.

### 7.5 Traceability matrix (`TraceabilityMatrixView`)

- Rows: requirements (scoped via `base_filters` on `object_type.name`).
- Columns: Customer → System → Subsystem → Component (via `DEFINING`), plus
  `ALLOCATED_TO`, `VERIFIED_BY`, `SATISFIED_BY`.
- Cells are click-through links; empty cells highlight **coverage gaps**.
- Export to CSV/Excel (as AWC supports export, S1).

### 7.6 My Worklist (`WorklistView`)

- Lists `WorkflowTask`s (Open / In Progress / Overdue), grouped by process.
- Columns: task, object (link), process, due date, state.
- Actions: Start, Complete, Reassign (assignment via app-level extension, §8).
- Filters: mine / my groups / all.

### 7.7 Configuration & baselines (`ConfigurationContextModelView`,
`BaselineModelView`, plus a compare view)

- Context selector in the global header (applies a `RevisionRule`).
- Baseline detail: members grouped by object type with revisions.
- **Baseline compare**: additions / removals / revision changes.

### 7.8 Changes & impact (`ChangeRequestModelView`, `ImpactAnalysisView`)

- Change request object page with affected items (`IMPACTED_BY_CHANGE`).
- Impact Analysis view: for a selected revision, show dependent
  relationships, affected BOM occurrences, and verification impact.

### 7.9 Documents & viewer (`DocumentModelView`, `DatasetModelView`)

- Document object page with Attachments tab and inline viewer for supported
  types; download links; mime/size metadata.

### 7.10 Setup / admin (existing meta-model views)

- Object Types, Property Definitions, Relationship Types, Revision Rules,
  Release States, Workflow Processes.
- Hidden from business users; guarded by Admin permission.

---

## 8. Supporting data model extensions (app-level)

The domain spec deliberately excludes users. To deliver personal context and a
worklist, add **thin app-level tables** (not part of the domain model), linking to
FAB's `ab_user`:

| New model | Columns | Purpose |
|---|---|---|
| `Favorite` | `id`, `user_id (FK ab_user)`, `business_object_id (FK)`, `created_on` | Favorites |
| `RecentView` | `id`, `user_id`, `business_object_id`, `viewed_on` | Recent items (prune by count/age) |
| `SavedSearch` | `id`, `user_id`, `name`, `query_json`, `is_preferred`, `created_on` | Saved/preferred searches |
| `UserPreference` | `id`, `user_id`, `configuration_context_id`, `default_page_size` | Active context & UI prefs |
| `WorkflowTaskAssignment` | `task_id (FK)`, `user_id (FK)`, `assigned_on` | Worklist assignment (keeps domain model user-free) |

Notes:

- `Favorite`/`RecentView` target `BusinessObject` (stable identity), not
  `Revision`, so links survive revisions.
- `SavedSearch.query_json` stores a serialised filter set interpreted by
  `GlobalSearchView`.
- `UserPreference.configuration_context_id` drives the global context selector.
- Add Alembic migrations for these (see `plan.md` Phase 0).

---

## 9. Implementation roadmap

Ordered so each phase yields a usable improvement. Phases are independent of
`plan.md`'s functional phases but assume its Phase 0 (migrations, tests).

### UI-0 — Shell, theme & menu skeleton (foundation) — ✅ Complete

1. ✅ Create `app/templates/base_layout.html` extending
   `appbuilder/baselayout.html`, overriding `navbar` and `content` to add the
   **header**, **location bar**, **navigation panel**, and **application pane**.
2. ✅ Set `FAB_BASE_TEMPLATE = "base_layout.html"` in `config.py`.
3. ✅ Implement `PLMSysIndexView(IndexView)` (`index_template = "index.html"`) and
   set `FAB_INDEX_VIEW`.
4. ✅ Restructure `register_views()` menu categories per §6.2 (no new pages yet);
   add `Setup` `menu_cond` for Admin.
5. ✅ Apply a config-driven Bootstrap colour schema (`PLMSYS_COLORS` /
   `PLMSYS_THEME_CSS` in `config.py`) plus CSS for tiles and the left rail.
6. **Deliverable:** ✅ new shell on every page; menu reflects business domains.

### UI-1 — Object page

1. Implement `ObjectDetailView(BaseView)` at `route_base = "/object"` with
   `@expose("/<int:pk>/")` and tab query param.
2. Build tabs: Summary, Details, Relations, History (Structure/Verification/
   Attachments added later).
3. Render `PropertyValue`s as a key/value panel grouped by property definition.
4. Add contextual commands via a command bar rendered from a config dict.
5. Add **Release-state badges** (`@renders`) on list/show views.
6. Link every referenced object (revision, relationships) to `/object/<pk>/`.
7. **Deliverable:** one unified page per business object.

### UI-2 — Search & saved searches

1. Implement `GlobalSearchView(BaseView)` querying `BusinessObject` (number,
   name) and `PropertyValue.string_value`, with `LIKE`/filter support.
2. Filter rail: type, status, context.
3. Add `SavedSearch` model + migration; save/load/preferred/history.
4. Add global search box in the header posting to the search view.
5. **Deliverable:** search-first navigation with persistence.

### UI-3 — Personal context (Favorites / Recent / Worklist)

1. Add `Favorite`, `RecentView`, `UserPreference` models + migrations.
2. `FavoritesView`, `RecentView`, `WorklistView`.
3. "Add to Favorites" command on object pages; auto-record `RecentView` on view.
4. `WorkflowTaskAssignment` + worklist query; Start/Complete actions.
5. **Deliverable:** personalized Home/nav with favorites, recents, tasks.

### UI-4 — Structure Manager (BOM)

1. `StructureManagerView(BaseView)` with recursive BOM traversal service
   (`plan.md` Phase 5).
2. Tree rendering (nested `<ul>`/JS tree), expand/collapse, quantity roll-up.
3. Data panes for the selected line incl. requirement traces and status symbol.
4. Search/filter area; export.
5. **Deliverable:** interactive product structure.

### UI-5 — Traceability & impact

1. `TraceabilityMatrixView` (requirements × targets) with coverage gaps.
2. `ImpactAnalysisView` using `IMPACTED_BY_CHANGE` and reverse relations.
3. Cross-link from object pages ("Show traceability").
4. **Deliverable:** traceability visible and clickable.

### UI-6 — Configuration context & baselines

1. Header **context selector** backed by `UserPreference`.
2. Baseline detail + **compare** view.
3. Show active rule/context on structure and object pages.
4. **Deliverable:** context-aware browsing.

### UI-7 — Attachments, verification & lifecycle polish

1. Attachments tab + viewer + download (`Dataset`/`ManagedFile`).
2. Verification tab wiring `VerificationResult`s and pass/fail indicators.
3. Lifecycle command bar: Create Revision, Release, Obsolete with the state
   machine from `plan.md` Phase 2.
4. **Deliverable:** complete object page.

### UI-8 — Reporting & charts

1. Home tiles + charts (`GroupByChartView`): requirements by status, BOM by
   parent, verification outcomes.
2. Coverage KPIs.
3. CSV/Excel export.
4. **Deliverable:** at-a-glance dashboards.

### UI-9 — Responsive, accessibility & role tailoring

1. Responsive breakpoints for the nav panel and structure tree.
2. Keyboard navigation, ARIA landmarks, focus order, contrast.
3. Role-based tiles and menu visibility.
4. **Deliverable:** accessible, role-aware UI.

---

## 10. FAB technical notes

- **Base layout**: override the FAB Jinja blocks
  (`head_css`, `navbar`, `content`, `tail_js`) via
  `app/templates/base_layout.html`; call `{{ super() }}` where extending.
- **Home**: subclass `IndexView` and set `FAB_INDEX_VIEW` (or
  `indexview=` to `AppBuilder`). Keep `index_template` under `app/templates/`.
- **Custom pages**: subclass `BaseView`; expose routes with `@expose` and guard
  with `@has_access`; render via `self.render_template(...)` (injects
  `base_template`/`appbuilder`).
- **Related data as tabs**: `related_views = [...]` on `ModelView` renders
  master/detail tabs on show/edit (already used for `BusinessObject → Revision`).
- **Object page tabs**: implement with one `BaseView` and a `tab` query
  parameter (simpler than many views), or `MultipleView` for a few panels.
- **Commands**: FAB `@action` for list/show actions; a config-driven command bar
  for the object page. Group permissions with `class_permission_name` /
  `method_permission_name` and keep `base_permissions` least-privilege.
- **Menu**: reorganise `add_view`/`add_link`/`add_separator`; use `menu_cond`
  for role/feature-based visibility (`FAB_ROLES` for read-only roles).
- **Icons**: Font-Awesome names (e.g. `fa-cube`, `fa-sitemap`, `fa-code-fork`,
  `fa-link`, `fa-check-circle`, `fa-tasks`, `fa-search`, `fa-star`, `fa-clock-o`,
  `fa-home`, `fa-cogs`).
- **Declarative panels**: drive object-page tabs/columns from small Python
  config dictionaries (type → tab/column definition) rather than hard-coding,
  echoing AWC's ViewModel/`ctx` pattern (S2).
- **Breadcrumbs**: build from the current route/view + object path; render in
  the location bar partial.
- **Search**: reuse FAB `SQLAInterface` filters; serialise them into
  `SavedSearch.query_json` and re-apply on load.
- **Context selector**: a `SimpleFormView`/header form writing
  `UserPreference.configuration_context_id`; apply the selected `RevisionRule`
  in structure/object queries.

---

## 11. Accessibility, performance & responsive

- **Accessibility**: semantic landmarks (`nav`, `main`, `header`), ARIA labels on
  the nav rail and tree, visible focus, colour-plus-text status badges (never
  colour alone), keyboard-operable tree and tabs.
- **Performance**: paginate all lists (FAB `page_size`); lazy-load structure
  nodes; add DB indexes on FK columns used by traversal; cache roll-ups.
- **Responsive**: collapse the nav rail to icons on medium screens; stack data
  panes under the tree on small screens; horizontal scroll for wide matrices.

---

## 12. Acceptance criteria

1. `/` lands on a personalized Home with tiles, worklist and recents.
2. Global search is available from every page and supports saved searches.
3. Every `BusinessObject` has an object page with Summary/Details/Relations/
   Structure/Verification/Attachments/History tabs.
4. All object references are clickable ("1-click-away").
5. The active configuration context (rule/baseline) is always visible and
   selectable.
6. Favorites, Recent and Worklist work per user.
7. Structure Manager supports expand/collapse, quantities and status.
8. Traceability matrix exposes and highlights coverage gaps.
9. Setup/meta-model views are visible only to administrators.
10. Primary navigation uses business terms, not table names.
11. Pages are keyboard-navigable and pass a basic accessibility audit.

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Custom base layout can drift from FAB upgrades | Extend `appbuilder/baselayout.html` and override only needed blocks; pin FAB version |
| Custom `BaseView` pages bypass FAB CRUD conventions | Reuse `SQLAInterface` and FAB widgets; keep services in `app/services` |
| BOM/trace tree performance at scale | Lazy loading, depth caps, indexes, server-side filtering |
| Personal-context tables complicate the "no users" domain boundary | Keep them in a separate app-level module with FKs to `ab_user` only |
| Search over `PropertyValue.string_value` is weak for typed data | Add type-aware search per `PropertyDataType`; consider a later search index |
| Saved-search JSON schema changes over time | Version the `query_json` payload |
| Menu/permission drift | `class_permission_name` conventions + `security-converge`; test role visibility |
| Scope creep in visual polish | Sequence phases; ship shell + object page first |

---

## 14. Appendix — glossary & source index

**Glossary**

- **AWC** — Active Workspace, Teamcenter's web client and preferred UI.
- **Rich Client / RAC / My Teamcenter** — Teamcenter's classic thick client.
- **Perspective / Application** — a functional workspace opened in the
  application pane.
- **Navigation pane / Quick links / Open items / History / Favorites /
  I Want to** — Rich Client navigation-pane entry points.
- **Item / ItemRevision** — Teamcenter's object/revision pair (≈
  `BusinessObject`/`Revision`).
- **Structure Manager** — product-structure (BOM) workspace.
- **Revision rule / configuration context** — decides which revision is shown.
- **`ctx`** — Active Workspace application context (selection + state).

**Sources**

- **S1** Siemens Teamcenter blog — *What's New in Teamcenter and Active
  Workspace*: <https://blogs.sw.siemens.com/teamcenter/whats-new-in-teamcenter-and-active-workspace/>
- **S2** PLM is Everything — *Active Workspace (AWC): How Teamcenter UI Really
  Works*: <https://plmiseverything.com/blog/active-workspace-awc-foundation>
- **S3** PLM Coach — *Siemens Teamcenter PLM Guide*:
  <https://plmcoach.com/siemens-teamcenter-plm-guide>
- **S4** Wikipedia — *Teamcenter*: <https://en.wikipedia.org/wiki/Teamcenter>
- **S5** Siemens — *Teamcenter PLM*:
  <https://plm.sw.siemens.com/en-US/teamcenter/>
