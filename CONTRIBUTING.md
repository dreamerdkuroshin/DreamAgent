# Contributing to DreamAgent

Thank you for your interest in DreamAgent! This system has undergone massive upgrades (now v1.0), shifting from a simple chatbot to a resilient autonomous LLM orchestrator. 

## 1. Setting Up Your Development Environment

1. **Fork & Clone** the repository.
2. **Install Backend Dependencies**: 
   ```bash
   pip install -r requirements.txt
   ```
3. **Install Frontend Dependencies**:
   ```bash
   cd "frontend of dreamAgent/DreamAgent-v1.0-UI"
   npm install
   ```
4. **Copy Environment Template**:
   ```bash
   cp .env.example .env
   ```
   *(Ensure you fill in your API keys for testing locally).*

## 2. Launching for Development
Use the provided batch script to boot the API and the Vite frontend simultaneously:
```bash
./start.bat
```
- The frontend proxy runs on port `5000`.
- The FastAPI backend runs on port `8001`.

## 3. Workflow Guidelines

### Submitting PRs
- **Test Before You Push**: We have a strict "No UI Flickering" and "No Crash" policy for the core worker queues. If you modify `task_router.py` or the SSE endpoint (`chat.py`), please verify that background tasks process fully without stalling the `/api/v1/stats` dashboard.
- **Do Not Push `.env` or `.db` files**: Always run a quick `git status` check to prevent accidental leakages of credentials or local test databases. `.gitignore` is set up to block these, but please verify.
- **Portability First**: Never use absolute hardcoded paths (e.g. `C:\Users\JohnDoe\...`). Use `os.path.dirname(__file__)` in Python or relative imports in React.

### Adding New Tools & Agents
Extensions should be fully modular. Register your new agent skills inside the `backend/tools/` directory and ensure they are parsed by the Universal Provider context engine before proposing a merge.

## 4. Resetting Your State Daily
When making DB schema changes, execute the cleanup script to drop tables safely without locking the physical file:
```bash
python clear_db.py
```
*(You may need to temporarily stop `start.bat` if you wish to delete the actual database file off your hard-drive).*
