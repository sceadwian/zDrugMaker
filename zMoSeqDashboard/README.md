# lbs MoSeq Syllable Explorer — v0.1

A portable, offline browser viewer for one MoSeq usage-by-subject dataset at a time. Includes treatment bar graphs with mean ± SEM, individual animal dots, Prism exports, and separate notes for syllables, animals and groups.

## Start the dashboard

**Windows:** double-click `Start Dashboard.bat`. Python 3.8 or newer and a modern browser are sufficient; no additional Python packages or JavaScript libraries are needed. The launcher opens your browser, lists the current files in `data_MoSeq_raw`, and refreshes the included offline catalog. Keep its window open while working. Use **Close dashboard** at the bottom of the sidebar when finished.

The close dialog lists datasets with unsaved notes or session settings (including combinations and heatmap settings). Save the current session, keep working to save another dataset, or explicitly close without saving. Closing stops this Python launcher cleanly; a command window opened by double-clicking the batch launcher should exit with it. An existing terminal stays open, with its command prompt restored. The browser shows “Dashboard closed”; close that tab normally. Other tabs using the same launcher lose their server connection, so save their work first. Direct HTML mode simply shows the closed screen because it has no server to stop. Restart the launcher once after installing this update to enable the button's shutdown action.

**Other computers:** run `python launch.py` (or `python3 launch.py`) from this folder.

The Windows batch launcher opens **Google Chrome** when it is on PATH or in a standard per-user/system installation folder. If Chrome is unavailable, it falls back to your default browser. This does not change the operating system's default browser. For the same behavior from Python, run `python launch.py --browser chrome`; plain `python launch.py` uses the OS default.

**Without Python:** open `index.html` directly. The included catalog lets you explore the four supplied datasets immediately. It is a snapshot: use **Choose data folder** or **Open a data file** to read new or edited raw files. Folder selection works in current Chrome and Edge; individual file selection is the fallback. Nothing needs to be downloaded from the internet.

Copy this entire `zMoSeqDashboard` folder to share it with colleagues, including its raw-data folder. The app uses only local files and, in launcher mode, a server bound to this computer's loopback address. No external services or accounts are involved.

## Your data folder

Place source `.txt`, `.tsv` or `.csv` files directly in `data_MoSeq_raw`. In launcher mode, click **Refresh local data folder** after adding or editing files. The app reads source files; it never changes them. Files opened through the browser are read in memory; copy them into the raw folder yourself if you want them listed on the next launch.

Required headers are `subject`, `group`, `syllable`, `usage`, `treat`. Tab- and comma-separated UTF-8 files are supported, including quoted fields. Usage must be a fraction between 0 and 1. Each subject belongs to one group; each group has one distinct treatment name. Duplicate subject–syllable rows and inconsistent group assignments are rejected, rather than silently averaged. File limit: 20 MB.

## Compare syllables

Choose an active file, then select syllable checkboxes. The initial six are ranked by overall mean usage among available observations. Select matches adds search results; Clear all removes every selected plot. All treatment groups in the source are included. Change plots per row, choose shared or independent y-axis scales, and show or hide animal dots. Hover over a dot to see its animal ID, value and any animal annotation.

The bar is the arithmetic mean. Each plot also lists mean ± SEM and n for every treatment beneath the graph, in the selected display units. These displayed numbers use five significant digits; exported data retain full precision. Error bars are mean ± SEM, where SEM is sample SD / √n and sample SD uses n − 1. n counts available values for that syllable and group, not the entire study. With n = 1, the mean is displayed without SEM (N/A in the value table); with n = 0, no bar is displayed. Zero is a measured value. Missing rows and blank/NA/N/A/NaN/null usage values remain missing, generate warnings, and are excluded from calculations. The full lower SEM is shown even if it extends below zero.

The percentage option multiplies values, means, SD and SEM by 100. It also changes export units. No statistical hypothesis tests, pooling across files or automatic behavior identification are performed. Syllable IDs from separately fitted models must not be assumed to mean the same behavior.

## Combined syllables workspace

Select two or more syllables using the sidebar, open **Combined syllables**, enter a name and choose **Add selected syllables**. Add additional named combinations to compare them in the same grid. The original treatment workspace and raw measurements remain available. Use Remove combination to discard a derived graph.

