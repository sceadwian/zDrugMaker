"""zToggl UI — tkinter dashboard for Toggl Track CSV exports.

Launched from zToggl.py (menu option 0) or on its own with `py zToggl_ui.py`.
Standard library only. Colours follow Leo's Dashboard (navy panels, amber accent).
"""
import csv
import math
import os
import re
import statistics
from collections import defaultdict
from datetime import datetime, date, timedelta

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

VERSION = '1.3'

# Folder the script lives in; exported Toggl CSVs normally sit in the data subfolder.
FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(FOLDER, 'TogglTimer_TimeTrackerData')

# Dashboard colours (sampled from Leo's Dashboard screenshot).
BG = '#071727'         # page background, input fields
SIDEBAR = '#081a2e'
PANEL = '#102740'      # cards, top bar, nav bar
CARD = '#091b2e'       # inset surfaces (lists, tables)
RAISED = '#122b46'     # hover, tooltips
BORDER = '#274765'
GRID = '#1a3350'       # recessive chart grid
SEL = '#292f2e'        # selected item (warm dark)
AMBER = '#ffb52e'
AMBER_DIM = '#6d582e'
TEXT = '#edf4fb'
TEXT2 = '#9fb2c6'
MUTED = '#768ba1'
RED = '#e66767'

# Categorical series colours — fixed order, colour-blind-safe on dark surfaces,
# each >= 3:1 contrast against PANEL. Never cycled: extra series fold into Other.
SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500',
          '#d55181', '#008300', '#9085e9', '#e66767']
OTHER = '#3e5165'
UNASSIGNED = '#5f768c'

# Sequential ramp (one hue, dark -> light) for the heatmap on a dark surface.
SEQ = ['#0d366b', '#104281', '#184f95', '#1c5cab', '#256abf',
       '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef']

FONT = 'Segoe UI'

# ---------------------------------------------------------------------------
# Description parsing
# ---------------------------------------------------------------------------

# Spelling variants folded together when "Merge spelling variants" is on.
# Case/space differences (DE Shaw vs DEShaw, quote vs Quote) are merged
# automatically; this table is for real renames.
ALIASES = {
    'Beiwe': 'Beiwebio',
    'Gondola': 'Gondola Bio',
}
ACTIVITY_ALIASES = {
    'Call': 'Client call',
    'zoom': 'Client call',
    'email': 'Communication',
}

# Study codenames with these suffixes carry the activity inside the name
# (EfrideetReport -> study Efrideet, activity Report).
STUDY_SUFFIXES = ('Report', 'Data')

# DRAFT mapping of IVS entries to NetSuite time-tracking domains.
# First match wins. who: 'IVS' (internal), 'client', or '*'. Activity '*' = any.
NETSUITE_RULES = [
    ('IVS',    'Admin', 'Meeting',       'Internal Meeting'),
    ('IVS',    'Admin', 'Team',          'Internal Meeting'),
    ('IVS',    'Admin', 'ACC',           'ACC Documentation'),
    ('IVS',    'Admin', 'NICE',          'Pre-Study Planning'),
    ('IVS',    'Admin', '*',             'Administration'),
    ('*',      'BD',    'Quote',         'Quoting'),
    ('*',      'BD',    'Client call',   'Client Meeting'),
    ('*',      'BD',    'Communication', 'Sponsor Communication'),
    ('*',      'BD',    '*',             'BD / Marketing'),
    ('client', 'Admin', 'Communication', 'Sponsor Communication'),
    ('client', 'Admin', 'Meeting',       'Client Meeting'),
    ('*',      'Study', 'Report',        'Report Writing / Deliverables'),
    ('*',      'Study', 'Data',          'Data Handling / Analysis'),
    ('*',      'Study', '*',             'Unassigned – Study work'),
]
WORK_PROJECT = 'IVS'


class Entry:
    __slots__ = ('start', 'end', 'hours', 'day', 'project', 'client', 'desc',
                 'tags', 'source', 'raw_parts', 'who', 'cat', 'detail',
                 'study', 'activity', 'domain')


def split_description(desc):
    """'Jazz - Study - Neturo' -> ['Jazz', 'Study', 'Neturo'].

    A trailing ' -' (e.g. 'DEShaw - Study -') is dropped instead of becoming a
    bogus 'Study -' category. Hyphens without spaces (TSA-250033) are kept.
    """
    s = desc.strip().rstrip('-').strip()
    if not s:
        return []
    return [p.strip() for p in s.split(' - ') if p.strip()]


def _variant_key(s):
    return re.sub(r'[\s_]+', '', s).lower()


def load_csv(path):
    """Read one Toggl export (current or legacy 'Detailed report' layout)."""
    entries, skipped = [], 0
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        end_d = 'End date' if 'End date' in header else 'Stop date'
        end_t = 'End time' if 'End time' in header else 'Stop time'
        needed = ['Description', 'Project', 'Start date', 'Start time', end_d, end_t]
        missing = [c for c in needed if c not in header]
        if missing:
            raise ValueError(f'{os.path.basename(path)} is missing column(s): {", ".join(missing)}')
        for row in reader:
            try:
                start = datetime.strptime(f"{row['Start date']} {row['Start time']}", '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(f'{row[end_d]} {row[end_t]}', '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                skipped += 1
                continue
            if end < start:
                end += timedelta(days=1)
            e = Entry()
            e.start, e.end = start, end
            e.hours = (end - start).total_seconds() / 3600
            e.day = start.date()
            e.project = (row.get('Project') or '').strip()
            e.client = (row.get('Client') or '').strip()
            e.desc = (row.get('Description') or '').strip()
            e.tags = (row.get('Tags') or '').strip()
            e.source = os.path.basename(path)
            e.raw_parts = split_description(e.desc)
            entries.append(e)
    return entries, skipped


def derive_fields(entries, merge):
    """Fill who/cat/detail/study/activity/domain, optionally merging variants."""
    canon = {}
    if merge:
        # Most common spelling wins within each case/space-insensitive group.
        counts = defaultdict(lambda: defaultdict(int))
        for e in entries:
            for p in e.raw_parts[:3]:
                counts[_variant_key(p)][p] += 1
        canon = {k: max(v.items(), key=lambda kv: kv[1])[0] for k, v in counts.items()}
        for src, dst in ALIASES.items():
            canon[_variant_key(src)] = dst

    def fix(s):
        return canon.get(_variant_key(s), s) if merge else s

    act_alias = {_variant_key(k): v for k, v in ACTIVITY_ALIASES.items()}

    for e in entries:
        parts = e.raw_parts
        e.who = fix(parts[0]) if parts else '(blank)'
        e.cat = fix(parts[1]) if len(parts) > 1 else '(none)'
        detail = ' - '.join(parts[2:])
        if len(parts) == 3:
            detail = fix(detail)
        e.detail = detail
        e.study, e.activity = '', ''
        if e.cat.lower() == 'study':
            e.study = detail or '(unnamed)'
            for suf in STUDY_SUFFIXES:
                if detail.endswith(suf) and len(detail) > len(suf):
                    e.study, e.activity = detail[:-len(suf)].strip(), suf
                    break
        else:
            e.activity = act_alias.get(_variant_key(detail), detail) if merge else detail
        e.domain = netsuite_domain(e)


def netsuite_domain(e):
    if e.project != WORK_PROJECT:
        return '(not IVS)'
    who = 'IVS' if e.who == 'IVS' else 'client'
    cat, act = e.cat.lower(), (e.activity or '').lower()
    for r_who, r_cat, r_act, domain in NETSUITE_RULES:
        if r_who not in ('*', who) or r_cat.lower() != cat:
            continue
        if r_act == '*' or r_act.lower() == act:
            return domain
    return f'Unassigned – {e.cat}'


DIMENSIONS = {
    'Category': lambda e: e.cat,
    'Client': lambda e: e.who,
    'Client · Category': lambda e: f'{e.who} · {e.cat}',
    'Study': lambda e: e.study or '(not a study)',
    'Activity': lambda e: e.activity or '(none)',
    'NetSuite (draft)': lambda e: e.domain,
    'Description': lambda e: e.desc or '(blank)',
    'Project': lambda e: e.project or '(no project)',
    'Weekday': lambda e: e.day.strftime('%a'),
    'Week': lambda e: (e.day - timedelta(days=e.day.weekday())).isoformat(),
    'Month': lambda e: e.day.strftime('%Y-%m'),
}
BAR_DIMS = ['Category', 'Client', 'Study', 'Activity', 'NetSuite (draft)', 'Description']
COLOR_DIMS = ['Category', 'Client', 'NetSuite (draft)', 'Activity', 'Project']
WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def aggregate(entries, keyfn):
    """key -> [hours, entry count, set of days]."""
    agg = defaultdict(lambda: [0.0, 0, set()])
    for e in entries:
        a = agg[keyfn(e)]
        a[0] += e.hours
        a[1] += 1
        a[2].add(e.day)
    return agg


def nice_max(v):
    if v <= 0:
        return 1
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def list_data_files():
    """(label, path) for CSVs in the data folder (newest first), then yearly ones."""
    found = []
    for folder, prefix in ((DATA_FOLDER, ''), (FOLDER, 'script folder · ')):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder), reverse=True):
            if name.lower().endswith('.csv') and name.startswith(('Toggl', 'toggl')):
                found.append((prefix + _short_name(name), os.path.join(folder, name)))
        if folder == DATA_FOLDER:
            for sub in sorted(os.listdir(folder)):
                sub_path = os.path.join(folder, sub)
                if os.path.isdir(sub_path):
                    for name in sorted(os.listdir(sub_path), reverse=True):
                        if name.lower().endswith('.csv'):
                            found.append(('yearly · ' + _short_name(name), os.path.join(sub_path, name)))
    return found


