#!/bin/bash

# 🚀 WanderMind Chroma Database Setup Script
# This script helps set up Chroma in different modes

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          WanderMind Chroma Database Setup                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check port availability
is_port_available() {
    lsof -i :$1 >/dev/null 2>&1
    return $?
}

# Function to generate API key
generate_api_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

# Main menu
show_menu() {
    echo -e "${YELLOW}Choose Chroma setup mode:${NC}"
    echo "1) Local Server Mode (Development)"
    echo "2) Docker Compose (Production)"
    echo "3) View Current Configuration"
    echo "4) Test Chroma Connection"
    echo "5) Ingest Data into Chroma"
    echo "6) Exit"
    echo ""
}

# Function: Local Server Mode
setup_local_server() {
    echo -e "${BLUE}→ Setting up Local Chroma Server${NC}"
    echo ""
    
    # Check if Chroma is installed
    if ! python3 -c "import chromadb" 2>/dev/null; then
        echo -e "${YELLOW}Installing chromadb with server support...${NC}"
        pip install "chromadb[server]" uvicorn
    fi
    
    # Check if port 8001 is available
    if is_port_available 8001; then
        echo -e "${YELLOW}Port 8001 is already in use${NC}"
        echo "Kill the process: lsof -i :8001 | grep -v PID | awk '{print \$2}' | xargs kill -9"
        return 1
    fi
    
    # Update .env
    echo -e "${BLUE}→ Updating .env configuration...${NC}"
    
    if [ -f .env ]; then
        # Backup existing .env
        cp .env .env.backup
        echo -e "${GREEN}✓ Backed up existing .env to .env.backup${NC}"
    fi
    
    # Update or create .env
    {
        grep -v "^CHROMA_" .env 2>/dev/null || true
        echo ""
        echo "# Chroma Configuration (Local Server Mode)"
        echo "CHROMA_MODE=server"
        echo "CHROMA_HOST=localhost"
        echo "CHROMA_PORT=8001"
        echo "CHROMA_URL=http://localhost:8001"
        echo "CHROMA_API_KEY=$(generate_api_key)"
        echo "CHROMA_COLLECTION_NAME=travel_kb"
    } > .env.tmp && mv .env.tmp .env
    
    echo -e "${GREEN}✓ .env updated${NC}"
    echo ""
    echo -e "${BLUE}→ Ready to start Chroma Server${NC}"
    echo ""
    echo -e "${YELLOW}Run in Terminal 1:${NC}"
    echo "  ${BLUE}chroma run --host 0.0.0.0 --port 8001${NC}"
    echo ""
    echo -e "${YELLOW}Run in Terminal 2:${NC}"
    echo "  ${BLUE}cd /Users/himatejagudi/Desktop/WM2${NC}"
    echo "  ${BLUE}uvicorn app:app --host 127.0.0.1 --port 8000 --reload${NC}"
    echo ""
}

