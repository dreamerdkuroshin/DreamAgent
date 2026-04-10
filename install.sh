#!/usr/bin/env bash
# install.sh — One-command DreamAgent setup for Linux / macOS

set -e
echo ""
echo "  ██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗"
echo "  ██╔══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝"
echo "  ██║  ██║██████╔╝█████╗  ███████║██╔████╔██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   "
echo "  ██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   "
echo "  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝"
echo ""
echo "  Autonomous Multi-Model AI Agent Platform — v1.0.0"
echo ""

# ── Check Python ───────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3.11+ is required. Install from https://python.org"
  exit 1
fi

# ── Check Node ─────────────────────────────────────
if ! command -v node &>/dev/null; then
  echo "⚠️   Node.js not found. Frontend won't start without it."
  echo "    Install from https://nodejs.org"
fi

# ── Install pnpm if missing ─────────────────────────
if ! command -v pnpm &>/dev/null; then
  echo "→  Installing pnpm..."
  npm install -g pnpm
fi

# ── Python package install ──────────────────────────
echo "→  Installing DreamAgent Python package..."
pip install -e . --quiet

# ── Env file ────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️   Created .env from .env.example — add your API keys before running agents."
fi

# ── Frontend deps ───────────────────────────────────
dreamagent install-frontend

echo ""
echo "✅  Installation complete!"
echo ""
echo "   Run DreamAgent:"
echo "   ──────────────"
echo "   dreamagent run"
echo ""
echo "   Or start services individually:"
echo "   dreamagent run --backend   # API on :8000"
echo "   dreamagent run --worker    # RQ worker"
echo "   dreamagent run --frontend  # UI on :5000"
echo ""
