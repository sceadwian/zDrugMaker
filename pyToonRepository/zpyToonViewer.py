"""zpyToonViewer -- GUI browser for the universal character roster.

Naming schema
-------------
This script follows the *zpy* schema: new scripts are named zpyNameOfScript.
(Legacy scripts follow the older pyNameOfScript convention.)

Data source
-----------
Reads universal_characters_master.csv (schema 1.0, see
universal_character_schema.md) from the same folder as this script, falling
back to a pyToonRepository/ subfolder. The CSV is treated as read-only; this
tool only visualizes it.

Views
-----
* Characters  -- per-character attribute bars, color-coded by rating band,
                 with population median / quartile notches on every bar,
                 politics and morality spectrum strips, and an optional
                 second-character comparison overlay.
* Population  -- roster-wide analytics: demographics, political and moral
                 spectra, core group averages (PHY/COG/PSY/SOC), per-
                 attribute box plots, correlations, and a rating band census.

Python 3, standard library only (tkinter + csv + statistics).
"""

import csv
import statistics as st
import tkinter as tk
from collections import Counter
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

SCRIPT_NAME = "zpyToonViewer"
SCHEMA_NOTE = ("naming schema: zpy  |  new tools are named zpyNameOfScript  "
               "(legacy tools: pyNameOfScript)")

CSV_NAME = "universal_characters_master.csv"
_HERE = Path(__file__).resolve().parent
# Look next to the script first, then in a pyToonRepository subfolder.
CSV_PATH = next((p for p in (_HERE / CSV_NAME,
                             _HERE / "pyToonRepository" / CSV_NAME)
                 if p.exists()), _HERE / CSV_NAME)

# Attribute groups, in schema order.
GROUPS = [
    ("Physical", ["strength", "stamina", "speed", "agility", "coordination",
                  "dexterity", "balance", "recovery", "resilience",
                  "metabolism", "lifespan"]),
    ("Cognitive", ["intelligence", "perception", "focus", "memory",
                   "creativity", "learning", "technical_aptitude",
                   "tactical_awareness"]),
    ("Psychological", ["willpower", "faith", "courage", "composure",
                       "discipline", "determination", "adaptability",
                       "patience", "risk_assessment"]),
    ("Social", ["charisma", "empathy", "conversation", "deception",
                "loyalty", "aggression"]),
]
ALL_ATTRS = [a for _, attrs in GROUPS for a in attrs]

# Core sub-groups used for per-character averages: capability traits only.
# Physical drops the lifestyle traits (metabolism, lifespan); Social drops
# the morally-flavoured tendencies (aggression, loyalty, deception).
CORE_EXCLUDE = {
    "Physical": {"metabolism", "lifespan"},
    "Social": {"aggression", "loyalty", "deception"},
}
CORE_GROUPS = [(g, [a for a in attrs if a not in CORE_EXCLUDE.get(g, ())])
               for g, attrs in GROUPS]
CORE_ABBR = {"Physical": "PHY", "Cognitive": "COG",
             "Psychological": "PSY", "Social": "SOC"}

# 1-99 axis columns rendered as gradient strips, not rating bars:
# (column, caption, left-end RGB, right-end RGB, bucket names).
AXES = [
    ("left2right", "left2right (politics)",
     (0x33, 0x55, 0xb7), (0xb7, 0x55, 0x33), ("left", "centre", "right")),
    ("evil2good", "evil2good (morality)",
     (0x7a, 0x1a, 0x1a), (0x2e, 0x7d, 0x32), ("evil", "neutral", "good")),
]

# Rating bands from universal_character_schema.md:
# (upper bound, color, schema label, compact word shown next to each bar).
BANDS = [
    (9,  "#b71c1c", "Extremely low", "dire"),
    (24, "#d84315", "Very low",      "weak"),
    (39, "#ef6c00", "Below average", "poor"),
    (59, "#f2b41f", "Average",       "average"),
    (74, "#9e9d24", "Above average", "solid"),
    (89, "#558b2f", "Excellent",     "great"),
    (98, "#2e7d32", "Exceptional",   "elite"),
    (99, "#b8860b", "Maximum",       "max"),
]
BAND_RANGES = ["1-9", "10-24", "25-39", "40-59", "60-74", "75-89",
               "90-98", "99"]


