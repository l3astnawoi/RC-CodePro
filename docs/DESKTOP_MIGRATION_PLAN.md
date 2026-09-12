# Native Desktop Migration — PySide6

## Guardrails

- Streamlit remains the reference UI until each native page is accepted.
- `modules/` and `utils/` calculation engines are not rewritten for UI work.
- Every migrated page requires engine equivalence, regression, and Windows EXE packaging checks.

## Sequence

1. Desktop shell and navigation — complete.
2. Shared project state and Home dashboard.
3. Member pages: Beam, Column, Slab, Footing, Stair.
4. Building Model and direct-biaxial member display.
5. PDF/download workflow, visual QA, PyInstaller EXE acceptance.

Run development shell: `python run_desktop.py`.

## Column migration — 2026-09-06

- Native Column navigation now opens rectangular tied and circular spiral forms.
- MKS inputs, reference P-M curves, section drawing, steel ratio, axial and
  transverse-spacing checks are available. Changes invalidate prior results.
- Existing `modules/column.py` calculation helpers remain unchanged; the native
  summary follows the reference UI criteria, including recommended spacing.
- 13 tests passed: desktop integration and existing column regression tests.
- PyInstaller build succeeded in `dist/column-migration/RC-CodePro-Desktop`.
- Offscreen layout inspected with Tahoma loaded explicitly (the offscreen Qt
  platform did not discover system fonts automatically).
- Interactive packaged-EXE acceptance and PDF workflow remain pending.

### Packaged QtCore fix

- The first package failed on launch: dependency discovery picked Windows
  runtime DLLs from an unrelated Codex libheif directory on PATH.
- The spec now removes Codex runtime paths during dependency discovery and
  excludes OS-provided UCRT/API-set DLLs from the Windows 10/11 package.
- Replacement: `dist/column-fixed/RC-CodePro-Desktop/RC-CodePro-Desktop.exe`.
  `Open-RC-CodePro.cmd` points to this build.
- Actual packaged `--smoke-test` passed (exit 0, `build/exe-smoke.json`):
  native window construction, Column navigation, both shapes, calculations,
  section images and P-M images. PDF workflow remains pending.

### Column PDF workflow

- Column exports through the existing `build_report` engine with current saved
  project metadata, MKS parameters, check results and both figures.
- Editing inputs disables export until recalculation. Save uses QSaveFile to
  commit the completed PDF atomically; cancellation leaves files unchanged.
- Thai font is included in the package. Both three-page sample PDFs were
  rendered and visually inspected. All 13 desktop/column tests passed.
- `dist/column-pdf` passed the actual packaged smoke test including PDF creation
  for both shapes (exit 0; `build/exe-pdf-smoke.json`). Launcher updated.

## Slab native page — 2026-09-06

- Slab now opens a native form for the active one-way/two-way reference flow.
  Aspect ratio classification, MKS loads, flexural steel, spacing, and
  tension-controlled checks mirror that flow; original helpers are unchanged.
- Invalid depth or infeasible flexure clears old results. Input changes also
  clear the drawing and verdict until recalculation.
- 19 tests passed across native Slab, reference slab helpers and native Column.
  Integration tests execute the reference UI with captured outputs for both
  slab types, the 0.5 boundary, and reversed span inputs.
- Native layout and reinforcement plan visually checked.
- Slab PDF export and other slab types remain pending.
- Packaged EXE smoke test passed (exit 0; `build/exe-slab-smoke.json`),
  including both Slab types and Column/PDF. Launcher points to `dist/slab-desktop`.

### Slab PDF completed

- Native Slab exports the current calculation snapshot with saved project
  metadata, MKS inputs, direction-specific checks and the reinforcement plan.
- Recalculation is required after input changes. Saving uses QSaveFile;
  cancelling the file dialog leaves existing files intact.
- Both two-page reference PDFs were rendered and visually inspected.
- 20 tests passed; actual packaged smoke test passed including Slab/Column
  PDF creation (exit 0; `build/exe-slab-pdf-smoke.json`).
