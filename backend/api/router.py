from fastapi import APIRouter
from backend.api import agents, conversations, tasks, auth, chat, stream
from backend.api.trace import router as trace_router, router_compat as trace_router_compat
from backend.api.integrations import router as integrations_router
from backend.api.models import router as models_router
from backend.api.settings import router as settings_router
from backend.api.files import router as files_router
from backend.oauth.oauth_router import router as universal_oauth_router
from backend.oauth.advanced_config import router as advanced_oauth_router
from backend.mcp.mcp_router import router as universal_mcp_router
from backend.api.autonomous_router import router as autonomous_router
from backend.api.tool_router import router as tool_marketplace_router
from backend.api.builder import router as builder_router
from backend.api.debug import router as debug_router
from backend.api.monitoring import router as monitoring_router

router = APIRouter()
router.include_router(debug_router)
router.include_router(builder_router)
router.include_router(universal_oauth_router)
router.include_router(advanced_oauth_router)
router.include_router(universal_mcp_router)
router.include_router(autonomous_router)
router.include_router(tool_marketplace_router)
router.include_router(agents.router)
router.include_router(conversations.router)
router.include_router(tasks.router)
router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(stream.router)
router.include_router(trace_router)
router.include_router(trace_router_compat)
router.include_router(integrations_router)
router.include_router(models_router)
router.include_router(settings_router)
router.include_router(files_router)
router.include_router(monitoring_router)
