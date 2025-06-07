import os
import sys

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
    if len(sys.argv) < 2:
        print("Usage: python list_files_by_size.py <folder_path> [filter_string]")
        sys.exit(1)
    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(f"Error: {folder} is not a folder.")
        sys.exit(1)

    filter_string = sys.argv[2].lower() if len(sys.argv) > 2 else None

    files = get_all_files(folder)
    files.sort()  # Sort by size, smallest first

    for size, path in files:
        if filter_string and filter_string not in path.lower():
            continue
        # Print, replacing unprintable characters
        try:
            print(f"{size/1024/1024:.2f} MB\t{path}")
        except UnicodeEncodeError:
            print(f"{size/1024/1024:.2f} MB\t{path.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)}")

if __name__ == "__main__":
    main()