- Launcher now points to `dist/slab-pdf`. Other slab types remain pending.

## Isolated Footing native page

- Added native isolated-footing form with rectangular/circular column inputs,
  independent long/short reinforcement, MKS results, and plan/elevation.
- Calculation orchestration is copied from the active reference UI into
  `desktop_app/footing_calc.py`; calculation helpers and original UI remain
  unchanged. Invalid geometry raises an error and clears previous results.
- 20 tests passed across Footing helpers, native Footing, Slab and Column.
  Native/reference comparisons cover square, rectangular and circular-column
  cases for pressure, shear, moments, steel, spacing and verdict.
- Native layout and plan/elevation visually inspected.
- Footing PDF and pile-cap pages remain pending.
- Packaged EXE smoke test passed (exit 0; `build/exe-footing-smoke.json`),
  covering both column shapes plus existing Slab/Column PDF. Launcher updated
  to `dist/footing-desktop`.

### Footing PDF completed — 2026-09-07

- Native export includes saved project metadata, MKS parameters, ten checks,
  plan/elevation and verdict. Input changes invalidate export; QSaveFile
  commits completed output and dialog cancellation leaves files unchanged.
- Rectangular/circular-column samples were rendered and inspected: two pages
  each, with all checks together and the verdict beneath the drawing.
- Generic report image-height override is optional; existing callers retain
  their default layout. Footing uses a 205 mm image limit.
- 21 tests passed. Actual EXE smoke test passed with exit 0, including
  Footing, Column and Slab PDF creation (`build/exe-footing-pdf-smoke.json`).
- Launcher now points to `dist/footing-pdf`. Pile-cap migration remains pending.

## F2/F4 preliminary pile-cap page

- Footing navigation now contains isolated footing and F2/F4 tabs.
- Native pile-cap page covers centred columns, automatic cap dimensions,
  four pile shapes, long/short reinforcement, reactions and reference checks.
  Preliminary-design status is retained from the original workflow.
- Calculation block copied from the reference UI into `pile_cap_calc.py`;
  original engine unchanged. Eccentricity/manual sizing are not exposed.
- 26 tests passed, including native/reference comparisons for F2/F4 and all
  pile shapes, insufficient pile capacity and invalid effective depth.
- Form, F2 plan/elevation and F4 plan/elevation visually inspected.
- Pile-cap PDF, eccentricity and manual cap dimensions remain pending.
- Actual EXE smoke test passed (exit 0; `build/exe-pile-smoke.json`), covering
  F2/F4 and existing member PDFs. Launcher points to `dist/pile-cap-desktop`.

### F2/F4 PDF workflow

- Export includes saved project metadata, input snapshot, service pile reactions,
  twelve check rows, plan/elevation and preliminary-design scope.
- Input changes invalidate export. Save uses QSaveFile; cancellation preserves
  files. Both F2/F4 two-page samples were rendered and visually inspected.
- 27 tests passed across native pile caps, footing, slab, column and footing
  helpers, including PDF creation, saving and cancellation.
- Actual packaged smoke test passed (exit 0; `build/exe-pile-pdf-smoke.json`),
  including F2/F4 PDFs and existing member PDFs. Launcher now uses `dist/pile-cap-pdf`.

## Straight Stair native page

- Stair opens the straight-flight one-metre-strip workflow with MKS inputs,
  loads, flexural steel, spacing and reference tension-controlled checks.
- Calculation block copied into `desktop_app/stair_calc.py`; reference module
  and helpers remain unchanged. Invalid depth/infeasible flexure clears results.
- 32 tests passed across Stair helpers/native Stair and existing native pages.
  Reference comparisons cover different step counts and live loads.
- Native form and elevation visually inspected.
- Stair PDF and U-shape migration remain pending.
- Actual packaged smoke test passed (exit 0; `build/exe-stair-smoke.json`),
  including Stair and existing member PDFs. Launcher uses `dist/stair-desktop`.

