"""
zFolderAudit.py
---------------
A terminal-based folder archaeology tool.
Scans the directory where this script lives and all subdirectories.
Uses only the Python 3 standard library — no installs required.

Run: python zFolderAudit.py
"""

import os
import sys
import datetime
import collections
import pathlib
import shutil

# ─────────────────────────────────────────────
# CONFIG — edit these at the top of the file
# ─────────────────────────────────────────────
SKIP_FOLDERS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "$RECYCLE.BIN",
    "System Volume Information",
}

PAGE_SIZE = 50          # files shown per page in file listings
SCAN_PROGRESS_EVERY = 100   # print progress every N folders during scan

# ─────────────────────────────────────────────
# COLOUR HELPERS (Windows 10+ ANSI support)
# ─────────────────────────────────────────────
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
MAGENTA= "\033[35m"
DIM    = "\033[2m"
RED    = "\033[31m"

def c(text, colour): return f"{colour}{text}{RESET}"
def banner(text):
    width = min(shutil.get_terminal_size().columns, 80)
    print()
    print(c("─" * width, CYAN))
    print(c(f"  {text}", BOLD + CYAN))
    print(c("─" * width, CYAN))

def divider():
    width = min(shutil.get_terminal_size().columns, 80)
    print(c("─" * width, DIM))

# ─────────────────────────────────────────────
# SIZE FORMATTING
# ─────────────────────────────────────────────
def fmt_size(n_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024:
            return f"{n_bytes:,.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:,.1f} PB"

# ─────────────────────────────────────────────
# SCAN ENGINE
# ─────────────────────────────────────────────
class FolderIndex:
    """Holds a single in-memory scan of the root directory."""

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.scan_time = datetime.datetime.now()
        # {abs_path_str: {"parent", "children", "files":[{name,size,mtime,ext}]}}
        self.folders: dict = {}
        self.total_files = 0
        self.total_size = 0
        self.ext_counter = collections.Counter()

    def scan(self):
        """Walk the tree once and build the index."""
        print()
        print(c("  Scanning …  (this may take a moment for large trees)", YELLOW))
        print()

        folder_count = 0
        root_str = str(self.root)

        for dirpath, dirnames, filenames in os.walk(self.root, topdown=True):
            # Skip unwanted folders in-place so os.walk won't descend into them
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_FOLDERS and not d.startswith(".")
            ]
            dirnames.sort()

            abs_dir = pathlib.Path(dirpath)
            abs_dir_str = str(abs_dir)

            child_strs = [str(abs_dir / d) for d in dirnames]

            files_data = []
            for fname in sorted(filenames):
                fpath = abs_dir / fname
                try:
                    stat = fpath.stat()
                    size = stat.st_size
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                    ext = fpath.suffix.lower() if fpath.suffix else "(none)"
                except OSError:
                    size, mtime, ext = 0, datetime.datetime.min, "(error)"
                files_data.append({
                    "name": fname,
                    "path": str(fpath),
                    "size": size,
                    "mtime": mtime,
                    "ext": ext,
                })
                self.total_files += 1
                self.total_size += size
                self.ext_counter[ext] += 1

            parent_str = str(abs_dir.parent) if abs_dir != self.root else None

            self.folders[abs_dir_str] = {
                "parent": parent_str,
                "children": child_strs,
                "files": files_data,
            }

            folder_count += 1
            if folder_count % SCAN_PROGRESS_EVERY == 0:
                print(c(
                    f"  Folders scanned: {folder_count:,}  |  "
                    f"Files found: {self.total_files:,}  |  "
                    f"Total size: {fmt_size(self.total_size)}",
                    DIM
                ), end="\r")

        print(" " * 80, end="\r")  # clear progress line
        print(c(f"  ✓ Scan complete — {folder_count:,} folders, "
                f"{self.total_files:,} files, {fmt_size(self.total_size)}", GREEN))

    # ── helpers ──────────────────────────────

    def folder_list(self):
        """Sorted list of all folder path strings."""
        return sorted(self.folders.keys())

    def children_of(self, path_str):
        return self.folders.get(path_str, {}).get("children", [])

    def files_in(self, path_str, recursive=False):
        """Return list of file dicts under path_str, optionally recursive."""
        if not recursive:
            return list(self.folders.get(path_str, {}).get("files", []))
        result = []
        for key, data in self.folders.items():
            if key == path_str or key.startswith(path_str + os.sep):
                result.extend(data["files"])
        return result

    def folder_size(self, path_str):
        total = 0
        for key, data in self.folders.items():
            if key == path_str or key.startswith(path_str + os.sep):
                for f in data["files"]:
                    total += f["size"]
        return total

    def folder_file_count(self, path_str):
        total = 0
        for key, data in self.folders.items():
            if key == path_str or key.startswith(path_str + os.sep):
                total += len(data["files"])
        return total


