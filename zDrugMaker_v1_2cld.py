"""
zDrugMaker v1.2
Leo's Dilution Calculator and Volume Conversion Applet

Changes from v1.1:
- Input validation with per-field error messages (no more silent crashes
  on zero/empty values, ZeroDivisionError handled)
- Dilution sanity checks (final conc must be lower than stock, warns when
  there is not enough stock solution)
- BEW values stored without duplicates, shown in a searchable table
  (double-click a row to fill the compound name + BEW fields)
- Data files anchored next to the script instead of the current directory
- Export to .txt or .csv, filename sanitized
- Copy / Clear buttons on every tab, Clear Output button
- Window size and last compound remembered between sessions
- Refactored tab construction (one builder for all calculation tabs)
- Visual refresh using only ttk styling (no external libraries)

Requires: Python 3.8+ (standard library only)
"""

import csv
import json
import os
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ---------------------------------------------------------------- constants

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BEW_FILE = os.path.join(SCRIPT_DIR, "zDrugMakerBEW.txt")
LOG_FILE = os.path.join(SCRIPT_DIR, "zDrugMakerLog.txt")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "zDrugMakerSettings.json")

# (label, ml per kg) - edit here to change the standard dosing volumes
VOLUME_FACTORS = [
    ("Rats", 1),
    ("Oral", 5),
    ("Mice", 10),
]

# ------------------------------------------------------------------ colors

COL_BG = "#eef1f5"        # window background
COL_PANEL = "#ffffff"     # input panels / result boxes
COL_HEADER = "#1f3a5f"    # header bar
COL_HEADER_TXT = "#ffffff"
COL_ACCENT = "#2e6fb7"    # buttons / highlights
COL_ACCENT_DARK = "#24588f"
COL_TEXT = "#1c2733"
COL_SUBTLE = "#5c6b7a"
COL_RESULT_BG = "#f8fafc"

FONT_BASE = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_SUB = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 10)


class InputError(Exception):
    """Raised when a user-supplied value is missing or invalid."""


# -------------------------------------------------------------------- app

class ZDrugMakerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Leo's Dilution Calculator and Volume Conversion Applet v1.2")
        self.minsize(900, 620)
        self.configure(bg=COL_BG)

        self.settings = self._load_settings()
        self.geometry(self.settings.get("geometry", "1024x768"))

        self.records = []          # structured history for CSV export
        self.bew_data = {}         # compound -> (bew, date_str)

        self._setup_style()
        self._create_header()
        self._create_compound_frame()

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=12, pady=(6, 4))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._create_estimate_tab()
        self._create_vehicle_tab()
        self._create_dilution_tab()
        self._create_bew_tab()
        self._create_output_tab()

        self._create_footer()

        self._load_bew_file()
        self._refresh_bew_tree()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------- styling

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=COL_BG, foreground=COL_TEXT,
                        font=FONT_BASE)
        style.configure("TFrame", background=COL_BG)
        style.configure("Panel.TFrame", background=COL_PANEL)
        style.configure("TLabel", background=COL_BG, foreground=COL_TEXT)
        style.configure("Panel.TLabel", background=COL_PANEL)
        style.configure("Subtle.TLabel", background=COL_BG,
                        foreground=COL_SUBTLE, font=FONT_SUB)

        style.configure("TNotebook", background=COL_BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 7), font=FONT_BASE)
        style.map("TNotebook.Tab",
                  background=[("selected", COL_PANEL), ("!selected", "#d8dee6")],
                  foreground=[("selected", COL_ACCENT_DARK)])

        style.configure("TButton", padding=(12, 5))
        style.configure("Accent.TButton", background=COL_ACCENT,
                        foreground="#ffffff", padding=(16, 6),
                        font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton",
                  background=[("active", COL_ACCENT_DARK),
                              ("pressed", COL_ACCENT_DARK)])

        style.configure("TEntry", padding=4)
        style.configure("Treeview", background=COL_PANEL,
                        fieldbackground=COL_PANEL, rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _create_header(self):
        header = tk.Frame(self, bg=COL_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="zDrugMaker", bg=COL_HEADER, fg=COL_HEADER_TXT,
                 font=FONT_HEADER).grid(row=0, column=0, sticky="w",
                                        padx=16, pady=(10, 0))
        tk.Label(header,
                 text="Dilution calculator and volume conversion  ·  v1.2",
                 bg=COL_HEADER, fg="#b9c8dc", font=FONT_SUB
                 ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

    def _create_compound_frame(self):
        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 0))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Compound name:").grid(row=0, column=0, sticky="w")
        self.compound_name = tk.StringVar(
            value=self.settings.get("last_compound", ""))
        ttk.Entry(frame, textvariable=self.compound_name).grid(
            row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(frame, text="Comments:").grid(row=1, column=0, sticky="nw",
                                                pady=(6, 0))
        self.comments = tk.Text(frame, height=2, wrap=tk.WORD, font=FONT_BASE,
                                relief="solid", borderwidth=1,
                                highlightthickness=0)
        self.comments.grid(row=1, column=1, sticky="ew", padx=(6, 0),
                           pady=(6, 0))

    def _create_footer(self):
        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        footer.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(footer, textvariable=self.status_var,
                  style="Subtle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Close", command=self._on_close).grid(
            row=0, column=1, sticky="e")

    # -------------------------------------------------------- tab builder

    def _build_calc_tab(self, title, fields, command):
        """Create a calculation tab.

        fields: list of (label, key) tuples.
        Returns (vars_dict, result_text_widget).
        """
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text=title)
        tab.columnconfigure(2, weight=1)
        tab.rowconfigure(0, weight=1)

        inputs = ttk.Frame(tab)
        inputs.grid(row=0, column=0, sticky="new")
        inputs.columnconfigure(1, weight=1)

        variables = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(inputs, text=label).grid(row=i, column=0, sticky="e",
                                               padx=(0, 6), pady=4)
            var = tk.StringVar()
            variables[key] = (var, label)
            entry = ttk.Entry(inputs, textvariable=var, width=14)
            entry.grid(row=i, column=1, sticky="ew", pady=4)
            if i == 0:
                first_entry = entry
        first_entry.focus_set()

        buttons = ttk.Frame(inputs)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(buttons, text="Calculate", style="Accent.TButton",
                   command=command).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Clear",
                   command=lambda: self._clear_fields(variables)
                   ).pack(side="left")

        result = tk.Text(tab, wrap=tk.WORD, font=FONT_MONO, bg=COL_RESULT_BG,
                         relief="solid", borderwidth=1, highlightthickness=0,
                         padx=10, pady=8, state="disabled")
        result.grid(row=0, column=2, sticky="nsew", padx=(14, 0))

        ttk.Button(tab, text="Copy result",
                   command=lambda: self._copy_result(result)).grid(
            row=1, column=2, sticky="e", pady=(6, 0))

        return variables, result

    @staticmethod
    def _clear_fields(variables):
        for var, _label in variables.values():
            var.set("")

    def _copy_result(self, widget):
        text = widget.get("1.0", tk.END).strip()
        if not text:
            self.status_var.set("Nothing to copy.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Result copied to clipboard.")

    @staticmethod
    def _set_result(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state="disabled")

    # ---------------------------------------------------------- validation

    @staticmethod
    def _parse_float(variables, key, positive=True):
        var, label = variables[key]
        raw = var.get().strip()
        if not raw:
            raise InputError(f"'{label}' is empty.")
        try:
            value = float(raw)
        except ValueError:
            raise InputError(f"'{label}' must be a number (got '{raw}').")
        if positive and value <= 0:
            raise InputError(f"'{label}' must be greater than zero.")
        return value

    # ---------------------------------------------------------------- tabs

    def _create_estimate_tab(self):
        fields = [("BEW", "bew"),
                  ("Dose (mg/kg)", "dose"),
                  ("Avg body weight (g)", "avgbw"),
                  ("Number of animals", "animals"),
                  ("Number of trials", "trials")]
        self.est_vars, self.est_result = self._build_calc_tab(
            "Estimate Drug Amount", fields, self.estimate_drug_amount)

    def _create_vehicle_tab(self):
        fields = [("BEW", "bew"),
                  ("Dose (mg/kg)", "dose"),
                  ("Drug weighed (mg)", "amt")]
        self.veh_vars, self.veh_result = self._build_calc_tab(
            "Calculate Vehicle Amount", fields, self.calculate_vehicle_amount)

    def _create_dilution_tab(self):
        fields = [("Volume of starting solution (ml)", "vol_stock"),
                  ("Starting concentration (mg/ml)", "conc_stock"),
                  ("Final concentration (mg/ml)", "conc_final"),
                  ("Volume of new solution (ml)", "vol_final")]
        self.dil_vars, self.dil_result = self._build_calc_tab(
            "Perform Dilution", fields, self.perform_dilution)

    def _create_bew_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="BEW Values")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Search:").grid(row=0, column=0, padx=(0, 6))
        self.bew_search = tk.StringVar()
        self.bew_search.trace_add("write",
                                  lambda *a: self._refresh_bew_tree())
        ttk.Entry(top, textvariable=self.bew_search).grid(row=0, column=1,
                                                          sticky="ew")
        ttk.Label(tab, text="Double-click a row to fill the compound name "
                            "and BEW fields.",
                  style="Subtle.TLabel").grid(row=2, column=0, sticky="w",
                                              pady=(6, 0))

        cols = ("compound", "bew", "date")
        self.bew_tree = ttk.Treeview(tab, columns=cols, show="headings")
        self.bew_tree.heading("compound", text="Compound")
        self.bew_tree.heading("bew", text="BEW")
        self.bew_tree.heading("date", text="Last used")
        self.bew_tree.column("compound", width=280)
        self.bew_tree.column("bew", width=100, anchor="center")
        self.bew_tree.column("date", width=140, anchor="center")
        self.bew_tree.grid(row=1, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(tab, orient="vertical",
                               command=self.bew_tree.yview)
        self.bew_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=1, column=1, sticky="ns")

        self.bew_tree.bind("<Double-1>", self._on_bew_double_click)

    def _create_output_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Output")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        self.output_text = tk.Text(tab, wrap=tk.WORD, font=FONT_MONO,
                                   bg=COL_RESULT_BG, relief="solid",
                                   borderwidth=1, highlightthickness=0,
                                   padx=10, pady=8)
        self.output_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(tab, orient="vertical",
                               command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        buttons = ttk.Frame(tab)
        buttons.grid(row=1, column=0, pady=(10, 0))
        ttk.Button(buttons, text="Export...", style="Accent.TButton",
                   command=self.export_output).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Clear output",
                   command=self._clear_output).pack(side="left")

    def _clear_output(self):
        if messagebox.askyesno("Clear output",
                               "Clear the output history shown in this tab?\n"
                               "(The log file on disk is not affected.)"):
            self.output_text.delete("1.0", tk.END)
            self.records.clear()

    # -------------------------------------------------------- calculations

    def estimate_drug_amount(self):
        try:
            bew = self._parse_float(self.est_vars, "bew")
            dose = self._parse_float(self.est_vars, "dose")
            avgbw = self._parse_float(self.est_vars, "avgbw")
            animals = self._parse_float(self.est_vars, "animals")
            trials = self._parse_float(self.est_vars, "trials")
        except InputError as exc:
            messagebox.showerror("Input error", str(exc))
            return

        drugtot = bew * dose * 0.001 * avgbw * animals * trials

        lines = [
            "Estimated Drug Amount and Volumes",
            "=" * 40,
            f"Compound: {self.compound_name.get()}",
            f"BEW: {bew:.3g}",
            f"Dose: {dose:.3g} mg/kg",
            f"Animals x trials: {animals:.3g} x {trials:.3g}",
            "=" * 40,
            f"Drug amount needed: {drugtot:.3g} mg",
            "=" * 40,
            "Volumes:",
        ]
        for name, factor in VOLUME_FACTORS:
            vol = factor * 0.001 * avgbw * animals * trials
            lines.append(f"- {name} ({factor} ml/kg): {vol:.3g} ml")
        lines.append("=" * 40)
        result = "\n".join(lines) + "\n"

        self._set_result(self.est_result, result)
        self._record("Estimate Drug Amount", result)
        self._add_bew(self.compound_name.get(), bew)

    def calculate_vehicle_amount(self):
        try:
            bew = self._parse_float(self.veh_vars, "bew")
            dose = self._parse_float(self.veh_vars, "dose")
            amt = self._parse_float(self.veh_vars, "amt")
        except InputError as exc:
            messagebox.showerror("Input error", str(exc))
            return

        lines = [
            "Vehicle Amounts for Different Concentrations",
            "=" * 50,
            f"Compound: {self.compound_name.get()}",
            f"BEW: {bew:.3g}",
            f"Dose: {dose:.3g} mg/kg",
            f"Drug weighed: {amt:.3g} mg",
            "=" * 50,
        ]
        for name, factor in VOLUME_FACTORS:
            vol = (factor * amt) / (dose * bew)
            lines.append(f"Add {vol:.3g} ml of vehicle to your {amt:.3g} mg "
                         f"of drug")
            lines.append(f"to produce a {factor} ml/kg solution "
                         f"({name})\n")
        lines.append("=" * 50)
        result = "\n".join(lines) + "\n"

        self._set_result(self.veh_result, result)
        self._record("Calculate Vehicle Amount", result)
        self._add_bew(self.compound_name.get(), bew)

    def perform_dilution(self):
        try:
            vol_stock = self._parse_float(self.dil_vars, "vol_stock")
            conc_stock = self._parse_float(self.dil_vars, "conc_stock")
            conc_final = self._parse_float(self.dil_vars, "conc_final")
            vol_final = self._parse_float(self.dil_vars, "vol_final")
        except InputError as exc:
            messagebox.showerror("Input error", str(exc))
            return

        if conc_final >= conc_stock:
            messagebox.showerror(
                "Input error",
                "The final concentration must be lower than the starting "
                "concentration.\nA dilution cannot increase concentration.")
            return

        vol_needed = (conc_final / conc_stock) * vol_final
        vol_vehicle = vol_final - vol_needed
        vol_remaining = vol_stock - vol_needed

        warning = ""
        if vol_needed > vol_stock:
            shortfall = vol_needed - vol_stock
            warning = ("\n*** WARNING: you need "
                       f"{vol_needed:.3g} ml of stock but only have "
                       f"{vol_stock:.3g} ml ({shortfall:.3g} ml short). ***\n")

        lines = [
            "Dilution Calculation",
            "=" * 40,
            f"Compound: {self.compound_name.get()}",
            "=" * 40,
            f"Starting solution concentration: {conc_stock:.3g} mg/ml",
            f"Final solution concentration: {conc_final:.3g} mg/ml",
            f"Volume of new solution: {vol_final:.3g} ml",
            f"Dilution factor: {conc_stock / conc_final:.3g}x",
            "=" * 40,
            f"Mix {vol_needed:.3g} ml of your stock solution",
            f"with {vol_vehicle:.3g} ml of the appropriate vehicle",
            "=" * 40,
            f"This will leave you with {vol_remaining:.3g} ml of your "
            f"stock solution",
            f"Producing a final volume of {vol_final:.3g} ml",
            "=" * 40,
        ]
        result = "\n".join(lines) + warning + "\n"

        self._set_result(self.dil_result, result)
        self._record("Perform Dilution", result)

    # ------------------------------------------------------ output and log

    def _record(self, calc_type, result):
        timestamp = time.strftime("%Y/%m/%d - %H:%M:%S")
        comments = self.comments.get("1.0", tk.END).strip()

        block = (f"Date: {timestamp}\n"
                 f"Calculation Type: {calc_type}\n"
                 f"Comments: {comments}\n"
                 f"{result}\n" + "=" * 50 + "\n\n")

        self.output_text.insert(tk.END, block)
        self.output_text.see(tk.END)

        self.records.append({
            "date": timestamp,
            "type": calc_type,
            "compound": self.compound_name.get(),
            "comments": comments,
            "result": result.strip(),
        })

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as log_file:
                log_file.write(block)
        except OSError as exc:
            self.status_var.set(f"Could not write log file: {exc}")
        else:
            self.status_var.set(f"{calc_type} logged at {timestamp}.")

    def export_output(self):
        compound = self.compound_name.get().strip()
        if not compound:
            messagebox.showerror("Export error",
                                 "Please enter a compound name before "
                                 "exporting.")
            return
        if not self.output_text.get("1.0", tk.END).strip():
            messagebox.showerror("Export error", "There is nothing to export.")
            return

        safe_name = re.sub(r"[^\w\-]+", "_", compound).strip("_")
        filename = f"{time.strftime('%Y%m%d_%H%M')}_{safe_name}"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv")],
            initialfile=filename)
        if not file_path:
            return

        try:
            if file_path.lower().endswith(".csv"):
                with open(file_path, "w", newline="",
                          encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f, fieldnames=["date", "type", "compound",
                                       "comments", "result"])
                    writer.writeheader()
                    writer.writerows(self.records)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.output_text.get("1.0", tk.END))
        except OSError as exc:
            messagebox.showerror("Export error",
                                 f"An error occurred while exporting:\n{exc}")
        else:
            messagebox.showinfo("Export successful",
                                f"Output exported to {file_path}")

    # ------------------------------------------------------------ BEW file

    def _load_bew_file(self):
        """Load BEW values. Supports the old 'name - value' format and the
        new tab-separated 'name<TAB>value<TAB>date' format."""
        self.bew_data = {}
        if not os.path.exists(BEW_FILE):
            return
        try:
            with open(BEW_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    name = value = date = None
                    if "\t" in line:
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            name, value = parts[0], parts[1]
                            date = parts[2] if len(parts) > 2 else ""
                    elif " - " in line:
                        name, value = line.rsplit(" - ", 1)
                        date = ""
                    if name is None:
                        continue
                    try:
                        self.bew_data[name.strip()] = (float(value), date)
                    except ValueError:
                        continue
        except OSError as exc:
            self.status_var.set(f"Could not read BEW file: {exc}")

    def _save_bew_file(self):
        try:
            with open(BEW_FILE, "w", encoding="utf-8") as f:
                for name in sorted(self.bew_data, key=str.lower):
                    bew, date = self.bew_data[name]
                    f.write(f"{name}\t{bew:.6g}\t{date}\n")
        except OSError as exc:
            self.status_var.set(f"Could not write BEW file: {exc}")

    def _add_bew(self, compound, bew):
        compound = compound.strip()
        if not compound:
            return
        existing = self.bew_data.get(compound)
        date = time.strftime("%Y-%m-%d")
        # Only rewrite the file when the value is new or has changed
        if existing is None or abs(existing[0] - bew) > 1e-9:
            self.bew_data[compound] = (bew, date)
            self._save_bew_file()
            self._refresh_bew_tree()
        elif existing[1] != date:
            self.bew_data[compound] = (bew, date)
            self._save_bew_file()
            self._refresh_bew_tree()

    def _refresh_bew_tree(self):
        query = self.bew_search.get().strip().lower()
        self.bew_tree.delete(*self.bew_tree.get_children())
        for name in sorted(self.bew_data, key=str.lower):
            if query and query not in name.lower():
                continue
            bew, date = self.bew_data[name]
            self.bew_tree.insert("", tk.END,
                                 values=(name, f"{bew:.6g}", date or "-"))

    def _on_bew_double_click(self, _event):
        selection = self.bew_tree.selection()
        if not selection:
            return
        name, bew, _date = self.bew_tree.item(selection[0], "values")
        self.compound_name.set(name)
        self.est_vars["bew"][0].set(bew)
        self.veh_vars["bew"][0].set(bew)
        self.status_var.set(f"Loaded '{name}' (BEW {bew}) into the "
                            f"calculation tabs.")

    # ------------------------------------------------------------ settings

    @staticmethod
    def _load_settings():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (OSError, ValueError):
            pass
        return {}

    def _save_settings(self):
        settings = {
            "geometry": self.geometry(),
            "last_compound": self.compound_name.get(),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except OSError:
            pass

    def _on_close(self):
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    app = ZDrugMakerApp()
    app.mainloop()
