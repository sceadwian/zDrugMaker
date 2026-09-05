# v0.1 validation — 2026-09-05

Passed using Node for the standalone calculation checks, Python's standard library for local-server checks, and headless Microsoft Edge for browser checks. Development tools are not required by dashboard users.

- All 100 syllables in each of the four supplied datasets: every treatment mean and SEM matched an independent direct mean/two-pass variance calculation.
- Verified animal totals: 2BrLSD 23, Ariadne 23, LSD 24, Psilocybin 24; 2,300 or 2,400 observation rows per file, respectively. All four loaded without missing-data warnings.
- Synthetic cases verified valid zero values, absent rows, explicit missing values, n = 0 and n = 1, unequal group sizes, seven/nine treatment groups, quoted CSV fields, invalid values, conflicting assignments and duplicate rejection.
- Verified Prism column layout, blank padding, missing-position preservation, individual ID export and percentage conversion.
- Browser checks passed both for `file://` direct opening and Python-served localhost mode: dataset selection, six initial graphs, notes for all three entity types, downloaded notes round trip, wrong-file rejection, session restoration, Prism export, selection controls, Help and About.
- Inspected desktop and mobile screenshots. No horizontal page overflow at 390 px; wide individual charts scroll within their cards.
- No external web requests or uncaught browser errors during either browser run.
- Branding/labels follow-up: verified the personalized logo loads, custom treatment labels appear on axes and in value tables, custom syllable headings retain smaller original IDs, and SVG downloads contain custom labels. Checked displayed mean ± SEM values against the calculation layer in percentage units. Inspected the updated desktop screenshot; responsive browser checks passed.
- Local-server checks verified folder discovery, rescan after a new file, raw-file byte preservation during catalog creation, and rejection of invalid raw-file paths.

The tests validate descriptive calculations and app behavior. They do not establish behavioral meanings for syllables, validate upstream MoSeq processing, or perform biological/statistical inference. Safari and Firefox were not browser-tested.

## Workspaces and local sessions follow-up

- A hand-constructed paired dataset verified that combination means/SEM are calculated from per-animal sums, including a zero-SEM total despite varying component values. Explicit and absent missing components remain missing; repeated component IDs are rejected.
- The workspace browser test verified summed Prism values, percentage y-axis labels and bar outlines, treatment and individual-animal heatmap dimensions, invalid-threshold handling, unit conversion and heatmap values export.
- A temporary application copy verified direct local session saving and automatic restoration of combination definitions, active workspace and heatmap settings. Source raw-file bytes remained unchanged. No test sessions were written into the real raw-data folder.
- Python tests verified session read/write, previous-version backup, rejection of saves after raw data changes, and rejection of writes from an unrelated web origin.
- Close-dashboard follow-up: the browser test verified unsaved-settings detection, cancellation leaving the server running, saving from the close dialog clearing the warning, and shutdown ending Python with exit code 0. The server rejects shutdown requests from an unrelated origin.
- Updated desktop screenshots were inspected for the combined and heatmap workspaces. Existing direct-HTML browser regression checks also passed.

Run `node tests/workspaces-smoke.cjs` with the browser-test environment variables plus `PYTHON_EXECUTABLE` pointing to a standard Python installation to repeat the local-workspace test.

## Top 20, palette and layout follow-up

Browser checks passed for Top 20/Top 6 selection sizes, black bar-chart axes and tick labels, transposed heatmap cell coordinates, Viridis/Magma availability, cell width/height controls, square cells and session restoration of dimensions. SVG exports preserve adjusted cell geometry. Heatmap TSV exports now have syllable columns and treatment/animal rows; their orientation was checked. Updated title, author details, contact link and MoSeq background were checked in About. Desktop heatmap screenshots were inspected, including the horizontal Top 20 Viridis view. Existing browser regression checks passed without external requests or page errors.

Additional heatmap checks passed for 100 syllables at 8 px width (2,300 animal cells), three treatment headers and larger gaps at group boundaries, all five bundled scientific palettes, exact endpoint colors for the five custom gradients, and restoration of an 8 px / Mako session. The 100-syllable grouped Mako screenshot was inspected. Source color tables were parsed as data only; no third-party Python code was executed or installed.

Heatmap defaults/description follow-up: browser tests verified a new view starts in fractions with 12 × 12 cells and Turbo; horizontal/rotated labels toggle; description show/hide works; SVG output includes visible description text and horizontal labels; session restoration retains the description, orientation and user-selected units. Existing workspace and direct-HTML regression tests passed. The horizontal-label heatmap screenshot with a sample test description was inspected.

Defaults correction: verified the Python-served interface initially selects all 100 syllables (2,300 individual-animal cells for 2BrLSD), individual-animal rows, fractions, Turbo and 12 × 12 cells. The description box is visible above row/palette controls. A simulated older 36 × 32 / teal / treatment-means session migrated to these defaults while retaining a syllable annotation and test description. Independent heatmap selections, the restore-defaults button, current-session restoration, and existing browser regressions passed. The verified-defaults screenshot was inspected.

To repeat the browser test, provide paths to an existing Playwright module and browser using `PLAYWRIGHT_MODULE` and `BROWSER_EXECUTABLE`, then run `node tests/browser-smoke.cjs`. Optionally set `DASHBOARD_URL` to a running local launcher's URL. Test outputs in `tests/artifacts` include synthetic annotations and must not be treated as study notes.