# ─────────────────────────────────────────────
# FOLDER TREE PRINTER
# ─────────────────────────────────────────────
def print_tree(index: FolderIndex, path_str: str, prefix="", depth=0, max_depth=None):
    children = index.children_of(path_str)
    for i, child in enumerate(children):
        if max_depth is not None and depth >= max_depth:
            break
        is_last = (i == len(children) - 1)
        connector = "└── " if is_last else "├── "
        folder_name = pathlib.Path(child).name
        n_files = len(index.folders.get(child, {}).get("files", []))
        size = index.folder_size(child)
        info = c(f"  [{n_files} files | {fmt_size(size)}]", DIM)
        print(f"{prefix}{c(connector, DIM)}{c(folder_name, CYAN)}{info}")
        extension = "    " if is_last else "│   "
        print_tree(index, child, prefix + extension, depth + 1, max_depth)


def show_folder_tree(index: FolderIndex):
    banner("Folder Tree")
    print()
    print(c("Depth limit:", YELLOW),
          "1. Full tree   2. Depth 2   3. Depth 3   4. Depth 4")
    choice = input(c("  Choice [1–4, default=1]: ", BOLD)).strip() or "1"
    depth_map = {"1": None, "2": 2, "3": 3, "4": 4}
    max_depth = depth_map.get(choice, None)

    root_name = index.root.name or str(index.root)
    n_files = index.total_files
    root_size = fmt_size(index.total_size)
    print()
    print(c(f"  {root_name}", BOLD + CYAN),
          c(f"  [root | {n_files} total files | {root_size}]", DIM))
    print_tree(index, str(index.root), prefix="  ", max_depth=max_depth)
    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# SUMMARY STATS
# ─────────────────────────────────────────────
def show_summary(index: FolderIndex):
    banner("Summary Statistics")
    print()
    total_folders = len(index.folders)
    print(f"  {c('Root folder  :', YELLOW)} {index.root}")
    print(f"  {c('Scanned at   :', YELLOW)} {index.scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {c('Total folders:', YELLOW)} {total_folders:,}")
    print(f"  {c('Total files  :', YELLOW)} {index.total_files:,}")
    print(f"  {c('Total size   :', YELLOW)} {fmt_size(index.total_size)}")
    print()
    divider()
    print(c("  File type breakdown (top 20):", BOLD))
    print()
    print(f"  {'Extension':<15} {'Count':>8}   {'%':>6}")
    divider()
    top = index.ext_counter.most_common(20)
    for ext, count in top:
        pct = 100 * count / index.total_files if index.total_files else 0
        bar = "█" * int(pct / 2)
        print(f"  {c(ext, CYAN):<24} {count:>8,}   {pct:>5.1f}%  {c(bar, GREEN)}")
    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# FILE LISTING WITH PAGINATION
