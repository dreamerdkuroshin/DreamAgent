import os
import sys
import threading
import socket
from sqlalchemy import create_engine
import psycopg2

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0

print("--- DreamAgent Diagnostics ---")

# 1. Backend API Check
backend_8000 = check_port(8000)
backend_8001 = check_port(8001)
print(f"Backend (Port 8000): {'ONLINE' if backend_8000 else 'OFFLINE'}")
print(f"Backend (Port 8001): {'ONLINE' if backend_8001 else 'OFFLINE'}")

# 2. Redis/Dragonfly Check
redis_port = check_port(6379)
print(f"Dragonfly/Redis (Port 6379): {'ONLINE' if redis_port else 'OFFLINE'}")

# 3. PostgreSQL Check
try:
    # Try connecting to postgres on localhost
    conn = psycopg2.connect(host="localhost", user="postgres", password="yourpassword", dbname="dreamagent", connect_timeout=2)
    conn.close()
    print("PostgreSQL: ONLINE (connected successfully)")
except Exception as e:
    print(f"PostgreSQL: OFFLINE ({type(e).__name__}) - System will fallback to SQLite")

# 4. SQLite Check
sqlite_path = "sqlite:///./dreamagent_state.db"
try:
    engine = create_engine(sqlite_path)
    with engine.connect() as conn:
        pass
    print("SQLite: ONLINE (fallback database available)")
except Exception as e:
    print(f"SQLite: ERROR ({str(e)})")

# 5. MCP Servers
# Assuming ports 3010-3013 from .env
print(f"Notion MCP (Port 3010): {'ONLINE' if check_port(3010) else 'OFFLINE'}")
print(f"Slack MCP (Port 3011):  {'ONLINE' if check_port(3011) else 'OFFLINE'}")
print(f"Figma MCP (Port 3012):  {'ONLINE' if check_port(3012) else 'OFFLINE'}")
print(f"Stripe MCP (Port 3013): {'ONLINE' if check_port(3013) else 'OFFLINE'}")

# 6. MongoDB Check
mongo_port = check_port(27017)
print(f"MongoDB (Port 27017): {'ONLINE' if mongo_port else 'OFFLINE'}")
