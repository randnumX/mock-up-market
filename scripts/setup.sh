#!/bin/bash
# One-command setup for local development. Safe to re-run - every step
# skips or no-ops if it's already done, so this also works as a "did I
# set everything up right?" check.
set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
warn() { echo -e "  ${YELLOW}!${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; }

echo -e "${BOLD}🚀 Setting up Mock-Up Market${RESET}"
echo ""

# ----- 1. Check prerequisites -----
echo -e "${BOLD}Checking prerequisites...${RESET}"

if command -v python3 >/dev/null 2>&1; then
    ok "python3 found ($(python3 --version 2>&1))"
else
    fail "python3 not found - install Python 3.10+ before continuing (https://www.python.org/downloads/)"
    exit 1
fi

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    ok "node/npm found (node $(node --version), npm $(npm --version))"
else
    fail "node/npm not found - install Node.js 20+ before continuing (https://nodejs.org/, or via nvm)"
    exit 1
fi

DOCKER_AVAILABLE=false
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        ok "Docker found and running"
        DOCKER_AVAILABLE=true
    else
        warn "Docker is installed but the daemon isn't running - start Docker Desktop if you want MongoDB / real data / live trading"
    fi
else
    warn "Docker not found - the app still works fully without it (synthetic data, backtesting only). Install Docker Desktop for MongoDB, real ticker sync, and Live Trading: https://www.docker.com/products/docker-desktop/"
fi

echo ""

# ----- 2. Backend .env -----
echo -e "${BOLD}Configuring environment...${RESET}"
if [ -f backend/.env ]; then
    ok "backend/.env already exists (leaving it as-is)"
else
    cp .env.example backend/.env
    ok "Created backend/.env from .env.example (defaults are fine to start - add Kite Connect keys later if you want real market data)"
fi
echo ""

# ----- 3. Backend venv + deps -----
echo -e "${BOLD}Setting up backend...${RESET}"
cd "$ROOT_DIR/backend"
if [ ! -d .venv ]; then
    python3 -m venv .venv
    ok "Created virtualenv"
else
    ok "Virtualenv already exists"
fi
source .venv/bin/activate
pip install -r requirements.txt --quiet
ok "Backend dependencies installed"
deactivate
echo ""

# ----- 4. Frontend deps -----
echo -e "${BOLD}Setting up frontend...${RESET}"
cd "$ROOT_DIR/frontend"
npm install --silent
ok "Frontend dependencies installed"
echo ""

# ----- 5. MongoDB (optional) -----
cd "$ROOT_DIR"
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo -e "${BOLD}Starting MongoDB...${RESET}"
    docker compose up -d
    ok "MongoDB running (docker compose up -d) - only starts Mongo, not the full stack"
    echo ""
fi

# ----- Done -----
echo -e "${BOLD}======================================${RESET}"
echo -e "${GREEN}🎉 Setup complete!${RESET}"
echo ""
echo "Run the app (pick one):"
echo ""
echo -e "  ${BOLD}Native (fastest for development):${RESET}"
echo "    Terminal 1: cd backend && source .venv/bin/activate && python run.py"
echo "    Terminal 2: cd frontend && npm run dev"
echo "    Dashboard:  http://localhost:5173"
echo ""
echo -e "  ${BOLD}Fully containerized:${RESET}"
echo "    docker compose --profile full up --build -d"
echo "    Dashboard:  http://localhost:3000"
echo ""
echo "API health check either way: http://localhost:5000/api/health"
echo ""
echo "Optional next steps:"
echo "  - Real BSE data (no broker account needed): cd backend && python scripts/fetch_bse_data.py"
echo "  - Real Zerodha data: add KITE_API_KEY/KITE_API_SECRET to backend/.env, then click 'Connect Zerodha' in the dashboard"
echo -e "${BOLD}======================================${RESET}"