# Function: Docker Compose Setup
setup_docker_compose() {
    echo -e "${BLUE}→ Setting up Docker Compose${NC}"
    echo ""
    
    # Check if Docker is installed
    if ! command_exists docker; then
        echo -e "${RED}✗ Docker is not installed${NC}"
        echo "Please install Docker from https://www.docker.com"
        return 1
    fi
    
    # Check if Docker is running
    if ! docker ps >/dev/null 2>&1; then
        echo -e "${RED}✗ Docker daemon is not running${NC}"
        echo "Please start Docker"
        return 1
    fi
    
    echo -e "${GREEN}✓ Docker is available${NC}"
    
    # Generate API key
    API_KEY=$(generate_api_key)
    
    # Update .env
    echo -e "${BLUE}→ Updating .env configuration...${NC}"
    
    if [ -f .env ]; then
        cp .env .env.backup
        echo -e "${GREEN}✓ Backed up existing .env to .env.backup${NC}"
    fi
    
    # Update or create .env
    {
        grep -v "^CHROMA_\|^GOOGLE_" .env 2>/dev/null || true
        echo ""
        echo "# Chroma Configuration (Docker Mode)"
        echo "CHROMA_MODE=server"
        echo "CHROMA_HOST=chroma"
        echo "CHROMA_PORT=8000"
        echo "CHROMA_URL=http://chroma:8000"
        echo "CHROMA_API_KEY=$API_KEY"
        echo "CHROMA_COLLECTION_NAME=travel_kb"
        echo ""
        echo "# Google API (set these from your existing .env)"
        echo "# GOOGLE_API_KEY=your-key"
        echo "# GOOGLE_PROJECT_ID=your-project"
    } > .env.tmp && mv .env.tmp .env
    
    echo -e "${GREEN}✓ .env updated with API key: $API_KEY${NC}"
    echo ""
    
    # Check if docker-compose.yml exists
    if [ ! -f docker-compose.yml ]; then
        echo -e "${RED}✗ docker-compose.yml not found${NC}"
        echo "Please create docker-compose.yml first"
        return 1
    fi
    
    if [ ! -f Dockerfile ]; then
        echo -e "${RED}✗ Dockerfile not found${NC}"
        echo "Please create Dockerfile first"
        return 1
    fi
    
    echo -e "${GREEN}✓ docker-compose.yml and Dockerfile found${NC}"
    echo ""
    
    echo -e "${BLUE}→ Building Docker images...${NC}"
    docker-compose build
    
    echo -e "${GREEN}✓ Docker images built successfully${NC}"
    echo ""
    
    echo -e "${BLUE}→ Starting services...${NC}"
    docker-compose up -d
    
    echo -e "${GREEN}✓ Services started${NC}"
    echo ""
    
    # Wait for services to be ready
    echo -e "${BLUE}→ Waiting for services to be healthy...${NC}"
    sleep 10
    
    # Check status
    docker-compose ps
    echo ""
    
    echo -e "${GREEN}✓ Docker Compose setup complete${NC}"
    echo ""
    echo -e "${BLUE}→ Access your services:${NC}"
    echo "  Backend:  http://localhost:8000"
    echo "  Chroma:   http://localhost:8001"
    echo ""
    echo -e "${BLUE}→ Useful commands:${NC}"
    echo "  View logs:       docker-compose logs -f"
    echo "  View services:   docker-compose ps"
    echo "  Stop services:   docker-compose down"
    echo "  Rebuild:         docker-compose build --no-cache"
    echo ""
}

# Function: View Configuration
view_config() {
    echo -e "${BLUE}→ Current Chroma Configuration${NC}"
    echo ""
    
    if [ -f .env ]; then
        echo -e "${YELLOW}Settings from .env:${NC}"
        grep "^CHROMA_\|^CHROMA_" .env || echo "  No Chroma settings found"
    else
        echo -e "${YELLOW}.env file not found${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}→ Running Services${NC}"
    
    echo -n "Chroma Server (port 8001): "
    if is_port_available 8001; then
        echo -e "${GREEN}✓ Running${NC}"
        curl -s http://localhost:8001/api/v1/heartbeat | head -c 50
        echo ""
    else
        echo -e "${RED}✗ Not running${NC}"
    fi
    
    echo -n "FastAPI Backend (port 8000): "
    if is_port_available 8000; then
        echo -e "${GREEN}✓ Running${NC}"
        curl -s http://localhost:8000/health | head -c 50
        echo ""
    else
        echo -e "${RED}✗ Not running${NC}"
    fi
    
    echo ""
}

# Function: Test Connection
test_connection() {
    echo -e "${BLUE}→ Testing Chroma Connection${NC}"
    echo ""
    
    # Check local server
    echo -n "Testing Chroma Server (localhost:8001): "
    if curl -s -f http://localhost:8001/api/v1/heartbeat >/dev/null; then
        echo -e "${GREEN}✓ Connected${NC}"
        
        # List collections
        echo -e "${BLUE}→ Collections:${NC}"
        curl -s http://localhost:8001/api/v1/collections | python3 -m json.tool 2>/dev/null || echo "Could not parse response"
    else
        echo -e "${RED}✗ Connection failed${NC}"
        echo "Make sure Chroma server is running:"
        echo "  chroma run --host 0.0.0.0 --port 8001"
    fi
    
    echo ""
}

# Function: Ingest Data
ingest_data() {
    echo -e "${BLUE}→ Ingesting Data into Chroma${NC}"
    echo ""
    
    if [ ! -d "./data" ]; then
        echo -e "${RED}✗ ./data directory not found${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Running data ingestion...${NC}"
    python3 << 'PYTHON_SCRIPT'
from src.rag import ingest
result = ingest("./data")
print(f"✓ Successfully inserted {result['inserted']} chunks into Chroma")
PYTHON_SCRIPT
    
    echo ""
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice (1-6): " choice
    
    case $choice in
        1)
            setup_local_server
            ;;
        2)
            setup_docker_compose
            ;;
        3)
            view_config
            ;;
        4)
            test_connection
            ;;
        5)
            ingest_data
            ;;
        6)
            echo -e "${GREEN}Exiting...${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            ;;
    esac
    
    read -p "Press Enter to continue..."
done
