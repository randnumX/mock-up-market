#!/bin/bash
set -e

echo "🚀 Setting up Mock-Up Market..."
echo ""

# Backend
echo "📦 Setting up backend..."
cd "$(dirname "$0")/../backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt --quiet
echo "✅ Backend ready"

# Frontend
echo ""
echo "📦 Setting up frontend..."
cd ../frontend
npm install --silent
echo "✅ Frontend ready"

echo ""
echo "======================================"
echo "🎉 Setup complete!"
echo ""
echo "To start the app:"
echo "  Terminal 1: cd backend && source .venv/bin/activate && python run.py"
echo "  Terminal 2: cd frontend && npm run dev"
echo ""
echo "Dashboard: http://localhost:5173"
echo "API:       http://localhost:5000/api/health"
echo "======================================"