### Straight Stair PDF

- Added export with saved project metadata, calculation snapshot, MKS loads,
  reinforcement/spacing checks and elevation. Input edits invalidate export.
- QSaveFile writes completed output; cancelling the dialog preserves files.
- Two-page sample rendered and visually inspected. 33 tests passed across
  Stair helpers and native member pages, including PDF save/cancel checks.
- Actual packaged smoke test passed (exit 0; `build/exe-stair-pdf-smoke.json`)
  for Stair and existing PDFs. Launcher points to `dist/stair-pdf`.

## U-Shape native page

- Stair now has straight and U-shape tabs. U-shape follows the reference
  one-flight-plus-landing, simply supported 1 m strip calculation, including
  user-selected bar spacing and provided-steel tension-controlled checks.
- Reference calculation block copied into `u_stair_calc.py`, with invalid
  depth/infeasible flexure raising errors and clearing previous results.
- 37 tests passed across Stair helpers and native pages. U-shape equivalence
  covers step counts, spacing and reference loads/steel/verdict values.
- Native form and elevation visually inspected. U-shape PDF remains pending.
- Actual packaged smoke test passed (exit 0; `build/exe-u-stair-smoke.json`),
  covering U-shape and existing member PDFs. Launcher uses `dist/u-stair-desktop`.

### U-Shape PDF

- Export implemented with input snapshot, project metadata, reinforcement
  checks and elevation. Input edits invalidate export; atomic save/cancel tested.
- Two-page sample rendered and visually inspected. Native member regression:
  38 tests passed.

## Building Model native starter

- Replaced placeholder with X/Y bay spacings, per-storey heights, common sections,
  concrete strength and slab thickness/SDL/LIVE inputs. Generated columns and
  beams are shown from actual analytical connectivity in a rotatable 3-D view.
- Uses existing geometry helpers and `run_building_analysis`; engineering
  equations unchanged. Table shows signed local end forces for SELF/SDL/LIVE
  and U1/U2, explicitly not member interior envelopes or design verdicts.
- Edits clear results and preview. Nonfinite/nonpositive dimensions are rejected;
  initial dense-solver UI is limited to 180 nodes.
- 44 native Building/pipeline/frame tests passed; 38 native member regressions
  passed. Native screenshot visually inspected (`build/building-native.png`).
- Full ACI 318M-08 audit, lateral loads, stability, free member editing and
  project persistence remain outstanding. See `BUILDING_MODEL_NATIVE_SCOPE.md`.
- Packaged EXE smoke passed (exit 0, `build/exe-building-grid-smoke.json`),
  including Building analysis/3-D lines/results table and all migrated PDFs.
  Launcher now uses `dist/building-grid-desktop`.

### Model files and member selection

- Save/open versioned `.rcmodel` files containing grid, heights, common sections,
  material and gravity load inputs. Results are recomputed after loading; shared
  project metadata is not part of this model-only format.
- Validate complete files before changing current inputs/results; reject invalid
  dimensions, malformed data and unsupported versions. QSaveFile commits writes
  atomically. Cancelled dialogs preserve current state.
- Pick a 3-D member or select its type/id/level in the list to highlight it and
  filter signed end forces. All-members selection restores the full table.
- 25 native Building and pipeline tests passed, including roundtrip, invalid-file
  preservation, cancel and member/level filtering. Screenshot inspected:
  `build/building-selection.png`.
- Packaged EXE smoke passed (exit 0, `build/exe-building-files-smoke.json`),
  exercising model save/load, member filtering, analysis and existing PDFs.
  Launcher updated to `dist/building-model-files`.

### Internal-force diagrams

- Added a separate diagram tab for selected member/level and SELF, SDL, LIVE,
  U1 or U2. Components: N, V2, V3, M2, M3 and T, with local units and i-to-j axis.
