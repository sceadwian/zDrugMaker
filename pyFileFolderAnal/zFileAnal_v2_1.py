# This Python script provides multiple functionalities:
# 1. List files in the current directory and display folder structure.
# 2. Run list_files function - reads down 2 levels of directories and reports sizes as well
# 3. Rename files in the current directory with a prefix.
# 4. Remove prefix from files in the current directory.
# 5. Replace empty spaces in file names with underscores. Only current folder or directory.
# 6. Manage [tags] in filenames - view, edit, add, and reorder.
# 7. Reports on images and video files by date
# 8. List sub folder structure
# 9. Scan for Study IDs in filenames and content.
# 10. Compare two folders (recursive): identical, only-in-A/B, and modified/different files.
# The user can select the desired function from the main menu.
# The script prompts for user input and performs the chosen operation.
# v2 - introduces new AI, it was a Claude revamped version. feels like an upgrade. there is still an issue with function 9, it could be improved as well. and function 4 which is removing first tag after date as well.
# v2.1 - added [tag] management (view / edit / add / reorder) as menu item 6, everything after it shifted +1. Printout function extended to files as well
# v2.2 - 

"""
finalAnalisis.py
----------------
File & folder management toolkit.
Runs from the directory where this script lives.
Uses only the Python 3 standard library — no installs required.

Run: python finalAnalisis.py
"""

import os
import re
import math
import datetime
import hashlib
import shutil

# ─────────────────────────────────────────────
# COLOUR HELPERS (Windows 10+ ANSI support)
# ─────────────────────────────────────────────
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

RESET   = "\033[0m"
BOLD    = "\033[1m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
DIM     = "\033[2m"
RED     = "\033[31m"

def c(text, colour):
    return f"{colour}{text}{RESET}"

def banner(text):
    width = min(shutil.get_terminal_size().columns, 80)
    print()
    print(c("─" * width, CYAN))
    print(c(f"  {text}", BOLD + CYAN))
    print(c("─" * width, CYAN))

def divider():
    width = min(shutil.get_terminal_size().columns, 80)
    print(c("─" * width, DIM))

def category_label(text):
    """Print a dim category eyebrow above a group of menu items."""
    print(c(f"  {text}", DIM))

