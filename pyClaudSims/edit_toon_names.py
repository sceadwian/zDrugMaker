"""
edit_toon_names.py — Interactive editor for toon_names.csv

Three independent name pools:
  male_first_name | female_first_name | last_name

Operations: add / remove / rename (edit) entries in any pool.
File is always rewritten sorted and deduplicated on save.
"""

import csv
import os
import sys

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NAMES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toon_names.csv")

POOLS = {
    "m": ("Male first names",   "male_first_name"),
    "f": ("Female first names", "female_first_name"),
    "l": ("Last names",         "last_name"),
}

# ---------------------------------------------------------------------------
# ANSI colour helpers (gracefully disabled if not supported)
# ---------------------------------------------------------------------------
_USE_COLOR = False
_CODES = {
    "reset":  "\x1b[0m",
    "bold":   "\x1b[1m",
    "dim":    "\x1b[2m",
    "cyan":   "\x1b[36m",
    "green":  "\x1b[32m",
    "yellow": "\x1b[33m",
    "red":    "\x1b[31m",
    "grey":   "\x1b[90m",
    "white":  "\x1b[97m",
}

def _enable_color():
    global _USE_COLOR
    if os.environ.get("NO_COLOR"):
        return
    if sys.platform == "win32":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            handle = k32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if k32.GetConsoleMode(handle, ctypes.byref(mode)):
                k32.SetConsoleMode(handle, mode.value | 4)
                _USE_COLOR = True
        except Exception:
            pass
    else:
        _USE_COLOR = sys.stdout.isatty()

def col(text, *styles):
    if not _USE_COLOR or not styles:
        return str(text)
    pre = "".join(_CODES.get(s, "") for s in styles)
    return f"{pre}{text}{_CODES['reset']}" if pre else str(text)

