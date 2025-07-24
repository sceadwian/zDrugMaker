# This Python script provides multiple functionalities:
# 1. List files in the current directory and display folder structure.
# 2. Run list_files function - reads down 2 levels of directories and reports sizes as well
# 3. Rename files in the current directory with a prefix.
# 4. Remove prefix from files in the current directory.
# 5. Reports on images and video files by date
# 6. List sub folder structure
# 7. Replace empty spaces in file names with underscores. Only current folder or directory.
# 8. Scan for Study IDs in filenames and content.
# The user can select the desired function from the main menu.
# The script prompts for user input and performs the chosen operation.


import os
import math
import re
import datetime

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
    
    # Skip files larger than 100 MB
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
            
            # 2b. Check the content within the file (line‑by‑line)
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
                    print(f"    ↳ Skipped large file (>100 MB): {os.path.relpath(filepath, base_path)}", flush=True)
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


def main():
    while True:
        menu = """
    Select a function:
    ------------------------------------------------------------
    1) FILES/FOLDERS - List files alphabetically
       • Print every filename in the current directory, A → Z

    2) FILES/FOLDERS - List files & folder structure
       • Run your full list_files() routine:
         – Show sizes of each top‑level folder (largest first)
         – List every file with its share of the directory’s total size
         – Display a two‑level deep tree view of folders & files

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

    0) Exit
    ------------------------------------------------------------
    """
        print(menu)
        choice = input("Enter your choice [0–8]: ").strip()

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
        elif choice == "0":
            print("Exiting the script.")
            break
        else:
            print("Invalid choice. Please try again.")
        
        # This part makes the script wait for user input before showing the menu again
        if choice != "0":
            input("\nPress Enter to return to the main menu...")


if __name__ == "__main__":
    main()