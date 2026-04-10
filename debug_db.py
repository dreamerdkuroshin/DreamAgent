import sqlite3
import os

DB_NAME = "app.db"

def check_db():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} does not exist.")
        return

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("--- Tables ---")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    for table in tables:
        print(table['name'])

    print("\n--- Agents Table Content ---")
    try:
        cur.execute("SELECT * FROM agents")
        rows = cur.fetchall()
        if not rows:
            print("No agents found in database.")
        for row in rows:
            print(dict(row))
    except sqlite3.OperationalError as e:
        print(f"Error reading agents table: {e}")

    conn.close()

if __name__ == "__main__":
    check_db()
