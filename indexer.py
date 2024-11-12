import os
import sqlite3
from datetime import datetime

# Specify the directory to index and the SQLite database file
BASE_DIR = os.path.expanduser('~/nas/vol1/mus/smc/')

# Set the working directory to the directory of this script
script_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_directory)

DB_FILE = "file_index.db"



# Function to remove the old SQLite database file if it exists
def remove_database(db_file):
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"Deleted existing database: {db_file}")
    else:
        print(f"No existing database found at: {db_file}")

# Function to initialize the SQLite database and create the table
def initialize_db(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            name TEXT,
            size INTEGER,
            modified TEXT
        )
    ''')
    conn.commit()
    return conn

# Function to count total number of files and show progress while counting
def count_files(base_dir):
    total_files = 0
    for root, dirs, files in os.walk(base_dir):
        total_files += len(files)
        print(f"Counting files... {total_files} found", end="\r")  # Update count in terminal
    print(f"\nTotal files to index: {total_files}")
    return total_files

# Recursively walk through the directory and subdirectories and index the files
def index_files(base_dir, conn, total_files):
    cursor = conn.cursor()
    processed_files = 0

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_info = {
                "path": file_path,
                "name": file,
                "size": os.path.getsize(file_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            # Insert or update file info in the database
            cursor.execute('''
                INSERT OR REPLACE INTO file_index (path, name, size, modified)
                VALUES (:path, :name, :size, :modified)
            ''', file_info)

            # Update and display progress
            processed_files += 1
            print(f"Processed {processed_files} of {total_files} files", end="\r")

    conn.commit()

# Main function to index the directory
def main():
    print("Starting the reindexing process...")

    # Step 1: Remove the existing database if it exists
    remove_database(DB_FILE)

    # Step 2: Initialize a new SQLite database
    conn = initialize_db(DB_FILE)

    # Step 3: Count the total number of files and show progress
    print("Counting total files in:", BASE_DIR)
    total_files = count_files(BASE_DIR)

    # Step 4: Index the files in the directory
    index_files(BASE_DIR, conn, total_files)

    # Step 5: Close the database connection
    conn.close()
    print(f"\nIndex stored in SQLite database {DB_FILE}")

if __name__ == "__main__":
    main()
