#!/usr/bin/env python3
"""
pyClaudFootyEditor.py
Tkinter GUI editor for ClaudFooty data files.

Edits:
  pyCldFooty_players.jsonl      — cumulative player roster
  pyCldFooty_premade_teams.json — hand-crafted NPC team definitions
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional

# ── file constants (must match pyClaudFootyPrototype.py) ──────────────────────
ROSTER_FILE  = "pyCldFooty_players.jsonl"
PREMADE_FILE = "pyCldFooty_premade_teams.json"

ROLES = ["Goalie", "Defender", "Attacker", "Unassigned"]

TRAIT_NAMES = [
    "Speed", "Stamina", "Strength", "Agility", "Shooting",
    "Passing", "Dribbling", "Tackling", "Marking", "Goalkeeping",
    "Vision", "Composure", "Discipline", "Teamwork", "Aggression",
]
STAT_NAMES = [
    "goals", "shots", "saves", "goals_allowed",
    "tackles", "key_passes", "fouls", "yellow_cards", "red_cards",
]

# ── OVR calculation (mirrors pyClaudFootyPrototype.py) ───────────────────────
def _gk(t: Dict) -> float:
    return (t.get("Goalkeeping", 10) * .50 + t.get("Agility", 10) * .20 +
            t.get("Composure",   10) * .15 + t.get("Strength", 10) * .10 +
            t.get("Vision",      10) * .05)

def _df(t: Dict) -> float:
    return (t.get("Tackling",   10) * .35 + t.get("Marking",    10) * .25 +
            t.get("Strength",   10) * .15 + t.get("Agility",    10) * .10 +
            t.get("Stamina",    10) * .10 + t.get("Discipline", 10) * .05)

def _at(t: Dict) -> float:
    return (t.get("Shooting",  10) * .35 + t.get("Dribbling", 10) * .25 +
            t.get("Speed",     10) * .20 + t.get("Agility",   10) * .10 +
            t.get("Composure", 10) * .10)

def calc_ovr(traits: Dict, role: str) -> float:
    gk, df, at = _gk(traits), _df(traits), _at(traits)
    if role == "Goalie":   return gk * .70 + df * .15 + at * .15
    if role == "Defender": return df * .70 + gk * .10 + at * .20
    if role == "Attacker": return at * .70 + df * .15 + gk * .15
    return (gk + df + at) / 3


# ── Application ───────────────────────────────────────────────────────────────
class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("ClaudFooty Editor")
        self.geometry("1200x780")
        self.minsize(960, 660)

        self.script_dir  = os.path.dirname(os.path.abspath(__file__))
        self.roster_path = os.path.join(self.script_dir, ROSTER_FILE)
        self.teams_path  = os.path.join(self.script_dir, PREMADE_FILE)

        self.roster: List[Dict] = []
        self.teams:  List[Dict] = []
        self._r_sel: Optional[int] = None   # selected roster index
        self._t_sel: Optional[int] = None   # selected team index
        self._p_sel: Optional[int] = None   # selected player-in-team index

        self._build_ui()
        self._load_all()

    # ── menus + top-level layout ───────────────────────────────────────────────
    def _build_ui(self):
        m  = tk.Menu(self)
        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label="Save Roster          Ctrl+R", command=self._save_roster)
        fm.add_command(label="Save Premade Teams   Ctrl+T", command=self._save_teams)
        fm.add_command(label="Save All             Ctrl+S", command=self._save_all)
        fm.add_separator()
        fm.add_command(label="Reload from disk",            command=self._load_all)
        fm.add_separator()
        fm.add_command(label="Exit", command=self._on_close)
        m.add_cascade(label="File", menu=fm)
        self.config(menu=m)

        self.bind("<Control-s>", lambda _: self._save_all())
        self.bind("<Control-r>", lambda _: self._save_roster())
        self.bind("<Control-t>", lambda _: self._save_teams())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._build_roster_tab(nb)
        self._build_teams_tab(nb)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w",
                 relief=tk.SUNKEN, padx=6, bg="#e8e8e8").pack(fill=tk.X, side=tk.BOTTOM)

    def _status(self, msg: str):
        self._status_var.set(msg)
        self.update_idletasks()

    def _on_close(self):
        if messagebox.askokcancel("Exit", "Exit ClaudFooty Editor?\n(Unsaved changes will be lost.)"):
            self.destroy()

    # ── load / save ───────────────────────────────────────────────────────────
    def _load_all(self):
        self._load_roster()
        self._load_teams()

    def _save_all(self):
        self._save_roster()
        self._save_teams()

    def _load_roster(self):
        self.roster.clear()
        if os.path.exists(self.roster_path):
            with open(self.roster_path, encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s:
                        try:
                            self.roster.append(json.loads(s))
                        except json.JSONDecodeError:
                            pass
        self._refresh_roster_tree()
        self._status(f"Loaded {len(self.roster)} player(s)  ←  {self.roster_path}")

    def _save_roster(self):
        with open(self.roster_path, "w", encoding="utf-8") as f:
            for rec in self.roster:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self._status(f"Saved {len(self.roster)} player(s)  →  {self.roster_path}")

    def _load_teams(self):
        self.teams.clear()
        if os.path.exists(self.teams_path):
            try:
                with open(self.teams_path, encoding="utf-8") as f:
                    self.teams = json.load(f)
            except (json.JSONDecodeError, TypeError):
                pass
        self._refresh_teams_lb()
        self._status(f"Loaded {len(self.teams)} team(s)  ←  {self.teams_path}")

    def _save_teams(self):
        with open(self.teams_path, "w", encoding="utf-8") as f:
            json.dump(self.teams, f, indent=2)
        self._status(f"Saved {len(self.teams)} team(s)  →  {self.teams_path}")

    # ══════════════════════════════════════════════════════════════════════════
    #  ROSTER TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_roster_tab(self, nb: ttk.Notebook):
        tab = ttk.Frame(nb)
        nb.add(tab, text="  Player Roster  ")

        # ── left: treeview list ───────────────────────────────────────────────
        left = ttk.Frame(tab, width=400)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0), pady=6)
        left.pack_propagate(False)

        ttk.Label(left, text="Roster", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")

        tree_wrap = ttk.Frame(left)
        tree_wrap.pack(fill=tk.BOTH, expand=True)

        cols = ("name", "season", "team", "role", "ovr")
        self._rtree = ttk.Treeview(tree_wrap, columns=cols,
                                   show="headings", selectmode="browse")
        for col, hdr, w, anch in [
            ("name",   "Name",   145, "w"),
            ("season", "Season",  80, "w"),
            ("team",   "Team",   105, "w"),
            ("role",   "Role",    75, "w"),
            ("ovr",    "OVR",     50, "e"),
        ]:
            self._rtree.heading(col, text=hdr,
                                command=lambda c=col: self._sort_roster(c))
            self._rtree.column(col, width=w, anchor=anch)

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical",
                            command=self._rtree.yview)
        self._rtree.configure(yscrollcommand=vsb.set)
        self._rtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._rtree.bind("<<TreeviewSelect>>", self._on_r_select)

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text="+ Add Player",  command=self._r_add).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="✕ Delete",      command=self._r_delete).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Save Roster",   command=self._save_roster).pack(side=tk.RIGHT, padx=2)

        # ── right: edit form ──────────────────────────────────────────────────
        right = ttk.Frame(tab)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._build_r_edit(right)

    def _build_r_edit(self, parent):
        self._rv = {
            "first_name":    tk.StringVar(),
            "last_name":     tk.StringVar(),
            "team_name":     tk.StringVar(),
            "season":        tk.StringVar(),
            "assigned_role": tk.StringVar(value="Attacker"),
            "age":           tk.IntVar(value=22),
            "id":            tk.IntVar(value=1),
        }
        self._rt = {t: tk.IntVar(value=10) for t in TRAIT_NAMES}
        self._rs = {s: tk.IntVar(value=0)  for s in STAT_NAMES}
        self._r_ovr_var = tk.StringVar(value="OVR: —")

        for v in self._rt.values():
            v.trace_add("write", self._r_refresh_ovr)
        self._rv["assigned_role"].trace_add("write", self._r_refresh_ovr)

        # basic info
        bi = ttk.LabelFrame(parent, text=" Basic Info ")
        bi.pack(fill=tk.X, pady=(0, 4))
        g = ttk.Frame(bi)
        g.pack(fill=tk.X, padx=8, pady=4)

        for row, col, label, key, width in [
            (0, 0, "First Name:", "first_name", 18),
            (0, 2, "Last Name:",  "last_name",  18),
            (1, 0, "Team:",       "team_name",  18),
            (1, 2, "Season:",     "season",     18),
        ]:
            ttk.Label(g, text=label).grid(row=row, column=col,   sticky="e", padx=4, pady=2)
            ttk.Entry(g, textvariable=self._rv[key],
                      width=width).grid(row=row, column=col+1, sticky="w", padx=4)

        ttk.Label(g, text="Role:").grid(row=2, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(g, textvariable=self._rv["assigned_role"], values=ROLES,
                     state="readonly", width=14).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(g, text="Age:").grid(row=2, column=2, sticky="e", padx=4)
        ttk.Spinbox(g, textvariable=self._rv["age"],
                    from_=16, to=45, width=6).grid(row=2, column=3, sticky="w", padx=4)
        ttk.Label(g, text="ID:").grid(row=3, column=0, sticky="e", padx=4, pady=2)
        ttk.Spinbox(g, textvariable=self._rv["id"],
                    from_=1, to=9999, width=7).grid(row=3, column=1, sticky="w", padx=4)

        # traits
        tr_frame = ttk.LabelFrame(parent, text=" Traits ")
        tr_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(tr_frame, textvariable=self._r_ovr_var,
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="ne", padx=10, pady=(4, 0))
        self._build_trait_grid(tr_frame, self._rt)

        # stats
        st_frame = ttk.LabelFrame(parent, text=" Tournament Stats ")
        st_frame.pack(fill=tk.X, pady=(0, 4))
        self._build_stat_grid(st_frame, self._rs)

        # action buttons
        bf = ttk.Frame(parent)
        bf.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(bf, text="Apply Changes",
                   command=self._r_apply).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Revert",
                   command=lambda: self._on_r_select()).pack(side=tk.LEFT, padx=4)

    # ── shared grid builders ──────────────────────────────────────────────────
    def _build_trait_grid(self, parent, trait_vars: Dict):
        g = ttk.Frame(parent)
        g.pack(fill=tk.X, padx=8, pady=(0, 6))
        for i, trait in enumerate(TRAIT_NAMES):
            r, c = divmod(i, 5)
            cell = ttk.Frame(g)
            cell.grid(row=r, column=c, padx=6, pady=3, sticky="nw")
            ttk.Label(cell, text=trait, width=11).pack(anchor="w")
            ttk.Spinbox(cell, textvariable=trait_vars[trait],
                        from_=1, to=20, width=5).pack(anchor="w")

    def _build_stat_grid(self, parent, stat_vars: Dict):
        g = ttk.Frame(parent)
        g.pack(fill=tk.X, padx=8, pady=4)
        for i, stat in enumerate(STAT_NAMES):
            r, c = divmod(i, 4)
            cell = ttk.Frame(g)
            cell.grid(row=r, column=c, padx=6, pady=3, sticky="nw")
            ttk.Label(cell, text=stat.replace("_", " ").title(), width=13).pack(anchor="w")
            ttk.Spinbox(cell, textvariable=stat_vars[stat],
                        from_=0, to=9999, width=7).pack(anchor="w")

    # ── roster: OVR refresh ───────────────────────────────────────────────────
    def _r_refresh_ovr(self, *_):
        try:
            traits = {t: self._rt[t].get() for t in TRAIT_NAMES}
            ov = calc_ovr(traits, self._rv["assigned_role"].get())
            self._r_ovr_var.set(f"OVR: {ov:.1f}")
        except Exception:
            pass

    # ── roster: treeview ─────────────────────────────────────────────────────
    def _refresh_roster_tree(self):
        self._rtree.delete(*self._rtree.get_children())
        for i, rec in enumerate(self.roster):
            name   = f"{rec.get('first_name','')} {rec.get('last_name','')}".strip()
            season = rec.get("season", "")
            team   = rec.get("team_name", "")
            role   = rec.get("assigned_role", "")
            ov     = calc_ovr(rec.get("traits", {}), role)
            self._rtree.insert("", "end", iid=str(i),
                               values=(name, season, team, role, f"{ov:.1f}"))

    def _sort_roster(self, col: str):
        key_fn = {
            "name":   lambda r: f"{r.get('first_name','')} {r.get('last_name','')}",
            "season": lambda r: r.get("season", ""),
            "team":   lambda r: r.get("team_name", ""),
            "role":   lambda r: r.get("assigned_role", ""),
            "ovr":    lambda r: calc_ovr(r.get("traits", {}), r.get("assigned_role", "")),
        }.get(col)
        if not key_fn:
            return
        asc = getattr(self, f"_sort_{col}_asc", True)
        self.roster.sort(key=key_fn, reverse=not asc)
        setattr(self, f"_sort_{col}_asc", not asc)
        self._refresh_roster_tree()

    # ── roster: selection / apply / add / delete ──────────────────────────────
    def _on_r_select(self, _event=None):
        sel = self._rtree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self._r_sel = idx
        rec = self.roster[idx]
        self._rv["first_name"].set(rec.get("first_name", ""))
        self._rv["last_name"].set(rec.get("last_name", ""))
        self._rv["team_name"].set(rec.get("team_name", ""))
        self._rv["season"].set(rec.get("season", ""))
        self._rv["assigned_role"].set(rec.get("assigned_role", "Unassigned"))
        self._rv["age"].set(rec.get("age", 22))
        self._rv["id"].set(rec.get("id", 1))
        for t in TRAIT_NAMES:
            self._rt[t].set(rec.get("traits", {}).get(t, 10))
        for s in STAT_NAMES:
            self._rs[s].set(rec.get("stats", {}).get(s, 0))
        self._r_refresh_ovr()

    def _r_apply(self):
        if self._r_sel is None:
            messagebox.showinfo("Nothing selected", "Select a player first.")
            return
        rec = self.roster[self._r_sel]
        rec["first_name"]    = self._rv["first_name"].get().strip()
        rec["last_name"]     = self._rv["last_name"].get().strip()
        rec["team_name"]     = self._rv["team_name"].get().strip()
        rec["season"]        = self._rv["season"].get().strip()
        rec["assigned_role"] = self._rv["assigned_role"].get()
        try:
            rec["age"] = self._rv["age"].get()
            rec["id"]  = self._rv["id"].get()
            rec["traits"] = {t: self._rt[t].get() for t in TRAIT_NAMES}
            rec["stats"]  = {s: self._rs[s].get() for s in STAT_NAMES}
        except tk.TclError:
            messagebox.showerror("Invalid value",
                                 "Age, ID, traits, and stats must all be numbers.")
            return
        self._refresh_roster_tree()
        self._rtree.selection_set(str(self._r_sel))
        self._status("Changes applied in memory — use Save Roster to write to disk.")

    def _r_add(self):
        new_id = max((r.get("id", 0) for r in self.roster), default=0) + 1
        self.roster.append({
            "schema": "cldfooty_player_v1",
            "season": "SEASON_001",
            "id": new_id,
            "first_name": "New", "last_name": "Player",
            "team_name": "", "assigned_role": "Attacker", "age": 22,
            "traits": {t: 10 for t in TRAIT_NAMES},
            "stats":  {s: 0  for s in STAT_NAMES},
        })
        self._refresh_roster_tree()
        iid = str(len(self.roster) - 1)
        self._rtree.selection_set(iid)
        self._rtree.see(iid)
        self._on_r_select()

    def _r_delete(self):
        sel = self._rtree.selection()
        if not sel:
            return
        idx  = int(sel[0])
        rec  = self.roster[idx]
        name = f"{rec.get('first_name','')} {rec.get('last_name','')}".strip()
        if not messagebox.askyesno("Delete Player",
                                   f"Remove {name!r} from the roster?\nThis cannot be undone."):
            return
        self.roster.pop(idx)
        self._r_sel = None
        self._refresh_roster_tree()
        self._status(f"Deleted {name!r} — save roster to write to disk.")

    # ══════════════════════════════════════════════════════════════════════════
    #  PREMADE TEAMS TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_teams_tab(self, nb: ttk.Notebook):
        tab = ttk.Frame(nb)
        nb.add(tab, text="  Premade Teams  ")

        # ── left: team list ───────────────────────────────────────────────────
        tl = ttk.Frame(tab, width=210)
        tl.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0), pady=6)
        tl.pack_propagate(False)

        ttk.Label(tl, text="Teams", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self._teams_lb = tk.Listbox(tl, selectmode=tk.SINGLE, exportselection=False)
        self._teams_lb.pack(fill=tk.BOTH, expand=True)
        self._teams_lb.bind("<<ListboxSelect>>", self._on_t_select)

        tb = ttk.Frame(tl)
        tb.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(tb, text="+ Team",   command=self._t_add).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb, text="✕ Delete", command=self._t_delete).pack(side=tk.LEFT, padx=1)

        ttk.Label(tl, text="Team name:").pack(anchor="w", pady=(10, 0))
        name_row = ttk.Frame(tl)
        name_row.pack(fill=tk.X)
        self._t_name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self._t_name_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(name_row, text="✓", width=2,
                   command=self._t_rename).pack(side=tk.LEFT)

        ttk.Button(tl, text="Save Teams File",
                   command=self._save_teams).pack(fill=tk.X, pady=(10, 0))

        # ── middle: player list ───────────────────────────────────────────────
        ml = ttk.Frame(tab, width=235)
        ml.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0), pady=6)
        ml.pack_propagate(False)

        ttk.Label(ml, text="Players", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self._players_lb = tk.Listbox(ml, selectmode=tk.SINGLE, exportselection=False,
                                      font=("Courier New", 9))
        self._players_lb.pack(fill=tk.BOTH, expand=True)
        self._players_lb.bind("<<ListboxSelect>>", self._on_p_select)

        pb = ttk.Frame(ml)
        pb.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(pb, text="+ Player",  command=self._p_add).pack(side=tk.LEFT, padx=1)
        ttk.Button(pb, text="✕ Delete",  command=self._p_delete).pack(side=tk.LEFT, padx=1)

        # ── right: player edit ────────────────────────────────────────────────
        rl = ttk.Frame(tab)
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._build_p_edit(rl)

    def _build_p_edit(self, parent):
        self._pv = {
            "first_name":    tk.StringVar(),
            "last_name":     tk.StringVar(),
            "age":           tk.IntVar(value=22),
            "assigned_role": tk.StringVar(value="Attacker"),
        }
        self._pt = {t: tk.IntVar(value=10) for t in TRAIT_NAMES}
        self._p_ovr_var = tk.StringVar(value="OVR: —")

        for v in self._pt.values():
            v.trace_add("write", self._p_refresh_ovr)
        self._pv["assigned_role"].trace_add("write", self._p_refresh_ovr)

        # basic info
        bi = ttk.LabelFrame(parent, text=" Player Info ")
        bi.pack(fill=tk.X, pady=(0, 4))
        g = ttk.Frame(bi)
        g.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(g, text="First:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(g, textvariable=self._pv["first_name"],
                  width=16).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(g, text="Last:").grid(row=0, column=2, sticky="e", padx=4)
        ttk.Entry(g, textvariable=self._pv["last_name"],
                  width=16).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(g, text="Role:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(g, textvariable=self._pv["assigned_role"],
                     values=["Goalie", "Defender", "Attacker"],
                     state="readonly", width=14).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(g, text="Age:").grid(row=1, column=2, sticky="e", padx=4)
        ttk.Spinbox(g, textvariable=self._pv["age"],
                    from_=16, to=45, width=6).grid(row=1, column=3, sticky="w", padx=4)

        # traits
        tr_frame = ttk.LabelFrame(parent, text=" Traits ")
        tr_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(tr_frame, textvariable=self._p_ovr_var,
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="ne", padx=10, pady=(4, 0))
        self._build_trait_grid(tr_frame, self._pt)

        # action buttons
        bf = ttk.Frame(parent)
        bf.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(bf, text="Apply Player Changes",
                   command=self._p_apply).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Revert",
                   command=lambda: self._on_p_select()).pack(side=tk.LEFT, padx=4)

    # ── teams tab: OVR refresh ────────────────────────────────────────────────
    def _p_refresh_ovr(self, *_):
        try:
            traits = {t: self._pt[t].get() for t in TRAIT_NAMES}
            ov = calc_ovr(traits, self._pv["assigned_role"].get())
            self._p_ovr_var.set(f"OVR: {ov:.1f}")
        except Exception:
            pass

    # ── teams tab: list refresh ───────────────────────────────────────────────
    def _refresh_teams_lb(self):
        self._teams_lb.delete(0, tk.END)
        for td in self.teams:
            n  = td.get("name", "Unnamed")
            np = len(td.get("players", []))
            self._teams_lb.insert(tk.END, f"{n}  ({np}p)")

    def _refresh_players_lb(self):
        self._players_lb.delete(0, tk.END)
        if self._t_sel is None:
            return
        for pd in self.teams[self._t_sel].get("players", []):
            name = f"{pd.get('first_name','')} {pd.get('last_name','')}".strip()
            role = pd.get("assigned_role", "?")[:2]
            ov   = calc_ovr(pd.get("traits", {}), pd.get("assigned_role", ""))
            self._players_lb.insert(tk.END, f"{name:<20} [{role}]  {ov:.1f}")

    # ── teams tab: selection ──────────────────────────────────────────────────
    def _on_t_select(self, _=None):
        sel = self._teams_lb.curselection()
        if not sel:
            return
        self._t_sel = sel[0]
        self._p_sel = None
        self._t_name_var.set(self.teams[self._t_sel].get("name", ""))
        self._refresh_players_lb()

    def _on_p_select(self, _=None):
        sel = self._players_lb.curselection()
        if not sel or self._t_sel is None:
            return
        self._p_sel = sel[0]
        pd = self.teams[self._t_sel]["players"][self._p_sel]
        self._pv["first_name"].set(pd.get("first_name", ""))
        self._pv["last_name"].set(pd.get("last_name", ""))
        self._pv["age"].set(pd.get("age", 22))
        self._pv["assigned_role"].set(pd.get("assigned_role", "Attacker"))
        for t in TRAIT_NAMES:
            self._pt[t].set(pd.get("traits", {}).get(t, 10))
        self._p_refresh_ovr()

    # ── teams tab: apply / add / delete ──────────────────────────────────────
    def _p_apply(self):
        if self._t_sel is None or self._p_sel is None:
            messagebox.showinfo("No selection", "Select a player to edit first.")
            return
        pd = self.teams[self._t_sel]["players"][self._p_sel]
        pd["first_name"]    = self._pv["first_name"].get().strip()
        pd["last_name"]     = self._pv["last_name"].get().strip()
        pd["assigned_role"] = self._pv["assigned_role"].get()
        try:
            pd["age"]    = self._pv["age"].get()
            pd["traits"] = {t: self._pt[t].get() for t in TRAIT_NAMES}
        except tk.TclError:
            messagebox.showerror("Invalid value", "Age and traits must be numbers.")
            return
        self._refresh_players_lb()
        self._players_lb.selection_set(self._p_sel)
        self._status("Player updated in memory — save file to persist.")

    def _t_rename(self):
        if self._t_sel is None:
            return
        self.teams[self._t_sel]["name"] = self._t_name_var.get().strip()
        self._refresh_teams_lb()
        self._teams_lb.selection_set(self._t_sel)

    def _t_add(self):
        self.teams.append({
            "name": f"New Team {len(self.teams) + 1}",
            "players": [
                {"first_name": "New", "last_name": "Keeper",    "age": 25,
                 "assigned_role": "Goalie",   "traits": {t: 10 for t in TRAIT_NAMES}},
                {"first_name": "New", "last_name": "Defender",  "age": 25,
                 "assigned_role": "Defender", "traits": {t: 10 for t in TRAIT_NAMES}},
                {"first_name": "New", "last_name": "Defender2", "age": 25,
                 "assigned_role": "Defender", "traits": {t: 10 for t in TRAIT_NAMES}},
                {"first_name": "New", "last_name": "Forward",   "age": 25,
                 "assigned_role": "Attacker", "traits": {t: 10 for t in TRAIT_NAMES}},
                {"first_name": "New", "last_name": "Forward2",  "age": 25,
                 "assigned_role": "Attacker", "traits": {t: 10 for t in TRAIT_NAMES}},
            ],
        })
        self._refresh_teams_lb()
        self._teams_lb.selection_set(len(self.teams) - 1)
        self._on_t_select()

    def _t_delete(self):
        if self._t_sel is None:
            return
        name = self.teams[self._t_sel].get("name", "?")
        if not messagebox.askyesno("Delete Team",
                                   f"Delete team {name!r}?\nThis cannot be undone."):
            return
        self.teams.pop(self._t_sel)
        self._t_sel = None
        self._p_sel = None
        self._refresh_teams_lb()
        self._refresh_players_lb()

    def _p_add(self):
        if self._t_sel is None:
            messagebox.showinfo("No team", "Select a team first.")
            return
        self.teams[self._t_sel].setdefault("players", []).append({
            "first_name": "New", "last_name": "Player", "age": 22,
            "assigned_role": "Attacker",
            "traits": {t: 10 for t in TRAIT_NAMES},
        })
        self._refresh_players_lb()
        last = len(self.teams[self._t_sel]["players"]) - 1
        self._players_lb.selection_set(last)
        self._on_p_select()

    def _p_delete(self):
        if self._t_sel is None or self._p_sel is None:
            return
        players = self.teams[self._t_sel].get("players", [])
        if len(players) <= 1:
            messagebox.showwarning("Cannot delete",
                                   "A team must have at least one player.")
            return
        pd   = players[self._p_sel]
        name = f"{pd.get('first_name','')} {pd.get('last_name','')}".strip()
        if not messagebox.askyesno("Delete Player", f"Remove {name!r}?"):
            return
        players.pop(self._p_sel)
        self._p_sel = None
        self._refresh_players_lb()


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import traceback

    # Change working directory to the script's own folder so relative file
    # paths work whether the user double-clicks or runs from another directory.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        App().mainloop()
    except Exception:
        # Show crash details in a message box rather than silently vanishing.
        err = traceback.format_exc()
        try:
            _r = tk.Tk()
            _r.withdraw()
            messagebox.showerror(
                "ClaudFooty Editor — Startup Error",
                f"The editor crashed on startup:\n\n{err}\n\n"
                "Please report this error.",
            )
            _r.destroy()
        except Exception:
            pass
        raise
