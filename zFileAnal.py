# This Python script provides multiple functionalities:
# 1. List files in the current directory and display folder structure.
# 2. Rename files in the current directory with a prefix.
# 3. Remove prefix from files in the current directory.
# The user can select the desired function from the main menu.
# The script prompts for user input and performs the chosen operation.

import os
import math
import re

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
    input("Press any key to view files in the current directory...")
    files = []
    folders = []
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            if file.endswith((".exe", ".py")):
                files.append((file, size, True))  # Mark .exe and .py files with red flag
            else:
                files.append((file, size, False))
        else:
            size = get_directory_size(file_path)
            folders.append((file, size))

    files.sort(key=lambda x: x[1], reverse=True)
    folders.sort(key=lambda x: x[1], reverse=True)

    print("Files in the current directory:")
    for file, size, red in files:
        size_string = get_size_string(size)
        if red:
            print(f"\033[91m{file}\033[0m ({size_string})")  # Print executables and .py files in red
        else:
            print(f"\033[92m{file}\033[0m ({size_string})")  # Print other files in green

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
                if f.endswith((".exe", ".py")):
                    print(f"{subindent}\033[91m{f}\033[0m ({size_string})")  # Print executables and .py files in red
                else:
                    print(f"{subindent}\033[92m{f}\033[0m ({size_string})")  # Print other files in green

def list_files_alphabetical():
    path = os.getcwd()
    print("Files in the current directory (alphabetical order):")
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

def main():
    while True:
        print("\nSelect a function:")
        print("1. List files in the current directory and display folder structure")
        print("2. Rename files in the current directory with a prefix")
        print("3. Remove prefix from files in the current directory")
        print("0. Exit")
        choice = input("Enter your choice: ")

        if choice == "1":
            list_files_alphabetical()
        elif choice == "2":
            rename_files_with_prefix()
        elif choice == "3":
            remove_prefix_from_files()
        elif choice == "0":
            print("Exiting the script.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
