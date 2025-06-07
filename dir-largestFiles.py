import os
import sys

def print_usage():
    print("Usage: python list_files_by_size.py [folder_path] [filter_string]")
    print("Lists all files in the folder (recursively), sorted by size.")
    print("If no folder_path is provided, the current directory is used.")
    print("Optional: filter_string will only show files containing that string (case-insensitive).")

def get_all_files(folder):
    file_list = []
    for root, dirs, files in os.walk(folder):
        for name in files:
            filepath = os.path.join(root, name)
            try:
                size = os.path.getsize(filepath)
                file_list.append((size, filepath))
            except Exception as e:
                print(f"Could not access {filepath}: {e}")
    return file_list

def main():
    # Handle --help
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        sys.exit(0)

    # Determine folder and filter_string
    folder = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    filter_string = sys.argv[2].lower() if len(sys.argv) > 2 else None

    if not os.path.isdir(folder):
        print(f"Error: {folder} is not a folder.")
        print_usage()
        sys.exit(1)

    files = get_all_files(folder)
    files.sort()  # Sort by size, smallest first

    for size, path in files:
        if filter_string and filter_string not in path.lower():
            continue
        try:
            print(f"{size/1024/1024:.2f} MB\t{path}")
        except UnicodeEncodeError:
            print(f"{size/1024/1024:.2f} MB\t{path.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)}")

if __name__ == "__main__":
    main()
