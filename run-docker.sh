#!/usr/bin/env bash
# ==============================================================================
# 24FPS Forensic Platform - Docker Launcher for Linux (Arch Linux / Ubuntu / etc.)
# ==============================================================================
set -e

echo "======================================================"
echo "    24FPS Forensic Analysis Platform Docker Setup     "
echo "======================================================"

# 1. Verify Docker CLI is installed
if ! command -v docker &> /dev/null; then
    echo "[-] Error: 'docker' command not found."
    echo "    On Arch Linux, install it via: sudo pacman -S docker docker-compose"
    echo "    Then start the daemon:       sudo systemctl enable --now docker"
    exit 1
fi

# 2. Determine Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "[-] Error: Neither 'docker compose' (v2 plugin) nor 'docker-compose' (v1) was found."
    echo "    On Arch Linux, install it via: sudo pacman -S docker-compose"
    exit 1
fi

# 3. Check Docker daemon connectivity
if ! docker info &> /dev/null; then
    echo "[!] Cannot connect to Docker daemon as user '$(whoami)'."
    echo "    Checking with sudo..."
    if sudo -n docker info &> /dev/null 2>&1 || sudo docker info &> /dev/null; then
        COMPOSE_CMD="sudo $COMPOSE_CMD"
    else
        echo "[-] Docker daemon is not running or current user does not have permission."
        echo "    To fix permissions on Arch Linux:"
        echo "      sudo usermod -aG docker \$USER"
        echo "      newgrp docker"
        echo "    To start the daemon:"
        echo "      sudo systemctl start docker"
        exit 1
    fi
fi

# 4. Create host data directories if not present
mkdir -p backend/data/evidence \
         backend/data/artifacts \
         backend/data/reports \
         backend/data/temp \
         backend/data/logs \
         backend/data/models

echo "[+] Building and starting 24FPS containers..."
$COMPOSE_CMD up --build -d

echo ""
echo "======================================================"
echo "    24FPS PLATFORM IS RUNNING!                        "
echo "======================================================"
echo "  Frontend Application: http://localhost:3000"
echo "  Backend API / Docs:   http://localhost:8000/docs"
echo "  Health Endpoint:      http://localhost:8000/api/v1/health"
echo ""
echo "  Default Admin Credentials:"
echo "    Username: admin"
echo "    Password: admin"
echo "======================================================"
echo "  Useful Commands:"
echo "    View live logs:      $COMPOSE_CMD logs -f"
echo "    Stop containers:     $COMPOSE_CMD down"
echo "    Restart containers:  $COMPOSE_CMD restart"
echo "======================================================"
