import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.database import engine
from backend.core.models import Base

print("Initializing DB schema...")
Base.metadata.create_all(engine)
print("Done!")
