import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "dreamagent.db")

if not os.path.exists(db_path):
    print(f"Database {db_path} does not exist.")
    exit(0)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table_name in tables:
        table = table_name[0]
        if table != "sqlite_sequence":
            print(f"Dropping table {table}...")
            cursor.execute(f"DROP TABLE IF EXISTS \"{table}\";")
            
    conn.commit()
    conn.close()
    print("Database cleared successfully (all tables dropped).")
except Exception as e:
    print(f"Failed to clear database: {e}")
    # Try deleting it again if it was a connection issue
    try:
        os.remove(db_path)
        print("Database file deleted successfully.")
    except Exception as e2:
        print(f"Final attempt to delete file failed: {e2}")
