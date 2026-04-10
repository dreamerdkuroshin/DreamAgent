import sqlite3
import json

def check_db():
    try:
        conn = sqlite3.connect('dreamagent.db')
        cursor = conn.cursor()
        
        print("--- Tables ---")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(tables)
        
        for table in tables:
            print(f"\n--- {table} (last 10) ---")
            cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 10")
            cols = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            for row in rows:
                d = dict(zip(cols, row))
                # Prune long content for readability if needed, but let's see it for messages
                if table == 'messages':
                    print(f"MSG {d['id']} ({d['role']}): {d['content']}")
                else:
                    print(d)
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
