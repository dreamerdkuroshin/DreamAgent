import os
import sys
import importlib
import json
import logging

logger = logging.getLogger(__name__)

PLUGINS = {}

def load_plugins():
    base_path = "plugins"
    
    # Ensure plugins directory is in sys.path
    if os.path.abspath(".") not in sys.path:
        sys.path.insert(0, os.path.abspath("."))
        
    if not os.path.exists(base_path):
        return

    for plugin in os.listdir(base_path):
        plugin_dir = os.path.join(base_path, plugin)
        if os.path.isdir(plugin_dir) and not plugin.startswith("__"):
            # Check for manifest
            manifest_path = os.path.join(plugin_dir, "plugin.json")
            if not os.path.exists(manifest_path):
                continue
                
            try:
                module = importlib.import_module(f"plugins.{plugin}.tool")

                for attr in dir(module):
                    cls = getattr(module, attr)
                    
                    # Ensure it's a class and has the required plugin interface
                    if isinstance(cls, type) and hasattr(cls, "execute") and hasattr(cls, "name"):
                        instance = cls()
                        
                        # Apply a compatibility wrapper so ReAct loop's .run() can seamlessly use it
                        if not hasattr(instance, "run"):
                            def run_wrapper(tool_input, inst=instance):
                                # Fix #17: Look up real token from auth instead of hardcoded dummy
                                try:
                                    from backend.core.database import SessionLocal
                                    from backend.services.auth_service import get_api_key
                                    with SessionLocal() as db:
                                        real_token = get_api_key(db, inst.name) or ""
                                except Exception:
                                    real_token = ""
                                res = inst.execute(tool_input, {"token": real_token})
                                return json.dumps(res) if isinstance(res, dict) else str(res)
                            
                            instance.run = run_wrapper

                        PLUGINS[instance.name] = instance
                        logger.info(f"Loaded plugin: {instance.name}")

            except Exception as e:
                logger.error(f"Failed loading {plugin}: {e}")

# Automatically execute on import
load_plugins()