# ─────────────────────────────────────────────
def format_file_table(files):
    """Return a list of formatted strings for the file table."""
    header = (
        f"  {'File Name':<45} {'Size':>10}  {'Modified':<20}  {'Ext'}"
    )
    sep = "  " + "─" * 90
    rows = [header, sep]
    for f in files:
        name = f["name"]
        if len(name) > 44:
            name = name[:41] + "…"
        mtime = f["mtime"].strftime("%Y-%m-%d %H:%M") if f["mtime"] != datetime.datetime.min else "—"
        row = (
            f"  {c(name, GREEN):<54} {fmt_size(f['size']):>10}  "
            f"{mtime:<20}  {c(f['ext'], MAGENTA)}"
        )
        rows.append(row)
    return rows


def paginate_files(files, title="Files"):
    """Display files with paging."""
    if not files:
        print(c("  (no files here)", DIM))
        input(c("  Press Enter …", DIM))
        return

    total = len(files)
    page = 0
    while True:
        os.system("cls")
        banner(title)
        start = page * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)
        page_files = files[start:end]

        rows = format_file_table(page_files)
        for r in rows:
            print(r)

        print()
        print(c(f"  Showing {start+1}–{end} of {total} files", DIM))
        print()

        options = []
        if end < total:
            options.append("[N] Next page")
        if page > 0:
            options.append("[P] Previous page")
        options.append("[Q] Back")
        print(c("  " + "   ".join(options), YELLOW))
        choice = input(c("  > ", BOLD)).strip().upper()

        if choice == "N" and end < total:
            page += 1
        elif choice == "P" and page > 0:
            page -= 1
        elif choice == "Q" or choice == "":
            break


# ─────────────────────────────────────────────
# INTERACTIVE BROWSER
# ─────────────────────────────────────────────
def browse_folders(index: FolderIndex):
    """Navigate folders interactively."""
    current = str(index.root)
    history = []

    while True:
        os.system("cls")
        banner("Browse Folders")
        rel = os.path.relpath(current, index.root)
        rel_label = "." if rel == "." else rel
        print(f"  {c('Location:', YELLOW)} {c(rel_label, CYAN)}")
        print()

        children = index.children_of(current)
        direct_files = index.folders.get(current, {}).get("files", [])
        n_files = len(direct_files)
        total_below = index.folder_file_count(current)
        size_below = index.folder_size(current)

        print(f"  {c('Direct files:', DIM)} {n_files}   "
              f"{c('Total below:', DIM)} {total_below:,}   "
              f"{c('Size below:', DIM)} {fmt_size(size_below)}")
        print()
        divider()

        menu = []
        if children:
            print(c("  Subfolders:", BOLD))
            for i, child in enumerate(children, 1):
                cname = pathlib.Path(child).name
                cn_files = index.folder_file_count(child)
                csz = fmt_size(index.folder_size(child))
                print(f"  [{i}] {c(cname, CYAN)}  {c(f'({cn_files:,} files | {csz})', DIM)}")
                menu.append(child)
        else:
            print(c("  (no subfolders)", DIM))

        print()
        print(c("  Actions:", BOLD))
        print("  [F] List files in this folder")
        print("  [A] List ALL files below this folder (recursive)")
        if history:
            print("  [B] Go back")
        print("  [Q] Return to main menu")
        print()

        choice = input(c("  > ", BOLD)).strip().upper()

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(menu):
                history.append(current)
                current = menu[idx]
        elif choice == "F":
            paginate_files(direct_files,
                           title=f"Files in: {os.path.relpath(current, index.root)}")
        elif choice == "A":
            all_files = index.files_in(current, recursive=True)
            paginate_files(all_files,
                           title=f"All files below: {os.path.relpath(current, index.root)}")
        elif choice == "B" and history:
            current = history.pop()
        elif choice == "Q":
            break


# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────
def search_files(index: FolderIndex):
    banner("Search Filenames")
    print()
    print(c("  Search by filename (partial match) or extension (e.g. .pdf)", DIM))
    print()
    term = input(c("  Search term: ", BOLD)).strip()
    if not term:
        return

    term_lower = term.lower()
    matches = []
    for folder_str, data in index.folders.items():
        for f in data["files"]:
            if term_lower in f["name"].lower() or term_lower in f["ext"].lower():
                matches.append(f)

    os.system("cls")
    banner(f'Search Results — "{term}"')
    print()

    if not matches:
        print(c("  No matching files found.", RED))
        print()
        input(c("  Press Enter to return …", DIM))
        return

    total_size = sum(f["size"] for f in matches)
    print(f"  {c('Matches found:', YELLOW)} {len(matches):,}")
    print(f"  {c('Total size:   ', YELLOW)} {fmt_size(total_size)}")
    print()

    paginate_files(matches, title=f'Search: "{term}"')