def _short_name(name):
    m = re.match(r'Toggl_time_entries_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})(.*)\.csv$', name)
    if m:
        extra = m.group(3).strip('_ ')
        return f'{m.group(1)} → {m.group(2)}' + (f' ({extra})' if extra else '')
    return name[:-4] if name.lower().endswith('.csv') else name


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------

class Tooltip:
    def __init__(self, root):
        self.root = root
        self.label = tk.Label(root, bg=RAISED, fg=TEXT, font=(FONT, 9), justify='left',
                              padx=9, pady=6, highlightthickness=1, highlightbackground=BORDER)

    def show(self, event, text):
        self.label.config(text=text)
        self.label.update_idletasks()
        w, h = self.label.winfo_reqwidth(), self.label.winfo_reqheight()
        x = event.x_root - self.root.winfo_rootx() + 16
        y = event.y_root - self.root.winfo_rooty() + 16
        if x + w > self.root.winfo_width():
            x -= w + 32
        if y + h > self.root.winfo_height():
            y -= h + 32
        self.label.place(x=x, y=y)
        self.label.lift()

    def hide(self):
        self.label.place_forget()


class Chart(tk.Canvas):
    """Canvas with per-item hover tooltips and debounced redraw on resize."""

    def __init__(self, parent, app, draw, bg=PANEL, **kw):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, **kw)
        self.app, self.draw_fn, self.tips, self._pending = app, draw, {}, None
        self.bind('<Motion>', self._motion)
        self.bind('<Leave>', lambda _e: app.tooltip.hide())
        self.bind('<Configure>', lambda _e: self.schedule())

    def schedule(self):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(60, self.redraw)

    def redraw(self):
        self._pending = None
        self.delete('all')
        self.tips = {}
        if self.winfo_width() > 20 and self.winfo_height() > 20:
            self.draw_fn(self)

    def tip(self, item, text):
        self.tips[item] = text
        return item

    def _motion(self, event):
        current = self.find_withtag('current')
        if current and current[0] in self.tips:
            self.app.tooltip.show(event, self.tips[current[0]])
        else:
            self.app.tooltip.hide()


class Chip(tk.Label):
    """Toggle button bound to a BooleanVar."""

    def __init__(self, parent, text, var, command):
        super().__init__(parent, text=text, font=(FONT, 9), padx=9, pady=3, cursor='hand2',
                         highlightthickness=1, bd=0)
        self.var, self.command = var, command
        self.bind('<Button-1>', self._toggle)
        self.render()

    def _toggle(self, _event):
        self.var.set(not self.var.get())
        self.render()
        self.command()

    def render(self):
        on = self.var.get()
        self.config(bg=SEL if on else PANEL, fg=AMBER if on else TEXT2,
                    highlightbackground=AMBER_DIM if on else BORDER)


class Segmented(tk.Frame):
    """Row of mutually exclusive options bound to a StringVar."""

    def __init__(self, parent, options, var, command, bg=PANEL):
        super().__init__(parent, bg=bg)
        self.var, self.command, self.labels = var, command, {}
        for opt in options:
            lbl = tk.Label(self, text=opt, font=(FONT, 9), padx=10, pady=3, cursor='hand2',
                           highlightthickness=1, bd=0)
            lbl.pack(side='left', padx=(0, 4))
            lbl.bind('<Button-1>', lambda _e, o=opt: self.pick(o))
            self.labels[opt] = lbl
        var.trace_add('write', lambda *_: self.render())
        self.render()

    def pick(self, opt):
        self.var.set(opt)
        self.render()
        self.command()

    def render(self):
        for opt, lbl in self.labels.items():
            on = opt == self.var.get()
            lbl.config(bg=SEL if on else BG, fg=AMBER if on else TEXT2,
                       highlightbackground=AMBER_DIM if on else BORDER)


def make_button(parent, text, command, primary=False, bg=None):
    base = AMBER if primary else (bg or BG)
    fg = BG if primary else TEXT2
    hover = '#ffc34d' if primary else RAISED
    btn = tk.Label(parent, text=text, font=(FONT, 9, 'bold' if primary else 'normal'),
                   bg=base, fg=fg, padx=12, pady=4, cursor='hand2',
                   highlightthickness=0 if primary else 1, highlightbackground=BORDER)
    btn.bind('<Button-1>', lambda _e: command())
    btn.bind('<Enter>', lambda _e: btn.config(bg=hover))
    btn.bind('<Leave>', lambda _e: btn.config(bg=base))
    return btn


def section_label(parent, text, bg=SIDEBAR):
    return tk.Label(parent, text=' '.join(text.upper()), font=(FONT, 8, 'bold'),
                    bg=bg, fg=MUTED, anchor='w')


def make_listbox(parent, height):
    return tk.Listbox(parent, height=height, selectmode='extended', exportselection=False,
                      bg=CARD, fg=TEXT, selectbackground=SEL, selectforeground=AMBER,
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=AMBER_DIM,
                      bd=0, activestyle='none', font=(FONT, 9))


def make_entry(parent, var, width):
    return tk.Entry(parent, textvariable=var, width=width, bg=BG, fg=TEXT, insertbackground=TEXT,
                    relief='flat', highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=AMBER_DIM, font=(FONT, 9))


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------

