# DreamAgent Environment Setup

The DreamAgent system requires a `.env` file located in the root of the project folder.

## Core Variables

- `DATABASE_URL`: Connection string for PostgreSQL or SQLite. Example: `sqlite:///./dreamagent.db`
- `REDIS_URL`: Address for the Redis/Dragonfly cache. Defaults to `redis://localhost:6379/0`
- `EXECUTION_MODE`: `auto` | `local` | `distributed`. Distributed mode requires the worker process to be running to pick up Redis queued tasks. 

## LLM API Keys

Order of Provider Fallback:
1. `GEMINI_API_KEY`
2. `GROQ_API_KEY`
3. `OPENAI_API_KEY`
4. `ANTHROPIC_API_KEY` (Native Streaming adapter integrated)
5. `OPENROUTER_API_KEY`

Populate as many keys as possible to guarantee maximum pipeline resiliency.

## Connectors & Services
- `GITHUB_TOKEN`: For repository scanning capabilities.
- `BING_API_KEY`: Used by the web search tool in the `NewsAnalystTool`.
- `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`: Used to automatically spin up chatbot listeners if integrated.

## Tuning Constraints
- `SSE_TIMEOUT`: Max stream polling duration inside `api/stream.py` (Default: 180s)
- `CHUNK_SIZE`: Vector store chunk size for file processor (Default: 20_000)
- `MAX_ARCHIVE_SIZE_MB`: Limit for extracting ZIP/TAR bombs (Default: 50MB)