# ─────────────────────────────────────────────
# EXPORT REPORT
# ─────────────────────────────────────────────
def tree_lines_to_text(index: FolderIndex, path_str, prefix="", depth=0, max_depth=None):
    """Recursively build plain-text tree lines for the export."""
    lines = []
    children = index.children_of(path_str)
    for i, child in enumerate(children):
        if max_depth is not None and depth >= max_depth:
            break
        is_last = (i == len(children) - 1)
        connector = "└── " if is_last else "├── "
        folder_name = pathlib.Path(child).name
        n_files = len(index.folders.get(child, {}).get("files", []))
        size = index.folder_size(child)
        lines.append(f"{prefix}{connector}{folder_name}  [{n_files} files | {fmt_size(size)}]")
        extension = "    " if is_last else "│   "
        lines.extend(tree_lines_to_text(index, child, prefix + extension, depth + 1, max_depth))
    return lines


def export_report(index: FolderIndex):
    banner("Export Report")
    print()
    print(c("  Include in report:", BOLD))
    print("  [1] Folder tree only")
    print("  [2] Folder tree + file listing for all folders")
    print("  [3] Folder tree + file listing + search results")
    print()
    choice = input(c("  Choice [1–3]: ", BOLD)).strip()

    search_results = None
    if choice == "3":
        term = input(c("  Search term to include in report: ", BOLD)).strip()
        if term:
            term_lower = term.lower()
            search_results = []
            for folder_str, data in index.folders.items():
                for f in data["files"]:
                    if term_lower in f["name"].lower() or term_lower in f["ext"].lower():
                        search_results.append(f)

    timestamp = index.scan_time.strftime("%Y-%m-%d_%H%M")
    filename = f"folder_audit_report_{timestamp}.txt"
    out_path = index.root / filename

    lines = []
    W = 90

    def rule():
        lines.append("─" * W)

    def heading(text):
        lines.append("")
        rule()
        lines.append(f"  {text}")
        rule()

    # Header
    lines.append("=" * W)
    lines.append(f"  FOLDER AUDIT REPORT")
    lines.append(f"  Generated : {index.scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Root      : {index.root}")
    lines.append("=" * W)

    # Summary
    heading("SUMMARY")
    lines.append(f"  Total folders : {len(index.folders):,}")
    lines.append(f"  Total files   : {index.total_files:,}")
    lines.append(f"  Total size    : {fmt_size(index.total_size)}")
    lines.append("")
    lines.append(f"  {'Extension':<15} {'Count':>8}   {'%':>6}")
    rule()
    for ext, count in index.ext_counter.most_common(30):
        pct = 100 * count / index.total_files if index.total_files else 0
        lines.append(f"  {ext:<15} {count:>8,}   {pct:>5.1f}%")

    # Folder tree
    heading("FOLDER TREE")
    root_name = index.root.name or str(index.root)
    lines.append(f"  {root_name}")
    lines.extend(["  " + l for l in tree_lines_to_text(index, str(index.root))])

    # File listing
    if choice in ("2", "3"):
        heading("FULL FILE LISTING")
        for folder_str in sorted(index.folders.keys()):
            files = index.folders[folder_str]["files"]
            if not files:
                continue
            rel = os.path.relpath(folder_str, index.root)
            lines.append("")
            lines.append(f"  ▶ {rel}")
            lines.append(f"  {'File Name':<45} {'Size':>10}  {'Modified':<20}  Ext")
            lines.append("  " + "─" * 86)
            for f in files:
                mtime = f["mtime"].strftime("%Y-%m-%d %H:%M") if f["mtime"] != datetime.datetime.min else "—"
                lines.append(
                    f"  {f['name']:<45} {fmt_size(f['size']):>10}  {mtime:<20}  {f['ext']}"
                )

    # Search results
    if search_results is not None:
        heading(f"SEARCH RESULTS — \"{term}\"")
        if not search_results:
            lines.append(f"  No files matched '{term}'.")
        else:
            total_sz = sum(f["size"] for f in search_results)
            lines.append(f"  Matches : {len(search_results):,}")
            lines.append(f"  Size    : {fmt_size(total_sz)}")
            lines.append("")
            lines.append(f"  {'File Name':<45} {'Size':>10}  {'Modified':<20}  Path")
            lines.append("  " + "─" * 110)
            for f in search_results:
                mtime = f["mtime"].strftime("%Y-%m-%d %H:%M") if f["mtime"] != datetime.datetime.min else "—"
                rel_path = os.path.relpath(f["path"], index.root)
                lines.append(
                    f"  {f['name']:<45} {fmt_size(f['size']):>10}  {mtime:<20}  {rel_path}"
                )

    lines.append("")
    lines.append("=" * W)
    lines.append("  END OF REPORT")
    lines.append("=" * W)

    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print()
        print(c(f"  ✓ Report saved to:", GREEN))
        print(f"    {out_path}")
    except OSError as e:
        print(c(f"  ✗ Could not write report: {e}", RED))

    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────
