# DreamAgent

<div align="center">

![DreamAgent Banner](https://img.shields.io/badge/DreamAgent-Autonomous%20AI%20Platform-6C63FF?style=for-the-badge&logo=robot&logoColor=white)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io)

**A self-healing, DAG-aware autonomous AI agent platform with production-grade task continuation, OAuth-resilient tool execution, and real-time streaming.**

[Features](#features) • [Architecture](#architecture) • [Quick Start](#quick-start) • [API Reference](#api-reference) • [Contributing](#contributing)

</div>

---

## What is DreamAgent?

DreamAgent is a **production-grade autonomous AI agent platform** that goes far beyond a simple chat interface. It is a self-healing execution engine capable of:

- **Orchestrating complex multi-step tasks** using a DAG (Directed Acyclic Graph) execution model
- **Seamlessly resuming paused tasks** after OAuth re-authentication — exactly from where it left off
- **Preventing duplicate side-effects** with two-level idempotency (orchestrator-level + tool-level)
- **Protecting against split-brain execution** with distributed locking and lease validation per wave
- **Self-healing rate limits** via a non-blocking ZSET retry scheduler with jitter
- **Observability-first design** with immutable event logs for every state transition

---

## Features

### 🧠 Autonomous Execution Engine
- **DAG-based task planning** — tasks are broken into dependency-aware execution waves
- **Parallel wave execution** — independent steps run concurrently within each wave
- **Dynamic replanning** — failed steps trigger replan up to `MAX_REPLANS` times
- **Trust Mode** — `fast`, `truth`, and `research` execution depths

### 🔐 Production-Grade OAuth & Security
- **Fernet-encrypted CSRF state** with embedded nonces and 15-minute TTLs
- **Bound resume tokens** — cryptographically tied to `task_id + user_id`
- **Truth-based token expiry** — 10-minute safety buffer against mid-task expiry
- **Checkpoint version validation** — prevents resume drift after code deployments

### 🛡️ Fault Tolerance & Resilience
- **Distributed locking** — `SET NX PX` with UUID-based ownership and background heartbeats
- **Split-brain abort** — lease ownership validated before each execution wave
- **ZSET retry scheduler** — 429 rate limits become non-blocking deferred tasks with jitter
- **Dynamic zombie cleanup** — inactive tasks purged after `3600 + (completed_steps × 600)` seconds

### 📊 Observability
- **State transition log** — immutable event trail at `tasks:{id}:state_log` with auto-compaction
- **Task timeline events** — every transition logged with timestamp and message
- **System Intelligence Scorecard** — Truth Confidence Score, execution rate, adaptive replans

### 🔧 Tool Integrations
- **Notion** — create learning trackers, search pages, append notes (with full idempotency)
- **Slack** — send messages to channels via OAuth
- **Microsoft** — calendar and email via Graph API
- **Google** — Drive and Calendar integration
- **Telegram / Discord / Slack / WhatsApp** — bot platform integrations

### 🤖 Multi-Provider LLM
- OpenAI, Anthropic (Claude), Google (Gemini), NVIDIA, Groq, HuggingFace, OpenRouter, Ollama
- Automatic provider fallback chain
- Semantic caching for repeated queries

### 🏗️ Multi-Agent Builder
- Generates full applications from natural language descriptions
- Planner → Researcher → Tool-Agent → Synthesizer → Validator pipeline

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         Frontend (SSE)                              │
│          Chat UI → Real-time streaming via Server-Sent Events        │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼─────────────────────────────────────────┐
│                     FastAPI Backend                                  │
│  /chat/stream  /chat/resume  /oauth/{provider}/connect              │
└──┬──────────────────────┬─────────────────────┬────────────────────┘
   │                      │                     │
   ▼                      ▼                     ▼
┌──────────┐     ┌────────────────┐    ┌────────────────────┐
│ HybridRouter │ │  TaskController │    │   OAuth Manager    │
│ Intent +  │     │  DAG Executor   │    │  Fernet + Tokens   │
│ Priority  │     │  Wave Scheduler │    │  Resume Contracts  │
└──────────┘     └───────┬────────┘    └────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
   ┌──────────────────┐   ┌──────────────────┐
   │  Parallel Agents  │   │  Retry Handler   │
   │  Planner/Executor │   │  ZSET Scheduler  │
   │  Research/Coder   │   │  Jitter + 429    │
   └──────────────────┘   └──────────────────┘
              │
              ▼
   ┌──────────────────────────────┐
   │         Tool Layer           │
   │  Notion / Slack / MS / Google│
   │  Idempotency (execution_id)  │
   └──────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────┐
   │    Persistence Layer         │
   │  Redis/Dragonfly  SQLite/PG  │
   │  State Logs  Checkpoints     │
   └──────────────────────────────┘
```

### Key Design Decisions

| Component | Design | Why |
|-----------|--------|-----|
| **Lock** | `SET NX PX` + UUID + heartbeat | Prevents deadlocks and split-brain on worker crash |
| **Idempotency** | 2-level: DAG node skip + tool-level Redis cache | Prevents duplicate Slack/Notion side effects |  
| **Retry** | ZSET scheduled, non-blocking, with jitter | Prevents thundering herd on shared APIs |
| **Checkpoint** | Dict keyed by `node_id` with version field | Deterministic resume, drift-safe across deploys |
| **Token Expiry** | Truth-based DB timestamp, 10-min buffer | Prevents mid-task OAuth failures |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Redis or Dragonfly (for distributed features)
- At least one LLM API key

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/DreamAgent.git
cd DreamAgent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Minimum required for basic chat:**
```env
GEMINI_API_KEY=your_key_here
# OR
OPENAI_API_KEY=your_key_here
```

**For full autonomous features:**
```env
REDIS_URL=redis://localhost:6379/0
BACKEND_URL=http://localhost:8001
ENCRYPTION_KEY=  # auto-generated on first run

# OAuth (for tool integrations)
NOTION_CLIENT_ID=...
NOTION_CLIENT_SECRET=...
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
```

### 3. Initialize Database

```bash
python init_db.py
```

### 4. Start the Server

**Windows:**
```cmd
start.bat
```

**Linux/Mac:**
```bash
./install.sh
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Open the Frontend

Navigate to `http://localhost:5000` (or open `frontend/index.html` directly).

---

## API Reference

### Chat

#### `GET /api/v1/chat/stream`
Stream agent responses via Server-Sent Events.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | User message |
| `task_id` | string | ✅ | Unique task identifier |
| `bot_id` | string | ❌ | Agent personality ID |
| `provider` | string | ❌ | LLM provider (`auto`, `openai`, `gemini`, etc.) |
| `model` | string | ❌ | Specific model name |
| `trust_mode` | string | ❌ | `fast`, `truth`, or `research` |

**SSE Event Types:**
```
step        → Progress update
token       → Streamed response token
final       → Task completed
error       → Error occurred
oauth_reconnect → OAuth re-auth required
truth_metrics   → Accuracy scorecard
```

#### `GET /api/v1/chat/resume`
Resume a paused task after OAuth re-authentication.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | ✅ | Task to resume |
| `resume_token` | string | ✅ | Cryptographic bound token |
| `user_id` | string | ✅ | Must match original user |

**Response on expired token:**
```json
{
  "status": "expired",
  "action": "restart_required",
  "message": "The resume window has expired. Please start a new task."
}
```

### OAuth

#### `GET /api/v1/oauth/{provider}/connect`
Initiates the OAuth flow for a provider.

**Supported providers:** `notion`, `slack`, `microsoft`, `google`

#### `GET /api/v1/oauth/{provider}/callback`
OAuth callback handler (set this as your redirect URI in provider settings).

### Task Status

#### `GET /api/v1/chat/status/{task_id}`
Get current task status and steps.

---

## OAuth Setup Guide

### Notion
1. Go to [Notion Developers](https://www.notion.so/my-integrations) → New Integration
2. Set redirect URI: `http://localhost:8001/api/v1/oauth/notion/callback`
3. Copy Client ID and Secret to `.env`

### Slack
1. Go to [Slack API](https://api.slack.com/apps) → Create App
2. Add OAuth redirect URL: `http://localhost:8001/api/v1/oauth/slack/callback`
3. Required scopes: `chat:write`, `channels:read`, `users:read`

### Microsoft
1. Go to [Azure Portal](https://portal.azure.com) → App Registrations
2. Add redirect URI: `http://localhost:8001/api/v1/oauth/microsoft/callback`
3. Required scopes: `User.Read`, `Calendars.ReadWrite`, `Mail.Send`

---

## Task Execution Model

### Normal Flow
```
User Query
    ↓
Intent Detection (HybridRouter)
    ↓
DAG Planning (PlannerAgent)
    ↓
Wave Execution (parallel within wave)
    ↓
Synthesis + Truth Scoring
    ↓
Response Streamed
```

### Resume Flow (OAuth interruption)
```
Tool hits auth error
    ↓
Checkpoint saved (completed_steps dict)
    ↓
SSE emits: oauth_reconnect { resume_token, expires_in: 900, fallback: "task_cancel" }
    ↓
User clicks auth link → OAuth completes
    ↓
Frontend calls /resume with token
    ↓
Version check: checkpoint_version == CHECKPOINT_VERSION?
  → YES: Resume from node_id, skip completed steps
  → NO:  Restart from original_query (safe fallback)
    ↓
Execution continues from exactly where it stopped
```

### Rate Limit Flow
```
Tool returns 429
    ↓
Task → RETRYING state
Checkpoint saved
    ↓
ZADD tasks:scheduled_retries  score=(now + delay + jitter)
    ↓
retry_scheduler_loop polls every 5s
    ↓
Auto-resume when score <= now
```

---

## Configuration Reference

### Feature Flags (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `TOOL_PYTHON_ENABLED` | `true` | Allow Python code execution |
| `TOOL_TERMINAL_ENABLED` | `true` | Allow shell commands |
| `TOOL_BROWSER_ENABLED` | `false` | Headless browser tool |
| `TOOL_TAVILY_ENABLED` | `true` | Web search via Tavily |
| `MAX_STEPS` | `10` | Maximum steps per task |

### Trust Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `fast` | Single-pass execution | Quick answers, chat |
| `truth` | Multi-pass with verification | Research, facts |
| `research` | Deep web search + synthesis | Comprehensive reports |

---

## Development

### Running Tests

```bash
# Unit tests
pytest backend/tests/ -v

# Integration tests  
python dreamagent_test_pack.py

# Orchestration tests
python orchestration_test_pack.py

# Architecture validation
python test_architecture.py
```

### Project Structure

```
DreamAgent/
├── backend/
│   ├── agents/          # Specialized agents (Planner, Coder, Writer, Research...)
│   ├── api/             # FastAPI routes (chat, oauth, files, integrations)
│   ├── builder/         # Multi-agent app builder pipeline
│   ├── core/            # Infrastructure (Redis lock, execution context, cache)
│   ├── llm/             # Universal LLM provider abstraction
│   ├── memory/          # 3-layer memory (session, long-term, core)
│   ├── oauth/           # OAuth flow management + token security
│   ├── orchestrator/    # Task controller, DAG planner, state machine, retry handler
│   ├── services/        # Database services (conversation, memory, bot)
│   └── tools/           # External API tools (Notion, Slack, etc.)
├── frontend/            # Chat UI
├── docs/                # Extended documentation
├── .env.example         # Environment template
├── requirements.txt     # Python dependencies
├── start.bat            # Windows startup script
└── install.sh           # Linux/Mac startup script
```

### Key Files

| File | Purpose |
|------|---------|
| `backend/orchestrator/task_controller.py` | Main execution engine, DAG orchestrator |
| `backend/orchestrator/task_state.py` | State machine, checkpoints, observability logs |
| `backend/core/redis_lock.py` | Distributed lock with heartbeat |
| `backend/core/execution_context.py` | Async-safe execution ID tracking |
| `backend/orchestrator/retry_handler.py` | Rate limit + 429 handling |
| `backend/oauth/oauth_manager.py` | Token management, Fernet encryption |
| `backend/api/chat_worker.py` | Background task worker, scheduler loops |

---

## Deployment

### Docker / Podman

```bash
podman-compose up -d
# OR
docker-compose up -d
```

### Production Checklist

- [ ] Set `ENCRYPTION_KEY` (32-byte base64 Fernet key)
- [ ] Use PostgreSQL: `DATABASE_URL=postgresql://...`
- [ ] Point `REDIS_URL` to production Redis/Dragonfly
- [ ] Set `BACKEND_URL` to your public domain
- [ ] Configure OAuth redirect URIs to point to production domain
- [ ] Enable HTTPS (required for OAuth)
- [ ] Set `MAX_STEPS` appropriate for your compute budget

---

## Security

- **Never commit `.env`** — it is gitignored by default
- All OAuth tokens are encrypted at rest using **Fernet symmetric encryption**
- Resume tokens are cryptographically bound to `task_id + user_id` — cannot be replayed across tasks
- CSRF state parameters include encrypted nonces with 15-minute TTLs
- Distributed lock prevents concurrent execution of the same task across workers
- Checkpoint version field prevents stale state replay after code deployments

To report a security vulnerability, please open a private issue or email the maintainers directly.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Quick contribution workflow:**
1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest backend/tests/`
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ — a self-healing autonomous AI agent platform
</div>
