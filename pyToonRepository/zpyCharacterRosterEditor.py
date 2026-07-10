#!/usr/bin/env python3
"""
zpyCharacterRosterEditor.py

A standard-library Python 3 GUI for viewing and editing the zpy Universal
Character Master CSV roster.

Naming convention:
    Older scripts may use pyNameOfScript.
    Scripts using the universal zpy character schema should use zpyNameOfScript.

Default CSV discovery:
    The editor looks in the same folder as this script for:
        1. .universal_characters_master.csv
        2. universal_characters_master.csv

Core features:
    - Load a zpy roster CSV.
    - Visualize identity, political orientation, dynamic age, and attributes.
    - Edit identity fields, description, and all 1-99 attributes.
    - Add, duplicate, and delete characters.
    - Validate before saving.
    - Save over the current roster.
    - Save As to a manually chosen file.
    - Save New Version with a timestamped filename.
    - Preserve extra CSV columns not currently known to the zpy schema.

Dependencies:
    Python standard library only: csv, datetime, pathlib, tkinter.
"""

from __future__ import annotations

import csv
import re
import tkinter as tk
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "zpyCharacterRosterEditor"
SCHEMA_NAME = "zpy"
SCHEMA_VERSION = "1.0"
DEFAULT_CSV_CANDIDATES = [
    ".universal_characters_master.csv",
    "universal_characters_master.csv",
]

RELIGION_CHOICES = ["christian", "atheist", "muslim", "hindu", "buddhist"]
SEX_CHOICES = ["", "F", "M", "X", "Other"]
SPECIES_DEFAULT = "human"


IDENTITY_FIELDS = [
    "schema_version",
    "character_id",
    "first_name",
    "last_name",
    "display_name",
    "short_name",
    "sex",
    "birth_year",
    "nationality",
    "religion",
    "left2right",
    "evil2good",
    "species",
    "height_cm",
    "weight_kg",
    "description",
]


PHYSICAL_ATTRS = [
    ("strength", "Strength"),
    ("stamina", "Stamina"),
    ("speed", "Speed"),
    ("agility", "Agility"),
    ("coordination", "Coordination"),
    ("dexterity", "Dexterity"),
    ("balance", "Balance"),
    ("recovery", "Recovery"),
    ("resilience", "Resilience"),
    ("metabolism", "Metabolism"),
    ("lifespan", "Lifespan"),
]

COGNITIVE_ATTRS = [
    ("intelligence", "Intelligence"),
    ("perception", "Perception"),
    ("focus", "Focus"),
    ("memory", "Memory"),
    ("creativity", "Creativity"),
    ("learning", "Learning"),
    ("technical_aptitude", "Technical Aptitude"),
    ("tactical_awareness", "Tactical Awareness"),
]

PSYCHOLOGICAL_ATTRS = [
    ("willpower", "Willpower"),
    ("faith", "Faith"),
    ("courage", "Courage"),
    ("composure", "Composure"),
    ("discipline", "Discipline"),
    ("determination", "Determination"),
    ("adaptability", "Adaptability"),
    ("patience", "Patience"),
    ("risk_assessment", "Risk Assessment"),
]

SOCIAL_ATTRS = [
    ("charisma", "Charisma"),
    ("empathy", "Empathy"),
    ("conversation", "Conversation"),
    ("deception", "Deception"),
    ("loyalty", "Loyalty"),
    ("aggression", "Aggression"),
]

ATTRIBUTE_GROUPS = [
    ("Physical Attributes", PHYSICAL_ATTRS),
    ("Cognitive Attributes", COGNITIVE_ATTRS),
    ("Psychological Attributes", PSYCHOLOGICAL_ATTRS),
    ("Social & Behavioural Attributes", SOCIAL_ATTRS),
]

ATTRIBUTE_FIELDS = [
    attr_key
    for _group_name, attr_list in ATTRIBUTE_GROUPS
    for attr_key, _attr_label in attr_list
]

SCHEMA_FIELDS = IDENTITY_FIELDS + ATTRIBUTE_FIELDS

RATING_FIELDS = ["left2right", "evil2good"] + ATTRIBUTE_FIELDS
MEASUREMENT_FIELDS = ["height_cm", "weight_kg"]
INTEGER_FIELDS = ["birth_year"] + RATING_FIELDS + MEASUREMENT_FIELDS


def get_rating_color(value: int) -> str:
    """Return a colour reflecting the zpy 1-99 rating band."""
    if value <= 9:
        return "#991B1B"
    if value <= 24:
        return "#DC2626"
    if value <= 39:
        return "#D97706"
    if value <= 59:
        return "#4B5563"
    if value <= 74:
        return "#65A30D"
    if value <= 89:
        return "#16A34A"
    if value <= 98:
        return "#0D9488"
    return "#7C3AED"


def get_rating_desc(value: int) -> str:
    """Return a compact textual interpretation of a zpy 1-99 rating."""
    if value <= 9:
        return "Extremely low"
    if value <= 24:
        return "Very low"
    if value <= 39:
        return "Below average"
    if value <= 59:
        return "Average range"
    if value <= 74:
        return "Above average"
    if value <= 89:
        return "Excellent"
    if value <= 98:
        return "Exceptional"
    return "Maximum (99)"


