#!/usr/bin/env python3
"""
zFolderAudit.py

A lightweight Windows-friendly folder archaeology tool.

Purpose:
- Run this script from any folder.
- It scans the folder where the script is located and all subfolders.
- It builds an in-memory index so browsing/searching/exporting are fast after the initial scan.
- It can optionally save/load a JSON cache to avoid rescanning very large folders every time.

Standard library only.
Tested design target: Python 3.9+ on Windows 11.

Author: Generated with ChatGPT
"""

from __future__ import annotations

import os
import sys
import json
import time
import math
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# User-editable settings
# ---------------------------------------------------------------------------

CACHE_FILE_NAME = ".folder_audit_cache.json"

# Skip obvious technical/system folders. You can edit this list.
SKIP_FOLDERS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "$RECYCLE.BIN",
    "System Volume Information",
}

# Display/progress settings
PAGE_SIZE = 50
SCAN_PROGRESS_EVERY_SECONDS = 1.0
TREE_DEFAULT_DEPTH = 3

# Use visual tree characters. If your terminal displays these badly,
# change this to False.
USE_UNICODE_TREE = True


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    name: str
    rel_path: str
    parent_rel: str
    size_bytes: int
    modified_ts: float
    extension: str

    @property
    def modified_text(self) -> str:
        try:
            return datetime.fromtimestamp(self.modified_ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Unknown"


@dataclass
class FolderRecord:
    name: str
    rel_path: str
    parent_rel: Optional[str]
    child_folders: List[str] = field(default_factory=list)
    files: List[FileRecord] = field(default_factory=list)


@dataclass
class AuditIndex:
    root: str
    scanned_at: str
    folders: Dict[str, FolderRecord]
    total_files: int = 0
    total_folders: int = 0
    total_size_bytes: int = 0
    extension_counts: Dict[str, int] = field(default_factory=dict)
    extension_sizes: Dict[str, int] = field(default_factory=dict)
    inaccessible_paths: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(message: str = "Press Enter to continue...") -> None:
    input(f"\n{message}")


def format_size(num_bytes: int) -> str:
    if num_bytes is None:
        return "Unknown"
    if num_bytes < 0:
        return "Unknown"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def safe_rel_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
        rel_text = str(rel)
        return "." if rel_text == "." else rel_text
    except Exception:
        return str(path)


def normalize_rel(rel_path: str) -> str:
    if not rel_path or rel_path == ".":
        return "."
    return rel_path.replace("/", os.sep).replace("\\", os.sep)


def get_extension(file_name: str) -> str:
    ext = Path(file_name).suffix.lower()
    return ext if ext else "[no extension]"


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sort_key_path(rel_path: str) -> Tuple[int, str]:
    # Root first, then alphabetical.
    if rel_path == ".":
        return (0, "")
    return (1, rel_path.lower())


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def cache_path(root: Path) -> Path:
    return root / CACHE_FILE_NAME


def file_record_from_dict(d: dict) -> FileRecord:
    return FileRecord(
        name=d["name"],
        rel_path=d["rel_path"],
        parent_rel=d["parent_rel"],
        size_bytes=int(d["size_bytes"]),
        modified_ts=float(d["modified_ts"]),
        extension=d["extension"],
    )


def folder_record_from_dict(d: dict) -> FolderRecord:
    return FolderRecord(
        name=d["name"],
        rel_path=d["rel_path"],
        parent_rel=d.get("parent_rel"),
        child_folders=list(d.get("child_folders", [])),
        files=[file_record_from_dict(x) for x in d.get("files", [])],
    )


def load_cache(root: Path) -> Optional[AuditIndex]:
    cp = cache_path(root)
    if not cp.exists():
        return None

    try:
        with cp.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("root") != str(root):
            return None

        folders = {
            rel: folder_record_from_dict(fr)
            for rel, fr in data.get("folders", {}).items()
        }

        return AuditIndex(
            root=data["root"],
            scanned_at=data.get("scanned_at", "Unknown"),
            folders=folders,
            total_files=int(data.get("total_files", 0)),
            total_folders=int(data.get("total_folders", len(folders))),
            total_size_bytes=int(data.get("total_size_bytes", 0)),
            extension_counts=dict(data.get("extension_counts", {})),
            extension_sizes={k: int(v) for k, v in data.get("extension_sizes", {}).items()},
            inaccessible_paths=list(data.get("inaccessible_paths", [])),
        )

    except Exception as e:
        print(f"Could not load cache: {e}")
        return None


def save_cache(index: AuditIndex) -> None:
    root = Path(index.root)
    cp = cache_path(root)

    try:
        data = asdict(index)
        with cp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Cache saved: {cp}")
    except Exception as e:
        print(f"Could not save cache: {e}")


def ask_use_cache(root: Path) -> Optional[AuditIndex]:
    cached = load_cache(root)
    if cached is None:
        return None

    print("\nA previous scan cache was found.")
    print(f"Cache file: {cache_path(root)}")
    print(f"Cached scan date: {cached.scanned_at}")
    print(f"Cached folders: {cached.total_folders:,}")
    print(f"Cached files: {cached.total_files:,}")
    print(f"Cached size: {format_size(cached.total_size_bytes)}")
    print("\nUse the cache only if the folder has not changed significantly.")

    while True:
        choice = input("\nUse cached scan? [Y]es / [N]o, rescan: ").strip().lower()
        if choice in {"y", "yes"}:
            return cached
        if choice in {"n", "no", ""}:
            return None
        print("Please enter Y or N.")


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_directory(root: Path) -> AuditIndex:
    print("\nScanning folder tree...")
    print(f"Root: {root}")
    print("This may take a while for large folders.\n")

    root = root.resolve()
    folders: Dict[str, FolderRecord] = {}

    root_record = FolderRecord(
        name=root.name if root.name else str(root),
        rel_path=".",
        parent_rel=None,
    )
    folders["."] = root_record

    total_files = 0
    total_size = 0
    extension_counts = Counter()
    extension_sizes = Counter()
    inaccessible_paths: List[str] = []

    stack: List[Tuple[Path, str]] = [(root, ".")]
    last_progress = time.time()
    scanned_folders = 0

    while stack:
        current_path, current_rel = stack.pop()
        scanned_folders += 1

        try:
            entries = list(os.scandir(current_path))
        except PermissionError:
            inaccessible_paths.append(str(current_path))
            continue
        except OSError as e:
            inaccessible_paths.append(f"{current_path} [{e}]")
            continue

        child_dirs: List[Tuple[Path, str]] = []

        for entry in entries:
            try:
                # Avoid following symlinked directories. This reduces risk of loops.
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in SKIP_FOLDERS:
                        continue

                    child_path = Path(entry.path)
                    child_rel = safe_rel_path(child_path, root)
                    child_rel = normalize_rel(child_rel)

                    folders[current_rel].child_folders.append(child_rel)
                    folders[child_rel] = FolderRecord(
                        name=entry.name,
                        rel_path=child_rel,
                        parent_rel=current_rel,
                    )
                    child_dirs.append((child_path, child_rel))

                elif entry.is_file(follow_symlinks=False):
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        size = int(stat.st_size)
                        modified = float(stat.st_mtime)
                    except OSError:
                        size = 0
                        modified = 0.0

                    file_path = Path(entry.path)
                    rel_file = safe_rel_path(file_path, root)
                    rel_file = normalize_rel(rel_file)
                    ext = get_extension(entry.name)

                    fr = FileRecord(
                        name=entry.name,
                        rel_path=rel_file,
                        parent_rel=current_rel,
                        size_bytes=size,
                        modified_ts=modified,
                        extension=ext,
                    )

                    folders[current_rel].files.append(fr)
                    total_files += 1
                    total_size += size
                    extension_counts[ext] += 1
                    extension_sizes[ext] += size

            except PermissionError:
                inaccessible_paths.append(str(Path(entry.path)))
            except OSError as e:
                inaccessible_paths.append(f"{Path(entry.path)} [{e}]")

        # Sort child directories/files alphabetically for readable output.
        folders[current_rel].child_folders.sort(key=lambda x: x.lower())
        folders[current_rel].files.sort(key=lambda x: x.name.lower())

        # Stack is LIFO. Reverse so printed/index order remains alphabetical.
        for child in reversed(sorted(child_dirs, key=lambda x: x[1].lower())):
            stack.append(child)

        now = time.time()
        if now - last_progress >= SCAN_PROGRESS_EVERY_SECONDS:
            print(
                f"Scanning... folders: {scanned_folders:,} | "
                f"files: {total_files:,} | "
                f"size: {format_size(total_size)}"
            )
            last_progress = now

    index = AuditIndex(
        root=str(root),
        scanned_at=now_text(),
        folders=folders,
        total_files=total_files,
        total_folders=len(folders),
        total_size_bytes=total_size,
        extension_counts=dict(extension_counts),
        extension_sizes=dict(extension_sizes),
        inaccessible_paths=inaccessible_paths,
    )

    print("\nScan complete.")
    print(f"Folders: {index.total_folders:,}")
    print(f"Files: {index.total_files:,}")
    print(f"Total size: {format_size(index.total_size_bytes)}")
    if inaccessible_paths:
        print(f"Inaccessible/skipped due to errors: {len(inaccessible_paths):,}")

    return index


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def build_summary_lines(index: AuditIndex, top_n: int = 20) -> List[str]:
    lines = []
    lines.append("SUMMARY")
    lines.append("=" * 80)
    lines.append(f"Root: {index.root}")
    lines.append(f"Scanned at: {index.scanned_at}")
    lines.append(f"Total folders: {index.total_folders:,}")
    lines.append(f"Total files: {index.total_files:,}")
    lines.append(f"Total size: {format_size(index.total_size_bytes)}")
    lines.append(f"Inaccessible paths: {len(index.inaccessible_paths):,}")
    lines.append("")

    lines.append(f"Top file types by count, top {top_n}:")
    lines.append(f"{'Type':<18} {'Files':>12} {'Size':>14}")
    lines.append("-" * 48)

    items = sorted(
        index.extension_counts.items(),
        key=lambda kv: (-kv[1], kv[0])
    )[:top_n]

    if not items:
        lines.append("(No files found.)")
    else:
        for ext, count in items:
            size = index.extension_sizes.get(ext, 0)
            lines.append(f"{ext:<18} {count:>12,} {format_size(size):>14}")

    return lines


def show_summary(index: AuditIndex) -> None:
    clear_screen()
    print("\n".join(build_summary_lines(index)))
    pause()


# ---------------------------------------------------------------------------
# Tree output
# ---------------------------------------------------------------------------

def tree_chars() -> Tuple[str, str, str, str]:
    if USE_UNICODE_TREE:
        return "├── ", "└── ", "│   ", "    "
    return "|-- ", "`-- ", "|   ", "    "


def build_tree_lines(index: AuditIndex, start_rel: str = ".", max_depth: Optional[int] = None) -> List[str]:
    branch_mid, branch_last, pipe, blank = tree_chars()

    start_rel = normalize_rel(start_rel)
    if start_rel not in index.folders:
        return [f"Folder not found: {start_rel}"]

    start_folder = index.folders[start_rel]
    title = start_folder.name if start_rel != "." else Path(index.root).name
    if not title:
        title = index.root

    lines: List[str] = [title]

    def add_children(folder_rel: str, prefix: str, depth: int) -> None:
        if max_depth is not None and depth >= max_depth:
            children = index.folders[folder_rel].child_folders
            if children:
                lines.append(prefix + "... [tree depth limit reached]")
            return

        children = index.folders[folder_rel].child_folders
        for i, child_rel in enumerate(children):
            is_last = i == len(children) - 1
            connector = branch_last if is_last else branch_mid
            child_name = index.folders[child_rel].name
            lines.append(prefix + connector + child_name)
            extension = blank if is_last else pipe
            add_children(child_rel, prefix + extension, depth + 1)

    add_children(start_rel, "", 0)
    return lines


def show_folder_tree(index: AuditIndex) -> None:
    clear_screen()
    print("Folder tree display")
    print("=" * 80)
    print("Choose tree depth:")
    print("1. Depth 1")
    print("2. Depth 2")
    print("3. Depth 3")
    print("4. Full tree")
    print("5. Custom depth")

    choice = input("\nChoice: ").strip()

    if choice == "1":
        max_depth = 1
    elif choice == "2":
        max_depth = 2
    elif choice == "3" or choice == "":
        max_depth = 3
    elif choice == "4":
        max_depth = None
    elif choice == "5":
        raw = input("Enter maximum depth number: ").strip()
        try:
            max_depth = max(1, int(raw))
        except ValueError:
            max_depth = TREE_DEFAULT_DEPTH
    else:
        max_depth = TREE_DEFAULT_DEPTH

    clear_screen()
    lines = build_tree_lines(index, ".", max_depth=max_depth)
    print("\n".join(lines))
    pause()


# ---------------------------------------------------------------------------
# Folder selection and browsing
# ---------------------------------------------------------------------------

def folder_display_name(index: AuditIndex, rel_path: str) -> str:
    if rel_path == ".":
        return f"[ROOT] {index.root}"
    return rel_path


def select_folder_from_list(index: AuditIndex) -> Optional[str]:
    """
    Search/select folder by entering part of the path.
    Useful when the user does not want to manually browse.
    """
    query = input("\nEnter part of folder name/path to search: ").strip().lower()
    if not query:
        return None

    matches = [
        rel for rel in sorted(index.folders.keys(), key=sort_key_path)
        if query in rel.lower() or query in index.folders[rel].name.lower()
    ]

    if not matches:
        print("No matching folders found.")
        pause()
        return None

    page = 0
    while True:
        clear_screen()
        print(f"Folder matches for: {query}")
        print("=" * 80)

        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        chunk = matches[start:end]

        for i, rel in enumerate(chunk, start=1):
            print(f"[{i}] {folder_display_name(index, rel)}")

        print(f"\nShowing {start + 1}-{min(end, len(matches))} of {len(matches)}")
        print("[N] Next page | [P] Previous page | [Q] Cancel")
        raw = input("\nSelect folder number: ").strip().lower()

        if raw == "q":
            return None
        if raw == "n":
            if end < len(matches):
                page += 1
            continue
        if raw == "p":
            if page > 0:
                page -= 1
            continue

        try:
            selected = int(raw)
            if 1 <= selected <= len(chunk):
                return chunk[selected - 1]
        except ValueError:
            pass

        print("Invalid selection.")
        time.sleep(0.8)


def browse_folders(index: AuditIndex) -> Optional[str]:
    current = "."
    history: List[str] = []

    while True:
        clear_screen()
        current_record = index.folders[current]
        child_folders = current_record.child_folders

        print("Folder browser")
        print("=" * 80)
        print(f"Current: {folder_display_name(index, current)}")
        print(f"Subfolders: {len(child_folders):,}")
        print(f"Direct files in this folder: {len(current_record.files):,}")
        print("")

        print("[0] Select this folder")
        for i, child_rel in enumerate(child_folders, start=1):
            child_record = index.folders[child_rel]
            print(f"[{i}] {child_record.name}/")

        print("\n[B] Back | [S] Search folder names | [Q] Quit browser")
        raw = input("\nChoice: ").strip().lower()

        if raw == "q":
            return None

        if raw == "b":
            if history:
                current = history.pop()
            continue

        if raw == "s":
            selected = select_folder_from_list(index)
            if selected is not None:
                return selected
            continue

        if raw == "0" or raw == "":
            return current

        try:
            selected_num = int(raw)
            if 1 <= selected_num <= len(child_folders):
                history.append(current)
                current = child_folders[selected_num - 1]
                continue
        except ValueError:
            pass

        print("Invalid choice.")
        time.sleep(0.8)


# ---------------------------------------------------------------------------
# File listing
# ---------------------------------------------------------------------------

def get_files_under_folder(index: AuditIndex, folder_rel: str, recursive: bool) -> List[FileRecord]:
    folder_rel = normalize_rel(folder_rel)
    if folder_rel not in index.folders:
        return []

    if not recursive:
        return list(index.folders[folder_rel].files)

    files: List[FileRecord] = []
    stack = [folder_rel]

    while stack:
        rel = stack.pop()
        record = index.folders[rel]
        files.extend(record.files)
        for child in reversed(record.child_folders):
            stack.append(child)

    files.sort(key=lambda f: f.rel_path.lower())
    return files


def file_listing_lines(files: List[FileRecord], root: str, show_paths: bool = True) -> List[str]:
    lines: List[str] = []
    lines.append(f"{'File':<55} {'Size':>12} {'Modified':<18} {'Type':<16}")
    lines.append("-" * 110)

    if not files:
        lines.append("(No files found.)")
        return lines

    for fr in files:
        label = fr.rel_path if show_paths else fr.name
        if len(label) > 55:
            label = "..." + label[-52:]

        lines.append(
            f"{label:<55} "
            f"{format_size(fr.size_bytes):>12} "
            f"{fr.modified_text:<18} "
            f"{fr.extension:<16}"
        )

    return lines


def paginated_print(lines: List[str], header: Optional[str] = None, page_size: int = PAGE_SIZE) -> None:
    if not lines:
        print("(Nothing to display.)")
        pause()
        return

    page = 0
    total_pages = max(1, math.ceil(len(lines) / page_size))

    while True:
        clear_screen()
        if header:
            print(header)
            print("=" * 80)

        start = page * page_size
        end = start + page_size
        for line in lines[start:end]:
            print(line)

        print(f"\nPage {page + 1} of {total_pages}")
        print("[Enter/N] Next | [P] Previous | [Q] Quit")
        raw = input("\nChoice: ").strip().lower()

        if raw in {"q", "quit"}:
            break
        if raw in {"p", "prev", "previous"}:
            if page > 0:
                page -= 1
            continue
        if raw in {"", "n", "next"}:
            if page < total_pages - 1:
                page += 1
            else:
                break
            continue


def list_files_menu(index: AuditIndex) -> None:
    selected = browse_folders(index)
    if selected is None:
        return

    print("\nList files:")
    print("1. Direct files only")
    print("2. All files recursively under this folder")
    choice = input("\nChoice [2]: ").strip()

    recursive = choice != "1"

    files = get_files_under_folder(index, selected, recursive=recursive)
    total_size = sum(f.size_bytes for f in files)

    header = (
        f"Files under: {folder_display_name(index, selected)}\n"
        f"Mode: {'Recursive' if recursive else 'Direct only'}\n"
        f"Files: {len(files):,} | Size: {format_size(total_size)}"
    )

    lines = file_listing_lines(files, index.root, show_paths=recursive)
    paginated_print(lines, header=header)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def all_files(index: AuditIndex) -> List[FileRecord]:
    files: List[FileRecord] = []
    for rel in sorted(index.folders.keys(), key=sort_key_path):
        files.extend(index.folders[rel].files)
    return files


def search_files(index: AuditIndex, query: str) -> List[FileRecord]:
    query = query.strip().lower()
    if not query:
        return []

    terms = [term.strip().lower() for term in query.split() if term.strip()]
    files = all_files(index)

    results: List[FileRecord] = []
    for fr in files:
        name = fr.name.lower()
        path = fr.rel_path.lower()
        ext = fr.extension.lower()

        matched_all_terms = True
        for term in terms:
            if term.startswith("."):
                matched = ext == term or path.endswith(term)
            else:
                matched = term in name or term in path or term == ext.lstrip(".")
            if not matched:
                matched_all_terms = False
                break

        if matched_all_terms:
            results.append(fr)

    results.sort(key=lambda f: f.rel_path.lower())
    return results


def search_menu(index: AuditIndex) -> Optional[Tuple[str, List[FileRecord]]]:
    clear_screen()
    print("Search filenames")
    print("=" * 80)
    print("Examples:")
    print("  ketamine")
    print("  TSA-250374")
    print("  .pdf")
    print("  invoice .xlsx")
    print("")
    query = input("Enter search term(s): ").strip()
    if not query:
        return None

    results = search_files(index, query)
    total_size = sum(f.size_bytes for f in results)

    header = (
        f"Search: {query}\n"
        f"Matches: {len(results):,} | Total size: {format_size(total_size)}"
    )

    lines = file_listing_lines(results, index.root, show_paths=True)
    paginated_print(lines, header=header)

    return query, results


def search_report_lines(query: str, results: List[FileRecord]) -> List[str]:
    total_size = sum(f.size_bytes for f in results)
    lines = []
    lines.append("SEARCH RESULTS")
    lines.append("=" * 80)
    lines.append(f"Search term(s): {query}")
    lines.append(f"Matches: {len(results):,}")
    lines.append(f"Total size: {format_size(total_size)}")
    lines.append("")
    lines.extend(file_listing_lines(results, root="", show_paths=True))
    return lines


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def build_full_file_report_lines(index: AuditIndex) -> List[str]:
    files = all_files(index)
    lines = []
    lines.append("FULL FILE LISTING")
    lines.append("=" * 80)
    lines.append(f"Files: {len(files):,}")
    lines.append(f"Total size: {format_size(sum(f.size_bytes for f in files))}")
    lines.append("")
    lines.extend(file_listing_lines(files, index.root, show_paths=True))
    return lines


def export_report(index: AuditIndex, last_search: Optional[Tuple[str, List[FileRecord]]] = None) -> None:
    clear_screen()
    print("Export report")
    print("=" * 80)

    include_full_tree = input("Include full folder tree? [Y/n]: ").strip().lower()
    full_tree = include_full_tree not in {"n", "no"}

    include_files = input("Include full file listing? This can be huge. [y/N]: ").strip().lower()
    full_files = include_files in {"y", "yes"}

    include_last_search = False
    if last_search is not None:
        q, r = last_search
        print(f"\nLast search available: {q} ({len(r):,} matches)")
        raw = input("Include last search results? [Y/n]: ").strip().lower()
        include_last_search = raw not in {"n", "no"}

    report_name = f"folder_audit_report_{timestamp_for_filename()}.txt"
    report_path = Path(index.root) / report_name

    lines: List[str] = []
    lines.append("FOLDER AUDIT REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated at: {now_text()}")
    lines.append("")
    lines.extend(build_summary_lines(index))
    lines.append("")

    lines.append("FOLDER TREE")
    lines.append("=" * 80)
    if full_tree:
        lines.extend(build_tree_lines(index, ".", max_depth=None))
    else:
        lines.extend(build_tree_lines(index, ".", max_depth=TREE_DEFAULT_DEPTH))
    lines.append("")

    if full_files:
        lines.extend(build_full_file_report_lines(index))
        lines.append("")

    if include_last_search and last_search is not None:
        q, r = last_search
        lines.extend(search_report_lines(q, r))
        lines.append("")

    if index.inaccessible_paths:
        lines.append("INACCESSIBLE PATHS / SCAN ERRORS")
        lines.append("=" * 80)
        for p in index.inaccessible_paths:
            lines.append(p)
        lines.append("")

    try:
        with report_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nReport exported:")
        print(report_path)
    except Exception as e:
        print(f"\nCould not write report: {e}")

    pause()


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def print_main_menu(index: AuditIndex) -> None:
    clear_screen()
    print("zFolderAudit.py")
    print("=" * 80)
    print(f"Root: {index.root}")
    print(f"Scanned at: {index.scanned_at}")
    print(f"Folders: {index.total_folders:,} | Files: {index.total_files:,} | Size: {format_size(index.total_size_bytes)}")
    print("")
    print("1. Show summary statistics")
    print("2. Show folder tree")
    print("3. Browse folders")
    print("4. List files under selected folder")
    print("5. Search filenames")
    print("6. Export report")
    print("7. Save scan cache")
    print("8. Rescan")
    print("9. Exit")


def main() -> None:
    try:
        root = Path(__file__).resolve().parent
    except NameError:
        root = Path.cwd().resolve()

    print("zFolderAudit.py")
    print("=" * 80)
    print("This tool is read-only. It does not move, rename, or delete files.")
    print(f"Script/root folder: {root}")

    index = ask_use_cache(root)
    if index is None:
        index = scan_directory(root)
        raw = input("\nSave scan cache for faster future startup? [Y/n]: ").strip().lower()
        if raw not in {"n", "no"}:
            save_cache(index)
        pause()

    last_search: Optional[Tuple[str, List[FileRecord]]] = None

    while True:
        print_main_menu(index)
        choice = input("\nChoice: ").strip().lower()

        if choice == "1":
            show_summary(index)

        elif choice == "2":
            show_folder_tree(index)

        elif choice == "3":
            selected = browse_folders(index)
            if selected is not None:
                clear_screen()
                print("Selected folder")
                print("=" * 80)
                print(folder_display_name(index, selected))
                record = index.folders[selected]
                recursive_files = get_files_under_folder(index, selected, recursive=True)
                print(f"Subfolders directly inside: {len(record.child_folders):,}")
                print(f"Files directly inside: {len(record.files):,}")
                print(f"Files recursively under this folder: {len(recursive_files):,}")
                print(f"Recursive size: {format_size(sum(f.size_bytes for f in recursive_files))}")
                pause()

        elif choice == "4":
            list_files_menu(index)

        elif choice == "5":
            result = search_menu(index)
            if result is not None:
                last_search = result

        elif choice == "6":
            export_report(index, last_search=last_search)

        elif choice == "7":
            save_cache(index)
            pause()

        elif choice == "8":
            confirm = input("Rescan from disk now? [y/N]: ").strip().lower()
            if confirm in {"y", "yes"}:
                index = scan_directory(root)
                raw = input("\nSave updated cache? [Y/n]: ").strip().lower()
                if raw not in {"n", "no"}:
                    save_cache(index)
                last_search = None
                pause()

        elif choice in {"9", "q", "quit", "exit"}:
            print("Exiting.")
            break

        else:
            print("Invalid choice.")
            time.sleep(0.8)


if __name__ == "__main__":
    main()