Each combination sums the selected usage values **within each animal**. Means, sample SD and SEM are then calculated from those animal totals. Component SEMs are never added together. If any component is explicitly missing or has no row for an animal, that animal's combined value is missing and excluded; measured zeros remain valid. Overlapping combinations share measurements and should not be treated as independent outcomes. Prism exports contain the individual summed values. Save your session to preserve combination definitions and names.

All bar charts, including SVG exports, have a labeled y-axis, left and bottom axis lines and subtle bar outlines. Percentage is the default for a new dataset; choosing original fractions changes the label truthfully to fraction units.

## Heatmaps workspace

Select syllables in the sidebar and open **Heatmaps**. Syllables are horizontal columns; treatment means or individual animals are vertical rows. Palettes include ivory/teal, ivory/purple, blue/white/red, Viridis, Magma, Cividis, Mako and Turbo, plus five custom gradients: `#FF2CDF → #0014FF`, `#00E1FD → #FC007A`, `#00FF5B → #0014FF`, `#FFE53B → #FF2525`, and ivory (`#FFF9E9`) → `#FF005B`. The low, midpoint and high thresholds map to the beginning, middle and end of the palette, in the selected units; low < midpoint < high is required. Values outside the range use the nearest endpoint color. **Fit color range** sets zero to the maximum selected usage, with a halfway midpoint. Gray cells indicate missing values. Hover over a cell for its value and IDs.

The heatmap is reconstructed from the loaded usage-by-subject table. It uses actual usage, not row-normalized scores, statistical significance or clustering, so it may differ from upstream MoSeq figures that use those transformations. Columns follow syllable ID order; animal rows are grouped by treatment and sorted by animal ID. Labels use your annotations. SVG and tabular value exports are available; exported value tables have syllable columns and original group/treatment/animal identifiers down the rows.