def band_for(value):
    for upper, color, label, short in BANDS:
        if value <= upper:
            return color, label, short
    return BANDS[-1][1], BANDS[-1][2], BANDS[-1][3]


def load_roster(path):
    """Load the master CSV (UTF-8 with BOM) into a list of dicts."""
    roster = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("character_id"):
                continue
            for attr in ALL_ATTRS + ["left2right", "evil2good",
                                     "birth_year", "height_cm", "weight_kg"]:
                try:
                    row[attr] = int(row[attr])
                except (ValueError, TypeError, KeyError):
                    row[attr] = None
            roster.append(row)
    return roster


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return 0.0
    return sxy / (sxx * syy) ** 0.5


def compute_attr_stats(roster):
    """Per-attribute population stats: mean, spread, quartiles, extremes."""
    out = {}
    for attr in ALL_ATTRS:
        vals = [c[attr] for c in roster]
        q1, med, q3 = st.quantiles(vals, n=4, method="inclusive")
        mn, mx = min(vals), max(vals)
        min_who = [c["short_name"] for c in roster if c[attr] == mn]
        max_who = [c["short_name"] for c in roster if c[attr] == mx]
        out[attr] = {
            "vals": vals,
            "mean": st.fmean(vals),
            "stdev": st.pstdev(vals),
            "q1": q1, "median": med, "q3": q3,
            "min": mn, "max": mx,
            "min_who": "/".join(min_who[:2]),
            "max_who": "/".join(max_who[:2]),
        }
    return out