def rule(char="─", width=60):
    try:
        char.encode(sys.stdout.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        char = "-"
    print(col(char * width, "dim"))

def header(title):
    rule()
    print(col(f"  {title}", "bold", "cyan"))
    rule()

# ---------------------------------------------------------------------------
# CSV load / save  (mirrors pySimBlockchainCldSocial.py exactly)
# ---------------------------------------------------------------------------
def load_pools():
    """Return (male_set, female_set, last_set)."""
    male, female, lasts = set(), set(), set()
    if not os.path.exists(NAMES_CSV):
        return male, female, lasts
    try:
        with open(NAMES_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                m   = (row.get("male_first_name")   or "").strip()
                fem = (row.get("female_first_name") or "").strip()
                ln  = (row.get("last_name")         or "").strip()
                if m:   male.add(m)
                if fem: female.add(fem)
                if ln:  lasts.add(ln)
                # Legacy single-column format: treat as unisex.
                legacy = (row.get("first_name") or "").strip()
                if legacy:
                    male.add(legacy)
                    female.add(legacy)
    except (OSError, csv.Error) as e:
        print(col(f"  Could not read {NAMES_CSV}: {e}", "red"))
    return male, female, lasts


def save_pools(male, female, lasts):
    """Rewrite CSV sorted and deduplicated."""
    m_sorted = sorted(male,   key=str.casefold)
    f_sorted = sorted(female, key=str.casefold)
    l_sorted = sorted(lasts,  key=str.casefold)
    rows = max(len(m_sorted), len(f_sorted), len(l_sorted), 1)
    try:
        with open(NAMES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["male_first_name", "female_first_name", "last_name"])
            for i in range(rows):
                writer.writerow([
                    m_sorted[i] if i < len(m_sorted) else "",
                    f_sorted[i] if i < len(f_sorted) else "",
                    l_sorted[i] if i < len(l_sorted) else "",
                ])
        print(col(f"  Saved to {NAMES_CSV}", "green"))
    except OSError as e:
        print(col(f"  Could not write {NAMES_CSV}: {e}", "red"))

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def _pool_set(pools, key):
    """Return the set corresponding to a pool key m/f/l."""
    if key == "m": return pools[0]
    if key == "f": return pools[1]
    return pools[2]

def show_pool(pool_set, label, search=None):
    """Print a numbered list of names in the pool, optionally filtered."""
    names = sorted(pool_set, key=str.casefold)
    filtered = [(i + 1, n) for i, n in enumerate(names)
                if search is None or search.lower() in n.lower()]
    if not filtered:
        print(col(f"  (no entries{' matching' if search else ''})", "dim"))
        return []
    print(col(f"\n  {label}  ({len(pool_set)} total):", "bold"))
    cols = 4
    for chunk_start in range(0, len(filtered), cols):
        chunk = filtered[chunk_start:chunk_start + cols]
        row_parts = []
        for idx, name in chunk:
            entry = col(f"{idx:>3}.", "grey") + " " + col(name, "white")
            row_parts.append(f"{entry:<26}")
        print("  " + "  ".join(row_parts))
    return [name for _, name in filtered]

def show_summary(pools):
    male, female, lasts = pools
    print(col(f"\n  Pools  ->  "
              f"Male first: {col(len(male), 'cyan')}  "
              f"Female first: {col(len(female), 'cyan')}  "
              f"Last: {col(len(lasts), 'cyan')}",
              "bold"))

# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""

def pick_pool(prompt="  Pool (m=male / f=female / l=last / blank=cancel): "):
    key = ask(prompt).lower()
    if key not in POOLS:
        if key:
            print(col("  Invalid pool key.", "yellow"))
        return None
    return key


def op_add(pools):
    key = pick_pool()
    if key is None:
        return
    pool = _pool_set(pools, key)
    label = POOLS[key][0]
    raw = ask(f"  Add to {col(label, 'cyan')} (comma-separated): ")
    if not raw:
        return
    added = 0
    for name in raw.split(","):
        name = name.strip()
        if not name:
            continue
        if name in pool:
            print(col(f"  '{name}' already exists — skipped.", "yellow"))
        else:
            pool.add(name)
            print(col(f"  + {name}", "green"))
            added += 1
    if added:
        save_pools(*pools)


def op_remove(pools):
    key = pick_pool()
    if key is None:
        return
    pool = _pool_set(pools, key)
    label = POOLS[key][0]
    search = ask(f"  Search {col(label, 'cyan')} (blank = show all): ") or None
    visible = show_pool(pool, label, search)
    if not visible:
        return
    raw = ask("  Name(s) to remove (comma-separated, or blank to cancel): ")
    if not raw:
        return
    for name in raw.split(","):
        name = name.strip()
        if name in pool:
            pool.discard(name)
            print(col(f"  - {name}", "red"))
        else:
            print(col(f"  '{name}' not found.", "yellow"))
    save_pools(*pools)


def op_edit(pools):
    key = pick_pool()
    if key is None:
        return
    pool = _pool_set(pools, key)
    label = POOLS[key][0]
    search = ask(f"  Search {col(label, 'cyan')} (blank = show all): ") or None
    visible = show_pool(pool, label, search)
    if not visible:
        return
    old = ask("  Name to rename (exact, or blank to cancel): ").strip()
    if not old:
        return
    if old not in pool:
        print(col(f"  '{old}' not found.", "yellow"))
        return
    new = ask(f"  Rename '{old}' to: ").strip()
    if not new:
        return
    if new in pool:
        print(col(f"  '{new}' already exists — rename skipped.", "yellow"))
        return
    pool.discard(old)
    pool.add(new)
    print(col(f"  {old}  ->  {new}", "green"))
    save_pools(*pools)


def op_view(pools):
    key = pick_pool("  Pool to view (m / f / l / blank=all): ")
    if key is None:
        # Show all three.
        for k, (label, _) in POOLS.items():
            show_pool(_pool_set(pools, k), label)
        return
    label = POOLS[key][0]
    search = ask(f"  Search filter (blank = show all): ") or None
    show_pool(_pool_set(pools, key), label, search)


def op_move(pools):
    """Move a first name from one sex pool to the other."""
    print("  Move a first name between male and female pools.")
    src_key = ask("  Source pool (m=male / f=female / blank=cancel): ").lower()
    if src_key not in ("m", "f"):
        if src_key:
            print(col("  Must be m or f.", "yellow"))
        return
    dst_key = "f" if src_key == "m" else "m"
    src = _pool_set(pools, src_key)
    dst = _pool_set(pools, dst_key)
    src_label = POOLS[src_key][0]
    dst_label = POOLS[dst_key][0]
    search = ask(f"  Search {col(src_label, 'cyan')} (blank = show all): ") or None
    show_pool(src, src_label, search)
    raw = ask("  Name(s) to move (comma-separated, or blank to cancel): ")
    if not raw:
        return
    moved = 0
    for name in raw.split(","):
        name = name.strip()
        if name in src:
            src.discard(name)
            dst.add(name)
            print(col(f"  {src_label} -> {dst_label}: {name}", "green"))
            moved += 1
        else:
            print(col(f"  '{name}' not in {src_label}.", "yellow"))
    if moved:
        save_pools(*pools)

# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------
MENU = [
    ("v", "View pool",                   op_view),
    ("a", "Add name(s)",                 op_add),
    ("r", "Remove name(s)",              op_remove),
    ("e", "Edit / rename a name",        op_edit),
    ("x", "Move first name M <-> F",     op_move),
    ("q", "Quit",                        None),
]

def main():
    _enable_color()
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    header("Toon Names CSV Editor")
    print(col(f"  File: {NAMES_CSV}", "dim"))

    pools = list(load_pools())  # [male_set, female_set, last_set]
    if not any(pools):
        print(col("  (File not found or empty — starting with empty pools)", "yellow"))

    while True:
        show_summary(pools)
        rule()
        for key, desc, _ in MENU:
            print(f"  {col(f'[{key}]', 'bold', 'cyan')}  {desc}")
        rule()

        try:
            choice = ask(col("> ", "bold")).lower()
        except (EOFError, KeyboardInterrupt):
            print(col("\n  Bye.", "dim"))
            break
        print()

        if choice == "":
            continue
        matched = [(k, fn) for k, _, fn in MENU if k == choice]
        if not matched:
            print(col("  Unrecognised option.", "yellow"))
            continue
        key, fn = matched[0]
        if fn is None:
            print(col("  Bye.", "dim"))
            break
        fn(pools)
        print()


if __name__ == "__main__":
    main()