Use the **Cell width** (8–120 px) and **Cell height** (12–90 px) sliders to make cells wider, taller or more compact. Below 18 px width, compact vertical syllable IDs replace long column labels; hover retains full labels. Individual-animal rows are separated into treatment blocks with named headers, animal counts, colored markers and gaps. Treatment-mean rows also have spacing between groups. These separators appear in SVG exports and do not add rows to data exports. **Square cells** matches their dimensions (minimum 12 px, to keep row labels readable); **Reset dimensions** restores 36 × 32 pixels. Wide heatmaps scroll horizontally. Dimensions, palette, thresholds and row mode are saved with the session and carried into SVG figures. Viridis and Magma use the original 256-color tables, bundled locally from the [BIDS colormap project](https://github.com/BIDS/colormap), released under [CC0](https://creativecommons.org/publicdomain/zero/1.0/); there is no runtime download or added library dependency. Cividis/Turbo tables are bundled from [Matplotlib](https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/_cm_listed.py); Mako comes from [Seaborn](https://github.com/mwaskom/seaborn/blob/master/seaborn/cm.py). Their notices and licenses are retained in `PALETTE_LICENSES.md`.

## Export for GraphPad Prism

Choose **Prism table** on a syllable plot. **Copy values for Prism** copies a tab-separated table for a Prism Column table: original treatment names across columns, individual animal values down each column. You can also download it as `.tsv`, or select the fallback text and copy manually.

Animal IDs are naturally sorted separately within each treatment. Rows across treatment columns do not establish pairing. Unequal group sizes are padded with blanks; missing observations leave blanks in their animal's position. Use **Download values + animal IDs** to retain the exact ID/value mapping. The table contains full numeric values, not rounded chart labels. Annotation labels do not replace treatment names or alter measurements.

**Export selected summary** provides dataset, syllable, group, treatment, units, n, mean, sample SD and SEM for selected plots. **Save SVG** saves a scalable chart image. Text labels beginning with spreadsheet formula characters are prefixed with an apostrophe in tabular exports.

## Keep labels and commentary separate

Open **Notes & labels**, or **Note** on a plot. Choose a syllable, animal or treatment group by its original ID. Add an optional display label and comment. Edits are retained in the current page session as you type; **Apply note** refreshes the note list and plot display. Removing a note does not remove an observation. Notes never exclude an animal from calculations.

Custom treatment labels appear on the graph axes, legend and per-plot value tables, including exported SVG figures. Custom syllable labels become the bold plot heading, with the original `Syllable #` below in smaller green text. Exported SVG figures use the same heading hierarchy. Original treatment names remain in Prism and data exports for traceability. Remove a custom label to return to the original name.

**Save notes file** downloads a small JSON sidecar, for example:

```text
MOS-VIZ1_usage_bysubject_LSD.txt
MOS-VIZ1_usage_bysubject_LSD.moseq-notes.json
```

Move the downloaded notes file next to the matching raw file yourself. Browser downloads normally go to Downloads; this app does not silently write to the raw-data folder. On another computer or on your next visit, open the raw dataset, then use **Notes & labels → Open notes file**. Sidecars are loaded explicitly in v0.1, even when they are beside the source. Saving again may produce a numbered download: keep the newest copy as your shared notes file.

Notes are matched by the raw filename and a content fingerprint. Moving the containing folder is fine. Renaming or editing a dataset prevents old notes from being loaded accidentally. BOM and Windows/Unix line-ending differences are ignored. The fingerprint is an accidental-mismatch guard, not a security signature. Syllable, animal and group notes are stored under original IDs in separate JSON sections. There is no automatic merge between collaborators' versions.

An asterisk indicates notes that have not been saved. Notes for other datasets stay in memory while you switch files; switch back to save each dataset's notes before closing the page. The browser warns about unsaved notes when possible. **Save session** includes the active dataset's notes, original data text, selected syllables, combinations, active workspace and heatmap/display settings. Save explicitly before closing to retain changes.

## Save sessions beside the raw data

When using **Start Dashboard.bat** / `launch.py` and a dataset from the live raw folder, **Save session** writes directly to `data_MoSeq_raw`, using the existing name such as `MOS-VIZ1_usage_bysubject_LSD_session.json`. No save dialog or Downloads move is needed. A later save replaces that session and keeps one previous version as `_session.previous.json`. The raw TXT/CSV/TSV file is never overwritten.

Opening that active dataset in a fresh dashboard visit automatically restores its matching session, including notes and workspace settings. The raw filename and contents must match; changed raw data prevents automatic restoration of an older session. Within an already open page, switching datasets retains the most recent in-memory settings. **Open session** can still open a saved snapshot manually.

If you open `index.html` directly, or load a file outside the launcher's raw folder, **Save session** retains the download workflow. Browsers cannot silently write beside an arbitrary selected file. Put outside files in `data_MoSeq_raw` and refresh the launcher view to use direct saves. Restart the Python launcher after updating its code to enable this feature. Separate notes-only files still use explicit download/open; automatically restored sessions already contain their notes.

## About and Help

Both are available in the sidebar. About lists author **Leo B Silenieks**, Transpharmation Inc., University of Guelph, contact **leo.silenieks@gmail.com**, and the supplied [Google Scholar profile](https://scholar.google.ca/citations?user=w4Str-YAAAAJ&hl=en). It describes this study viewer and the underlying MoSeq method, developed in the Datta laboratory at Harvard Medical School. The background links to [Datta Lab's behavioral-analysis research](https://datta.hms.harvard.edu/research/behavioral-analysis/) and its [MoSeq protocol](https://datta.hms.harvard.edu/publications/characterizing-the-structure-of-mouse-behavior-using-motion-sequencing/). Help provides the user workflow and calculation definitions.

## Files and maintenance

| File | Purpose |
| --- | --- |
| `index.html` | Application layout, About and Help text |
| `styles.css` | Appearance and responsive layout |
| `core.js` | Data validation, descriptive statistics, exports and notes format |
| `palettes.js` | Bundled Viridis, Magma, Cividis, Mako and Turbo color tables |
| `PALETTE_LICENSES.md` | Color table sources and license notices |
| `app.js` | Browser controls, graphs, file loading and annotations |
| `launch.py` | Optional standard-library local server and catalog refresher |
| `Start Dashboard.bat` | Windows launcher |
| `catalog.js` | Generated offline snapshot; contains copies of the raw data |
| `data_MoSeq_raw/` | Original study files; application does not edit them |
| `tests/` | Developer verification scripts; not needed to use the app |

To refresh only the snapshot: `python launch.py --catalog-only`. To start without opening a browser automatically: `python launch.py --no-browser`. A specific local port can be selected with `--port 8765`.

Developer numerical checks use `node tests/core.test.js`; launcher checks use `python -m unittest discover -s tests -p "test_*.py"`. Node and browser automation are only development tools, not requirements for dashboard users.