class App:
    TABS = ['Overview', 'Day report', 'Timeline', 'Heatmap', 'Breakdown', 'Entries']

    def __init__(self, root):
        self.root = root
        self.entries, self.view, self.files = [], [], []
        self.colors = {}
        self.proj_vars = {}
        self.dirty = set(self.TABS)
        self.font = tkfont.Font(family=FONT, size=9)
        self.font_small = tkfont.Font(family=FONT, size=8)

        root.title(f'zToggl v{VERSION} — dashboard')
        root.configure(bg=BG)
        root.geometry('1500x900')
        root.minsize(1100, 700)
        self._style()
        self.tooltip = Tooltip(root)

        self.merge_var = tk.BooleanVar(value=True)
        self.color_var = tk.StringVar(value='Category')
        self.bar_dim = tk.StringVar(value='Category')
        self.bucket_var = tk.StringVar(value='Day')
        self.tl_range = tk.StringVar(value='Fit')
        self.hm_mode = tk.StringVar(value='Total')
        self.from_var, self.to_var = tk.StringVar(), tk.StringVar()
        self.month_var = tk.StringVar(value='All dates')
        self.search_var = tk.StringVar()
        self.wd_vars = [tk.BooleanVar(value=True) for _ in WEEKDAYS]
        self.search_var.trace_add('write', lambda *_: self._debounce_apply())
        self._apply_job = None

        self._build_topbar()
        self._build_nav()
        body = tk.Frame(root, bg=BG)
        body.pack(fill='both', expand=True)
        self._build_sidebar(body)
        self._build_main(body)
        root.bind_all('<MouseWheel>', self._wheel)
        self.show_tab('Overview')

    # ----- styling -------------------------------------------------------
    def _style(self):
        st = ttk.Style(self.root)
        st.theme_use('clam')
        st.configure('Treeview', background=CARD, fieldbackground=CARD, foreground=TEXT,
                     rowheight=24, borderwidth=0, font=(FONT, 9))
        st.configure('Treeview.Heading', background=PANEL, foreground=TEXT2, relief='flat',
                     borderwidth=0, font=(FONT, 9, 'bold'), padding=(6, 4))
        st.map('Treeview', background=[('selected', SEL)], foreground=[('selected', AMBER)])
        st.map('Treeview.Heading', background=[('active', RAISED)])
        for orient in ('Vertical', 'Horizontal'):
            st.configure(f'{orient}.TScrollbar', background=PANEL, troughcolor=SIDEBAR,
                         bordercolor=SIDEBAR, arrowcolor=TEXT2, lightcolor=PANEL, darkcolor=PANEL)
            st.map(f'{orient}.TScrollbar', background=[('active', RAISED)])
        st.configure('TCombobox', fieldbackground=BG, background=PANEL, foreground=TEXT,
                     arrowcolor=AMBER, bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                     selectbackground=BG, selectforeground=TEXT, padding=3)
        st.map('TCombobox', fieldbackground=[('readonly', BG)], foreground=[('readonly', TEXT)],
               selectbackground=[('readonly', BG)], selectforeground=[('readonly', TEXT)])
        self.root.option_add('*TCombobox*Listbox.background', CARD)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', SEL)
        self.root.option_add('*TCombobox*Listbox.selectForeground', AMBER)
        self.root.option_add('*TCombobox*Listbox.font', (FONT, 9))

    # ----- layout --------------------------------------------------------
    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=PANEL, height=58)
        bar.pack(fill='x')
        bar.pack_propagate(False)
        logo = tk.Canvas(bar, width=34, height=34, bg=PANEL, highlightthickness=0)
        logo.pack(side='left', padx=(14, 10))
        logo.create_rectangle(1, 1, 33, 33, outline=BORDER, fill=BG)
        for i, (h, col) in enumerate(((10, SERIES[0]), (18, SERIES[2]), (14, AMBER), (22, SERIES[1]))):
            logo.create_rectangle(6 + i * 6, 28 - h, 10 + i * 6, 28, fill=col, outline='')
        titles = tk.Frame(bar, bg=PANEL)
        titles.pack(side='left')
        tk.Label(titles, text='zToggl Dashboard', font=(FONT, 12, 'bold'), bg=PANEL, fg=TEXT).pack(anchor='w')
        tk.Label(titles, text=f'Toggl time-entry analyzer · v{VERSION}', font=(FONT, 8),
                 bg=PANEL, fg=TEXT2).pack(anchor='w')
        self.status = tk.Label(bar, text='No data loaded', font=(FONT, 9), bg=PANEL, fg=MUTED)
        self.status.pack(side='right', padx=16)
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x')

    def _build_nav(self):
        nav = tk.Frame(self.root, bg=PANEL)
        nav.pack(fill='x')
        self.nav_items = {}
        icons = {'Overview': '▦', 'Day report': '▤', 'Timeline': '☰', 'Heatmap': '▩', 'Breakdown': '≣', 'Entries': '⋮'}
        inner = tk.Frame(nav, bg=PANEL)
        inner.pack(padx=250, anchor='w')
        for name in self.TABS:
            cell = tk.Frame(inner, bg=PANEL, cursor='hand2')
            cell.pack(side='left', padx=6)
            lbl = tk.Label(cell, text=f'{icons[name]}  {name}', font=(FONT, 10), bg=PANEL,
                           fg=TEXT2, padx=14, pady=9, cursor='hand2')
            lbl.pack()
            line = tk.Frame(cell, bg=PANEL, height=2)
            line.pack(fill='x')
            for w in (cell, lbl):
                w.bind('<Button-1>', lambda _e, n=name: self.show_tab(n))
            self.nav_items[name] = (lbl, line)
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x')

    def _build_sidebar(self, body):
        outer = tk.Frame(body, bg=SIDEBAR, width=290)
        outer.pack(side='left', fill='y')
        outer.pack_propagate(False)
        canvas = tk.Canvas(outer, bg=SIDEBAR, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        side = tk.Frame(canvas, bg=SIDEBAR)
        win = canvas.create_window(0, 0, window=side, anchor='nw')
        side.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(win, width=e.width))
        self.side_canvas = canvas
        pad = {'padx': 14}

        # Data files
        section_label(side, 'Data files').pack(fill='x', pady=(14, 6), **pad)
        self.file_list = make_listbox(side, 8)
        self.file_list.pack(fill='x', **pad)
        self.file_list.bind('<Double-Button-1>', lambda _e: self.load_selected())
        self.data_files = list_data_files()
        for label, _ in self.data_files:
            self.file_list.insert('end', label)
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', pady=(6, 0), **pad)
        make_button(row, 'Load selected', self.load_selected, primary=True).pack(side='left')
        make_button(row, 'Browse…', self.browse, bg=SIDEBAR).pack(side='left', padx=6)
        tk.Label(side, text='Ctrl/Shift-click to combine months. Entries repeated across '
                            'overlapping exports are counted once.',
                 font=(FONT, 8), bg=SIDEBAR, fg=MUTED, justify='left', wraplength=240,
                 anchor='w').pack(fill='x', pady=(4, 0), **pad)

        # Projects
        section_label(side, 'Projects').pack(fill='x', pady=(16, 6), **pad)
        self.proj_frame = tk.Frame(side, bg=SIDEBAR)
        self.proj_frame.pack(fill='x', **pad)
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', pady=(4, 0), **pad)
        for text, fn in (('IVS only', self._projects_ivs), ('All', lambda: self._projects_set(True)),
                         ('None', lambda: self._projects_set(False))):
            lbl = tk.Label(row, text=text, font=(FONT, 8, 'underline'), bg=SIDEBAR, fg=TEXT2, cursor='hand2')
            lbl.pack(side='left', padx=(0, 10))
            lbl.bind('<Button-1>', lambda _e, f=fn: f())

        # Dates
        section_label(side, 'Date range').pack(fill='x', pady=(16, 6), **pad)
        self.month_box = ttk.Combobox(side, textvariable=self.month_var, state='readonly',
                                      values=['All dates'], font=(FONT, 9))
        self.month_box.pack(fill='x', **pad)
        self.month_box.bind('<<ComboboxSelected>>', lambda _e: self._pick_month())
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', pady=(6, 0), **pad)
        tk.Label(row, text='From', font=(FONT, 8), bg=SIDEBAR, fg=MUTED).pack(side='left')
        self.from_entry = make_entry(row, self.from_var, 11)
        self.from_entry.pack(side='left', padx=(4, 8))
        tk.Label(row, text='To', font=(FONT, 8), bg=SIDEBAR, fg=MUTED).pack(side='left')
        self.to_entry = make_entry(row, self.to_var, 11)
        self.to_entry.pack(side='left', padx=4)
        for ent in (self.from_entry, self.to_entry):
            ent.bind('<Return>', lambda _e: self.apply())
            ent.bind('<FocusOut>', lambda _e: self.apply())
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', pady=(6, 0), **pad)
        for text, days in (('Last 7 d', 7), ('Last 30 d', 30), ('Last 90 d', 90)):
            make_button(row, text, lambda d=days: self._last_days(d), bg=SIDEBAR).pack(side='left', padx=(0, 4))
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', pady=(8, 0), **pad)
        for i, name in enumerate(WEEKDAYS):
            chip = Chip(row, name[:2], self.wd_vars[i], self.apply)
            chip.config(padx=5)
            chip.pack(side='left', padx=(0, 3))

        # Category / client
        section_label(side, 'Category').pack(fill='x', pady=(16, 2), **pad)
        tk.Label(side, text='None selected = all', font=(FONT, 8), bg=SIDEBAR, fg=MUTED).pack(anchor='w', **pad)
        self.cat_list = make_listbox(side, 6)
        self.cat_list.pack(fill='x', pady=(2, 0), **pad)
        self.cat_list.bind('<<ListboxSelect>>', lambda _e: self.apply())
        section_label(side, 'Client / who').pack(fill='x', pady=(14, 2), **pad)
        self.client_list = make_listbox(side, 9)
        self.client_list.pack(fill='x', pady=(2, 0), **pad)
        self.client_list.bind('<<ListboxSelect>>', lambda _e: self.apply())

        # Search + options
        section_label(side, 'Search descriptions').pack(fill='x', pady=(14, 6), **pad)
        make_entry(side, self.search_var, 30).pack(fill='x', ipady=3, **pad)
        section_label(side, 'Options').pack(fill='x', pady=(16, 6), **pad)
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', **pad)
        tk.Label(row, text='Colour by', font=(FONT, 9), bg=SIDEBAR, fg=TEXT2).pack(side='left')
        box = ttk.Combobox(row, textvariable=self.color_var, state='readonly', values=COLOR_DIMS,
                           width=18, font=(FONT, 9))
        box.pack(side='left', padx=8)
        box.bind('<<ComboboxSelected>>', lambda _e: self.apply())
        row = tk.Frame(side, bg=SIDEBAR)
        row.pack(fill='x', pady=(8, 0), **pad)
        Chip(row, 'Merge spelling variants', self.merge_var, self._remerge).pack(side='left')
        make_button(side, 'Reset filters', self.reset_filters, bg=SIDEBAR).pack(anchor='w', pady=(14, 20), **pad)

    def _build_main(self, body):
        main = tk.Frame(body, bg=BG)
        main.pack(side='left', fill='both', expand=True, padx=16, pady=14)
        self.kpi_frame = tk.Frame(main, bg=BG)
        self.kpi_frame.pack(fill='x')
        self.kpis = {}
        for i, key in enumerate(('Hours', 'Days tracked', 'Avg / tracked day', 'Entries',
                                 'Median entry', 'NetSuite draft-mapped')):
            tile = tk.Frame(self.kpi_frame, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
            tile.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 10, 0))
            self.kpi_frame.columnconfigure(i, weight=1)
            section_label(tile, key, bg=PANEL).pack(anchor='w', padx=12, pady=(10, 0))
            val = tk.Label(tile, text='—', font=(FONT, 18, 'bold'), bg=PANEL, fg=TEXT)
            val.pack(anchor='w', padx=12)
            sub = tk.Label(tile, text='', font=(FONT, 8), bg=PANEL, fg=TEXT2)
            sub.pack(anchor='w', padx=12, pady=(0, 10))
            self.kpis[key] = (val, sub)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill='both', expand=True, pady=(14, 0))
        self.pages = {}
        self._build_overview()
        self._build_dayreport()
        self._build_timeline()
        self._build_heatmap()
        self._build_breakdown()
        self._build_entries()

    def _card(self, parent, title, subtitle=''):
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill='x', padx=14, pady=(10, 4))
        titles = tk.Frame(head, bg=PANEL)
        titles.pack(side='left')
        section_label(titles, title, bg=PANEL).pack(anchor='w')
        sub = tk.Label(titles, text=subtitle, font=(FONT, 11), bg=PANEL, fg=TEXT)
        sub.pack(anchor='w')
        tools = tk.Frame(head, bg=PANEL)
        tools.pack(side='right')
        return card, tools, sub

    def _page(self, name):
        page = tk.Frame(self.content, bg=BG)
        self.pages[name] = page
        return page

    def _build_overview(self):
        page = self._page('Overview')
        page.rowconfigure(0, weight=5)
        page.rowconfigure(1, weight=6)
        page.columnconfigure(0, weight=1)
        card, tools, self.bar_title = self._card(page, 'Distribution', 'Hours by category')
        card.grid(row=0, column=0, sticky='nsew', pady=(0, 12))
        Segmented(tools, BAR_DIMS, self.bar_dim, self._redraw_overview).pack()
        self.bar_chart = Chart(card, self, self.draw_bars)
        self.bar_chart.pack(fill='both', expand=True, padx=8, pady=(0, 10))
        card, tools, self.time_title = self._card(page, 'Over time', 'Hours per day')
        card.grid(row=1, column=0, sticky='nsew')
        Segmented(tools, ['Day', 'Week', 'Month'], self.bucket_var, self._redraw_overview).pack()
        self.time_chart = Chart(card, self, self.draw_time)
        self.time_chart.pack(fill='both', expand=True, padx=8, pady=(0, 10))

    def _build_dayreport(self):
        page = self._page('Day report')
        card, tools, self.dr_title = self._card(page, 'Day-by-day report',
                                                'Client / Category / Study per day, with suggested time windows')
        card.pack(fill='both', expand=True)
        self.dr_order = tk.StringVar(value='Oldest first')
        Segmented(tools, ['Oldest first', 'Newest first'], self.dr_order, self.render_dayreport).pack(side='left')
        make_button(tools, 'Expand all', lambda: self._tree_open(True, self.dr_tree), bg=PANEL).pack(side='left', padx=(12, 4))
        make_button(tools, 'Collapse', lambda: self._tree_open(False, self.dr_tree), bg=PANEL).pack(side='left', padx=4)
        make_button(tools, 'Export CSV', self.export_dayreport, bg=PANEL).pack(side='left', padx=4)
        self.dr_note = tk.Label(card, text='', font=(FONT, 8), bg=PANEL, fg=MUTED, anchor='w')
        self.dr_note.pack(fill='x', padx=14)
        self.dr_tree = self._tree(card, ('hours', 'pct', 'window'),
                                  {'#0': ('Date  /  Client - Category - Study', 480, 'w'),
                                   'hours': ('Hours', 90, 'e'), 'pct': ('Percentage', 100, 'e'),
                                   'window': ('Suggested time window', 180, 'center')},
                                  lambda _c: None)
        self.dr_tree.tag_configure('day', foreground=AMBER, font=(FONT, 9, 'bold'))

    def _build_timeline(self):
        page = self._page('Timeline')
        card, tools, self.tl_title = self._card(page, 'Day timeline', 'When each entry happened')
        card.pack(fill='both', expand=True)
        Segmented(tools, ['Fit', 'Work 6–20', 'Full day'], self.tl_range, lambda: self.tl_body.redraw()).pack()
        self.tl_legend = Chart(card, self, self.draw_tl_legend, height=24)
        self.tl_legend.pack(fill='x', padx=8)
        self.tl_head = Chart(card, self, self.draw_tl_head, height=22)
        self.tl_head.pack(fill='x', padx=(8, 24))
        frame = tk.Frame(card, bg=PANEL)
        frame.pack(fill='both', expand=True, padx=8, pady=(0, 10))
        self.tl_body = Chart(frame, self, self.draw_tl_body)
        sb = ttk.Scrollbar(frame, orient='vertical', command=self.tl_body.yview)
        self.tl_body.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tl_body.pack(side='left', fill='both', expand=True)

    def _build_heatmap(self):
        page = self._page('Heatmap')
        card, tools, self.hm_title = self._card(page, 'Rhythm', 'Hours by weekday and hour of day')
        card.pack(fill='both', expand=True)
        Segmented(tools, ['Total', 'Average per week'], self.hm_mode, lambda: self.hm_chart.redraw()).pack()
        self.hm_chart = Chart(card, self, self.draw_heatmap)
        self.hm_chart.pack(fill='both', expand=True, padx=8, pady=(0, 10))

    def _build_breakdown(self):
        page = self._page('Breakdown')
        card, tools, self.bd_title = self._card(page, 'Pivot table', 'Group and sort hours')
        card.pack(fill='both', expand=True)
        self.bd_group = tk.StringVar(value='NetSuite (draft)')
        self.bd_then = tk.StringVar(value='Client · Category')
        for label, var, values in (('Group by', self.bd_group, list(DIMENSIONS)),
                                   ('then by', self.bd_then, ['(none)'] + list(DIMENSIONS))):
            tk.Label(tools, text=label, font=(FONT, 9), bg=PANEL, fg=TEXT2).pack(side='left', padx=(8, 4))
            box = ttk.Combobox(tools, textvariable=var, values=values, state='readonly', width=18, font=(FONT, 9))
            box.pack(side='left')
            box.bind('<<ComboboxSelected>>', lambda _e: self.render_breakdown())
        make_button(tools, 'Expand all', lambda: self._tree_open(True), bg=PANEL).pack(side='left', padx=(12, 4))
        make_button(tools, 'Collapse', lambda: self._tree_open(False), bg=PANEL).pack(side='left', padx=4)
        make_button(tools, 'Export CSV', self.export_breakdown, bg=PANEL).pack(side='left', padx=4)
        cols = ('hours', 'pct', 'entries', 'days', 'avg')
        self.bd_tree = self._tree(card, cols, {'#0': ('Name', 420, 'w'), 'hours': ('Hours', 90, 'e'),
                                               'pct': ('% of view', 90, 'e'), 'entries': ('Entries', 80, 'e'),
                                               'days': ('Days', 70, 'e'), 'avg': ('Avg entry (min)', 120, 'e')},
                                  self._sort_breakdown)
        self.bd_sort = ('hours', True)

    def _build_entries(self):
        page = self._page('Entries')
        card, tools, self.en_title = self._card(page, 'Time entries', 'Every entry in the current filter')
        card.pack(fill='both', expand=True)
        make_button(tools, 'Export CSV', self.export_entries, bg=PANEL).pack(side='left')
        spec = {'date': ('Date', 90, 'w'), 'dow': ('Day', 45, 'w'), 'start': ('Start', 55, 'w'),
                'end': ('End', 55, 'w'), 'hours': ('Hours', 60, 'e'), 'project': ('Project', 90, 'w'),
                'desc': ('Description', 300, 'w'), 'cat': ('Category', 90, 'w'), 'who': ('Client', 100, 'w'),
                'study': ('Study', 110, 'w'), 'activity': ('Activity', 100, 'w'),
                'domain': ('NetSuite (draft)', 190, 'w')}
        self.en_tree = self._tree(card, tuple(spec), spec, self._sort_entries, show='headings')
        self.en_sort = ('date', False)

    def _tree(self, parent, cols, spec, sorter, show='tree headings'):
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill='both', expand=True, padx=10, pady=(4, 10))
        tree = ttk.Treeview(frame, columns=cols, show=show, selectmode='extended')
        for col, (text, width, anchor) in spec.items():
            tree.heading(col, text=text, anchor=anchor, command=lambda c=col: sorter(c))
            tree.column(col, width=width, anchor=anchor, stretch=(col in ('#0', 'desc')))
        sb = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        tree.pack(side='left', fill='both', expand=True)
        tree.tag_configure('child', foreground=TEXT2)
        tree.tag_configure('total', foreground=AMBER)
        return tree

    # ----- navigation / scrolling ---------------------------------------
    def show_tab(self, name):
        self.tab = name
        for n, (lbl, line) in self.nav_items.items():
            on = n == name
            lbl.config(fg=AMBER if on else TEXT2, bg=SEL if on else PANEL)
            line.config(bg=AMBER if on else PANEL)
        for n, page in self.pages.items():
            if n == name:
                page.pack(fill='both', expand=True)
            else:
                page.pack_forget()
        self.tooltip.hide()
        if name in self.dirty:
            self.render_tab(name)

    def _wheel(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):  # e.g. over a combobox popdown
            return
        if widget is None or isinstance(widget, (tk.Listbox, ttk.Treeview)):
            return
        w = widget
        while w is not None:
            if w in (self.side_canvas, self.tl_body):
                w.yview_scroll(int(-event.delta / 120) * 3, 'units')
                return
            w = w.master

    # ----- loading -------------------------------------------------------
    def load_selected(self):
        picked = [self.data_files[i][1] for i in self.file_list.curselection()]
        if not picked:
            messagebox.showinfo('zToggl', 'Select one or more files in DATA FILES first.')
            return
        self.load_files(picked)

    def browse(self):
        start = DATA_FOLDER if os.path.isdir(DATA_FOLDER) else FOLDER
        paths = filedialog.askopenfilenames(title='Open Toggl CSV export(s)', initialdir=start,
                                            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if paths:
            self.load_files(list(paths))

    def load_files(self, paths):
        seen, entries, skipped, dupes, errors = set(), [], 0, 0, []
        for path in paths:
            try:
                rows, bad = load_csv(path)
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                errors.append(str(exc))
                continue
            skipped += bad
            for e in rows:
                key = (e.start, e.end, e.desc, e.project)
                if key in seen:
                    dupes += 1
                    continue
                seen.add(key)
                entries.append(e)
        if errors:
            messagebox.showwarning('zToggl', 'Some files could not be read:\n\n' + '\n'.join(errors))
        if not entries:
            return
        entries.sort(key=lambda e: e.start)
        self.entries, self.files = entries, paths
        derive_fields(self.entries, self.merge_var.get())

        projects = defaultdict(float)
        for e in entries:
            projects[e.project or '(no project)'] += e.hours
        old = {p: v.get() for p, v in self.proj_vars.items()}
        for child in self.proj_frame.winfo_children():
            child.destroy()
        self.proj_vars = {}
        default_ivs = WORK_PROJECT in projects
        for i, (proj, _h) in enumerate(sorted(projects.items(), key=lambda kv: -kv[1])):
            on = old.get(proj, (proj == WORK_PROJECT) if default_ivs else True)
            var = tk.BooleanVar(value=on)
            self.proj_vars[proj] = var
            Chip(self.proj_frame, proj, var, self._projects_changed).grid(
                row=i // 2, column=i % 2, sticky='ew', padx=(0, 4), pady=2)
        self.proj_frame.columnconfigure(0, weight=1)
        self.proj_frame.columnconfigure(1, weight=1)

        names = ', '.join(os.path.basename(p) for p in paths[:2]) + (f' +{len(paths) - 2}' if len(paths) > 2 else '')
        extra = []
        if dupes:
            extra.append(f'{dupes} duplicate(s) skipped')
        if skipped:
            extra.append(f'{skipped} unreadable row(s)')
        self.status.config(text=f'{len(entries):,} entries · {names}' + (f'  ({"; ".join(extra)})' if extra else ''),
                           fg=TEXT2)
        self.month_var.set('All dates')
        self.from_var.set(entries[0].day.isoformat())
        self.to_var.set(entries[-1].day.isoformat())
        self._projects_changed()

    # ----- filters -------------------------------------------------------
    def _project_scope(self):
        projs = {p for p, v in self.proj_vars.items() if v.get()}
        return [e for e in self.entries if (e.project or '(no project)') in projs]

    def _projects_changed(self):
        scope = self._project_scope()
        self._compute_colors(scope)
        months = sorted({e.day.strftime('%Y-%m') for e in scope}, reverse=True)
        self.month_box.config(values=['All dates'] + months)
        self._fill_list(self.cat_list, scope, lambda e: e.cat)
        self._fill_list(self.client_list, scope, lambda e: e.who)
        self.apply()

    def _projects_set(self, value):
        for var in self.proj_vars.values():
            var.set(value)
        self._refresh_chips()

    def _projects_ivs(self):
        for proj, var in self.proj_vars.items():
            var.set(proj == WORK_PROJECT)
        self._refresh_chips()

    def _refresh_chips(self):
        for chip in self.proj_frame.winfo_children():
            chip.render()
        self._projects_changed()

    def _remerge(self):
        if self.entries:
            derive_fields(self.entries, self.merge_var.get())
            self._projects_changed()

    def _fill_list(self, listbox, scope, keyfn):
        keep = set(self._selected(listbox))
        agg = aggregate(scope, keyfn)
        items = sorted(agg.items(), key=lambda kv: -kv[1][0])
        listbox.delete(0, 'end')
        listbox.names = []
        for i, (name, (hours, _n, _d)) in enumerate(items):
            listbox.insert('end', f'{name}   ·  {hours:.1f} h')
            listbox.names.append(name)
            if name in keep:
                listbox.selection_set(i)

    @staticmethod
    def _selected(listbox):
        names = getattr(listbox, 'names', [])
        return [names[i] for i in listbox.curselection() if i < len(names)]

    def _pick_month(self):
        choice = self.month_var.get()
        scope = self._project_scope() or self.entries
        if not scope:
            return
        if choice == 'All dates':
            self.from_var.set(min(e.day for e in scope).isoformat())
            self.to_var.set(max(e.day for e in scope).isoformat())
        else:
            y, m = map(int, choice.split('-'))
            first = date(y, m, 1)
            last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
            self.from_var.set(first.isoformat())
            self.to_var.set(last.isoformat())
        self.apply()

    def _last_days(self, days):
        scope = self._project_scope() or self.entries
        if not scope:
            return
        last = max(e.day for e in scope)
        self.month_var.set('All dates')
        self.from_var.set((last - timedelta(days=days - 1)).isoformat())
        self.to_var.set(last.isoformat())
        self.apply()

    def _date_bounds(self):
        bounds = []
        for var, entry, fallback in ((self.from_var, self.from_entry, date.min),
                                     (self.to_var, self.to_entry, date.max)):
            text = var.get().strip()
            try:
                bounds.append(datetime.strptime(text, '%Y-%m-%d').date() if text else fallback)
                entry.config(highlightbackground=BORDER)
            except ValueError:
                bounds.append(fallback)
                entry.config(highlightbackground=RED)
        return bounds

    def reset_filters(self):
        for var in self.wd_vars:
            var.set(True)
        for listbox in (self.cat_list, self.client_list):
            listbox.selection_clear(0, 'end')
        self.search_var.set('')
        self.month_var.set('All dates')
        if self.entries:
            self._projects_ivs() if WORK_PROJECT in self.proj_vars else self._projects_set(True)
            self._pick_month()
        # Weekday chips need repainting after their vars changed.
        for w in self.side_canvas.winfo_children()[0].winfo_children():
            for chip in w.winfo_children():
                if isinstance(chip, Chip):
                    chip.render()

    def _debounce_apply(self):
        if self._apply_job:
            self.root.after_cancel(self._apply_job)
        self._apply_job = self.root.after(250, self.apply)

    def apply(self):
        self._apply_job = None
        if not self.entries:
            self.view = []
            self._update_kpis()
            self.dirty = set(self.TABS)
            self.render_tab(self.tab)
            return
        d0, d1 = self._date_bounds()
        weekdays = {i for i, v in enumerate(self.wd_vars) if v.get()}
        cats = set(self._selected(self.cat_list))
        clients = set(self._selected(self.client_list))
        query = self.search_var.get().strip().lower()
        self.view = [e for e in self._project_scope()
                     if d0 <= e.day <= d1 and e.day.weekday() in weekdays
                     and (not cats or e.cat in cats) and (not clients or e.who in clients)
                     and (not query or query in e.desc.lower())]
        self._update_kpis()
        self.dirty = set(self.TABS)
        self.render_tab(self.tab)

    # ----- colours -------------------------------------------------------
    def _compute_colors(self, scope):
        """Colour follows the entity: slots are ranked on the project scope only,
        so date/category/client filters never repaint surviving series."""
        self.colors = {}
        for dim in COLOR_DIMS:
            fn = DIMENSIONS[dim]
            agg = aggregate(scope, fn)
            ranked = [k for k, _ in sorted(agg.items(), key=lambda kv: -kv[1][0])
                      if not k.startswith('Unassigned')]
            slots = len(SERIES) if len(ranked) <= len(SERIES) else len(SERIES) - 1
            self.colors[dim] = {name: SERIES[i] for i, name in enumerate(ranked[:slots])}

    def color_for(self, dim, name):
        if name.startswith('Unassigned'):
            return UNASSIGNED
        return self.colors.get(dim, {}).get(name, OTHER)

    def series_name(self, dim, name):
        """Name used for stacking: entities without a slot fold into 'Other'."""
        if name.startswith('Unassigned') or name in self.colors.get(dim, {}):
            return name
        return 'Other'

    def series_order(self, dim, names):
        slots = list(self.colors.get(dim, {}))
        return sorted(names, key=lambda n: (slots.index(n) if n in slots else
                                            len(slots) + (1 if n == 'Other' else 0), n))

    # ----- KPIs ----------------------------------------------------------
    def _update_kpis(self):
        v = self.view
        hours = sum(e.hours for e in v)
        days = len({e.day for e in v})
        ivs = [e for e in v if e.project == WORK_PROJECT]
        values = {
            'Hours': (f'{hours:,.1f}', f'across {len({e.day.strftime("%Y-%m") for e in v})} month(s)' if v else ''),
            'Days tracked': (f'{days}', self._span_text(v)),
            'Avg / tracked day': (f'{hours / days:.1f} h' if days else '—', 'days with at least one entry'),
            'Entries': (f'{len(v):,}', f'{len(v) / days:.1f} per day' if days else ''),
            'Median entry': (f'{statistics.median(e.hours for e in v) * 60:.0f} min' if v else '—',
                             f'longest {max(e.hours for e in v):.1f} h' if v else ''),
        }
        if ivs:
            ivs_h = sum(e.hours for e in ivs)
            mapped = sum(e.hours for e in ivs if not e.domain.startswith('Unassigned'))
            values['NetSuite draft-mapped'] = (f'{100 * mapped / ivs_h:.0f}%',
                                               f'{ivs_h - mapped:.1f} h of IVS still unassigned')
        else:
            values['NetSuite draft-mapped'] = ('—', 'no IVS entries in view')
        for key, (val, sub) in values.items():
            self.kpis[key][0].config(text=val)
            self.kpis[key][1].config(text=sub)

    @staticmethod
    def _span_text(v):
        if not v:
            return ''
        first, last = min(e.day for e in v), max(e.day for e in v)
        return f'{first:%b %d} – {last:%b %d, %Y}'

    # ----- rendering -----------------------------------------------------
    def render_tab(self, name):
        self.dirty.discard(name)
        if name == 'Overview':
            self._redraw_overview()
        elif name == 'Day report':
            self.render_dayreport()
        elif name == 'Timeline':
            for chart in (self.tl_legend, self.tl_head, self.tl_body):
                chart.redraw()
        elif name == 'Heatmap':
            self.hm_chart.redraw()
        elif name == 'Breakdown':
            self.render_breakdown()
        elif name == 'Entries':
            self.render_entries()

    def _redraw_overview(self):
        self.bar_chart.redraw()
        self.time_chart.redraw()

    def _empty(self, c, text='No entries match the current filters.'):
        if not self.entries:
            text = 'No data loaded — pick month(s) in DATA FILES and press Load selected, or Browse…'
        c.create_text(c.winfo_width() / 2, c.winfo_height() / 2, text=text, fill=MUTED, font=(FONT, 10))

    def _legend(self, c, dim, names, x, y):
        """Legend — always shown for >= 2 series so identity is never colour-alone.
        Wraps onto extra lines; returns the y of its last line."""
        if len(names) < 2:
            return y
        x0 = x
        for name in names:
            label = self._clip(name, 180)
            width = 30 + self.font_small.measure(label)
            if x > x0 and x + width > c.winfo_width() - 8:
                x, y = x0, y + 18
            c.create_rectangle(x, y - 5, x + 10, y + 5, fill=self.color_for(dim, name) if name != 'Other' else OTHER,
                               outline='')
            c.create_text(x + 15, y, text=label, anchor='w', fill=TEXT2, font=self.font_small)
            x += width
        return y

    def _clip(self, text, width, font=None):
        font = font or self.font
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + '…') > width:
            text = text[:-1]
        return text + '…'

    def draw_bars(self, c):
        dim = self.bar_dim.get()
        self.bar_title.config(text=f'Hours by {dim}')
        entries = [e for e in self.view if not (dim == 'Study' and not e.study)]
        if not entries:
            return self._empty(c)
        W, H = c.winfo_width(), c.winfo_height()
        total = sum(e.hours for e in entries)
        agg = sorted(aggregate(entries, DIMENSIONS[dim]).items(), key=lambda kv: -kv[1][0])
        row_h = 24
        rows = max(1, int((H - 10) // row_h))
        if len(agg) > rows:
            rest = agg[rows - 1:]
            other = [sum(a[0] for _, a in rest), sum(a[1] for _, a in rest), set()]
            agg = agg[:rows - 1] + [(f'Other ({len(rest)})', other)]
        label_w = min(int(W * 0.34), max(self.font.measure(n) for n, _ in agg) + 12)
        value_w = 120
        bar_x0 = 12 + label_w
        avail = max(20, W - bar_x0 - value_w - 12)
        top = max(a[0] for _, a in agg)
        colored = dim in COLOR_DIMS and dim == self.color_var.get()
        for i, (name, (hours, count, days)) in enumerate(agg):
            y = 6 + i * row_h
            cy = y + row_h / 2
            c.create_text(bar_x0 - 10, cy, text=self._clip(name, label_w - 8), anchor='e', fill=TEXT2, font=self.font)
            length = max(2, hours / top * avail)
            fill = (self.color_for(dim, name) if colored else SERIES[0]) if not name.startswith('Other (') else OTHER
            hit = c.create_rectangle(bar_x0, y + 5, bar_x0 + length, y + row_h - 5, fill=fill, outline='')
            c.create_text(bar_x0 + length + 8, cy, text=f'{hours:.1f} h  ·  {100 * hours / total:.1f}%',
                          anchor='w', fill=TEXT, font=self.font)
            day_txt = f', {len(days)} day(s)' if days else ''
            c.tip(hit, f'{name}\n{hours:.2f} h  ·  {100 * hours / total:.1f}% of view\n{count} entries{day_txt}')

    def _bucket(self, d, mode):
        if mode == 'Week':
            return d - timedelta(days=d.weekday())
        if mode == 'Month':
            return d.replace(day=1)
        return d

    def draw_time(self, c):
        mode = self.bucket_var.get()
        dim = self.color_var.get()
        self.time_title.config(text=f'Hours per {mode.lower()} · coloured by {dim}')
        if not self.view:
            return self._empty(c)
        W, H = c.winfo_width(), c.winfo_height()
        fn = DIMENSIONS[dim]
        data = defaultdict(lambda: defaultdict(float))
        for e in self.view:
            data[self._bucket(e.day, mode)][self.series_name(dim, fn(e))] += e.hours
        first, last = min(data), max(data)
        buckets, b = [], first
        while b <= last:
            buckets.append(b)
            if mode == 'Day':
                b += timedelta(days=1)
            elif mode == 'Week':
                b += timedelta(weeks=1)
            else:
                b = date(b.year + (b.month == 12), b.month % 12 + 1, 1)
        series = self.series_order(dim, {s for v in data.values() for s in v})
        legend_end = self._legend(c, dim, series, 56, 12)

        left, right, top, bottom = 50, 16, legend_end + 18, 26
        pw, ph = W - left - right, H - top - bottom
        totals = [sum(data[b].values()) for b in buckets]
        ymax = nice_max(max(totals))
        for i in range(5):
            val = ymax * i / 4
            y = top + ph - ph * i / 4
            c.create_line(left, y, left + pw, y, fill=GRID if i else BORDER)
            c.create_text(left - 8, y, text=f'{val:g} h', anchor='e', fill=MUTED, font=self.font_small)
        slot = pw / len(buckets)
        bw = max(2, min(46, slot * 0.72))
        step = max(1, math.ceil(len(buckets) / max(1, pw // 70)))
        fmt = {'Day': '%b %d', 'Week': 'wk %b %d', 'Month': '%b %Y'}[mode]
        for i, b in enumerate(buckets):
            x = left + slot * i + (slot - bw) / 2
            y = top + ph
            stack = data.get(b, {})
            for s in series:
                h = stack.get(s, 0)
                if not h:
                    continue
                seg = ph * h / ymax
                gap = 2 if seg > 4 else 0
                item = c.create_rectangle(x, y - seg + gap, x + bw, y,
                                          fill=self.color_for(dim, s) if s != 'Other' else OTHER, outline='')
                c.tip(item, f'{b.strftime(fmt)}\n{s}: {h:.2f} h\nTotal: {totals[i]:.2f} h')
                y -= seg
            if i % step == 0:
                c.create_text(left + slot * i + slot / 2, top + ph + 13, text=b.strftime(fmt),
                              fill=MUTED, font=self.font_small)
        active = [t for t in totals if t > 0]
        if active:
            avg = sum(active) / len(active)
            y = top + ph - ph * avg / ymax
            c.create_line(left, y, left + pw, y, fill=AMBER, dash=(4, 4))
            c.create_text(left + pw - 4, y - 8, text=f'avg {avg:.1f} h per active {mode.lower()}',
                          anchor='e', fill=AMBER, font=self.font_small)

    # Timeline -------------------------------------------------------------
    def _tl_hours(self):
        mode = self.tl_range.get()
        if mode == 'Full day' or not self.view:
            return 0, 24
        if mode == 'Work 6–20':
            return 6, 20
        lo = min(e.start.hour for e in self.view)
        hi = max(min(24, (e.end - datetime.combine(e.day, datetime.min.time())).total_seconds() / 3600)
                 for e in self.view)
        lo, hi = max(0, lo), min(24, math.ceil(hi))
        return lo, max(hi, lo + 1)

    def _tl_geometry(self, c):
        h0, h1 = self._tl_hours()
        left, right = 118, 70
        pw = max(50, c.winfo_width() - left - right)
        return h0, h1, left, pw

    def draw_tl_legend(self, c):
        dim = self.color_var.get()
        names = self.series_order(dim, {self.series_name(dim, DIMENSIONS[dim](e)) for e in self.view})
        end = self._legend(c, dim, names, 8, 12)
        if int(c.cget('height')) != end + 12:
            c.configure(height=end + 12)

    def draw_tl_head(self, c):
        if not self.view:
            return
        h0, h1, left, pw = self._tl_geometry(c)
        for h in range(h0, h1 + 1):
            x = left + pw * (h - h0) / (h1 - h0)
            c.create_text(x, 11, text=f'{h:02d}:00' if (h1 - h0) <= 16 or h % 2 == 0 else '',
                          fill=MUTED, font=self.font_small)

    def draw_tl_body(self, c):
        dim = self.color_var.get()
        self.tl_title.config(text=f'When each entry happened · coloured by {dim}')
        if not self.view:
            c.configure(scrollregion=(0, 0, 0, 0))
            return self._empty(c)
        h0, h1, left, pw = self._tl_geometry(c)
        span = h1 - h0
        by_day = defaultdict(list)
        for e in self.view:
            by_day[e.day].append(e)
        days = sorted(by_day)
        row_h = 26
        height = row_h * len(days) + 4
        fn = DIMENSIONS[dim]
        for i, d in enumerate(days):
            y = 2 + i * row_h
            c.create_rectangle(0, y, left + pw + 70, y + row_h, fill=CARD if i % 2 else PANEL, outline='')
        for h in range(h0, h1 + 1):
            x = left + pw * (h - h0) / span
            c.create_line(x, 0, x, height, fill=BORDER if h % 3 == 0 else GRID)
        for i, d in enumerate(days):
            y = 2 + i * row_h
            weekend = d.weekday() >= 5
            c.create_text(8, y + row_h / 2, text=f'{d:%a}  {d.isoformat()}', anchor='w',
                          fill=MUTED if weekend else TEXT2, font=self.font)
            midnight = datetime.combine(d, datetime.min.time())
            day_total = 0.0
            for e in by_day[d]:
                day_total += e.hours
                a = (e.start - midnight).total_seconds() / 3600
                b = (e.end - midnight).total_seconds() / 3600
                a, b = max(a, h0), min(b, h1)
                if b <= a:
                    continue
                x0 = left + pw * (a - h0) / span
                x1 = max(x0 + 2, left + pw * (b - h0) / span - 1)
                name = self.series_name(dim, fn(e))
                item = c.create_rectangle(x0, y + 4, x1, y + row_h - 4,
                                          fill=self.color_for(dim, name) if name != 'Other' else OTHER, outline='')
                c.tip(item, f'{e.desc or "(no description)"}\n'
                            f'{e.start:%a %b %d}  {e.start:%H:%M}–{e.end:%H:%M}  ({e.hours:.2f} h)\n'
                            f'Project: {e.project}   ·   NetSuite (draft): {e.domain}')
            c.create_text(left + pw + 62, y + row_h / 2, text=f'{day_total:.1f} h', anchor='e',
                          fill=TEXT, font=self.font)
        c.configure(scrollregion=(0, 0, c.winfo_width(), height))

    # Heatmap --------------------------------------------------------------
    def draw_heatmap(self, c):
        avg = self.hm_mode.get() == 'Average per week'
        if not self.view:
            return self._empty(c)
        grid = [[0.0] * 24 for _ in range(7)]
        for e in self.view:
            t = e.start
            while t < e.end:
                slot_end = min(e.end, t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                grid[t.weekday()][t.hour] += (slot_end - t).total_seconds() / 3600
                t = slot_end
        weeks = 1
        if avg:
            first, last = min(e.day for e in self.view), max(e.day for e in self.view)
            weeks = max(1, ((last - first).days + 1) / 7)
            grid = [[v / weeks for v in row] for row in grid]
        self.hm_title.config(text='Hours by weekday and hour of day' +
                             (f' · average over {weeks:.1f} weeks' if avg else ' · total'))
        W, H = c.winfo_width(), c.winfo_height()
        left, right, top, bottom = 56, 80, 30, 60
        cw = (W - left - right) / 24
        ch = min(64, (H - top - bottom) / 7)
        vmax = max(max(r) for r in grid) or 1
        for h in range(24):
            c.create_text(left + cw * h + cw / 2, top - 12, text=f'{h:02d}', fill=MUTED, font=self.font_small)
        for d in range(7):
            y = top + d * ch
            c.create_text(left - 10, y + ch / 2, text=WEEKDAYS[d], anchor='e', fill=TEXT2, font=self.font)
            for h in range(24):
                v = grid[d][h]
                x = left + cw * h
                if v <= 0:
                    fill = CARD
                else:
                    fill = SEQ[min(len(SEQ) - 1, int(v / vmax * (len(SEQ) - 1) + 0.5))]
                item = c.create_rectangle(x + 1, y + 1, x + cw - 1, y + ch - 1, fill=fill, outline='')
                c.tip(item, f'{WEEKDAYS[d]} {h:02d}:00–{h + 1:02d}:00\n'
                            f'{v:.2f} h' + (' per week (avg)' if avg else ' total'))
                if v >= 0.05 and cw >= 30 and ch >= 22:
                    light = fill in SEQ[-3:]
                    c.create_text(x + cw / 2, y + ch / 2, text=f'{v:.1f}', fill=BG if light else TEXT,
                                  font=self.font_small)
            c.create_text(left + cw * 24 + 12, y + ch / 2, text=f'{sum(grid[d]):.1f} h', anchor='w',
                          fill=TEXT, font=self.font)
        # Ramp legend.
        ly = top + 7 * ch + 26
        c.create_text(left, ly, text='less', anchor='w', fill=MUTED, font=self.font_small)
        for i, col in enumerate(SEQ):
            c.create_rectangle(left + 34 + i * 22, ly - 6, left + 54 + i * 22, ly + 6, fill=col, outline='')
        c.create_text(left + 40 + len(SEQ) * 22, ly, text=f'more  (max {vmax:.1f} h)', anchor='w',
                      fill=MUTED, font=self.font_small)

    # Breakdown ------------------------------------------------------------
    def render_breakdown(self):
        tree = self.bd_tree
        tree.delete(*tree.get_children())
        group, then = self.bd_group.get(), self.bd_then.get()
        self.bd_title.config(text=f'{group}' + (f' → {then}' if then != '(none)' else ''))
        if not self.view:
            return
        total = sum(e.hours for e in self.view)
        col, desc = self.bd_sort
        top = aggregate(self.view, DIMENSIONS[group])

        def row_values(a):
            hours, n, days = a
            return (f'{hours:.2f}', f'{100 * hours / total:.1f}', n, len(days), f'{hours * 60 / n:.0f}')

        def order(items):
            idx = {'#0': None, 'hours': 0, 'pct': 0, 'entries': 1, 'days': 2, 'avg': 3}[col]
            if idx is None:
                return sorted(items, key=lambda kv: kv[0].lower(), reverse=desc)
            key = {0: lambda kv: kv[1][0], 1: lambda kv: kv[1][1], 2: lambda kv: len(kv[1][2]),
                   3: lambda kv: kv[1][0] / kv[1][1]}[idx]
            return sorted(items, key=key, reverse=desc)

        for name, a in order(top.items()):
            parent = tree.insert('', 'end', text=name, values=row_values(a))
            if then != '(none)' and then != group:
                sub = aggregate([e for e in self.view if DIMENSIONS[group](e) == name], DIMENSIONS[then])
                for sname, sa in order(sub.items()):
                    tree.insert(parent, 'end', text=sname, values=row_values(sa), tags=('child',))
        days = len({e.day for e in self.view})
        tree.insert('', 'end', text='Total', values=(f'{total:.2f}', '100.0', len(self.view), days,
                                                      f'{total * 60 / len(self.view):.0f}'), tags=('total',))

    def _sort_breakdown(self, col):
        cur, desc = self.bd_sort
        self.bd_sort = (col, not desc if col == cur else col != '#0')
        self.render_breakdown()

    def _tree_open(self, state, tree=None):
        tree = tree or self.bd_tree
        for item in tree.get_children():
            tree.item(item, open=state)

    # Day report (same logic as menu option 5) -------------------------------
    def dayreport_rows(self):
        """Per day: (date, total hours, total window, [(key, hours, pct, window), ...]).

        Mirrors zToggl.py option 5: entries grouped by 'Client - Category'
        (plus ' - Study' for Study entries), sorted by hours; each group's
        suggested window starts at its earliest start, and anything before
        06:00 is moved to the day's earliest start after 06:00.
        """
        six = datetime.min.time().replace(hour=6)
        by_day = defaultdict(lambda: defaultdict(list))
        skipped = 0
        for e in self.view:
            if len(e.raw_parts) < 2:
                skipped += 1
                continue
            key = f'{e.who} - {e.cat}'
            if e.cat.lower() == 'study' and e.detail:
                key += f' - {e.detail}'
            by_day[e.day][key].append(e)
        days = []
        for d in sorted(by_day):
            groups = by_day[d]
            all_entries = [e for g in groups.values() for e in g]
            total = sum(e.hours for e in all_entries)
            after_six = [e.start for e in all_entries if e.start.time() >= six]
            anchor = min(after_six) if after_six else datetime.combine(d, six)
            rows = []
            for key, group in sorted(groups.items(), key=lambda kv: -sum(e.hours for e in kv[1])):
                hours = sum(e.hours for e in group)
                start = min(e.start for e in group)
                if start.time() < six:
                    start = anchor
                end = start + timedelta(hours=hours)
                rows.append((key, hours, 100 * hours / total if total else 0, f'{start:%H:%M}-{end:%H:%M}'))
            total_window = f'{anchor:%H:%M}-{anchor + timedelta(hours=total):%H:%M}'
            days.append((d, total, total_window, rows))
        return days, skipped

    def render_dayreport(self):
        tree = self.dr_tree
        tree.delete(*tree.get_children())
        days, skipped = self.dayreport_rows()
        if self.dr_order.get() == 'Newest first':
            days.reverse()
        hours = sum(t for _, t, _, _ in days)
        self.dr_title.config(text=f'{len(days)} day(s) · {hours:.2f} h   (hours and windows as in menu option 5)')
        note = 'Suggested windows: each group starts at its first entry (pre-06:00 starts move to the day\'s ' \
               'first start after 06:00) and runs for its total hours, so windows can overlap.'
        if skipped:
            note += f'   {skipped} entr{"y" if skipped == 1 else "ies"} without a "Client - Category" ' \
                    'description left out, as in option 5.'
        self.dr_note.config(text=note)
        for d, total, window, rows in days:
            parent = tree.insert('', 'end', text=f'{d:%a}  {d.isoformat()}', open=True,
                                 values=(f'{total:.2f}', '100.00', window), tags=('day',))
            for key, h, pct, win in rows:
                tree.insert(parent, 'end', text=key, values=(f'{h:.2f}', f'{pct:.2f}', win), tags=('child',))

    def export_dayreport(self):
        days, _ = self.dayreport_rows()
        if not days:
            return
        path = self._save_path(f'zToggl_dayreport_{self._date_tag()}.csv')
        if not path:
            return
        # Same columns as option 5's client_hours_report.csv.
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Date', 'Client/Category/Study', 'Hours', 'Percentage', 'Suggested Time Window'])
            for d, total, window, rows in days:
                for key, h, pct, win in rows:
                    w.writerow([d.isoformat(), key, f'{h:.2f}', f'{pct:.2f}', win])
                w.writerow([d.isoformat(), 'Total', f'{total:.2f}', '100.00', window])
                w.writerow([])
        messagebox.showinfo('zToggl', f'Day report written to\n{path}')

    # Entries --------------------------------------------------------------
    ENTRY_KEYS = {
        'date': lambda e: e.start, 'dow': lambda e: e.day.weekday(), 'start': lambda e: e.start.time(),
        'end': lambda e: e.end.time(), 'hours': lambda e: e.hours, 'project': lambda e: e.project.lower(),
        'desc': lambda e: e.desc.lower(), 'cat': lambda e: e.cat.lower(), 'who': lambda e: e.who.lower(),
        'study': lambda e: e.study.lower(), 'activity': lambda e: e.activity.lower(),
        'domain': lambda e: e.domain.lower(),
    }

    def render_entries(self):
        tree = self.en_tree
        tree.delete(*tree.get_children())
        col, desc = self.en_sort
        rows = sorted(self.view, key=self.ENTRY_KEYS[col], reverse=desc)
        hours = sum(e.hours for e in rows)
        self.en_title.config(text=f'{len(rows):,} entries · {hours:.1f} h   (click a column header to sort)')
        for e in rows:
            tree.insert('', 'end', values=(e.day.isoformat(), e.day.strftime('%a'), e.start.strftime('%H:%M'),
                                           e.end.strftime('%H:%M'), f'{e.hours:.2f}', e.project, e.desc,
                                           e.cat, e.who, e.study, e.activity, e.domain))

    def _sort_entries(self, col):
        cur, desc = self.en_sort
        self.en_sort = (col, not desc if col == cur else col in ('hours',))
        self.render_entries()

    # ----- export --------------------------------------------------------
    def _save_path(self, default):
        return filedialog.asksaveasfilename(title='Export CSV', initialdir=FOLDER, initialfile=default,
                                            defaultextension='.csv', filetypes=[('CSV files', '*.csv')])

    def _date_tag(self):
        if not self.view:
            return 'empty'
        return f'{min(e.day for e in self.view):%Y%m%d}-{max(e.day for e in self.view):%Y%m%d}'

    def export_breakdown(self):
        if not self.view:
            return
        path = self._save_path(f'zToggl_breakdown_{self._date_tag()}.csv')
        if not path:
            return
        then = self.bd_then.get()
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow([self.bd_group.get(), then if then != '(none)' else '', 'Hours', '% of view',
                        'Entries', 'Days', 'Avg entry (min)'])
            for item in self.bd_tree.get_children():
                name = self.bd_tree.item(item, 'text')
                w.writerow([name, ''] + list(self.bd_tree.item(item, 'values')))
                for child in self.bd_tree.get_children(item):
                    w.writerow([name, self.bd_tree.item(child, 'text')] + list(self.bd_tree.item(child, 'values')))
        messagebox.showinfo('zToggl', f'Breakdown written to\n{path}')

    def export_entries(self):
        if not self.view:
            return
        path = self._save_path(f'zToggl_entries_{self._date_tag()}.csv')
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Date', 'Start', 'End', 'Hours', 'Project', 'Description', 'Category',
                        'Client', 'Study', 'Activity', 'NetSuite (draft)', 'Source file'])
            for e in sorted(self.view, key=lambda e: e.start):
                w.writerow([e.day.isoformat(), e.start.strftime('%H:%M:%S'), e.end.strftime('%H:%M:%S'),
                            f'{e.hours:.2f}', e.project, e.desc, e.cat, e.who, e.study, e.activity,
                            e.domain, e.source])
        messagebox.showinfo('zToggl', f'{len(self.view)} entries written to\n{path}')


def run(files=None):
    """Open the dashboard window; returns when it is closed."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp text on scaled displays
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    app = App(root)
    if files:
        root.after(100, lambda: app.load_files(files))
    root.mainloop()


if __name__ == '__main__':
    run()