class ToonViewer(tk.Tk):
    ROW_H = 22          # pixels per attribute bar row (character view)
    HEAD_H = 30         # pixels per group header
    LABEL_W = 150       # attribute label column width
    VALUE_W = 92        # value text column width

    def __init__(self, roster):
        super().__init__()
        self.roster = roster
        self.by_name = {c["display_name"]: c for c in roster}
        self.current = None
        self.compare = None
        self._compute_population()

        self.title("%s  --  universal character visualizer  [zpy schema]"
                   % SCRIPT_NAME)
        self.geometry("1120x760")
        self.minsize(900, 580)

        self._build_ui()
        self._refresh_list()
        if roster:
            self.listbox.selection_set(0)
            self._on_select()

    # -------------------------------------------------- population stats
    def _compute_population(self):
        roster = self.roster
        self.stats = compute_attr_stats(roster)
        # per-character core group averages and their composite
        self.core = {
            c["character_id"]: {g: st.fmean(c[a] for a in attrs)
                                for g, attrs in CORE_GROUPS}
            for c in roster}
        self.composite = {cid: st.fmean(gs.values())
                          for cid, gs in self.core.items()}
        self.ranking = sorted(
            roster, key=lambda c: self.composite[c["character_id"]],
            reverse=True)
        # spread of each character's own 34 ratings (well-rounded vs spiky)
        self.spread = {c["character_id"]:
                       st.pstdev([c[a] for a in ALL_ATTRS]) for c in roster}
        # all attribute-pair correlations across the roster
        pairs = []
        for i, a in enumerate(ALL_ATTRS):
            xs = self.stats[a]["vals"]
            for b in ALL_ATTRS[i + 1:]:
                pairs.append((pearson(xs, self.stats[b]["vals"]), a, b))
        pairs.sort()
        self.corr_neg = pairs[:5]
        self.corr_pos = pairs[::-1][:7]

    # ------------------------------------------------------------- UI build
    def _build_ui(self):
        # Header banner making the zpy naming schema obvious.
        banner = tk.Frame(self, bg="#1f2733")
        banner.pack(fill="x")
        tk.Label(banner, text=SCRIPT_NAME, bg="#1f2733", fg="#7fd4a8",
                 font=("Consolas", 15, "bold")).pack(side="left",
                                                     padx=(12, 8), pady=6)
        tk.Label(banner, text=SCHEMA_NOTE, bg="#1f2733", fg="#c9d4e0",
                 font=("Consolas", 9)).pack(side="left", pady=6)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        char_tab = ttk.Frame(self.notebook, padding=8)
        pop_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(char_tab, text="  Characters  ")
        self.notebook.add(pop_tab, text="  Population  ")

        self._build_character_tab(char_tab)
        self._build_population_tab(pop_tab)
        self.bind_all("<MouseWheel>", self._on_wheel)

    def _build_character_tab(self, body):
        # ---- left pane: search / sort / roster list
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 8))

        ttk.Label(left, text="Filter").pack(anchor="w")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._refresh_list())
        ttk.Entry(left, textvariable=self.filter_var, width=26).pack(
            fill="x", pady=(0, 6))

        ttk.Label(left, text="Sort by").pack(anchor="w")
        self.sort_var = tk.StringVar(value="display_name")
        sort_box = ttk.Combobox(left, textvariable=self.sort_var, width=24,
                                state="readonly",
                                values=(["display_name", "left2right",
                                         "evil2good"] + ALL_ATTRS))
        sort_box.pack(fill="x", pady=(0, 6))
        sort_box.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, width=28, exportselection=False,
                                  font=("Consolas", 10))
        sb = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_select())

        ttk.Label(left, text="Compare with (overlay)").pack(anchor="w",
                                                            pady=(6, 0))
        self.compare_var = tk.StringVar(value="(none)")
        cmp_box = ttk.Combobox(left, textvariable=self.compare_var, width=24,
                               state="readonly",
                               values=["(none)"] + sorted(self.by_name))
        cmp_box.pack(fill="x")
        cmp_box.bind("<<ComboboxSelected>>", lambda e: self._on_compare())

        # ---- right pane: identity card + scrollable attribute canvas
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.identity = tk.Label(right, justify="left", anchor="w",
                                 font=("Consolas", 10), bd=1, relief="solid",
                                 padx=10, pady=8, bg="#f4f6f8")
        self.identity.pack(fill="x", pady=(0, 6))

        canvas_frame = ttk.Frame(right)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="white",
                                highlightthickness=0)
        csb = ttk.Scrollbar(canvas_frame, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=csb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", lambda e: self._draw())

        legend_bands = "  ".join("%s %s" % (short, rng) for
                                 (_hi, _c, _label, short), rng in
                                 zip(BANDS, BAND_RANGES))
        self.legend = tk.Label(
            right, font=("Consolas", 8), anchor="w", justify="left",
            text=(legend_bands +
                  "\nbar marks:  ▾ population median   "
                  "▴▴ population Q1/Q3   "
                  "| black line = compare character"))
        self.legend.pack(fill="x")

    def _build_population_tab(self, body):
        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True)
        self.pcanvas = tk.Canvas(frame, bg="white", highlightthickness=0)
        psb = ttk.Scrollbar(frame, command=self.pcanvas.yview)
        self.pcanvas.configure(yscrollcommand=psb.set)
        self.pcanvas.pack(side="left", fill="both", expand=True)
        psb.pack(side="right", fill="y")
        self.pcanvas.bind("<Configure>", lambda e: self._draw_population())

    def _on_wheel(self, event):
        try:
            on_pop = self.notebook.index(self.notebook.select()) == 1
        except tk.TclError:
            return
        cv = self.pcanvas if on_pop else self.canvas
        cv.yview_scroll(-1 * (event.delta // 120), "units")

    # ------------------------------------------------------------ list ops
    def _sorted_roster(self):
        key = self.sort_var.get()
        if key == "display_name":
            return sorted(self.roster, key=lambda c: c["display_name"])
        return sorted(self.roster, key=lambda c: c[key] or 0, reverse=True)

    def _refresh_list(self):
        needle = self.filter_var.get().strip().lower()
        key = self.sort_var.get()
        self.listbox.delete(0, "end")
        self._visible = []
        for c in self._sorted_roster():
            if needle and needle not in c["display_name"].lower():
                continue
            label = c["display_name"]
            if key != "display_name":
                label = "%2d  %s" % (c[key] or 0, label)
            self.listbox.insert("end", label)
            self._visible.append(c)
        # keep current selection highlighted if still visible
        if self.current in self._visible:
            self.listbox.selection_set(self._visible.index(self.current))

    def _on_select(self):
        if not hasattr(self, "_visible"):
            self._refresh_list()
        sel = self.listbox.curselection()
        if sel and self._visible:
            self.current = self._visible[sel[0]]
            self._update_identity()
            self._draw()

    def _on_compare(self):
        self.compare = self.by_name.get(self.compare_var.get())
        self._draw()

    # ----------------------------------------------------- character view
    def _update_identity(self):
        c = self.current
        age = date.today().year - c["birth_year"]
        cid = c["character_id"]
        rank = self.ranking.index(c) + 1
        core_txt = "  ".join("%s %.1f" % (CORE_ABBR[g], self.core[cid][g])
                             for g, _attrs in CORE_GROUPS)
        self.identity.configure(text=(
            "%s  (%s / %s)\n"
            "%s %s, born %d (age %d today) | %s | %s | schema v%s\n"
            "%d cm, %d kg | politics (1L..99R): %d | "
            "morality (1 evil..99 good): %d\n"
            "core averages: %s  ->  composite %.1f (rank %d of %d)\n"
            "%s"
        ) % (c["display_name"], c["character_id"], c["short_name"],
             c["species"], c["sex"], c["birth_year"], age,
             c["nationality"], c["religion"], c["schema_version"],
             c["height_cm"], c["weight_kg"], c["left2right"],
             c["evil2good"],
             core_txt, self.composite[cid], rank, len(self.roster),
             c["description"]))

    def _draw_spectrum(self, cv, x, y, w, h, c0, c1):
        """Gradient strip between two RGB endpoint colors."""
        for i in range(w):
            frac = i / max(w - 1, 1)
            rgb = tuple(int(a + frac * (b - a)) for a, b in zip(c0, c1))
            cv.create_line(x + i, y, x + i, y + h,
                           fill="#%02x%02x%02x" % rgb)

    def _draw(self):
        cv = self.canvas
        cv.delete("all")
        if not self.current:
            return
        width = max(cv.winfo_width(), 400)
        bar_x = self.LABEL_W
        bar_w = width - bar_x - self.VALUE_W - 16
        y = 10

        # axis spectrum strips (politics, morality)
        for col, _caption, c0, c1, _buckets in AXES:
            cv.create_text(8, y + 8, anchor="w", text=col,
                           font=("Consolas", 9, "bold"))
            self._draw_spectrum(cv, bar_x, y + 2, bar_w, 12, c0, c1)
            px = bar_x + (self.current[col] - 1) / 98 * bar_w
            cv.create_polygon(px - 5, y - 2, px + 5, y - 2, px, y + 6,
                              fill="black")
            if self.compare and self.compare is not self.current:
                cx = bar_x + (self.compare[col] - 1) / 98 * bar_w
                cv.create_line(cx, y + 1, cx, y + 15, fill="#1f2733",
                               width=2)
            cv.create_text(bar_x + bar_w + 8, y + 8, anchor="w",
                           text=str(self.current[col]),
                           font=("Consolas", 9))
            y += 26
        y += 4

        for group, attrs in GROUPS:
            avg = sum(self.current[a] for a in attrs) / len(attrs)
            pop_avg = st.fmean(self.stats[a]["mean"] for a in attrs)
            cv.create_text(8, y + self.HEAD_H / 2, anchor="w",
                           text="%s  (avg %.0f, population avg %.0f)"
                                % (group.upper(), avg, pop_avg),
                           font=("Consolas", 10, "bold"), fill="#1f2733")
            cv.create_line(8, y + self.HEAD_H - 4, width - 12,
                           y + self.HEAD_H - 4, fill="#c0c8d0")
            y += self.HEAD_H
            for attr in attrs:
                val = self.current[attr]
                s = self.stats[attr]
                color, _label, short = band_for(val)
                cy = y + self.ROW_H / 2
                cv.create_text(12, cy, anchor="w", text=attr,
                               font=("Consolas", 9))
                cv.create_rectangle(bar_x, y + 4, bar_x + bar_w,
                                    y + self.ROW_H - 4,
                                    fill="#eceff2", outline="#d5dade")
                cv.create_rectangle(bar_x, y + 4,
                                    bar_x + val / 99 * bar_w,
                                    y + self.ROW_H - 4,
                                    fill=color, outline=color)
                # population notches: median (down-triangle, top edge),
                # Q1 / Q3 (up-triangles, bottom edge)
                mx = bar_x + s["median"] / 99 * bar_w
                cv.create_polygon(mx - 4, y + 1, mx + 4, y + 1, mx, y + 8,
                                  fill="#22303c", outline="")
                for q in (s["q1"], s["q3"]):
                    qx = bar_x + q / 99 * bar_w
                    cv.create_polygon(qx - 3, y + self.ROW_H - 1,
                                      qx + 3, y + self.ROW_H - 1,
                                      qx, y + self.ROW_H - 7,
                                      fill="#8a959e", outline="")
                if self.compare and self.compare is not self.current:
                    cx = bar_x + self.compare[attr] / 99 * bar_w
                    cv.create_line(cx, y + 1, cx, y + self.ROW_H - 1,
                                   fill="#1f2733", width=2)
                cv.create_text(bar_x + bar_w + 8, cy, anchor="w",
                               text="%2d %s" % (val, short),
                               font=("Consolas", 8))
                y += self.ROW_H
            y += 8

        if self.compare and self.compare is not self.current:
            cv.create_text(12, y + 8, anchor="w",
                           text="black tick = %s"
                                % self.compare["display_name"],
                           font=("Consolas", 8, "italic"), fill="#1f2733")
            y += 20

        cv.configure(scrollregion=(0, 0, width, y + 10))

    # ---------------------------------------------------- population view
    def _draw_population(self):
        cv = self.pcanvas
        cv.delete("all")
        roster = self.roster
        if not roster:
            return
        width = max(cv.winfo_width(), 640)
        n = len(roster)
        year = date.today().year

        def text(x, y, s, size=9, bold=False, color="#1f2733",
                 anchor="nw"):
            font = ("Consolas", size, "bold") if bold else ("Consolas", size)
            cv.create_text(x, y, anchor=anchor, text=s, font=font,
                           fill=color)

        def section(y, title):
            text(12, y, title, size=11, bold=True)
            cv.create_line(12, y + 20, width - 16, y + 20, fill="#8a959e")
            return y + 28

        y = 10
        text(12, y, "POPULATION REPORT -- %d characters -- %s" %
             (n, CSV_PATH.name), size=12, bold=True)
        y += 30

        # ---------------------------------------------------- demographics
        y = section(y, "DEMOGRAPHICS")
        sexes = Counter(c["sex"] for c in roster)
        by_sex_overall = {
            s: st.fmean(self.composite[c["character_id"]]
                        for c in roster if c["sex"] == s)
            for s in sexes}
        species = Counter(c["species"] for c in roster)
        ages = sorted(((year - c["birth_year"], c) for c in roster),
                      key=lambda t: t[0])
        heights = sorted(roster, key=lambda c: c["height_cm"])
        weights = sorted(roster, key=lambda c: c["weight_kg"])
        bmis = [c["weight_kg"] / (c["height_cm"] / 100) ** 2 for c in roster]
        religions = Counter(c["religion"] for c in roster)
        rel_faith = {r: st.fmean(c["faith"] for c in roster
                                 if c["religion"] == r) for r in religions}
        nats = Counter(c["nationality"] for c in roster)
        lines = [
            "Roster: %d characters | sex: %s | species: %s" % (
                n,
                "  ".join("%s %d (core composite avg %.1f)"
                          % (s, sexes[s], by_sex_overall[s])
                          for s in sorted(sexes)),
                ", ".join("%s %d" % (sp, ct)
                          for sp, ct in species.most_common())),
            "Age (in %d): mean %.1f | youngest %d (%s) | oldest %d (%s)" % (
                year, st.fmean(a for a, _ in ages),
                ages[0][0], ages[0][1]["display_name"],
                ages[-1][0], ages[-1][1]["display_name"]),
            "Height: mean %.1f cm (%d %s - %d %s)" % (
                st.fmean(c["height_cm"] for c in roster),
                heights[0]["height_cm"], heights[0]["short_name"],
                heights[-1]["height_cm"], heights[-1]["short_name"]),
            "Weight: mean %.1f kg (%d %s - %d %s) | mean BMI %.1f" % (
                st.fmean(c["weight_kg"] for c in roster),
                weights[0]["weight_kg"], weights[0]["short_name"],
                weights[-1]["weight_kg"], weights[-1]["short_name"],
                st.fmean(bmis)),
            "Religion (mean faith rating): " + "  ".join(
                "%s %d (%.0f)" % (r, religions[r], rel_faith[r])
                for r, _cnt in religions.most_common()),
            "Nationalities: %d distinct%s" % (
                len(nats),
                " (every character unique)" if len(nats) == n else
                " | most common: " + ", ".join(
                    "%s x%d" % (nm, ct) for nm, ct in nats.most_common(3))),
        ]
        for line in lines:
            text(20, y, line)
            y += 17
        y += 10

        # -------------------------------------- political and moral spectra
        y = section(y, "POLITICAL AND MORAL SPECTRA (each tick = one "
                       "character, marker = mean)")
        strip_x, strip_w = 20, width - 40
        for col, caption, c0, c1, buckets in AXES:
            vals = [c[col] for c in roster]
            text(20, y, caption, size=9, bold=True)
            y += 16
            self._draw_spectrum(cv, strip_x, y + 4, strip_w, 14, c0, c1)
            for c in roster:
                px = strip_x + (c[col] - 1) / 98 * strip_w
                cv.create_line(px, y + 2, px, y + 20, fill="#111", width=2)
            mean_px = strip_x + (st.fmean(vals) - 1) / 98 * strip_w
            cv.create_polygon(mean_px - 6, y - 4, mean_px + 6, y - 4,
                              mean_px, y + 3, fill="#1f2733")
            y += 26
            counts = (sum(1 for v in vals if v < 40),
                      sum(1 for v in vals if 40 <= v <= 60),
                      sum(1 for v in vals if v > 60))
            text(20, y, "mean %.1f | median %.1f | %s(<40) %d / %s(40-60) "
                        "%d / %s(>60) %d"
                 % (st.fmean(vals), st.median(vals),
                    buckets[0], counts[0], buckets[1], counts[1],
                    buckets[2], counts[2]))
            y += 16
            # which rated attributes track this axis most strongly?
            corr = sorted((pearson(vals, self.stats[a]["vals"]), a)
                          for a in ALL_ATTRS)
            text(20, y, "tracks: %s | opposes: %s"
                 % ("  ".join("%s %+.2f" % (a, r)
                              for r, a in corr[::-1][:3]),
                    "  ".join("%s %+.2f" % (a, r) for r, a in corr[:3])),
                 size=8, color="#5f6a73")
            y += 22

        # ------------------------------------------------ core group table
        y = section(y, "CORE GROUP AVERAGES (sorted by composite)")
        text(20, y, "PHY excludes metabolism/lifespan | SOC is charisma/"
                    "empathy/conversation only (no aggression/loyalty/"
                    "deception)", size=8, color="#5f6a73")
        y += 16
        comps = list(self.composite.values())
        text(20, y, "composite: mean %.1f | median %.1f | stdev %.1f | "
                    "range %.1f - %.1f"
             % (st.fmean(comps), st.median(comps), st.pstdev(comps),
                min(comps), max(comps)))
        y += 20
        name_w = 215
        slot_w = (width - name_w - 90) / 4
        for j, (g, attrs) in enumerate(CORE_GROUPS):
            text(name_w + j * slot_w, y, "%s (%d)" % (CORE_ABBR[g],
                                                      len(attrs)),
                 size=8, bold=True)
        text(name_w + 4 * slot_w + 6, y, "COMP", size=8, bold=True)
        y += 15
        for i, c in enumerate(self.ranking):
            cid = c["character_id"]
            ry = y + i * 18
            text(20, ry + 2, "%2d. %-20s" % (i + 1, c["display_name"]),
                 size=8)
            for j, (g, _attrs) in enumerate(CORE_GROUPS):
                v = self.core[cid][g]
                color = band_for(round(v))[0]
                bx = name_w + j * slot_w
                bw = slot_w - 48
                cv.create_rectangle(bx, ry + 3, bx + bw, ry + 15,
                                    fill="#eceff2", outline="#d5dade")
                cv.create_rectangle(bx, ry + 3, bx + v / 99 * bw, ry + 15,
                                    fill=color, outline=color)
                text(bx + bw + 4, ry + 2, "%.1f" % v, size=8)
            text(name_w + 4 * slot_w + 6, ry + 2,
                 "%.1f" % self.composite[cid], size=8, bold=True)
        y += len(self.ranking) * 18 + 10

        # ------------------------------------------- leaders and archetypes
        y = section(y, "GROUP LEADERS AND ARCHETYPES")
        for group, attrs in GROUPS:
            top3 = sorted(roster,
                          key=lambda c: st.fmean(c[a] for a in attrs),
                          reverse=True)[:3]
            text(20, y, "%-14s %s" % (group + ":", "  ".join(
                "%s %.1f" % (c["short_name"],
                             st.fmean(c[a] for a in attrs))
                for c in top3)))
            y += 17
        rounded = sorted(roster, key=lambda c: self.spread[c["character_id"]])
        text(20, y, "Most well-rounded (lowest own-rating spread): %s | "
                    "Most specialized: %s"
             % ("  ".join("%s sd %.1f" % (c["short_name"],
                                          self.spread[c["character_id"]])
                          for c in rounded[:3]),
                "  ".join("%s sd %.1f" % (c["short_name"],
                                          self.spread[c["character_id"]])
                          for c in rounded[::-1][:3])))
        y += 27

        # ------------------------------------------------------- highlights
        y = section(y, "ATTRIBUTE HIGHLIGHTS (population means)")
        by_mean = sorted(ALL_ATTRS, key=lambda a: self.stats[a]["mean"])
        by_sd = sorted(ALL_ATTRS, key=lambda a: self.stats[a]["stdev"])
        hi_lines = [
            "Highest means: " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["mean"])
                for a in by_mean[::-1][:5]),
            "Lowest means:  " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["mean"])
                for a in by_mean[:5]),
            "Most varied (stdev): " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["stdev"])
                for a in by_sd[::-1][:5]),
            "Most uniform (stdev): " + "  ".join(
                "%s %.1f" % (a, self.stats[a]["stdev"])
                for a in by_sd[:5]),
        ]
        for line in hi_lines:
            text(20, y, line)
            y += 17
        y += 10

        # ------------------------------------------- per-attribute boxplots
        y = section(y, "ATTRIBUTE DISTRIBUTIONS (box = Q1-median-Q3, "
                       "whiskers = min-max, dot = mean)")
        plot_x = 170
        plot_w = width - plot_x - 265
        stat_x = plot_x + plot_w + 12
        text(plot_x, y, "1", size=7, color="#8a959e")
        for tick in (25, 50, 75, 99):
            text(plot_x + (tick - 1) / 98 * plot_w, y, str(tick),
                 size=7, color="#8a959e", anchor="n")
        y += 14
        for group, attrs in GROUPS:
            text(12, y + 2, group.upper(), size=9, bold=True)
            y += 20
            g_top = y
            for attr in attrs:
                s = self.stats[attr]
                cy = y + 12
                sx = lambda v: plot_x + (v - 1) / 98 * plot_w
                text(16, y + 5, attr, size=8)
                cv.create_line(sx(s["min"]), cy, sx(s["max"]), cy,
                               fill="#9aa4ad")
                for w_end in (s["min"], s["max"]):
                    cv.create_line(sx(w_end), cy - 4, sx(w_end), cy + 4,
                                   fill="#9aa4ad")
                color, _l, _sh = band_for(round(s["median"]))
                cv.create_rectangle(sx(s["q1"]), cy - 6, sx(s["q3"]), cy + 6,
                                    fill=color, outline="#5f6a73")
                cv.create_line(sx(s["median"]), cy - 6,
                               sx(s["median"]), cy + 6,
                               fill="#111", width=2)
                cv.create_oval(sx(s["mean"]) - 3, cy - 3,
                               sx(s["mean"]) + 3, cy + 3,
                               fill="white", outline="#111")
                text(stat_x, y + 5,
                     "m %5.1f sd %4.1f | %2d %s - %2d %s"
                     % (s["mean"], s["stdev"], s["min"], s["min_who"],
                        s["max"], s["max_who"]), size=8)
                y += 24
            for tick in (25, 50, 75):
                tx = plot_x + (tick - 1) / 98 * plot_w
                cv.create_line(tx, g_top - 2, tx, y - 8, fill="#e3e7ea")
                cv.tag_lower(cv.find_all()[-1])
            y += 6

        # ----------------------------------------------------- correlations
        y = section(y, "NOTABLE CORRELATIONS (Pearson r across %d "
                       "characters)" % n)
        text(20, y, "Strongest positive:", bold=True, size=9)
        y += 17
        for r, a, b in self.corr_pos:
            text(28, y, "%-20s <-> %-20s  r = %+.2f" % (a, b, r), size=9)
            y += 16
        text(20, y + 4, "Strongest negative:", bold=True, size=9)
        y += 21
        for r, a, b in self.corr_neg:
            text(28, y, "%-20s <-> %-20s  r = %+.2f" % (a, b, r), size=9)
            y += 16
        y += 12

        # ------------------------------------------------------ band census
        total = n * len(ALL_ATTRS)
        y = section(y, "RATING BAND CENSUS (all %d ratings)" % total)
        census = Counter()
        for c in roster:
            for a in ALL_ATTRS:
                census[band_for(c[a])[1]] += 1
        cbar_x, cbar_w = 340, width - 340 - 30
        biggest = max(census.values()) if census else 1
        for (upper, color, label, short), rng in zip(BANDS, BAND_RANGES):
            cnt = census.get(label, 0)
            cv.create_rectangle(20, y + 2, 34, y + 14, fill=color,
                                outline=color)
            text(42, y + 2, "%-14s %-6s %4d ratings (%4.1f%%)"
                 % (label, rng, cnt, 100 * cnt / total), size=8)
            cv.create_rectangle(cbar_x, y + 3,
                                cbar_x + cnt / biggest * cbar_w, y + 13,
                                fill=color, outline=color)
            y += 18
        y += 10

        cv.configure(scrollregion=(0, 0, width, y + 10))


def main():
    if not CSV_PATH.exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(SCRIPT_NAME, "Roster CSV not found:\n%s"
                             % CSV_PATH)
        return
    roster = load_roster(CSV_PATH)
    app = ToonViewer(roster)
    app.mainloop()


if __name__ == "__main__":
    main()