- Desktop sampling adapter reuses existing analytical load integration and
  combination functions; samples at 81 positions plus load breakpoints.
  No interpolation between member end forces and no new engineering equations.
- Revision-checked result lookup guards availability. Input changes and model
  loads clear diagrams. Labels distinguish internal-cut signs from end actions,
  and display sampling from design-grade extrema/envelopes.
- 33 desktop Building/result-store tests passed, including endpoint signs,
  combination superposition and stale-plot invalidation. Full source smoke passed.
- Diagram screenshot inspected: `build/building-force-diagram.png`.
- Packaged EXE smoke passed (exit 0, `build/exe-building-diagrams-smoke.json`),
  including U2 diagram samples, model files, member filtering and existing PDFs.
  Launcher now uses `dist/building-force-diagrams`.

### Support reactions and equilibrium

- Added per-case/combo global support reaction table with node coordinates,
  force/moment units and an explicit support-on-structure sign convention.
  Artificial torsion constraints are excluded from physical support rows.
- Shows total downward applied gravity load, total upward support force,
  vertical difference and the solver's existing global force/moment residuals
  and acceptance flags. No new acceptance tolerances or design verdicts.
- Editing/loading the model clears reactions together with other results.
- 43 native Building/frame tests passed, including all five cases/combinations,
  raw support mapping, equilibrium and an independent LIVE area-load total.
- Source smoke passed; screenshot inspected: `build/building-reactions.png`.
- Packaged EXE smoke passed (exit 0, `build/exe-building-reactions-smoke.json`).
  Launcher updated to `dist/building-reactions`.

### Model editing history and standard views

- Added model-wide Undo/Redo buttons, grouping edits when field editing finishes
  or the preview is applied. Keep up to 50 snapshots in the current session.
  Pending edits can be undone; new edits after undo discard the redo branch.
- Opening a valid model is undoable. Invalid input can be undone without
  restoring old analysis: undo/redo clears reactions, forces and diagrams.
  Model files continue storing inputs only, without session history.
- Added top XY, front XZ and side YZ orthographic views plus perspective 3D.
  View changes retain calculation results; chosen view survives model rebuilds.
- 18 native Building tests passed, including invalid edits, redo branching,
  file-load undo and view changes retaining results. Screenshot inspected:
  `build/building-undo-views.png`.
- Source and packaged EXE smoke passed (exit 0,
  `build/exe-building-undo-smoke.json`). View regression rechecked after removing
  occluding panes in orthographic views. Launcher uses `dist/building-undo-views`.

## Home page redesign — 2026-09-08

- Removed the left `QListWidget` sidebar. Navigation is now a flat
  `QStackedWidget` driven by `DesktopWindow.go(name)` / `current_page()`.
- New Home is a card launcher (`desktop_app/home.py`): seven design categories
  in the requested order — Building Model, Beam, Column, Slab, Footing, Stair,
  Wall — each with a matching single-colour line icon
  (`assets/desktop_icons/*.svg`, accent `#2563eb`, 48-view / 2.5 stroke).
  Wall carries a "กำลังพัฒนา" badge and opens a placeholder page; no Wall
  engine was added.
- Project is separated into the header alongside Parameters and Help
  (`ข้อมูลโครงการ` / `พารามิเตอร์` / `แนะนำการใช้งาน`); Parameters and Help are
  placeholders. A breadcrumb ("หน้าหลัก / <section>") returns to Home.
- Shared light QSS theme, rounded hover cards, bundled Thai font loaded for
  offscreen/packaged runs. Calculation engines and existing member/Building
  pages are unchanged.
- `run_desktop.py` smoke test and `tests/test_desktop_column.py` moved to the
  `go()` API; the smoke test now also asserts all seven Home cards render an
  icon (guards QtSvg + asset bundling).
- Spec bundles `assets/desktop_icons/*.svg`. 49 desktop tests passed. Source
  and packaged EXE smoke passed (exit 0). Launcher now points to
  `dist/home-redesign`.

