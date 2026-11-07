#!/usr/bin/env bash
# NeverTwice - Live Hackathon Demo Launcher
# Boots both FastAPI backend & Vite React frontend in parallel

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  🚀 Starting NeverTwice Pre-Merge Referee System"
echo "=========================================================="

# 1. Activate Virtual Environment
if [ -d "backend/.venv" ]; then
    echo "✓ Activating Python virtual environment..."
    source backend/.venv/bin/activate
else
    echo "❌ backend/.venv not found. Run python3 -m venv backend/.venv"
    exit 1
fi

# 2. Reset Memory State for Clean Cold-Start
echo "✓ Resetting episodic memory to cold start..."
python backend/seed.py

# 3. Trap exit signals to terminate child processes cleanly
cleanup() {
    echo ""
    echo "🛑 Shutting down NeverTwice services..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 4. Launch Backend API + Fetch.ai Node
echo "✓ Launching FastAPI & Fetch.ai Gateway (port 8000 & 8001)..."
PYTHONPATH=. uvicorn backend.app.main:app --port 8000 &
BACKEND_PID=$!

# 5. Launch Frontend Dashboard
echo "✓ Launching Frontend Dashboard (port 5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "  🎉 NeverTwice is live!"
echo "  👉 Dashboard: http://localhost:5173"
echo "  👉 API Docs:  http://localhost:8000/docs"
echo "  👉 Fetch.ai:  http://127.0.0.1:8001/submit"
echo "=========================================================="
echo "Press Ctrl+C to stop all services."

wait

