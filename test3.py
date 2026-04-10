import sys
import os

sys.path.insert(0, os.path.abspath('c:/Users/manth/Downloads/DreamAgent2/DreamAgent'))
from backend.core.persona_engine import classify_speed

print('1', classify_speed("how does end-to-end work"))
print('2', classify_speed("give me info around fast classification"))
print('3', classify_speed("summarize this text"))
print('4', classify_speed("fix my error"))