def get_political_label(value: int) -> str:
    """Return a compact political-orientation label for left2right."""
    if value <= 15:
        return "Far Left"
    if value <= 39:
        return "Left-Leaning"
    if value <= 44:
        return "Center-Left"
    if value <= 56:
        return "Political Centre"
    if value <= 61:
        return "Center-Right"
    if value <= 84:
        return "Right-Leaning"
    return "Far Right"


def get_moral_label(value: int) -> str:
    """Return a compact moral-alignment label for evil2good."""
    if value <= 15:
        return "Profoundly Evil"
    if value <= 39:
        return "Evil-Leaning"
    if value <= 44:
        return "Morally Troubled"
    if value <= 56:
        return "Morally Neutral"
    if value <= 61:
        return "Good-Leaning"
    if value <= 84:
        return "Good"
    return "Profoundly Good"


def safe_int(value: object, default: int | None = None) -> int | None:
    """Convert a CSV value to int, returning default on failure."""
    try:
        text = str(value).strip()
        if text == "":
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def clean_cell(value: object) -> str:
    """Normalize a CSV cell to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


class ZpyCharacterRosterEditor:
    """Viewer/editor for a flat zpy Universal Character Master CSV."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} - {SCHEMA_NAME} schema editor")
        self.root.geometry("1280x860")
        self.root.minsize(1120, 680)

        self.current_path: Path | None = None
        self.fieldnames: list[str] = list(SCHEMA_FIELDS)
        self.characters: list[dict[str, str]] = []
        self.last_saved_snapshot: list[dict[str, str]] = []
        self.filtered_indices: list[int] = []
        self.current_index: int | None = None

        self.dirty = False
        self.updating_form = False

        self.form_vars: dict[str, tk.StringVar] = {}
        self.attribute_widgets: dict[str, dict[str, object]] = {}

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self.refresh_roster_list())

        self.sim_year_var = tk.StringVar(value=str(datetime.now().year))
        self.sim_year_var.trace_add("write", lambda *_args: self.update_dynamic_age())

        self.status_var = tk.StringVar(value="Ready.")
        self.selected_char_name = tk.StringVar(value="No Character Selected")

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_initial_data()

    # ---------------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------------

    def build_ui(self) -> None:
        self.build_banner()
        self.build_workspace()
        self.build_status_bar()

    def build_banner(self) -> None:
        banner = tk.Frame(self.root, bg="#1E293B", padx=15, pady=10)
        banner.pack(fill="x", side="top")

        title_frame = tk.Frame(banner, bg="#1E293B")
        title_frame.pack(side="left", fill="y")

        tk.Label(
            title_frame,
            text="zpy SCHEMA COMPLIANT ROSTER EDITOR",
            font=("Arial", 12, "bold"),
            fg="#F8FAFC",
            bg="#1E293B",
        ).pack(anchor="w")

        tk.Label(
            title_frame,
            text=(
                "Notice: scripts using this universal character schema should adopt "
                "the 'zpy' prefix, e.g. zpyCharacterRosterEditor."
            ),
            font=("Arial", 9, "italic"),
            fg="#94A3B8",
            bg="#1E293B",
        ).pack(anchor="w")

        controls = tk.Frame(banner, bg="#1E293B")
        controls.pack(side="right", fill="y")

        tk.Label(
            controls,
            text="Simulation Year:",
            fg="#F8FAFC",
            bg="#1E293B",
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=(0, 5))

        tk.Entry(
            controls,
            textvariable=self.sim_year_var,
            width=6,
            justify="center",
        ).pack(side="left", padx=(0, 12))

        self.make_banner_button(controls, "Open CSV", self.load_from_file).pack(
            side="left", padx=3
        )
        self.make_banner_button(controls, "Save", self.save_current).pack(
            side="left", padx=3
        )
        self.make_banner_button(controls, "Save As", self.save_as).pack(
            side="left", padx=3
        )
        self.make_banner_button(controls, "Save New Version", self.save_new_version).pack(
            side="left", padx=3
        )

    def make_banner_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#0F766E",
            fg="white",
            relief="flat",
            padx=10,
            activebackground="#0D9488",
            activeforeground="white",
        )

    def build_workspace(self) -> None:
        self.paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        sidebar = ttk.Frame(self.paned, padding=10)
        self.paned.add(sidebar, weight=1)

        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, weight=4)

        self.build_sidebar(sidebar)
        self.build_editor_panel(right_frame)

    def build_sidebar(self, sidebar: ttk.Frame) -> None:
        search_frame = ttk.Frame(sidebar)
        search_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(
            search_frame,
            text="Search Roster:",
            font=("Arial", 9, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        ttk.Entry(search_frame, textvariable=self.search_var).pack(fill="x")

        button_frame = ttk.Frame(sidebar)
        button_frame.pack(fill="x", pady=(0, 8))

        ttk.Button(button_frame, text="Add", command=self.add_character).pack(
            side="left", expand=True, fill="x", padx=(0, 3)
        )
        ttk.Button(button_frame, text="Duplicate", command=self.duplicate_character).pack(
            side="left", expand=True, fill="x", padx=3
        )
        ttk.Button(button_frame, text="Delete", command=self.delete_character).pack(
            side="left", expand=True, fill="x", padx=(3, 0)
        )

        self.lbl_roster_count = ttk.Label(
            sidebar,
            text="Roster:",
            font=("Arial", 9, "bold"),
        )
        self.lbl_roster_count.pack(anchor="w")

        list_container = ttk.Frame(sidebar)
        list_container.pack(fill="both", expand=True)

        self.roster_listbox = tk.Listbox(
            list_container,
            selectmode=tk.SINGLE,
            exportselection=False,
            font=("Courier", 10),
        )
        self.roster_listbox.pack(fill="both", expand=True, side="left")
        self.roster_listbox.bind("<<ListboxSelect>>", self.on_list_select)

        scroll_list = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.roster_listbox.yview,
        )
        scroll_list.pack(fill="y", side="right")
        self.roster_listbox.config(yscrollcommand=scroll_list.set)

        lower_buttons = ttk.Frame(sidebar)
        lower_buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(
            lower_buttons,
            text="Validate Roster",
            command=self.validate_and_report,
        ).pack(fill="x", pady=(0, 4))

        ttk.Button(
            lower_buttons,
            text="Revert From Disk",
            command=self.revert_from_disk,
        ).pack(fill="x")

    def build_editor_panel(self, parent: ttk.Frame) -> None:
        header = tk.Frame(parent, bg="#F1F5F9", pady=8, padx=12)
        header.pack(fill="x")

        tk.Label(
            header,
            textvariable=self.selected_char_name,
            font=("Arial", 16, "bold"),
            bg="#F1F5F9",
            fg="#1E293B",
        ).pack(anchor="w")

        tk.Label(
            header,
            text=(
                "Editable root roster. Save overwrites the current CSV; "
                "Save New Version creates a timestamped copy."
            ),
            font=("Arial", 9, "italic"),
            bg="#F1F5F9",
            fg="#475569",
        ).pack(anchor="w")

        scroll_container = ttk.Frame(parent)
        scroll_container.pack(fill="both", expand=True)

        self.canvas_scroll = tk.Canvas(
            scroll_container,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll_v = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=self.canvas_scroll.yview,
        )
        self.scroll_content = ttk.Frame(self.canvas_scroll, padding=10)

        self.scroll_content.bind(
            "<Configure>",
            lambda _event: self.canvas_scroll.configure(
                scrollregion=self.canvas_scroll.bbox("all")
            ),
        )
        self.canvas_window = self.canvas_scroll.create_window(
            (0, 0),
            window=self.scroll_content,
            anchor="nw",
        )
        self.canvas_scroll.bind(
            "<Configure>",
            lambda event: self.canvas_scroll.itemconfig(
                self.canvas_window,
                width=event.width,
            ),
        )

        self.canvas_scroll.configure(yscrollcommand=scroll_v.set)
        self.canvas_scroll.pack(side="left", fill="both", expand=True)
        scroll_v.pack(side="right", fill="y")

        self.build_identity_editor()
        self.build_attributes_grid()

    def build_identity_editor(self) -> None:
        identity_group = ttk.LabelFrame(
            self.scroll_content,
            text="Identity & Dimensions",
            padding=12,
        )
        identity_group.pack(fill="x", pady=(0, 10))

        grid = ttk.Frame(identity_group)
        grid.pack(fill="x")
        for col in range(8):
            grid.columnconfigure(col, weight=1 if col % 2 == 1 else 0)

        field_layout = [
            ("character_id", "Character ID", 0, 0, "entry"),
            ("short_name", "Short Name", 0, 2, "entry"),
            ("schema_version", "Schema Ver.", 0, 4, "entry"),
            ("sex", "Sex", 0, 6, "sex_combo"),
            ("first_name", "First Name", 1, 0, "entry"),
            ("last_name", "Last Name", 1, 2, "entry"),
            ("display_name", "Display Name", 1, 4, "entry"),
            ("species", "Species", 1, 6, "entry"),
            ("birth_year", "Birth Year", 2, 0, "number"),
            ("dynamic_age", "Dynamic Age", 2, 2, "readonly_label"),
            ("nationality", "Nationality", 2, 4, "entry"),
            ("religion", "Religion", 2, 6, "religion_combo"),
            ("height_cm", "Height cm", 3, 0, "number"),
            ("weight_kg", "Weight kg", 3, 2, "number"),
            ("left2right", "Left→Right", 3, 4, "spin_1_99"),
            ("evil2good", "Evil→Good", 3, 6, "spin_1_99"),
        ]

        for field, label_text, row, col, widget_type in field_layout:
            ttk.Label(
                grid,
                text=f"{label_text}:",
                font=("Arial", 9, "bold"),
            ).grid(row=row, column=col, sticky="e", padx=(8, 5), pady=4)

            if widget_type == "readonly_label":
                self.lbl_dynamic_age = ttk.Label(grid, text="—", font=("Arial", 9, "bold"))
                self.lbl_dynamic_age.grid(row=row, column=col + 1, sticky="w", pady=4)
                continue

            var = tk.StringVar()
            self.form_vars[field] = var
            var.trace_add("write", lambda *_args, f=field: self.on_form_change(f))

            if widget_type == "religion_combo":
                widget = ttk.Combobox(
                    grid,
                    textvariable=var,
                    values=RELIGION_CHOICES,
                    state="normal",
                    width=16,
                )
            elif widget_type == "sex_combo":
                widget = ttk.Combobox(
                    grid,
                    textvariable=var,
                    values=SEX_CHOICES,
                    state="normal",
                    width=10,
                )
            elif widget_type == "spin_1_99":
                widget = tk.Spinbox(
                    grid,
                    from_=1,
                    to=99,
                    width=8,
                    textvariable=var,
                    command=lambda f=field: self.on_form_change(f),
                )
            elif widget_type == "number":
                widget = ttk.Entry(grid, textvariable=var, width=14)
            else:
                widget = ttk.Entry(grid, textvariable=var, width=20)

            widget.grid(row=row, column=col + 1, sticky="ew", pady=4)

        ttk.Label(
            grid,
            text="Political Line:",
            font=("Arial", 9, "bold"),
        ).grid(row=4, column=4, sticky="e", padx=(8, 5), pady=6)

        self.pol_canvas = tk.Canvas(
            grid,
            width=200,
            height=20,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#CBD5E1",
        )
        self.pol_canvas.grid(row=4, column=5, columnspan=2, sticky="w", pady=6)

        self.lbl_pol_value = ttk.Label(grid, text="—")
        self.lbl_pol_value.grid(row=4, column=7, sticky="w", pady=6)

        ttk.Label(
            grid,
            text="Moral Line:",
            font=("Arial", 9, "bold"),
        ).grid(row=5, column=4, sticky="e", padx=(8, 5), pady=6)

        self.moral_canvas = tk.Canvas(
            grid,
            width=200,
            height=20,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#CBD5E1",
        )
        self.moral_canvas.grid(row=5, column=5, columnspan=2, sticky="w", pady=6)

        self.lbl_moral_value = ttk.Label(grid, text="—")
        self.lbl_moral_value.grid(row=5, column=7, sticky="w", pady=6)

        desc_group = ttk.LabelFrame(
            self.scroll_content,
            text="Narrative Profile Description",
            padding=10,
        )
        desc_group.pack(fill="x", pady=(0, 10))

        self.description_text = tk.Text(
            desc_group,
            height=4,
            wrap="word",
            font=("Arial", 10),
        )
        self.description_text.pack(fill="x", expand=True)
        self.description_text.bind("<KeyRelease>", self.on_description_change)

    def build_attributes_grid(self) -> None:
        attr_outer = ttk.Frame(self.scroll_content)
        attr_outer.pack(fill="both", expand=True)

        attr_outer.columnconfigure(0, weight=1)
        attr_outer.columnconfigure(1, weight=1)

        placements = {
            "Physical Attributes": (0, 0),
            "Cognitive Attributes": (0, 1),
            "Psychological Attributes": (1, 0),
            "Social & Behavioural Attributes": (1, 1),
        }

        for group_name, attrs in ATTRIBUTE_GROUPS:
            row, col = placements[group_name]
            group = ttk.LabelFrame(attr_outer, text=group_name, padding=8)
            group.grid(
                row=row,
                column=col,
                sticky="nsew",
                padx=(0, 5) if col == 0 else (5, 0),
                pady=5,
            )
            self.build_attribute_list(group, attrs)

    def build_attribute_list(
        self,
        parent: ttk.LabelFrame,
        attributes: list[tuple[str, str]],
    ) -> None:
        for attr_key, attr_label in attributes:
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=2)

            ttk.Label(row, text=attr_label, width=19, anchor="w").pack(
                side="left",
                padx=(0, 5),
            )

            canvas = tk.Canvas(
                row,
                width=120,
                height=14,
                borderwidth=0,
                highlightthickness=1,
                highlightbackground="#E2E8F0",
            )
            canvas.pack(side="left", padx=(0, 8))

            var = tk.StringVar()
            self.form_vars[attr_key] = var
            var.trace_add("write", lambda *_args, f=attr_key: self.on_form_change(f))

            spinbox = tk.Spinbox(
                row,
                from_=1,
                to=99,
                width=4,
                textvariable=var,
                justify="right",
                command=lambda f=attr_key: self.on_form_change(f),
            )
            spinbox.pack(side="left", padx=(0, 5))

            desc_label = ttk.Label(
                row,
                text="",
                width=15,
                anchor="w",
                font=("Arial", 8, "italic"),
            )
            desc_label.pack(side="left")

            self.attribute_widgets[attr_key] = {
                "canvas": canvas,
                "desc_label": desc_label,
            }

    def build_status_bar(self) -> None:
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=(5, 2),
        )
        status_bar.pack(side="bottom", fill="x")

    # ---------------------------------------------------------------------
    # Loading / saving
    # ---------------------------------------------------------------------

    def load_initial_data(self) -> None:
        script_dir = Path(__file__).resolve().parent
        for candidate_name in DEFAULT_CSV_CANDIDATES:
            candidate = script_dir / candidate_name
            if candidate.exists():
                self.load_csv(candidate, ask_if_dirty=False)
                return

        self.characters = []
        self.last_saved_snapshot = []
        self.current_path = None
        self.fieldnames = list(SCHEMA_FIELDS)
        self.refresh_roster_list()
        self.status_var.set(
            "No roster loaded. Place .universal_characters_master.csv or "
            "universal_characters_master.csv beside this script, or use Open CSV."
        )

    def load_from_file(self) -> None:
        if not self.confirm_discard_unsaved_changes():
            return

        file_path = filedialog.askopenfilename(
            title="Open Universal Character Master CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        self.load_csv(Path(file_path), ask_if_dirty=False)

    def load_csv(self, path: Path, ask_if_dirty: bool = True) -> None:
        if ask_if_dirty and not self.confirm_discard_unsaved_changes():
            return

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                loaded_headers = list(reader.fieldnames or [])
                rows = list(reader)
        except Exception as exc:
            messagebox.showerror("Error Reading CSV", f"Could not read file:\n{exc}")
            return

        if not loaded_headers:
            messagebox.showerror("Invalid CSV", "The file has no header row.")
            return

        self.fieldnames = self.merge_fieldnames(loaded_headers)
        self.characters = [self.normalize_record(row) for row in rows]
        self.last_saved_snapshot = deepcopy(self.characters)
        self.current_path = path
        self.current_index = None
        self.dirty = False

        self.refresh_roster_list()
        errors = self.validate_roster()
        if errors:
            self.status_var.set(
                f"Loaded {len(self.characters)} characters from {path.name} with "
                f"{len(errors)} validation issue(s)."
            )
            self.show_validation_errors(errors, title="Loaded with validation issues")
        else:
            self.status_var.set(
                f"Loaded {len(self.characters)} zpy character(s) from {path}."
            )

        self.update_window_title()

    def merge_fieldnames(self, loaded_headers: list[str]) -> list[str]:
        cleaned = [header.strip() for header in loaded_headers if header and header.strip()]
        extras = [header for header in cleaned if header not in SCHEMA_FIELDS]
        return list(SCHEMA_FIELDS) + extras

    def normalize_record(self, row: dict[str, object]) -> dict[str, str]:
        record: dict[str, str] = {}
        for field in self.fieldnames:
            record[field] = clean_cell(row.get(field, ""))
        return record

    def save_current(self) -> None:
        if self.current_path is None:
            self.save_as()
            return
        self.save_to_path(self.current_path)

    def save_as(self) -> None:
        initial_dir = (
            self.current_path.parent
            if self.current_path is not None
            else Path(__file__).resolve().parent
        )
        file_path = filedialog.asksaveasfilename(
            title="Save zpy roster CSV as",
            defaultextension=".csv",
            initialdir=str(initial_dir),
            initialfile="universal_characters_master.csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return
        self.save_to_path(Path(file_path))

    def save_new_version(self) -> None:
        base_dir = (
            self.current_path.parent
            if self.current_path is not None
            else Path(__file__).resolve().parent
        )
        base_name = (
            self.current_path.stem
            if self.current_path is not None
            else "universal_characters_master"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_path = base_dir / f"{base_name}_{timestamp}.csv"
        self.save_to_path(version_path)

    def save_to_path(self, path: Path) -> None:
        self.collect_current_form_edits()

        errors = self.validate_roster()
        if errors:
            self.show_validation_errors(errors, title="Cannot save: validation failed")
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=self.fieldnames,
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                writer.writeheader()
                for character in self.characters:
                    writer.writerow(self.prepare_record_for_save(character))
        except Exception as exc:
            messagebox.showerror("Save failed", f"Could not save file:\n{exc}")
            return

        self.current_path = path
        self.last_saved_snapshot = deepcopy(self.characters)
        self.dirty = False
        self.update_window_title()
        self.status_var.set(f"Saved {len(self.characters)} character(s) to {path}.")
        messagebox.showinfo("Saved", f"Roster saved successfully:\n{path}")

    def prepare_record_for_save(self, record: dict[str, str]) -> dict[str, str]:
        output = {field: clean_cell(record.get(field, "")) for field in self.fieldnames}

        # Normalize schema version for blank rows while preserving explicit user edits.
        if not output.get("schema_version"):
            output["schema_version"] = SCHEMA_VERSION

        # Ensure numeric values save as integer-looking strings where possible.
        for field in INTEGER_FIELDS:
            value = safe_int(output.get(field), None)
            if value is not None:
                output[field] = str(value)

        return output

    def revert_from_disk(self) -> None:
        if self.current_path is None or not self.current_path.exists():
            if self.last_saved_snapshot:
                if not messagebox.askyesno(
                    "Revert unsaved changes",
                    "No disk file is available. Revert to the last saved in-memory snapshot?",
                ):
                    return
                self.characters = deepcopy(self.last_saved_snapshot)
                self.dirty = False
                self.refresh_roster_list()
                self.update_window_title()
            else:
                messagebox.showinfo("Nothing to revert", "No saved roster is available.")
            return

        if not messagebox.askyesno(
            "Revert from disk",
            "Discard unsaved changes and reload the current CSV from disk?",
        ):
            return

        self.load_csv(self.current_path, ask_if_dirty=False)

    # ---------------------------------------------------------------------
    # Roster editing
    # ---------------------------------------------------------------------

    def add_character(self) -> None:
        new_id = self.next_character_id()
        record = {field: "" for field in self.fieldnames}
        record.update(
            {
                "schema_version": SCHEMA_VERSION,
                "character_id": new_id,
                "first_name": "New",
                "last_name": "Character",
                "display_name": "New Character",
                "short_name": new_id[-3:],
                "sex": "",
                "birth_year": "2000",
                "nationality": "",
                "religion": "atheist",
                "left2right": "50",
                "evil2good": "50",
                "species": SPECIES_DEFAULT,
                "height_cm": "170",
                "weight_kg": "70",
                "description": "New zpy character.",
            }
        )
        for attribute in ATTRIBUTE_FIELDS:
            record[attribute] = "50"

        self.characters.append(record)
        self.current_index = len(self.characters) - 1
        self.mark_dirty("Added new character.")
        self.refresh_roster_list(select_index=self.current_index)

    def duplicate_character(self) -> None:
        if self.current_index is None:
            messagebox.showinfo("No character selected", "Select a character to duplicate.")
            return

        source = deepcopy(self.characters[self.current_index])
        new_id = self.next_character_id()
        source["character_id"] = new_id
        source["display_name"] = f"{source.get('display_name', 'Character')} Copy"
        source["short_name"] = new_id[-3:]
        self.characters.append(source)
        self.current_index = len(self.characters) - 1
        self.mark_dirty("Duplicated character.")
        self.refresh_roster_list(select_index=self.current_index)

    def delete_character(self) -> None:
        if self.current_index is None:
            messagebox.showinfo("No character selected", "Select a character to delete.")
            return

        character = self.characters[self.current_index]
        label = character.get("display_name") or character.get("character_id") or "this character"
        if not messagebox.askyesno(
            "Delete character",
            f"Delete {label} from the roster?\n\nThis is not final until you save.",
        ):
            return

        del self.characters[self.current_index]
        self.current_index = None
        self.mark_dirty("Deleted character.")
        self.refresh_roster_list()

    def next_character_id(self) -> str:
        max_seen = 0
        pattern = re.compile(r"^CHR(\d+)$", re.IGNORECASE)
        for character in self.characters:
            match = pattern.match(clean_cell(character.get("character_id", "")))
            if match:
                max_seen = max(max_seen, int(match.group(1)))
        return f"CHR{max_seen + 1:04d}"

    # ---------------------------------------------------------------------
    # Form syncing
    # ---------------------------------------------------------------------

    def on_list_select(self, _event) -> None:
        selection = self.roster_listbox.curselection()
        if not selection:
            return

        filtered_position = selection[0]
        if filtered_position >= len(self.filtered_indices):
            return

        self.collect_current_form_edits()
        self.current_index = self.filtered_indices[filtered_position]
        self.display_current_character()

    def display_current_character(self) -> None:
        if self.current_index is None or self.current_index >= len(self.characters):
            self.clear_fields()
            return

        character = self.characters[self.current_index]
        self.updating_form = True

        try:
            for field, var in self.form_vars.items():
                var.set(clean_cell(character.get(field, "")))

            self.description_text.delete("1.0", tk.END)
            self.description_text.insert("1.0", clean_cell(character.get("description", "")))
        finally:
            self.updating_form = False

        display_name = character.get("display_name") or "Unnamed"
        short_name = character.get("short_name") or "—"
        char_id = character.get("character_id") or "NO_ID"
        self.selected_char_name.set(f"{display_name} [{short_name}] — {char_id}")

        self.update_dynamic_age()
        self.draw_political_gradient(safe_int(character.get("left2right"), None))
        self.draw_moral_gradient(safe_int(character.get("evil2good"), None))

        for attr_key in ATTRIBUTE_FIELDS:
            self.draw_attribute_row(attr_key, safe_int(character.get(attr_key), None))

    def clear_fields(self) -> None:
        self.updating_form = True
        try:
            for var in self.form_vars.values():
                var.set("")
            self.description_text.delete("1.0", tk.END)
        finally:
            self.updating_form = False

        self.selected_char_name.set("No Character Selected")
        self.lbl_dynamic_age.config(text="—")
        self.pol_canvas.delete("all")
        self.lbl_pol_value.config(text="—")
        self.moral_canvas.delete("all")
        self.lbl_moral_value.config(text="—")
        for attr_key in ATTRIBUTE_FIELDS:
            self.draw_attribute_row(attr_key, None)

    def collect_current_form_edits(self) -> None:
        if self.current_index is None or self.current_index >= len(self.characters):
            return

        record = self.characters[self.current_index]
        for field, var in self.form_vars.items():
            record[field] = clean_cell(var.get())
        record["description"] = self.description_text.get("1.0", "end-1c").strip()

    def on_form_change(self, field: str) -> None:
        if self.updating_form:
            return
        if self.current_index is None or self.current_index >= len(self.characters):
            return

        value = clean_cell(self.form_vars[field].get())
        self.characters[self.current_index][field] = value

        if field == "left2right":
            self.draw_political_gradient(safe_int(value, None))
        elif field == "evil2good":
            self.draw_moral_gradient(safe_int(value, None))
        elif field in ATTRIBUTE_FIELDS:
            self.draw_attribute_row(field, safe_int(value, None))
        elif field == "birth_year":
            self.update_dynamic_age()

        if field in {
            "character_id",
            "display_name",
            "short_name",
            "first_name",
            "last_name",
            "nationality",
            "religion",
        }:
            self.update_current_header()
            self.refresh_roster_list(select_index=self.current_index, preserve_scroll=True)

        self.mark_dirty()

    def on_description_change(self, _event) -> None:
        if self.updating_form:
            return
        if self.current_index is None or self.current_index >= len(self.characters):
            return

        self.characters[self.current_index]["description"] = (
            self.description_text.get("1.0", "end-1c").strip()
        )
        self.mark_dirty()

    def update_current_header(self) -> None:
        if self.current_index is None:
            self.selected_char_name.set("No Character Selected")
            return
        character = self.characters[self.current_index]
        display_name = character.get("display_name") or "Unnamed"
        short_name = character.get("short_name") or "—"
        char_id = character.get("character_id") or "NO_ID"
        self.selected_char_name.set(f"{display_name} [{short_name}] — {char_id}")

    def update_dynamic_age(self) -> None:
        if self.current_index is None or self.current_index >= len(self.characters):
            self.lbl_dynamic_age.config(text="—")
            return

        character = self.characters[self.current_index]
        birth_year = safe_int(character.get("birth_year"), None)
        sim_year = safe_int(self.sim_year_var.get(), None)

        if birth_year is None or sim_year is None:
            self.lbl_dynamic_age.config(text="Invalid")
            return

        age = sim_year - birth_year
        if age < 0:
            self.lbl_dynamic_age.config(text=f"{age} yrs (future birth)")
        else:
            self.lbl_dynamic_age.config(text=f"{age} yrs")

    # ---------------------------------------------------------------------
    # Visualization
    # ---------------------------------------------------------------------

    def draw_political_gradient(self, value: int | None) -> None:
        self.pol_canvas.delete("all")
        if value is None:
            self.pol_canvas.create_rectangle(0, 0, 200, 20, fill="#E2E8F0", outline="")
            self.lbl_pol_value.config(text="—")
            return

        value = max(1, min(99, int(value)))
        self.pol_canvas.create_rectangle(0, 0, 75, 20, fill="#3B82F6", outline="")
        self.pol_canvas.create_rectangle(75, 0, 125, 20, fill="#9CA3AF", outline="")
        self.pol_canvas.create_rectangle(125, 0, 200, 20, fill="#EF4444", outline="")
        self.pol_canvas.create_line(100, 0, 100, 20, fill="#FFFFFF", width=2)

        x_pos = ((value - 1) / 98.0) * 200
        self.pol_canvas.create_polygon(
            x_pos - 5,
            0,
            x_pos + 5,
            0,
            x_pos,
            8,
            fill="#1E293B",
        )
        self.pol_canvas.create_polygon(
            x_pos - 5,
            20,
            x_pos + 5,
            20,
            x_pos,
            12,
            fill="#1E293B",
        )
        self.lbl_pol_value.config(text=f"{value} ({get_political_label(value)})")

    def draw_moral_gradient(self, value: int | None) -> None:
        """Draw the evil-to-good moral alignment gradient for evil2good."""
        self.moral_canvas.delete("all")
        if value is None:
            self.moral_canvas.create_rectangle(0, 0, 200, 20, fill="#E2E8F0", outline="")
            self.lbl_moral_value.config(text="—")
            return

        value = max(1, min(99, int(value)))

        # Left = evil, centre = neutral, right = good.
        self.moral_canvas.create_rectangle(0, 0, 75, 20, fill="#111827", outline="")
        self.moral_canvas.create_rectangle(75, 0, 125, 20, fill="#9CA3AF", outline="")
        self.moral_canvas.create_rectangle(125, 0, 200, 20, fill="#22C55E", outline="")
        self.moral_canvas.create_line(100, 0, 100, 20, fill="#FFFFFF", width=2)

        x_pos = ((value - 1) / 98.0) * 200
        self.moral_canvas.create_polygon(
            x_pos - 5,
            0,
            x_pos + 5,
            0,
            x_pos,
            8,
            fill="#F8FAFC",
            outline="#1E293B",
        )
        self.moral_canvas.create_polygon(
            x_pos - 5,
            20,
            x_pos + 5,
            20,
            x_pos,
            12,
            fill="#F8FAFC",
            outline="#1E293B",
        )
        self.lbl_moral_value.config(text=f"{value} ({get_moral_label(value)})")

    def draw_attribute_row(self, attr_key: str, value: int | None) -> None:
        widgets = self.attribute_widgets.get(attr_key)
        if not widgets:
            return

        canvas: tk.Canvas = widgets["canvas"]  # type: ignore[assignment]
        desc_label: ttk.Label = widgets["desc_label"]  # type: ignore[assignment]

        canvas.delete("all")

        if value is None:
            canvas.create_rectangle(0, 0, 120, 14, fill="#E2E8F0", outline="")
            desc_label.config(text="N/A", foreground="#94A3B8")
            return

        value = max(1, min(99, int(value)))
        color = get_rating_color(value)
        percent_width = (value / 99.0) * 120

        canvas.create_rectangle(0, 0, 120, 14, fill="#F1F5F9", outline="")
        canvas.create_rectangle(0, 0, percent_width, 14, fill=color, outline="")
        desc_label.config(text=get_rating_desc(value), foreground=color)

    # ---------------------------------------------------------------------
    # Roster list and search
    # ---------------------------------------------------------------------

    def refresh_roster_list(
        self,
        select_index: int | None = None,
        preserve_scroll: bool = False,
    ) -> None:
        current_yview = self.roster_listbox.yview() if preserve_scroll else None

        search_term = self.search_var.get().strip().lower()
        self.roster_listbox.delete(0, tk.END)
        self.filtered_indices.clear()

        for index, character in enumerate(self.characters):
            searchable = " ".join(
                [
                    character.get("character_id", ""),
                    character.get("display_name", ""),
                    character.get("short_name", ""),
                    character.get("nationality", ""),
                    character.get("religion", ""),
                    character.get("species", ""),
                    character.get("description", ""),
                ]
            ).lower()

            if search_term and search_term not in searchable:
                continue

            self.filtered_indices.append(index)
            display_string = (
                f"{character.get('character_id', '???'):<7} - "
                f"{character.get('display_name', 'Unknown'):<24.24} "
                f"({character.get('short_name', '???'):<3})"
            )
            self.roster_listbox.insert(tk.END, display_string)

        self.lbl_roster_count.config(text=f"Roster Match ({len(self.filtered_indices)}):")

        target_index = select_index
        if target_index is None:
            target_index = self.current_index

        if target_index in self.filtered_indices:
            filtered_position = self.filtered_indices.index(target_index)
            self.roster_listbox.selection_clear(0, tk.END)
            self.roster_listbox.selection_set(filtered_position)
            self.roster_listbox.activate(filtered_position)
            self.current_index = target_index
            self.display_current_character()
        elif self.filtered_indices:
            self.roster_listbox.selection_clear(0, tk.END)
            self.roster_listbox.selection_set(0)
            self.roster_listbox.activate(0)
            self.current_index = self.filtered_indices[0]
            self.display_current_character()
        else:
            self.current_index = None
            self.clear_fields()

        if preserve_scroll and current_yview:
            self.roster_listbox.yview_moveto(current_yview[0])

    # ---------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------

    def validate_and_report(self) -> None:
        self.collect_current_form_edits()
        errors = self.validate_roster()
        if errors:
            self.show_validation_errors(errors, title="Roster validation issues")
        else:
            messagebox.showinfo("Validation passed", "No zpy schema validation errors found.")

    def validate_roster(self) -> list[str]:
        errors: list[str] = []
        ids_seen: dict[str, int] = {}

        for row_index, character in enumerate(self.characters, start=2):
            label = character.get("character_id", f"row {row_index}") or f"row {row_index}"

            char_id = clean_cell(character.get("character_id", ""))
            if not char_id:
                errors.append(f"Row {row_index}: character_id is required.")
            elif char_id in ids_seen:
                errors.append(
                    f"Row {row_index}: duplicate character_id {char_id!r}; "
                    f"first seen on row {ids_seen[char_id]}."
                )
            else:
                ids_seen[char_id] = row_index

            for required_field in ["schema_version", "display_name", "birth_year"]:
                if not clean_cell(character.get(required_field, "")):
                    errors.append(f"{label}: {required_field} is required.")

            religion = clean_cell(character.get("religion", "")).lower()
            if religion and religion not in RELIGION_CHOICES:
                errors.append(
                    f"{label}: religion must be one of "
                    f"{', '.join(RELIGION_CHOICES)}; got {religion!r}."
                )

            for field in RATING_FIELDS:
                value = safe_int(character.get(field), None)
                if value is None:
                    errors.append(f"{label}: {field} must be an integer from 1 to 99.")
                elif not 1 <= value <= 99:
                    errors.append(f"{label}: {field}={value} outside allowed range 1-99.")

            birth_year = safe_int(character.get("birth_year"), None)
            if birth_year is None:
                errors.append(f"{label}: birth_year must be an integer.")
            elif not 1 <= birth_year <= 9999:
                errors.append(f"{label}: birth_year={birth_year} is outside 1-9999.")

            for field in MEASUREMENT_FIELDS:
                value = safe_int(character.get(field), None)
                if value is None:
                    errors.append(f"{label}: {field} must be an integer measurement.")
                elif value <= 0:
                    errors.append(f"{label}: {field} must be greater than zero.")

        return errors

    def show_validation_errors(self, errors: list[str], title: str) -> None:
        max_shown = 40
        text = "\n".join(errors[:max_shown])
        if len(errors) > max_shown:
            text += f"\n\n...and {len(errors) - max_shown} more issue(s)."

        messagebox.showerror(title, text)

    # ---------------------------------------------------------------------
    # Dirty state and window lifecycle
    # ---------------------------------------------------------------------

    def mark_dirty(self, message: str | None = None) -> None:
        if not self.dirty:
            self.dirty = True
            self.update_window_title()
        if message:
            self.status_var.set(message)

    def update_window_title(self) -> None:
        dirty_marker = "*" if self.dirty else ""
        path_text = str(self.current_path) if self.current_path else "No file loaded"
        self.root.title(f"{dirty_marker}{APP_NAME} - {SCHEMA_NAME} schema editor - {path_text}")

    def confirm_discard_unsaved_changes(self) -> bool:
        if not self.dirty:
            return True

        return messagebox.askyesno(
            "Unsaved changes",
            "You have unsaved roster edits. Discard them and continue?",
        )

    def on_close(self) -> None:
        if self.dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save changes before closing?",
            )
            if choice is None:
                return
            if choice is True:
                self.save_current()
                if self.dirty:
                    return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = ZpyCharacterRosterEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