## Building Model tool rail + section library — 2026-09-08

- Left side is now a CAD-style vertical tool rail: กริด / ฐานราก / เสา / คาน /
  พื้น / บันได, each opening its own detail panel.
- Every element kind carries a small named-section library with a
  create/edit/delete dialog and a picker, e.g. "C1 · 30×40 cm · 240 ksc".
  The picked Column / Beam / Slab section (b, h, t, f′c) drives the existing
  uniform-grid engine unchanged; the model still resolves to the same
  `grid(...)` dict and the same `.rcmodel` v1 format (a new `sections` key is
  additive and ignored by older readers).
- Footing and Stair sections are stored and — for Footing — drawn as base
  markers on the 3D view (matplotlib scatter, not lines, so the frame line
  count is unchanged). Both are labelled "ยังไม่รวมในการวิเคราะห์"; per-member
  section assignment and free geometry remain out of scope until the frame
  engine accepts them (separate sign-off).
- `self.fields`, `inputs()`, `preview()`, `analyze()`, undo/redo, write/read
  model and every public attribute the tests and smoke rely on are preserved.
  Undo/redo now also snapshots the section library. Default model is
  byte-identical (26 members). New `grid.svg` icon added.
- 49 desktop tests passed; source and packaged EXE smoke passed (exit 0,
  `build/exe-building-tools-smoke.json`). Launcher now points to
  `dist/building-tools`.

## Building Model → free-draw 2D plan editor — 2026-09-08

- **Behaviour change (by request):** the page now opens EMPTY — no model,
  blank plan. The user draws every member themselves.
- New `desktop_app/plan_canvas.py`: a `QGraphicsView` free-draw surface
  (world units = cm). Click to place a Column/Footing point, two clicks for
  a Beam/Stair line, click+double-click for a Slab polygon. Right-drag pans,
  wheel zooms, optional grid snap + snap-to-endpoint. Members are stored as
  plain dicts `{kind, points, section}` + their graphics item.
- Each drawn member takes the active named section from its kind's library
  ("C1 · 20×20 cm · 240 ksc"); the Select tool can re-assign a section to a
  picked member and delete it. Undo/redo and a full history snapshot cover
  drawing, clearing, section edits and storey height.
- The 2D plan is the primary tab; "โมเดล 3D" is a read-only secondary tab
  that extrudes drawn columns by the storey-height field and lays beams/slabs
  at that level. `select.svg` icon added.
- `.rcmodel` is now `rc-codepro-plan` v1 (`plan` + `storey_h` + `sections`).
  Legacy `rc-codepro-grid` v1 files are imported by regenerating their grid
  as drawn columns + beams.
- **No force analysis of the drawn model** — the frame engine
  (`utils/analytical_model`, `utils/building_analysis`) is unchanged and
  untouched; `self.result` stays None. Analysis of an arbitrary drawn member
  list is a later round that needs an engine change + sign-off.
- `tests/test_desktop_building.py` fully rewritten for the new behaviour
  (21 tests); `run_desktop.py` building smoke rewritten (draw / 3D / save-open
  / undo-redo, no analyze). 52 desktop tests pass; source and packaged EXE
  smoke pass (exit 0, `build/exe-plan-editor-smoke.json`). Launcher now points
  to `dist/plan-editor`. (Defender briefly locked the fresh binary right after
  the build — a re-run of the smoke cleared it.)

### Grid tool — user-drawn grid lines with live dimensions — 2026-09-08

- The Grid tool now authors real grid lines. Pick an axis (vertical → A, B,
  C … / horizontal → 1, 2, 3 …), then either click on the plan to drop each
  line or type "ระยะถัดไป (m)" and press "เพิ่มกริดตามระยะนี้" (first add drops
  A/1 at the origin, each later add steps that spacing along the axis).