def fmt_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{round(size / 1024, 2):.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{round(size / (1024 * 1024), 2):.2f} MB"
    else:
        return f"{round(size / (1024 * 1024 * 1024), 2):.2f} GB"


# ─────────────────────────────────────────────
# 1 — LIST FILES ALPHABETICAL
# ─────────────────────────────────────────────
def list_files_alphabetical():
    os.system("cls")
    banner("Files — Alphabetical")
    path = os.getcwd()
    print(f"  {c('Location:', YELLOW)} {path}")
    print()
    files = sorted(os.listdir(path))
    for f in files:
        is_dir = os.path.isdir(os.path.join(path, f))
        if is_dir:
            print(f"  {c('▶', DIM)} {c(f, CYAN)}")
        elif f.endswith((".exe", ".py")):
            print(f"    {c(f, RED)}")
        else:
            print(f"    {c(f, GREEN)}")
    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 2 — LIST FILES & FOLDER STRUCTURE
# ─────────────────────────────────────────────
def get_directory_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total

def list_files():
    os.system("cls")
    banner("Files & Folder Structure")
    path = os.getcwd()

    # ── Folders ──────────────────────────────
    folders = []
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            folders.append((item, get_directory_size(item_path)))
    folders.sort(key=lambda x: x[1], reverse=True)

    print(c("  Subfolders (largest first):", BOLD))
    print()
    print(f"  {'Folder Name':<40} {'Size':>12}")
    divider()
    for name, size in folders:
        print(f"  {c(name, CYAN):<49} {c(fmt_size(size), YELLOW):>21}")

    print()
    input(c("  Press Enter to view files …", DIM))
    os.system("cls")
    banner("Files — Current Directory")

    # ── Files ────────────────────────────────
    file_items = []
    total_size = 0
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            size = os.path.getsize(item_path)
            total_size += size
            file_items.append((item, size))
    file_items.sort(key=lambda x: x[1], reverse=True)

    print(f"  {'File Name':<45} {'Size':>10}   {'Share':>6}")
    divider()
    for name, size in file_items:
        pct = (size / total_size * 100) if total_size else 0
        bar = c("█" * int(pct / 4), GREEN if not name.endswith((".exe", ".py")) else RED)
        name_c = c(name, RED if name.endswith((".exe", ".py")) else GREEN)
        print(f"  {name_c:<54} {fmt_size(size):>10}   {pct:>5.1f}%  {bar}")

    print()
    input(c("  Press Enter to view folder tree …", DIM))
    os.system("cls")
    banner("Folder Tree")

    # ── Tree ─────────────────────────────────
    for folder, _ in folders:
        dirpath_full = os.path.join(path, folder)
        size = get_directory_size(dirpath_full)
        print(f"  {c('▶', DIM)} {c(folder, CYAN)}  {c(fmt_size(size), DIM)}")
        for root, dirs, files in os.walk(dirpath_full):
            for f in sorted(files):
                fpath = os.path.join(root, f)
                fsize = os.path.getsize(fpath)
                rel = os.path.relpath(fpath, path)
                pct = (fsize / total_size * 100) if total_size else 0
                colour = RED if f.endswith((".exe", ".py")) else GREEN
                print(f"    {c(rel, colour)}  {c(fmt_size(fsize), DIM)}  {c(f'{pct:.1f}%', DIM)}")

    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 3 — RENAME FILES WITH PREFIX
# ─────────────────────────────────────────────
def rename_files_with_prefix():
    os.system("cls")
    banner("Rename Files — Add Prefix")
    path = os.getcwd()
    script_file = os.path.basename(__file__)
    files = sorted([f for f in os.listdir(path)
                    if os.path.isfile(os.path.join(path, f)) and f != script_file])

    print(c("  Current files:", BOLD))
    print()
    for f in files:
        print(f"  {c('·', DIM)} {c(f, GREEN)}")

    print()
    prefix = input(c("  Prefix (YYYYMMDD or YYYYMMXX): ", BOLD)).strip()
    if not re.match(r"\d{6}(?:\d{2}|XX)$", prefix):
        print(c("  ✗ Invalid prefix format.", RED))
        input(c("  Press Enter to return …", DIM))
        return

    description = input(c("  Description: ", BOLD)).strip()

    print()
    print(c("  Proposed renames:", BOLD))
    divider()
    for f in files:
        ext = os.path.splitext(f)[1]
        new = f"{prefix}_{description}_{os.path.splitext(f)[0]}{ext}"
        print(f"  {c(f, DIM)}  {c('→', YELLOW)}  {c(new, CYAN)}")

    print()
    confirm = input(c("  Type Y to confirm: ", BOLD)).strip().upper()
    if confirm != "Y":
        print(c("  Action cancelled.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    for f in files:
        ext = os.path.splitext(f)[1]
        new = f"{prefix}_{description}_{os.path.splitext(f)[0]}{ext}"
        os.rename(os.path.join(path, f), os.path.join(path, new))

    print()
    print(c("  ✓ Files renamed successfully.", GREEN))
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 4 — REMOVE PREFIX FROM FILES
# ─────────────────────────────────────────────
def remove_prefix_from_files():
    os.system("cls")
    banner("Rename Files — Remove Prefix")
    path = os.getcwd()
    files = sorted(os.listdir(path))

    print(c("  Current files:", BOLD))
    print()
    for f in files:
        print(f"  {c('·', DIM)} {c(f, GREEN)}")

    print()
    prefix = input(c("  Prefix to remove (YYYYMMDD): ", BOLD)).strip()
    if not re.match(r"\d{8}$", prefix):
        print(c("  ✗ Invalid prefix format.", RED))
        input(c("  Press Enter to return …", DIM))
        return

    pattern = fr"^{re.escape(prefix)}_[^_]+_"
    renamed = []
    for f in files:
        if os.path.isfile(os.path.join(path, f)) and re.search(pattern, f):
            renamed.append((f, re.sub(pattern, "", f)))

    if not renamed:
        print(c("  No files matched that prefix.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    print()
    print(c("  Proposed renames:", BOLD))
    divider()
    for old, new in renamed:
        print(f"  {c(old, DIM)}  {c('→', YELLOW)}  {c(new, CYAN)}")

    print()
    confirm = input(c("  Type Y to confirm: ", BOLD)).strip().upper()
    if confirm != "Y":
        print(c("  Action cancelled.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    for old, new in renamed:
        os.rename(os.path.join(path, old), os.path.join(path, new))

    print()
    print(c("  ✓ Files renamed successfully.", GREEN))
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 5 — REPLACE SPACES IN FILENAMES
# ─────────────────────────────────────────────
def replace_spaces_in_filenames():
    os.system("cls")
    banner("Naming — Replace Spaces with Underscores")
    path = os.getcwd()
    spaced = {f: f.count(" ") for f in os.listdir(path) if " " in f}

    if not spaced:
        print(c("  No files with spaces found.", YELLOW))
        print()
        input(c("  Press Enter to return …", DIM))
        return

    print(f"  {c('File Name', BOLD):<55} {c('Spaces', BOLD):>8}")
    divider()
    for f, n in sorted(spaced.items()):
        print(f"  {c(f, GREEN):<64} {c(str(n), YELLOW):>17}")
    print()

    choice = input(c("  Replace spaces with underscores? [Y/n]: ", BOLD)).strip().upper()
    if choice == "Y":
        for f in spaced:
            new = f.replace(" ", "_")
            os.rename(os.path.join(path, f), os.path.join(path, new))
        print()
        print(c("  ✓ Filenames updated.", GREEN))
    else:
        print(c("  No changes made.", DIM))

    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 6 — MANAGE [TAGS] IN FILENAMES
# ─────────────────────────────────────────────
# Tags are bracketed tokens like [draft] or [v2] that can appear anywhere
# in a filename, e.g.  Report_[draft]_[urgent]_Q1.pdf
# These helpers always operate on the name *without* the extension, so a
# tag is never accidentally matched inside ".pdf" etc.

TAG_PATTERN = re.compile(r"\[([^\[\]]+)\]")

def _tag_base_ext(filename):
    """Split filename into (base, ext) so tag operations never touch the extension."""
    return os.path.splitext(filename)

def _extract_tags(filename):
    """Return list of tag strings, in left-to-right order, found in the filename."""
    base, _ = _tag_base_ext(filename)
    return TAG_PATTERN.findall(base)

def _all_files(path, exclude):
    return sorted(f for f in os.listdir(path)
                  if f not in exclude and os.path.isfile(os.path.join(path, f)))

def _tagged_files(path, exclude):
    """Return [(filename, [tags]), ...] for every top-level file that has ≥1 tag."""
    result = []
    for f in _all_files(path, exclude):
        tags = _extract_tags(f)
        if tags:
            result.append((f, tags))
    return result

def _valid_tag_text(tag):
    return bool(tag) and "[" not in tag and "]" not in tag


def view_all_tags():
    os.system("cls")
    banner("Tags — View All")
    path = os.getcwd()
    script_file = os.path.basename(__file__)
    tagged = _tagged_files(path, {script_file})

    if not tagged:
        print(c("  No [tags] found on any file in this folder.", YELLOW))
        print()
        input(c("  Press Enter to return …", DIM))
        return

    counts = {}
    owners = {}
    for f, tags in tagged:
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
            owners.setdefault(t, []).append(f)

    print(f"  {c('Tag', BOLD):<30} {c('Files', BOLD):>8}")
    divider()
    for tag, n in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower())):
        label = c(f"[{tag}]", MAGENTA)
        print(f"  {label:<39} {c(str(n), YELLOW):>17}")

    print()
    term = input(c("  Enter a tag to see which files use it (or Enter to skip): ", BOLD)).strip()
    if term:
        if term in owners:
            print()
            print(c(f"  Files tagged [{term}]:", BOLD))
            for f in owners[term]:
                print(f"    {c('·', DIM)} {c(f, GREEN)}")
        else:
            print(c(f"  No files use the tag [{term}].", YELLOW))

    print()
    input(c("  Press Enter to return to menu …", DIM))


def edit_tag_globally():
    os.system("cls")
    banner("Tags — Edit Across Folder")
    path = os.getcwd()
    script_file = os.path.basename(__file__)
    tagged = _tagged_files(path, {script_file})

    if not tagged:
        print(c("  No [tags] found on any file in this folder.", YELLOW))
        print()
        input(c("  Press Enter to return …", DIM))
        return

    counts = {}
    for _, tags in tagged:
        for t in tags:
            counts[t] = counts.get(t, 0) + 1

    print(c("  Existing tags:", BOLD))
    print()
    for tag, n in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower())):
        plural = "file" if n == 1 else "files"
        print(f"  {c(f'[{tag}]', MAGENTA)}  {c(f'({n} {plural})', DIM)}")

    print()
    old_tag = input(c("  Tag to edit (exact name, without brackets): ", BOLD)).strip()
    if old_tag not in counts:
        print(c(f"  ✗ No files use the tag [{old_tag}].", RED))
        input(c("  Press Enter to return …", DIM))
        return

    new_tag = input(c(f"  New value for [{old_tag}] → [", BOLD)).strip()
    if not _valid_tag_text(new_tag):
        print(c("  ✗ Tag must be non-empty and cannot contain [ or ].", RED))
        input(c("  Press Enter to return …", DIM))
        return

    renames = []
    for f, tags in tagged:
        if old_tag in tags:
            base, ext = _tag_base_ext(f)
            new_base = base.replace(f"[{old_tag}]", f"[{new_tag}]")
            renames.append((f, new_base + ext))

    print()
    print(c("  Proposed renames:", BOLD))
    divider()
    for old, new in renames:
        print(f"  {c(old, DIM)}  {c('→', YELLOW)}  {c(new, CYAN)}")

    print()
    confirm = input(c(f"  Type Y to rename {len(renames)} file(s): ", BOLD)).strip().upper()
    if confirm != "Y":
        print(c("  Action cancelled.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    for old, new in renames:
        os.rename(os.path.join(path, old), os.path.join(path, new))

    print()
    print(c("  ✓ Tag updated across folder.", GREEN))
    input(c("  Press Enter to return to menu …", DIM))


def add_tags_to_files():
    os.system("cls")
    banner("Tags — Add to Files")
    path = os.getcwd()
    script_file = os.path.basename(__file__)
    files = _all_files(path, {script_file})

    if not files:
        print(c("  No files found in this folder.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    print(c("  Files:", BOLD))
    print()
    for i, f in enumerate(files, 1):
        print(f"  {c(f'[{i}]', CYAN)} {f}")

    print()
    selection = input(c("  File number(s) to tag — comma-separated, or 'all': ", BOLD)).strip()
    if selection.lower() == "all":
        chosen = files
    else:
        chosen, seen = [], set()
        for part in selection.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(files):
                f = files[int(part) - 1]
                if f not in seen:
                    chosen.append(f)
                    seen.add(f)

    if not chosen:
        print(c("  ✗ No valid files selected.", RED))
        input(c("  Press Enter to return …", DIM))
        return

    new_tag = input(c("  New tag text (without brackets): ", BOLD)).strip()
    if not _valid_tag_text(new_tag):
        print(c("  ✗ Tag must be non-empty and cannot contain [ or ].", RED))
        input(c("  Press Enter to return …", DIM))
        return

    renames = []
    for f in chosen:
        base, ext = _tag_base_ext(f)
        sep = "" if (not base or base.endswith("_")) else "_"
        renames.append((f, f"{base}{sep}[{new_tag}]{ext}"))

    print()
    print(c("  Proposed renames:", BOLD))
    divider()
    for old, new in renames:
        print(f"  {c(old, DIM)}  {c('→', YELLOW)}  {c(new, CYAN)}")

    print()
    confirm = input(c(f"  Type Y to tag {len(renames)} file(s): ", BOLD)).strip().upper()
    if confirm != "Y":
        print(c("  Action cancelled.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    for old, new in renames:
        os.rename(os.path.join(path, old), os.path.join(path, new))

    print()
    print(c("  ✓ Tag added.", GREEN))
    input(c("  Press Enter to return to menu …", DIM))


def reorder_tags_for_file():
    os.system("cls")
    banner("Tags — Reorder for One File")
    path = os.getcwd()
    script_file = os.path.basename(__file__)
    tagged = _tagged_files(path, {script_file})

    if not tagged:
        print(c("  No tagged files found in this folder.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    print(c("  Tagged files:", BOLD))
    print()
    for i, (f, tags) in enumerate(tagged, 1):
        print(f"  {c(f'[{i}]', CYAN)} {f}")

    print()
    sel = input(c("  File number to reorder: ", BOLD)).strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(tagged)):
        print(c("  ✗ Invalid selection.", RED))
        input(c("  Press Enter to return …", DIM))
        return

    filename, _ = tagged[int(sel) - 1]
    base, ext = _tag_base_ext(filename)
    parts = re.split(r"(\[[^\[\]]+\])", base)
    slot_idx = [i for i, p in enumerate(parts) if TAG_PATTERN.fullmatch(p)]

    if len(slot_idx) < 2:
        print(c("  This file only has one tag — nothing to reorder.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    current_tags = [TAG_PATTERN.fullmatch(parts[i]).group(1) for i in slot_idx]

    print()
    print(c(f"  Current order in: {filename}", BOLD))
    print()
    for n, t in enumerate(current_tags, 1):
        print(f"    {c(f'[{n}]', CYAN)} {t}")

    example = " ".join(str(x) for x in range(len(current_tags), 0, -1))
    print()
    order_in = input(c(f"  Enter the new order using the numbers above (e.g. {example}): ", BOLD)).strip()
    order = order_in.split()

    valid = (len(order) == len(current_tags)
             and all(o.isdigit() for o in order)
             and sorted(int(o) for o in order) == list(range(1, len(current_tags) + 1)))
    if not valid:
        print(c("  ✗ Enter every number exactly once.", RED))
        input(c("  Press Enter to return …", DIM))
        return

    new_tags = [current_tags[int(o) - 1] for o in order]
    for slot, tag in zip(slot_idx, new_tags):
        parts[slot] = f"[{tag}]"
    new_filename = "".join(parts) + ext

    print()
    print(c("  Proposed rename:", BOLD))
    divider()
    print(f"  {c(filename, DIM)}  {c('→', YELLOW)}  {c(new_filename, CYAN)}")

    print()
    confirm = input(c("  Type Y to confirm: ", BOLD)).strip().upper()
    if confirm != "Y":
        print(c("  Action cancelled.", YELLOW))
        input(c("  Press Enter to return …", DIM))
        return

    os.rename(os.path.join(path, filename), os.path.join(path, new_filename))
    print()
    print(c("  ✓ Tags reordered.", GREEN))
    input(c("  Press Enter to return to menu …", DIM))


def manage_tags():
    TAG_MENU = [
        ("1", "View all tags (counts)",        view_all_tags),
        ("2", "Edit a tag across the folder",  edit_tag_globally),
        ("3", "Add a tag to specific files",   add_tags_to_files),
        ("4", "Reorder tags on one file",      reorder_tags_for_file),
        ("0", "Back to main menu",             None),
    ]
    while True:
        os.system("cls")
        banner("Manage Tags")
        print()
        print(f"  {c('Working dir:', YELLOW)} {os.getcwd()}")
        print()
        divider()
        print()
        for key, label, _ in TAG_MENU:
            colour = RED if key == "0" else CYAN
            print(f"  [{c(key, colour)}] {label}")
        print()
        choice = input(c("  Choice: ", BOLD)).strip()

        if choice == "0":
            return

        handler = next((h for k, _, h in TAG_MENU if k == choice and h), None)
        if handler:
            os.system("cls")
            handler()
        else:
            input(c("  Invalid choice. Press Enter …", RED))


# ─────────────────────────────────────────────
# 7 — GROUP IMAGE/VIDEO FILES BY DATE
# ─────────────────────────────────────────────
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif"}
VIDEO_EXT = {".mp4", ".avi", ".mov"}

def group_files_by_date():
    os.system("cls")
    banner("Media — Group by Date")
    path = os.getcwd()
    prefix_pattern = r"(\d{8}|\d{6}XX)"
    groups = {}

    for f in sorted(os.listdir(path)):
        fp = os.path.join(path, f)
        if not os.path.isfile(fp):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext not in IMAGE_EXT and ext not in VIDEO_EXT:
            continue
        m = re.search(prefix_pattern, f)
        if not m:
            continue
        pfx = m.group(1)
        g = groups.setdefault(pfx, {"images": [], "videos": [], "size": 0,
                                     "num_images": 0, "num_videos": 0,
                                     "tags": set()})
        kind = "images" if ext in IMAGE_EXT else "videos"
        g[kind].append(f)
        g["size"] += os.path.getsize(fp)
        g["num_images"] += (1 if kind == "images" else 0)
        g["num_videos"] += (1 if kind == "videos" else 0)
        g["tags"].update(re.findall(r"_(.*?)_", f))

    if not groups:
        print(c("  No dated media files found.", YELLOW))
        print()
        input(c("  Press Enter to return …", DIM))
        return

    for pfx, data in sorted(groups.items()):
        divider()
        print(f"  {c('Date block:', YELLOW)} {c(pfx, BOLD + CYAN)}")
        print(f"  {c('Images:', DIM)} {data['num_images']}   "
              f"{c('Videos:', DIM)} {data['num_videos']}   "
              f"{c('Total size:', DIM)} {fmt_size(data['size'])}")
        if data["tags"]:
            print(f"  {c('Tags:', DIM)} {c(', '.join(sorted(data['tags'])), MAGENTA)}")
        print()
        for f in sorted(data["images"] + data["videos"]):
            ext = os.path.splitext(f)[1].lower()
            colour = MAGENTA if ext in VIDEO_EXT else GREEN
            print(f"    {c('·', DIM)} {c(f, colour)}")
    divider()
    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 8 — LIST SUBFOLDERS / FILES & SAVE
# ─────────────────────────────────────────────
def list_subfolders_and_save():
    os.system("cls")
    banner("List & Save — Folders or Files")
    print()
    print(c("  What would you like to list?", BOLD))
    print()
    print(f"  {c('[1]', CYAN)} Subfolders (recursive)")
    print(f"  {c('[2]', CYAN)} Files (recursive)")
    print()
    mode = input(c("  Choice [1-2, default 1]: ", BOLD)).strip() or "1"
    if mode not in {"1", "2"}:
        mode = "1"

    path = os.getcwd()
    script_file = os.path.basename(__file__)

    if mode == "1":
        items = sorted(
            os.path.join(root, d)
            for root, dirs, _ in os.walk(path)
            for d in dirs
        )
        noun, out_tag, icon = "subfolders", "subfolders", "▶"
    else:
        items = sorted(
            os.path.join(root, f)
            for root, _, files in os.walk(path)
            for f in files
            if not (root == path and f == script_file)
        )
        noun, out_tag, icon = "files", "files", "·"

    os.system("cls")
    banner(f"{'Subfolders' if mode == '1' else 'Files'} — List & Save")

    print(c(f"  Found {len(items):,} {noun} under:", YELLOW))
    print(f"  {path}")
    print()
    divider()
    for it in items:
        rel = os.path.relpath(it, path)
        depth = rel.count(os.sep)
        indent = "  " + "    " * depth
        name = os.path.basename(it)
        if mode == "1":
            print(f"{indent}{c(icon, DIM)} {c(name, CYAN)}")
        else:
            colour = RED if name.endswith((".exe", ".py")) else GREEN
            print(f"{indent}{c(icon, DIM)} {c(name, colour)}")

    ts = datetime.datetime.now().strftime("%Y%m%d%H%M")
    out = f"zfileanaloutput_{out_tag}_list_{ts}.txt"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(items) + "\n")

    print()
    print(c(f"  ✓ Saved to: {out}", GREEN))
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 9 — FIND STUDY IDs
# ─────────────────────────────────────────────
STUDY_ID_PATTERN = re.compile(
    r"TSA-\d{5,6}-[a-zA-Z]{3}|"
    r"TPC\d{1,3}-\d{5}-[a-zA-Z]{2,3}"
)
MAX_SCAN_SIZE = 100 * 1024 * 1024  # 100 MB

def find_study_ids():
    os.system("cls")
    banner("Scanning — Find Study IDs")
    base = os.getcwd()
    found = {}
    dir_count = 0

    print(f"  {c('Scanning from:', YELLOW)} {base}")
    print()

    for root, dirs, files in os.walk(base):
        dir_count += 1
        print(c(f"  [{dir_count}] {os.path.relpath(root, base) or '.'}  …", DIM), end="\r")

        for name in dirs:
            for m in STUDY_ID_PATTERN.finditer(name):
                found.setdefault(m.group(), set()).add(
                    ("in Folder Name", os.path.join(root, name))
                )

        for name in files:
            fp = os.path.join(root, name)
            for m in STUDY_ID_PATTERN.finditer(name):
                found.setdefault(m.group(), set()).add(("in File Name", fp))
            try:
                if os.path.getsize(fp) <= MAX_SCAN_SIZE:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        for line in fh:
                            for m in STUDY_ID_PATTERN.finditer(line):
                                found.setdefault(m.group(), set()).add(
                                    ("in File Content", fp)
                                )
                else:
                    pass  # silently skip huge files
            except (IOError, OSError):
                pass

    print(" " * 80, end="\r")
    print(c(f"  ✓ Scan complete — {dir_count:,} folders scanned", GREEN))
    print()

    if not found:
        print(c("  No Study IDs found.", YELLOW))
        print()
        input(c("  Press Enter to return …", DIM))
        return

    divider()
    print(c(f"  {len(found)} unique Study IDs located:", BOLD))
    print()

    for sid, locs in sorted(found.items()):
        print(f"  {c(sid, YELLOW + BOLD)}")
        for ctx, fp in sorted(locs):
            rel = os.path.relpath(fp, base)
            print(f"    {c('·', DIM)} {c(ctx, DIM)}  {c(rel, CYAN)}")
        print()

    # Write report
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M")
    out = f"zFileAnal_Studies_{ts}.txt"
    try:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"Study ID Scan Report\n")
            fh.write(f"Generated : {datetime.datetime.now()}\n")
            fh.write(f"Base path : {base}\n\n")
            for sid, locs in sorted(found.items()):
                fh.write(f"\nID: {sid}\n")
                for ctx, fp in sorted(locs):
                    fh.write(f"  • {ctx}: {os.path.relpath(fp, base)}\n")
        print(c(f"  ✓ Report saved to: {out}", GREEN))
    except IOError as e:
        print(c(f"  ✗ Could not write report: {e}", RED))

    print()
    term = input(c("  Filter by partial ID (or Enter to skip): ", BOLD)).strip()
    if term:
        matches = {k: v for k, v in found.items() if term in k}
        if matches:
            print()
            for sid, locs in sorted(matches.items()):
                print(f"  {c(sid, YELLOW + BOLD)}")
                for ctx, fp in sorted(locs):
                    print(f"    {c('·', DIM)} {c(ctx, DIM)}  {c(os.path.relpath(fp, base), CYAN)}")
        else:
            print(c(f"  No IDs containing '{term}'.", YELLOW))

    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# 10 — COMPARE TWO FOLDERS
# ─────────────────────────────────────────────
def _norm(path):
    return os.path.normpath(path).lower()

def _sha256(filepath, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()

def _scan_tree(base):
    files, folders = {}, set()
    for root, dirs, filenames in os.walk(base):
        rel_root = os.path.relpath(root, base)
        rel_root = "" if rel_root == "." else rel_root
        for d in dirs:
            folders.add(_norm(os.path.join(rel_root, d)))
        for fn in filenames:
            rel_file = os.path.join(rel_root, fn)
            full = os.path.join(root, fn)
            try:
                st = os.stat(full)
                files[_norm(rel_file)] = {
                    "rel": os.path.normpath(rel_file),
                    "full": full,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            except (OSError, IOError):
                continue
    return files, folders

def _fmt_ts(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def _mtime_close(a, b, tol=2.0):
    return abs(a - b) <= tol

def compare_two_folders():
    os.system("cls")
    banner("Compare Two Folders")
    print()
    path_a = input(c("  Folder A path: ", BOLD)).strip().strip('"')
    path_b = input(c("  Folder B path: ", BOLD)).strip().strip('"')

    for label, p in (("A", path_a), ("B", path_b)):
        if not os.path.isdir(p):
            print(c(f"  ✗ Folder {label} is not a valid directory: {p}", RED))
            input(c("  Press Enter to return …", DIM))
            return

    print()
    print(c("  Hash options:", BOLD))
    print(f"  {c('[0]', CYAN)} No hashing — fast, uses size + mtime only")
    print(f"  {c('[1]', CYAN)} Hash differing files only  {c('(recommended)', DIM)}")
    print(f"  {c('[2]', CYAN)} Hash all common files  {c('(slowest, most accurate)', DIM)}")
    print()
    hash_mode = int(input(c("  Choice [0–2, default 1]: ", BOLD)).strip() or "1")
    if hash_mode not in {0, 1, 2}:
        hash_mode = 1

    print()
    print(c("  Scanning Folder A …", YELLOW), end="\r")
    files_a, folders_a = _scan_tree(path_a)
    print(c(f"  ✓ Folder A — {len(files_a):,} files, {len(folders_a):,} folders", GREEN))

    print(c("  Scanning Folder B …", YELLOW), end="\r")
    files_b, folders_b = _scan_tree(path_b)
    print(c(f"  ✓ Folder B — {len(files_b):,} files, {len(folders_b):,} folders", GREEN))

    keys_a, keys_b = set(files_a), set(files_b)
    common_files   = sorted(keys_a & keys_b)
    only_a_files   = sorted(keys_a - keys_b)
    only_b_files   = sorted(keys_b - keys_a)
    only_a_folders = sorted(folders_a - folders_b)
    only_b_folders = sorted(folders_b - folders_a)
    common_folders = folders_a & folders_b

    identical, different = [], []
    hash_verified = 0

    for k in common_files:
        fa, fb = files_a[k], files_b[k]
        size_eq  = fa["size"]  == fb["size"]
        mtime_eq = _mtime_close(fa["mtime"], fb["mtime"])

        if size_eq and mtime_eq and hash_mode != 2:
            identical.append((fa, fb, "size+mtime"))
            continue

        if hash_mode == 0:
            (identical if (size_eq and mtime_eq) else different).append(
                (fa, fb, "size+mtime" if size_eq and mtime_eq else "size/mtime differs")
            )
            continue

        need_hash = hash_mode == 2 or (not size_eq or not mtime_eq)
        if need_hash:
            try:
                ha, hb = _sha256(fa["full"]), _sha256(fb["full"])
                if ha == hb:
                    identical.append((fa, fb, "sha256"))
                    hash_verified += 1
                else:
                    different.append((fa, fb, "sha256 differs"))
            except (OSError, IOError):
                different.append((fa, fb, "hash error"))
        else:
            identical.append((fa, fb, "size+mtime"))

    def newer(fa, fb):
        if _mtime_close(fa["mtime"], fb["mtime"]):
            return c("Same mtime", DIM)
        return c("A newer", CYAN) if fa["mtime"] > fb["mtime"] else c("B newer", MAGENTA)

    # ── Summary ──────────────────────────────
    os.system("cls")
    banner("Comparison Results")
    print()
    print(f"  {c('Folder A:', YELLOW)} {path_a}")
    print(f"  {c('Folder B:', YELLOW)} {path_b}")
    print()
    divider()

    def stat_row(label, val, colour=CYAN):
        print(f"  {c(label, DIM):<40} {c(str(val), colour)}")

    stat_row("Common folders",                  f"{len(common_folders):,}")
    stat_row("Folders only in A",               f"{len(only_a_folders):,}")
    stat_row("Folders only in B",               f"{len(only_b_folders):,}")
    print()
    stat_row("Common files (same relative path)", f"{len(common_files):,}")
    stat_row("Identical files",                 f"{len(identical):,}  (hash-verified: {hash_verified:,})", GREEN)
    stat_row("Different / modified files",       f"{len(different):,}", YELLOW if different else GREEN)
    stat_row("Files only in A",                 f"{len(only_a_files):,}")
    stat_row("Files only in B",                 f"{len(only_b_files):,}")
    divider()

    # ── Preview diffs ─────────────────────────
    if different:
        print()
        print(c(f"  Modified files (first {min(25, len(different))}):", BOLD))
        print()
        for fa, fb, reason in different[:25]:
            nw = newer(fa, fb)
            print(f"  {c(fa['rel'], CYAN)}  {c(f'[{reason}]', DIM)}  {nw}")
            print(f"    {c('A:', DIM)} {_fmt_ts(fa['mtime'])} | {fmt_size(fa['size'])}")
            print(f"    {c('B:', DIM)} {_fmt_ts(fb['mtime'])} | {fmt_size(fb['size'])}")

    # ── Write report ──────────────────────────
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M")
    out = f"zFileAnal_FolderCompare_{ts}.txt"
    try:
        with open(out, "w", encoding="utf-8") as fh:
            def sec(title):
                fh.write(f"\n{title}\n{'─' * len(title)}\n")

            fh.write("FOLDER COMPARISON REPORT\n")
            fh.write(f"Generated : {datetime.datetime.now()}\n")
            fh.write(f"Folder A  : {path_a}\n")
            fh.write(f"Folder B  : {path_b}\n")
            fh.write(f"Hash mode : {hash_mode}\n")

            sec("SUMMARY")
            fh.write(f"Common folders    : {len(common_folders)}\n")
            fh.write(f"Folders only in A : {len(only_a_folders)}\n")
            fh.write(f"Folders only in B : {len(only_b_folders)}\n\n")
            fh.write(f"Common files      : {len(common_files)}\n")
            fh.write(f"Identical         : {len(identical)} (hash-verified: {hash_verified})\n")
            fh.write(f"Different         : {len(different)}\n")
            fh.write(f"Only in A         : {len(only_a_files)}\n")
            fh.write(f"Only in B         : {len(only_b_files)}\n")

            for title, items in [
                (f"FOLDERS ONLY IN A", only_a_folders),
                (f"FOLDERS ONLY IN B", only_b_folders),
                (f"FILES ONLY IN A",   [files_a[k]["rel"] for k in only_a_files]),
                (f"FILES ONLY IN B",   [files_b[k]["rel"] for k in only_b_files]),
            ]:
                sec(title)
                fh.write("\n".join(f"  • {x}" for x in items) or "  (none)")
                fh.write("\n")

            sec("IDENTICAL FILES")
            for fa, fb, how in identical:
                fh.write(f"  • {fa['rel']}  [{how}]\n")

            sec("DIFFERENT / MODIFIED FILES")
            for fa, fb, reason in different:
                nw_label = "Same mtime" if _mtime_close(fa["mtime"], fb["mtime"]) else \
                            ("A newer" if fa["mtime"] > fb["mtime"] else "B newer")
                fh.write(f"  • {fa['rel']}  [{reason}]  [{nw_label}]\n")
                fh.write(f"      A: size={fa['size']}  mtime={_fmt_ts(fa['mtime'])}\n")
                fh.write(f"      B: size={fb['size']}  mtime={_fmt_ts(fb['mtime'])}\n")

        print()
        print(c(f"  ✓ Full report saved to: {out}", GREEN))
    except IOError as e:
        print(c(f"  ✗ Could not write report: {e}", RED))

    print()
    input(c("  Press Enter to return to menu …", DIM))


# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────
MENU = [
    # (key, category_label_or_None, display_label, handler)
    ("1",  "FILES / FOLDERS",  "List files alphabetically",          list_files_alphabetical),
    ("2",  None,               "List files & folder structure",       list_files),
    ("3",  "NAMING",           "Rename files — add prefix",           rename_files_with_prefix),
    ("4",  None,               "Rename files — remove prefix",        remove_prefix_from_files),
    ("5",  None,               "Replace spaces in filenames",         replace_spaces_in_filenames),
    ("6",  "TAGGING",          "Manage [tags] in filenames",          manage_tags),
    ("7",  "MEDIA",            "Group image/video files by date",     group_files_by_date),
    ("8",  "SCANNING",         "List subfolders or files & save",     list_subfolders_and_save),
    ("9",  None,               "Find Study IDs in files & folders",   find_study_ids),
    ("10", "COMPARISON",       "Compare two folders (recursive)",     compare_two_folders),
    ("0",  None,               "Exit",                                None),
]

def main_menu():
    while True:
        os.system("cls")
        banner("finalAnalisis — File & Folder Toolkit")
        print()
        print(f"  {c('Working dir:', YELLOW)} {os.getcwd()}")
        print()
        divider()
        print()

        last_cat = None
        for key, cat, label, _ in MENU:
            if cat and cat != last_cat:
                if last_cat is not None:
                    print()
                category_label(cat)
                last_cat = cat
            colour = RED if key == "0" else CYAN
            print(f"  [{c(key, colour)}] {label}")

        print()
        choice = input(c("  Choice: ", BOLD)).strip()

        if choice == "0":
            print()
            print(c("  Goodbye!", CYAN))
            print()
            break

        handler = next((h for k, _, _, h in MENU if k == choice and h), None)
        if handler:
            os.system("cls")
            handler()
        else:
            input(c("  Invalid choice. Press Enter …", RED))


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    os.system("cls")
    print()
    print(c("  ╔══════════════════════════════════════╗", CYAN))
    print(c("  ║       finalAnalisis — v3.0           ║", CYAN + BOLD))
    print(c("  ║   File & Folder Management Toolkit   ║", CYAN))
    print(c("  ╚══════════════════════════════════════╝", CYAN))
    print()
    print(f"  {c('Working from:', YELLOW)} {os.getcwd()}")
    print()
    input(c("  Press Enter to open the menu …", DIM))
    main_menu()