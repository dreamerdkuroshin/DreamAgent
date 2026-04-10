# DreamAgent Architecture Data Flow

DreamAgent v10 is built on a highly parallel, asynchronous architecture designed to handle long-running agent tasks without blocking the main event loop. Below is a detailed breakdown of the system components.

## 1. Gateway & Routing (`backend/api/`)
The `FastAPI` gateway handles incoming requests from the React UI and external Integrations (Telegram, Discord).
* **Multimodal Router**: Instantly classifies incoming queries using an intent engine. Simple conversational requests are routed to the **Fast Path** (direct SSE), while agentic workflows (e.g. building a website, pulling finance data) are routed to the **Complex Path**.
* **SSE Engine (`chat.py`)**: Uses Server-Sent Events to push UI updates down to the frontend in real-time, including agent *thoughts* and incremental file builds.

## 2. LLM Universal Provider (`backend/llm/universal_provider.py`)
A custom robust interface abstracting away provider-specific SDKs.
* Supports Anthropic, OpenAI, Meta, Gemini, Groq, and Ollama.
* **Bootstrap Fallback**: If a database key is missing or rate-limited (e.g., throwing a `429 Too Many Requests`), the Universal Provider automatically falls back and cycles through keys found in the local `.env` file, guaranteeing agent uptime.

## 3. High-Performance Queues (`backend/core/task_router.py`)
To prevent the FastAPI event loop from freezing, heavy multi-step autonomous tasks are dropped into priority queues.
* **Local Mode**: When running locally on Windows/Mac without a distributed grid, tasks are dispatched to an `asyncio` priority queue. An in-process background worker (`worker_local.py`) processes these seamlessly.
* **Distributed Mode**: If Dragonfly (a Redis drop-in replacement) is connected, tasks are routed to `tasks:processing` lists, allowing external worker nodes to pick them up for mass scalability.

## 4. State & Memory Management (`backend/core/models.py`)
* **SQLite Persistence**: Used for local deployments to store user preferences, API keys, chat history, and bot integration IDs. We eschewed PostgreSQL in v10 for better developer portability setup.
* **Context Engine**: Agents inject contextual metadata into every prompt, pulling from short-term DB memory bounds to recall past project constraints and tool preferences.

## 5. Web Platform (`frontend of dreamAgent/DreamAgent-v10-UI/`)
* Built on **React/Vite** with Tailwind CSS.
* **Optimistic Updates**: Uses React Query to immediately update the interface whilst polling the background sync loop for backend confirmation, completely eliminating message flickering or ghosting.
* **Dynamic KPI Dashboards**: The `/monitoring` page polls `/api/v1/stats` to visualize the queue backlog, agent run success rates, and token limits.
