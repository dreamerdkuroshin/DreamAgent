import psutil
import time
import logging

logger = logging.getLogger(__name__)

LITE_MODE = {
    "max_memories": 300,
    "short_memory": 5,
    "top_k": 3,
    "embedding_model": "all-minilm",
    "embedding_dim": 384,
    "store_full_text": False,
    "compression": True,
    "multi_agent": False,
    "global_memory": False
}

STANDARD_MODE = {
    "max_memories": 2000,
    "short_memory": 10,
    "top_k": 5,
    "embedding_model": "nomic-embed-text",
    "embedding_dim": 768,
    "store_full_text": True,
    "compression": True,
    "multi_agent": True,
    "global_memory": False
}

ULTRA_MODE = {
    "max_memories": 10000,
    "short_memory": 20,
    "top_k": 10,
    "embedding_model": "text-embedding-3-large",
    "embedding_dim": 1536,
    "store_full_text": True,
    "compression": False,
    "multi_agent": True,
    "global_memory": True
}

MODES = {
    "lite": LITE_MODE,
    "standard": STANDARD_MODE,
    "ultra": ULTRA_MODE
}

_last_mode = None
_last_switch_time = 0
_manual_override = None  # "auto", "lite", "standard", "ultra"

def set_mode_override(mode: str):
    global _manual_override
    mode = mode.lower()
    if mode in ["lite", "standard", "ultra"]:
        _manual_override = mode
        logger.info(f"[ModeSystem] Manual override set to: {mode.upper()}")
    else:
        _manual_override = None
        logger.info("[ModeSystem] Manual override lifted. Returning to AUTO.")

def detect_mode() -> str:
    global _last_mode, _last_switch_time, _manual_override
    
    if _manual_override:
        return _manual_override

    now = time.time()

    # prevent rapid switching
    if _last_mode and (now - _last_switch_time < 30):
        return _last_mode

    ram = psutil.virtual_memory().total
    cpu = psutil.cpu_percent()

    if ram < 4_000_000_000 or cpu > 80:
        mode = "lite"
    elif ram < 8_000_000_000:
        mode = "standard"
    else:
        mode = "ultra"

    if mode != _last_mode:
        if _last_mode is not None:
             logger.info(f"[ModeSystem] System constraints shifting. Mode automatically changed: {_last_mode.upper()} -> {mode.upper()}")
        _last_mode = mode
        _last_switch_time = now

    return mode

def get_current_mode() -> dict:
    mode_name = detect_mode()
    return MODES.get(mode_name, STANDARD_MODE)
