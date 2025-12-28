# This Python script provides multiple functionalities:
# 1. List files in the current directory and display folder structure.
# 2. Run list_files function - reads down 2 levels of directories and reports sizes as well
# 3. Rename files in the current directory with a prefix.
# 4. Remove prefix from files in the current directory.
# 5. Reports on images and video files by date
# 6. List sub folder structure
# 7. Replace empty spaces in file names with underscores. Only current folder or directory.
# 8. Scan for Study IDs in filenames and content.
# 9. Compare two folders (recursive): identical, only-in-A/B, and modified/different files.
# The user can select the desired function from the main menu.
# The script prompts for user input and performs the chosen operation.


import os
import math
import re
import datetime
import hashlib


def get_directory_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size


def get_size_string(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{round(size / 1024, 2)} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{round(size / (1024 * 1024), 2)} MB"
    else:
        return f"{round(size / (1024 * 1024 * 1024), 2)} GB"


def list_files():
    path = os.getcwd()
    input("Press any key to view folders and their sizes...")
    folders = []
    for folder in os.listdir(path):
        folder_path = os.path.join(path, folder)
        if os.path.isdir(folder_path):
            size = get_directory_size(folder_path)
            folders.append((folder, size))

    folders.sort(key=lambda x: x[1], reverse=True)

    print("Folders in the current directory:")
    for folder, size in folders:
        size_string = get_size_string(size)
        print(f"\033[93m{folder}\033[0m ({size_string})")  # Print folders in yellow

    input("Press any key to view files in the current directory...")
    files = []
    total_size = 0
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            total_size += size
            if file.endswith((".exe", ".py")):
                files.append((file, size, True))  # Mark .exe and .py files with red flag
            else:
                files.append((file, size, False))

    files.sort(key=lambda x: x[1], reverse=True)

    print("\nFiles in the current directory:")
    for file, size, red in files:
        size_string = get_size_string(size)
        percentage = (size / total_size) * 100 if total_size > 0 else 0
        if red:
            print(f"\033[91m{file}\033[0m ({size_string}) [{percentage:.2f}%]")  # Print executables and .py files in red
        else:
            print(f"\033[92m{file}\033[0m ({size_string}) [{percentage:.2f}%]")  # Print other files in green

    input("Press any key to view the folder structure...")
    print("\nFolder structure:")
    for folder, size in folders:
        dirpath = os.path.join(path, folder)
        depth = dirpath.count(os.path.sep) - path.count(os.path.sep)
        indent = " " * 4 * depth
        size_string = get_size_string(size)
        print(f"\033[93m{indent}{os.path.basename(dirpath)}\033[0m ({size_string})")  # Print folders in yellow
        subindent = " " * 4 * (depth + 1)
        for dirpath, dirnames, filenames in os.walk(dirpath):
            for f in filenames:
                file_path = os.path.join(dirpath, f)
                size = os.path.getsize(file_path)
                size_string = get_size_string(size)
                percentage = (size / total_size) * 100 if total_size > 0 else 0
                if f.endswith((".exe", ".py")):
                    print(f"{subindent}\033[91m{f}\033[0m ({size_string}) [{percentage:.2f}%]")  # Print executables and .py files in red
                else:
                    print(f"{subindent}\033[92m{f}\033[0m ({size_string}) [{percentage:.2f}%]")  # Print other files in green


def list_files_alphabetical():
    path = os.getcwd()
    print("\nFiles in the current directory (alphabetical order):\n")
    files = sorted(os.listdir(path))
    for file in files:
        print(file)


def rename_files_with_prefix():
    path = os.getcwd()
    files = sorted(os.listdir(path))

    script_file = os.path.basename(__file__)
    files = [file for file in files if file != script_file]

    print("Current files in the directory:")
    for file in files:
        print(file)

    prefix = input("\nEnter a prefix (YYYYMMDD or YYYYMMXX): ")
    if not re.match(r"\d{6}(?:\d{2}|XX)$", prefix):
        print("Invalid prefix format.")
        return

    description = input("Enter a description: ")

    print("\nNew file names:")
    for file in files:
        if os.path.isfile(os.path.join(path, file)):
            file_extension = os.path.splitext(file)[1]
            new_name = f"{prefix}_{description}_{os.path.splitext(file)[0]}{file_extension}"
            print(f"{file}\n{'--->'} {new_name}\n")

    confirm = input("\nType 'Y' to confirm renaming the files: ")
    if confirm.lower() != "y":
        print("Action canceled.")
        return

    new_files = []
    for old_name in files:
        if os.path.isfile(os.path.join(path, old_name)):
            file_extension = os.path.splitext(old_name)[1]
            new_name = f"{prefix}_{description}_{os.path.splitext(old_name)[0]}{file_extension}"
            new_files.append((old_name, new_name))

    for old_name, new_name in new_files:
        os.rename(os.path.join(path, old_name), os.path.join(path, new_name))

    print("\nFiles renamed successfully.")


def remove_prefix_from_files():
    path = os.getcwd()
    files = sorted(os.listdir(path))

    print("Current files in the directory:")
    for file in files:
        print(file)

    prefix = input("\nEnter the prefix to remove (YYYYMMDD): ")
    if not re.match(r"\d{8}$", prefix):
        print("Invalid prefix format.")
        return

    pattern = fr"^{re.escape(prefix)}_[^_]+_"

    print("\nFiles to be renamed:")
    renamed_files = []
    for file in files:
        if os.path.isfile(os.path.join(path, file)):
            match = re.search(pattern, file)
            if match:
                new_name = re.sub(pattern, "", file)
                print(f"{file} -> {new_name}")
                renamed_files.append((file, new_name))

    confirm = input("\nType 'Y' to confirm renaming the files: ")
    if confirm.lower() != "y":
        print("Action canceled.")
        return

    for old_name, new_name in renamed_files:
        os.rename(os.path.join(path, old_name), os.path.join(path, new_name))

    print("\nFiles renamed successfully.")


def group_files_by_date():
    path = os.getcwd()
    files = sorted(os.listdir(path))

    image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    video_extensions = ['.mp4', '.avi', '.mov']

    prefix_pattern = r"(\d{8}|\d{6}XX)"

    # Dictionary to store grouped files by date
    file_groups = {}

    # Iterate over the files
    for file in files:
        file_path = os.path.join(path, file)

        # Check if it's a file and has an image or video extension
        if os.path.isfile(file_path) and (file.lower().endswith(tuple(image_extensions)) or file.lower().endswith(tuple(video_extensions))):
            # Extract the prefix from the file name
            match = re.search(prefix_pattern, file)
            if match:
                prefix = match.group(1)

                # Create a new date block if it doesn't exist
                if prefix not in file_groups:
                    file_groups[prefix] = {
                        'images': [],
                        'videos': [],
                        'size': 0,
                        'num_images': 0,
                        'num_videos': 0,
                        'other_strings': set()
                    }

                # Group the file based on its type (image or video)
                file_type = 'images' if file.lower().endswith(tuple(image_extensions)) else 'videos'
                file_groups[prefix][file_type].append(file)

                # Update the size and count for the date block
                file_groups[prefix]['size'] += os.path.getsize(file_path)
                file_groups[prefix]['num_images'] += 1 if file_type == 'images' else 0
                file_groups[prefix]['num_videos'] += 1 if file_type == 'videos' else 0

                # Extract other strings from the file name
                other_strings = re.findall(r"_(.*?)_", file)
                file_groups[prefix]['other_strings'].update(other_strings)

    # Print the grouped files and summary for each date block
    for prefix, data in file_groups.items():
        print(f"\nDate Block: {prefix}")
        print(f"Images: {data['num_images']}")
        print(f"Videos: {data['num_videos']}")
        print(f"Total Size: {get_size_string(data['size'])}")
        print(f"Other Strings: {', '.join(data['other_strings'])}\n")
        print("Files:")
        for file_type, files_list in data.items():
            if file_type not in ['size', 'num_images', 'num_videos', 'other_strings']:
                for file in files_list:
                    print(f"\033[92m{file}\033[0m")


def list_subfolders_and_save():
    path = os.getcwd()
    subfolders = []

    # Traverse through all subfolders
    for root, dirs, files in os.walk(path):
        for dir in dirs:
            subfolder_path = os.path.join(root, dir)
            subfolders.append(subfolder_path)

    # Sort the subfolders for better readability
    subfolders.sort()

    # Print subfolders and write to a text file
    with open('zfileanaloutput_subfolders_list.txt', 'w') as file:
        for subfolder in subfolders:
            print(subfolder)
            file.write(subfolder + '\n')

    print("\nSubfolder structure saved to 'subfolders_list.txt'")


def replace_spaces_in_filenames():
    print("\n\nFunction to Replace Spaces in Filenames:")
    print("This function will scan all files in the current directory.")
    print("It will identify files with spaces in their names and display them.")
    print("You will then have the option to replace all spaces with underscores.\n\n")

    path = os.getcwd()
    files_with_spaces = {file: file.count(' ') for file in os.listdir(path) if ' ' in file}

    if not files_with_spaces:
        print("No files with spaces in their names were found.")
        return

    print("Files with spaces:")
    for file, space_count in files_with_spaces.items():
        print(f"{file} - {space_count} spaces")

    choice = input("Do you want to replace spaces with underscores in these files? (y/n): ")
    if choice.lower() == 'y':
        for file in files_with_spaces:
            new_name = file.replace(' ', '_')
            os.rename(os.path.join(path, file), os.path.join(path, new_name))
        print("Spaces in file names have been replaced with underscores.")
    else:
        print("No changes were made.")


def find_study_ids():
    # Get the current working directory, which will be our base path.
    base_path = os.getcwd()

    # Regex to be more flexible with the number of digits.
    study_id_pattern = re.compile(
        r'TSA-\d{5,6}-[a-zA-Z]{3}|'   # Matches TSA-#####-XXX or TSA-######-XXX
        r'TPC\d{1,3}-\d{5}-[a-zA-Z]{2,3}'  # Matches TPC#-#####-XX(X), TPC##-..., TPC###-...
    )

    # Dictionary to store locations. The value is a set of tuples (context, full_path)
    found_locations = {}

    # Skip files larger than 100 MB
    MAX_SIZE = 100 * 1024 * 1024  # bytes

    print(f"Starting scan in: {base_path}\n", flush=True)

    dir_count = 0
    for root, dirs, files in os.walk(base_path):
        dir_count += 1
        print(f"[{dir_count}] Scanning directory: {root}", flush=True)

        # 1. Check all directory names
        for name in dirs:
            for match in study_id_pattern.finditer(name):
                sid = match.group()
                found_locations.setdefault(sid, set()).add(
                    ('in Folder Name', os.path.join(root, name))
                )

        # 2. Check all file names and their content
        for name in files:
            filepath = os.path.join(root, name)

            # 2a. Check the filename itself
            for match in study_id_pattern.finditer(name):
                sid = match.group()
                found_locations.setdefault(sid, set()).add(
                    ('in File Name', filepath)
                )

            # 2b. Check the content within the file (line-by-line)
            try:
                size = os.path.getsize(filepath)
                if size <= MAX_SIZE:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            for match in study_id_pattern.finditer(line):
                                sid = match.group()
                                found_locations.setdefault(sid, set()).add(
                                    ('in File Content', filepath)
                                )
                else:
                    print(f"    ↳ Skipped large file (>100 MB): {os.path.relpath(filepath, base_path)}", flush=True)
            except (IOError, OSError):
                print(f"    ↳ Could not read: {os.path.relpath(filepath, base_path)}", flush=True)
                continue

        print(f"    → Unique IDs found so far: {len(found_locations)}\n", flush=True)

    if not found_locations:
        print("No Study IDs found matching the specified formats.", flush=True)
        return

    # --- File output logic ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    output_filename = f"zFileAnal_Studies_{timestamp}.txt"

    header = "--- Scan Complete. Found the following Study IDs ---"
    console_header = f"Base Directory: \033[92m{base_path}\033[0m"
    file_header = f"Base Directory: {base_path}"

    print(f"\n{header}")
    print(console_header + "\n")

    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(f"{header}\n{file_header}\n\n")

            for study_id, locations in sorted(found_locations.items()):
                print(f"\033[93mID: {study_id}\033[0m")
                f.write(f"\nID: {study_id}\n")

                for context, full_path in sorted(locations):
                    rel = os.path.relpath(full_path, base_path)
                    line = f"  • Found {context}: {rel}"
                    print(line)
                    f.write(f"{line}\n")

        print(f"\n\033[92mResults also saved to: {output_filename}\033[0m")
    except IOError:
        print(f"\n\033[91mError: Could not write results to file: {output_filename}\033[0m")
        return

    # --- Interactive filter ---
    substr = input("\nEnter any part of a Study ID to filter (or press Enter to exit): ").strip()
    if substr:
        print(f"\nFiltering for IDs containing \"{substr}\":\n")
        found_any = False
        for study_id, locations in sorted(found_locations.items()):
            if substr in study_id:
                found_any = True
                print(f"\033[93mID: {study_id}\033[0m")
                for context, full_path in sorted(locations):
                    rel = os.path.relpath(full_path, base_path)
                    print(f"  • Found {context}: {rel}")
                print()
        if not found_any:
            print(f"No Study IDs containing \"{substr}\" were found.")
    else:
        print("No filter entered; exiting.")


# ----------------------------
# Function 9: Compare two folders
# ----------------------------

def _safe_norm_relpath(path):
    """
    Normalizes a relative path for comparison.
    On Windows, comparisons are typically case-insensitive, so we lower() it.
    """
    return os.path.normpath(path).lower()


def _file_hash_sha256(filepath, chunk_size=1024 * 1024):
    """Compute SHA-256 hash of a file in chunks to support large files."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _scan_tree(base_path):
    """
    Returns:
      files: dict[normalized_relpath] -> dict with metadata + original relpath
      folders: set[normalized_relpath]
    """
    files = {}
    folders = set()

    for root, dirs, filenames in os.walk(base_path):
        rel_root = os.path.relpath(root, base_path)
        if rel_root == ".":
            rel_root = ""

        # record folders
        for d in dirs:
            rel_dir = os.path.join(rel_root, d)
            folders.add(_safe_norm_relpath(rel_dir))

        # record files
        for fn in filenames:
            rel_file = os.path.join(rel_root, fn)
            norm_rel = _safe_norm_relpath(rel_file)
            full = os.path.join(root, fn)

            try:
                st = os.stat(full)
                files[norm_rel] = {
                    "rel": os.path.normpath(rel_file),   # keep original-ish for display
                    "full": full,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            except (OSError, IOError):
                continue

    return files, folders


def compare_two_folders():
    """
    Compare two folder trees recursively.
      - Identical files present in both (same relative path and matching metadata; optional hashing)
      - Files/folders only in A or only in B (counts + organized lists)
      - Modified/different files (mtime and/or size differences; optional hash verification)
      - Console preview indicates which folder holds the most recent version (by mtime)
    """
    print("\nCOMPARE TWO FOLDERS (Recursive)\n")

    path_a = input("Enter Folder A path: ").strip().strip('"')
    path_b = input("Enter Folder B path: ").strip().strip('"')

    if not os.path.isdir(path_a):
        print(f"Folder A is not a valid directory: {path_a}")
        return
    if not os.path.isdir(path_b):
        print(f"Folder B is not a valid directory: {path_b}")
        return

    label_a = "A"
    label_b = "B"

    print("\nHash options (slower but more accurate):")
    print("  0) No hashing (fast; uses size+mtime)")
    print("  1) Hash only files that differ by size/mtime (recommended)")
    print("  2) Hash all files that exist in both folders (slowest)")
    hash_choice = input("Select hash option [0-2] (default 1): ").strip() or "1"
    if hash_choice not in {"0", "1", "2"}:
        print("Invalid choice. Defaulting to 1.")
        hash_choice = "1"
    hash_mode = int(hash_choice)

    print("\nScanning Folder A...")
    files_a, folders_a = _scan_tree(path_a)
    print(f"  Files: {len(files_a):,} | Folders: {len(folders_a):,}")

    print("Scanning Folder B...")
    files_b, folders_b = _scan_tree(path_b)
    print(f"  Files: {len(files_b):,} | Folders: {len(folders_b):,}")

    common_folders = folders_a.intersection(folders_b)
    only_folders_a = sorted(folders_a - folders_b)
    only_folders_b = sorted(folders_b - folders_a)

    keys_a = set(files_a.keys())
    keys_b = set(files_b.keys())

    common_files = sorted(keys_a.intersection(keys_b))
    only_files_a = sorted(keys_a - keys_b)
    only_files_b = sorted(keys_b - keys_a)

    identical = []
    different = []
    hash_verified_identical = 0

    def _mtime_close(a, b, tol_seconds=2.0):
        # Windows timestamp resolution differences can occur; use small tolerance.
        return abs(a - b) <= tol_seconds

    def _fmt_time(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    def _newer_label(fa, fb):
        # Decide which is most recent by mtime; if within tolerance, call it "same"
        if _mtime_close(fa["mtime"], fb["mtime"]):
            return "Same mtime"
        return f"{label_a} newer" if fa["mtime"] > fb["mtime"] else f"{label_b} newer"

    for k in common_files:
        fa = files_a[k]
        fb = files_b[k]

        size_same = (fa["size"] == fb["size"])
        mtime_same = _mtime_close(fa["mtime"], fb["mtime"])

        if size_same and mtime_same and hash_mode != 2:
            identical.append((fa, fb, "size+mtime"))
            continue

        if hash_mode == 0:
            if size_same and mtime_same:
                identical.append((fa, fb, "size+mtime"))
            else:
                different.append((fa, fb, "size/mtime differs"))
            continue

        need_hash = (hash_mode == 2) or (hash_mode == 1 and (not size_same or not mtime_same))
        if need_hash:
            try:
                ha = _file_hash_sha256(fa["full"])
                hb = _file_hash_sha256(fb["full"])
                if ha == hb:
                    identical.append((fa, fb, "sha256"))
                    hash_verified_identical += 1
                else:
                    different.append((fa, fb, "sha256 differs"))
            except (OSError, IOError):
                different.append((fa, fb, "hash failed/read error"))
        else:
            if size_same and mtime_same:
                identical.append((fa, fb, "size+mtime"))
            else:
                different.append((fa, fb, "size/mtime differs"))

    modified_mtime = []
    modified_size = []
    for fa, fb, reason in different:
        if fa["size"] != fb["size"]:
            modified_size.append((fa, fb, reason))
        if not _mtime_close(fa["mtime"], fb["mtime"]):
            modified_mtime.append((fa, fb, reason))

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    out_name = f"zFileAnal_FolderCompare_{timestamp}.txt"

    def _write_section(f, title):
        f.write("\n" + title + "\n")
        f.write("-" * len(title) + "\n")

    def _print_list_block(title, items, max_items=None):
        print(f"\n{title} ({len(items):,}):")
        if not items:
            print("  (none)")
            return
        show = items if (max_items is None) else items[:max_items]
        for x in show:
            print(f"  • {x}")
        if max_items is not None and len(items) > max_items:
            print(f"  ... and {len(items) - max_items:,} more")

    # Build human-readable rel paths for console listing
    only_files_a_rel = [files_a[k]["rel"] for k in only_files_a]
    only_files_b_rel = [files_b[k]["rel"] for k in only_files_b]

    # Folders are stored as normalized relpaths already (lowercase); print them as-is
    only_folders_a_rel = only_folders_a
    only_folders_b_rel = only_folders_b

    print("\n--- SUMMARY ---")
    print(f"Folder {label_a}: {path_a}")
    print(f"Folder {label_b}: {path_b}\n")

    print(f"Common folders: {len(common_folders):,}")
    print(f"Folders only in {label_a}: {len(only_folders_a_rel):,}")
    print(f"Folders only in {label_b}: {len(only_folders_b_rel):,}\n")

    print(f"Common files (same relative path): {len(common_files):,}")
    print(f"Identical files: {len(identical):,} (hash-verified: {hash_verified_identical:,})")
    print(f"Different/modified files: {len(different):,}")
    print(f"Files only in {label_a}: {len(only_files_a_rel):,}")
    print(f"Files only in {label_b}: {len(only_files_b_rel):,}")

    # Console listings (organized, but not overwhelming)
    # You can change max_items if you want longer/shorter default console output.
    max_console_list = 80
    _print_list_block(f"Folders only in {label_a}", only_folders_a_rel, max_items=max_console_list)
    _print_list_block(f"Folders only in {label_b}", only_folders_b_rel, max_items=max_console_list)
    _print_list_block(f"Files only in {label_a}", only_files_a_rel, max_items=max_console_list)
    _print_list_block(f"Files only in {label_b}", only_files_b_rel, max_items=max_console_list)

    try:
        with open(out_name, "w", encoding="utf-8") as f:
            f.write("FOLDER COMPARISON REPORT\n")
            f.write(f"Generated: {datetime.datetime.now()}\n\n")
            f.write(f"Folder {label_a}: {path_a}\n")
            f.write(f"Folder {label_b}: {path_b}\n")
            f.write(f"Hash mode: {hash_mode}\n")

            _write_section(f, "Summary")
            f.write(f"Common folders: {len(common_folders)}\n")
            f.write(f"Folders only in {label_a}: {len(only_folders_a_rel)}\n")
            f.write(f"Folders only in {label_b}: {len(only_folders_b_rel)}\n\n")
            f.write(f"Common files: {len(common_files)}\n")
            f.write(f"Identical files: {len(identical)} (hash-verified: {hash_verified_identical})\n")
            f.write(f"Different/modified files: {len(different)}\n")
            f.write(f"Files only in {label_a}: {len(only_files_a_rel)}\n")
            f.write(f"Files only in {label_b}: {len(only_files_b_rel)}\n")

            _write_section(f, f"Folders only in {label_a}")
            if only_folders_a_rel:
                for rel in only_folders_a_rel:
                    f.write(f"  • {rel}\n")
            else:
                f.write("  (none)\n")

            _write_section(f, f"Folders only in {label_b}")
            if only_folders_b_rel:
                for rel in only_folders_b_rel:
                    f.write(f"  • {rel}\n")
            else:
                f.write("  (none)\n")

            _write_section(f, f"Files only in {label_a}")
            if only_files_a_rel:
                for rel in only_files_a_rel:
                    f.write(f"  • {rel}\n")
            else:
                f.write("  (none)\n")

            _write_section(f, f"Files only in {label_b}")
            if only_files_b_rel:
                for rel in only_files_b_rel:
                    f.write(f"  • {rel}\n")
            else:
                f.write("  (none)\n")

            _write_section(f, "Identical files (relative paths)")
            for fa, fb, how in identical:
                f.write(f"  • {fa['rel']}  [{how}]\n")

            _write_section(f, "Different/modified files (relative paths + metadata + which is newer)")
            for fa, fb, reason in different:
                newer = _newer_label(fa, fb)
                f.write(f"  • {fa['rel']}  [{reason}]  [{newer}]\n")
                f.write(f"      {label_a}: size={fa['size']} mtime={_fmt_time(fa['mtime'])}\n")
                f.write(f"      {label_b}: size={fb['size']} mtime={_fmt_time(fb['mtime'])}\n")

            _write_section(f, "Modified by mtime (subset of different)")
            for fa, fb, reason in modified_mtime:
                newer = _newer_label(fa, fb)
                f.write(f"  • {fa['rel']}  [{reason}]  [{newer}]\n")
                f.write(f"      {label_a}: {_fmt_time(fa['mtime'])}\n")
                f.write(f"      {label_b}: {_fmt_time(fb['mtime'])}\n")

            _write_section(f, "Modified by size (subset of different)")
            for fa, fb, reason in modified_size:
                newer = _newer_label(fa, fb)
                f.write(f"  • {fa['rel']}  [{reason}]  [{newer}]\n")
                f.write(f"      {label_a}: {fa['size']} bytes\n")
                f.write(f"      {label_b}: {fb['size']} bytes\n")

        print(f"\nDetailed report written to: {out_name}")
    except IOError:
        print(f"Error: Could not write report to {out_name}")
        return

    # Improved console preview: include which side is newer
    preview_n = 25
    if different:
        print(f"\nPreview of first {min(preview_n, len(different))} different/modified files:")
        for fa, fb, reason in different[:preview_n]:
            newer = _newer_label(fa, fb)
            print(f"  • {fa['rel']} [{reason}] -> {newer}")
            print(f"      {label_a}: {_fmt_time(fa['mtime'])} | {fa['size']} bytes")
            print(f"      {label_b}: {_fmt_time(fb['mtime'])} | {fb['size']} bytes")
    else:
        print("\nNo modified/different files detected.")


def main():
    while True:
        menu = """
    Select a function:
    ------------------------------------------------------------
    1) FILES/FOLDERS - List files alphabetically
       • Print every filename in the current directory, A → Z

    2) FILES/FOLDERS - List files & folder structure
       • Run your full list_files() routine:
         – Show sizes of each top-level folder (largest first)
         – List every file with its share of the directory’s total size
         – Display a two-level deep tree view of folders & files

    3) NAMING - Rename files with prefix
       • Add a date prefix (YYYYMMDD or YYYYMMXX) + custom description
       • Preview proposed names before renaming

    4) NAMING - Remove prefix from files
       • Strip an existing date_prefix_description_ from filenames
       • Preview proposed names before renaming

    5) MEDIA - Group image/video files by date
       • Detect media files whose names start with date prefixes
       • Group them per-date and show count & total size

    6) List subfolders & save to file
       • Enumerate all subfolders under the current directory
       • Write the sorted list to "zfileanaloutput_subfolders_list.txt"

    7) NAMING/MEDIA - Replace spaces in filenames
       • Find files with spaces in their names
       • Replace spaces with underscores on confirmation

    8) SCANNING - Find Study IDs
       • Scan all files and folders for Study IDs
       • Searches filenames and file content for specific patterns

    9) FILES/FOLDERS - Compare two folders (recursive)
       • Provide Folder A and Folder B paths
       • Reports:
         – Identical files in both (count + list)
         – Files/folders only in A vs only in B (counts + organized lists)
         – Files modified/different (mtime/size; optional hashing)
         – Preview indicates which side is newer

    0) Exit
    ------------------------------------------------------------
    """
        print(menu)
        choice = input("Enter your choice [0–9]: ").strip()

        if choice == "1":
            list_files_alphabetical()
        elif choice == "2":
            list_files()
        elif choice == "3":
            rename_files_with_prefix()
        elif choice == "4":
            remove_prefix_from_files()
        elif choice == "5":
            group_files_by_date()
        elif choice == "6":
            list_subfolders_and_save()
        elif choice == "7":
            replace_spaces_in_filenames()
        elif choice == "8":
            find_study_ids()
        elif choice == "9":
            compare_two_folders()
        elif choice == "0":
            print("Exiting the script.")
            break
        else:
            print("Invalid choice. Please try again.")

        if choice != "0":
            input("\nPress Enter to return to the main menu...")


if __name__ == "__main__":
    main()