MENU_ITEMS = [
    ("1", "Show folder tree",                   show_folder_tree),
    ("2", "Summary statistics",                 show_summary),
    ("3", "Browse folders interactively",       browse_folders),
    ("4", "Search filenames",                   search_files),
    ("5", "Export report to .txt",              export_report),
    ("6", "Rescan directory",                   None),       # handled inline
    ("7", "Exit",                               None),
]

def main_menu(index: FolderIndex):
    while True:
        os.system("cls")
        banner("zFolderAudit — Folder Archaeology Tool")
        print()
        root_label = str(index.root)
        scan_label = index.scan_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {c('Root :', YELLOW)} {root_label}")
        print(f"  {c('Scan :', YELLOW)} {scan_label}  |  "
              f"{c(f'{len(index.folders):,} folders', CYAN)}  |  "
              f"{c(f'{index.total_files:,} files', CYAN)}  |  "
              f"{c(fmt_size(index.total_size), CYAN)}")
        print()
        divider()
        print()
        for key, label, _ in MENU_ITEMS:
            colour = RED if key == "7" else CYAN if key == "6" else BOLD
            print(f"  [{c(key, colour)}] {label}")
        print()

        choice = input(c("  Choice: ", BOLD)).strip()

        if choice == "7":
            print()
            print(c("  Goodbye!", CYAN))
            print()
            sys.exit(0)

        if choice == "6":
            index.folders.clear()
            index.total_files = 0
            index.total_size = 0
            index.ext_counter.clear()
            index.scan_time = datetime.datetime.now()
            index.scan()
            input(c("  Rescan complete. Press Enter …", GREEN))
            continue

        for key, label, handler in MENU_ITEMS:
            if choice == key and handler:
                os.system("cls")
                handler(index)
                break
        else:
            if choice not in [k for k, _, _ in MENU_ITEMS]:
                input(c("  Invalid choice. Press Enter …", RED))


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def main():
    os.system("cls")
    root = pathlib.Path(__file__).resolve().parent
    print()
    print(c("  ╔══════════════════════════════════════╗", CYAN))
    print(c("  ║       zFolderAudit — v1.0            ║", CYAN + BOLD))
    print(c("  ║  Folder Archaeology — Standard Lib   ║", CYAN))
    print(c("  ╚══════════════════════════════════════╝", CYAN))
    print()
    print(f"  Scanning from: {c(str(root), YELLOW)}")

    index = FolderIndex(root)
    index.scan()
    print()
    input(c("  Press Enter to open the main menu …", DIM))
    main_menu(index)


if __name__ == "__main__":
    main()