import sqlite3

try:
    conn = sqlite3.connect('dreamagent.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE memory ADD COLUMN confidence FLOAT DEFAULT 1.0;")
    conn.commit()
    print("Column 'confidence' added to 'memory' table successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower() or "duplicate" in str(e).lower():
        print("Column already exists.")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
