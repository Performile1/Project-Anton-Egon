#!/bin/bash
# Anton Egon Studio Launcher for macOS
# Starts the Web Dashboard with Studio & Harvester tabs

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  Anton Egon - Studio Launcher (macOS)${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    echo "Please install Python 3.11 or later from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "Python version: ${GREEN}$PYTHON_VERSION${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment created${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Check if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}Dependencies installed${NC}"
else
    echo -e "${YELLOW}Warning: requirements.txt not found${NC}"
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating a template .env file..."
    cat > .env << EOF
# Anton Egon Configuration
# Copy this file and fill in your values

# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# OpenAI API (optional, for fallback)
OPENAI_API_KEY=your_openai_key_here

# Web Dashboard Configuration
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8000
EOF
    echo -e "${YELLOW}Template .env created. Please edit it with your values.${NC}"
fi

# Create necessary directories
echo "Creating asset directories..."
mkdir -p assets/video
mkdir -p assets/audio/voice_samples
mkdir -p assets/audio/pre_roll_clips
mkdir -p assets/video/ghost_frames
mkdir -p memory/meeting
mkdir -p vault/internal
mkdir -p vault/client
mkdir -p vault/general
echo -e "${GREEN}Directories created${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Starting Anton Egon Studio Dashboard...${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo -e "Dashboard will be available at: ${GREEN}http://localhost:8000${NC}"
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop the server"
echo ""

# Start the dashboard
python ui/web_dashboard.py