- A **live dimension** in metres follows the cursor from the nearest / last
  grid before the click (with a pink cross-hair marker), matching the Revit
  behaviour in the reference. Permanent auto dimensions are drawn between
  every pair of consecutive grid lines and relabel/reflow on add or delete.
- Grid lines snap only to other grid lines (1 cm free otherwise), are snap
  targets for members, save into the plan `.rcmodel`, and are skipped in the
  3D tab this round.
- 5 new grid tests; 57 desktop tests pass; source and packaged EXE smoke
  pass (exit 0, `build/exe-grid-tool-smoke.json`). Launcher now points to
  `dist/grid-tool`.

### Grid tool — type-a-distance dynamic input — 2026-09-08

- While the Grid tool is armed and the cursor is over the plan (before the
  click), typing digits / a decimal point builds a distance in metres; a
  pink "X m (Enter)" tag and the live dimension jump to that exact offset
  from the reference grid, in the direction the cursor sits. Enter commits
  the line; Backspace edits; Esc or switching tools clears the buffer.
- The canvas takes keyboard focus on entering grid mode. Direction is the
  sign of (cursor − reference) so the same keystrokes place left or right
  (or up/down for horizontal grids).
- 3 new tests; 60 desktop tests pass; source and packaged EXE smoke pass
  (exit 0, `build/exe-grid-typed-smoke.json`). Launcher now points to
  `dist/grid-typed`.

### Grid tool — finite, endpoint-editable grid lines — 2026-09-08

- Grid lines are now finite axis-aligned segments: `points = [(x1,y1),(x2,y2)]`
  (vertical → equal x + a y-length; horizontal → equal y + an x-length).
- Create by click-one-end then drag / click the other end; the live tag shows
  "ยาว N m". Or, after the first click, type a length (m) + Enter. The
  "เพิ่มกริดตามระยะนี้" button and typed-coordinate flow still place a line at
  a default span.
- Edit any time: the Select tool now grabs a grid endpoint handle (small
  square) and drags it freely — the along-axis move changes the length, the
  perpendicular move shifts the whole line's coordinate; labels and auto
  dimensions reflow live, committing one history entry on release.
- `.rcmodel` stores both endpoints; a legacy single-coordinate grid loads
  with a default span. 6 new tests; 65 desktop tests pass; source and
  packaged EXE smoke pass (exit 0, `build/exe-grid-length-smoke.json`).
  Launcher now points to `dist/grid-length`.

### Plan editor — selection & navigation polish — 2026-09-08

- **Rubber-band multi-select**: left-drag on empty canvas draws a window
  and selects every member fully enclosed. `PlanCanvas` now tracks
  `selected_set`; `delete_selected` and section re-assign act on the whole
  set; the Select panel shows "เลือก N ชิ้น".
- **Right-click context menu**: เลือกชิ้นนี้ / ลบที่เลือก (N) / ยกเลิกการเลือก
  / ออกจากโหมดสร้าง — built by `_build_context_menu(sp)` and shown on
  right-press.
- **Esc leaves any create tool** back to Select/Edit; a new
  `PlanCanvas.mode_changed` signal re-checks the "เลือก" rail button and
  detail panel.
- **Pan moved to the middle mouse button** (was right); the wheel still
  zooms. Panel and page hints updated.
- 4 new tests; 69 desktop tests pass; source and packaged EXE smoke pass
  (exit 0, `build/exe-plan-interact-smoke.json`). Launcher now points to
  `dist/plan-interact`.

### Grid framework — seed lines, span-matching, linked edits — 2026-09-08

- The Building Model now opens with grid **A** (vertical) and grid **1**
  (horizontal) already placed, crossing at X, Y = (0, 0).
- A new grid line's default extent now matches the extent of the grid lines
  already on its axis, so consecutive lines line up end-to-end; the
  interactive draw still snaps an endpoint onto an existing grid's endpoint.
