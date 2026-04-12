# Horizontal Scaling Guide

DreamAgent utilizes a Redis-backed Distributed Task Queue that allows infinite horizontal scaling across worker nodes independently of the frontend API pods.

## Multi-Queue Load Balancing

DreamAgent routes queries into 3 specialized queues depending on text length, intent, and attached dependencies (files):
- `tasks:simple` (Lowest latency, smallest LLMs like Haiku/Flash)
- `tasks:medium`
- `tasks:complex` (Highest latency, coding loops, `BuilderAgent` allocations)

When horizontally scaling, you typically want dedicated worker pods listening to subsets of the queues.

### Node 1: Heavy Computation (Builder Node)
You can prioritize a node to exclusively run complex tasks:
```bash
python -m backend.worker --queues tasks:complex
```
*Auto-scaling policy: Scale up based on `LLEN tasks:complex` threshold > 5.*

### Node 2: Fast Task Processors
Listen to simple tasks ensuring no congestion from heavy workloads:
```bash
python -m backend.worker --queues tasks:medium,tasks:simple
```

## SSE Streaming Concurrency

The FastAPI node (`backend/api/chat.py` and `backend/api/stream.py`) holds open SSE connections up to `SSE_TIMEOUT` (180s).
To prevent socket starvation:
1. Ensure your reverse proxy does not timeout connections under 3 minutes.
2. Use horizontal pod autoscaling on the FastAPI deployment when active concurrent SSE counts exceed 50 per pod.
3. Deploy Dragonfly alongside Redis to drastically reduce connection handshake bottlenecks in task dispatch polling.
