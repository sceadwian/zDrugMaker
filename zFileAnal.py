import os
import math

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

def main():
    print("Select a function:")
    print("1. List files in the current directory and display folder structure")
    choice = input("Enter your choice (1): ")
    if choice == "1":
        list_files()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