- When a grid endpoint is dragged, every other same-axis grid whose matching
  endpoint shared that position moves the same amount, so a resized grid
  keeps the framework rectangular. `_linked_endpoints` captures the group on
  press; the drag applies to all; one history entry commits on release.
- Tests use a `blank_page()` helper (seed grids cleared) except where the
  seed / span-match / linked behaviour is under test. `run_desktop.py`
  building smoke asserts the seed then clears. 3 new tests; 71 desktop tests
  pass; source and packaged EXE smoke pass (exit 0,
  `build/exe-grid-framework-smoke.json`). Launcher now points to
  `dist/grid-framework`.

### Grid levels, auto-axis, dimension layout, shortcuts — 2026-09-08

- **Keyboard shortcuts** on the Building page: Ctrl+Z / Ctrl+Y (and the
  platform Redo) drive `undo_model` / `redo_model`; Ctrl+A selects every
  non-grid member.
- **Background grid mesh** is gone as a permanent fixture — `drawBackground`
  now paints the light mesh only while `snap` is on, so it appears and
  disappears together with snap mode (origin cross lines always shown).
  `set_snap` repaints the viewport.
- **Drawing levels / elevations**: the Grid detail panel gains a level list
  (`LevelDialog`: name + elevation in m, e.g. "ระดับฐานราก" −1.50,
  "พื้นชั้น 1" +0.55) with add / edit / remove. A "ระดับที่กำลังเขียน"
  combo in the top bar picks the active level; members drawn afterwards are
  stamped with that level's name (`m['level']`) and elevation
  (`m['z']`, metres). The 3D preview lifts each member by `m['z']`.
  Levels persist in the history snapshot and the `.rcmodel` file
  (`levels`, `current_level_idx`).
- **Grid axis is inferred, not chosen**: the axis picker is removed.
  `_resolve_grid_axis` decides X-grid (A, B, C) vs Y-grid (1, 2, 3) from the
  pointer position / drag direction; **Tab** flips and pins the inferred
  axis (`_axis_override`). Handled in `event()` so it wins over focus
  navigation.
- **Dimension layout**: A/B/C chains sit below the framework, 1/2/3 chains
  sit to the left, and each axis gets an **overall total dimension** placed
  between the separated chain and the bubbles (`_DIM_CHAIN_OFF`,
  `_DIM_TOTAL_OFF`, `_BUBBLE_OFF` measured from `_grid_axis_extent`).
- 55 building tests (15 new — 7 of them a dedicated Dimension Layout block:
  total = Σ chain, unique total, none for a 1-grid axis, vertical total
  between chain and bubble, horizontal total right of the bubble, distinct
  total styling, rebuild-on-insert, offset tracks `_grid_axis_extent` after a
  length edit) + 86 desktop tests pass; source smoke exit 0. Launcher points
  to `dist/grid-levels`; previous `dist/grid-framework` removed.
- Packaged EXE rebuilt (exit 0); packaged smoke passes exit 0
  (`build/exe-grid-levels-smoke.json`, `{"ok": true}`). Note: right after a
  build Smart App Control on this host (policy `{0283ac0f-…}`, enforced) can
  block the new unsigned binary with "Application Control policy has blocked
  this file" until Microsoft ISG grants the hash reputation — retry the
  packaged smoke after a few minutes if that happens.

### Off-grid point / line placement — hover dimension + typed offset — 2026-09-08

- Column, footing, beam and stair tools now show a live **offset dimension**
  while aiming (before the first click): a dashed measure from the nearest
  vertical grid to the cursor (X offset) and from the nearest horizontal grid
  (Y offset), each with its distance in metres.
- Typing a distance (digits / `.`) then **Enter** drops the point exactly that
  far from the reference grid on the active axis; the other axis stays on its
  nearest grid line. **Tab** flips which axis the typed number applies to
  (`_pt_axis_override`), mirroring the grid tool. `event()` grabs Tab in these
  modes too.
- The active axis is inferred from whichever offset is larger
  (`_resolve_point_axis`). With no grid lines present the tools fall back to
  the ordinary snapped cursor position — no crash, no reference.
- A plain click with an empty type buffer is unchanged (`_snap_point`,
  including the background-grid snap). `_pt_target` from the live preview is
  what both click and Enter commit.
- New helpers in `plan_canvas.py`: `_nearest_grid`, `_resolve_point_axis`,
  `_toggle_point_axis`, `_point_type_key`, `_refresh_point_preview`,
  `_point_preview`, `_draw_measure`, `_point_confirm_typed`.
- 62 building tests (7 new for this feature) + 93 desktop tests pass; source
  smoke exit 0. EXE not rebuilt this round.

### Home dashboard redesign — real data, no demo rows — 2026-09-12

User feedback was a screenshot of a proposed marketing-style dashboard
(search bar, notifications, language toggle, avatar, a left-nav wizard shell
`Project→Building→Model→Properties→Loads→Analysis→Results→Design→
Reinforcement→Detailing→Export`, a workflow stepper). The app's actual shell
is a ribbon + project-tree + inspector CAD layout, and most of those pages
don't exist, so that part was scoped down with the user (kept the ribbon
shell; skipped search/notifications/language/avatar — no real backing
system for any of them). What shipped, against the real app, no fabricated
data:

- **Title**: "Welcome Start Screen Dashboard" → "Welcome to RC Code Pro";
  subtitle is the real project name + `ACI 318M-19 · Metric (cm · kg)`.
- **Sidebar**: the two 110px NEW/OPEN buttons shrank to normal size; added
  real links (Recent → scrolls to the section, Settings → Parameters page)
  instead of leaving the space empty.
- **Recent Projects is real**: new `desktop_app/recent_files.py`, a tiny
  QSettings-backed MRU list (`RCCodePro`/`Desktop`, key `recent_projects`,
  max 8, pruned to files that still exist). `BuildingPage.save_model`,
  `save_model_as` and the new `open_model_path(path)` (used by both File>Open
  and Home) call `recent_files.add`. `RecentProjectCard` gained a ⋮ menu
  (open / show in folder via `QDesktopServices` / remove from the list) and
  click-anywhere-to-open; empty state is an honest message, not 3 hard-coded
  rows. Per-project 3D thumbnails need a render pipeline — out of scope,
  all cards still share one generic preview image.
- **Continue Designing hero**: new `HeroCard` widget — Building Model is one
  big card with a "เริ่ม Building Model →" button; the other six categories
  render as the standalone-tool row below it (kept the 4-column wrap from
  before — 6 cards in one row overflowed the default window width).
- **Project Overview panel**: new `BuildingPage.overview_data()` reads real
  element counts (grouped by kind, grids excluded), level count, and
  analysis status off `self.result`; Home shows it in a `QStackedWidget`
  alongside a Getting Started checklist shown instead when the canvas has no
  members yet.
- `HomePage` now takes `on_open_file`, `get_project`, `get_building` (lazy
  callables — Home is built before BuildingPage exists) and a `refresh()`
  method called from `DesktopWindow.go()` on every navigation to Home.
- Fixed a latent widget-lifetime bug found while testing: `_refresh_recent`
  was clearing the grid with `deleteLater()` alone, which leaves the old
  cards as live children (still found by `findChildren`) until the event
  loop processes the deferred delete; now `setParent(None)` first.
- `tests/test_desktop_workbench.py` rewritten for the new layout (asserts
  `HeroCard`×1 + `CategoryCard`×6, and exercises both the empty and
  populated Recent Projects states via a monkeypatched `recent_files.load`).
  `run_desktop.py`'s smoke test updated to match. 117 desktop tests pass —
  the 3 remaining `test_desktop_footing.py::test_reference` failures are a
  pre-existing, unrelated `build_report()` signature mismatch (confirmed via
  `git stash`), flagged as a separate follow-up task, not fixed here.
- EXE not rebuilt this round.
