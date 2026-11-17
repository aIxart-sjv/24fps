# 24FPS Forensic Analysis Platform — Docker Guide
> Cross-platform containerized deployment for **Arch Linux** and **Windows 11** (Docker Desktop / WSL2).

---

## 1. Overview & Architecture

The 24FPS Docker deployment packages the complete multi-vendor DVR/NVR forensic analysis platform into standardized Linux containers that run with identical behavior on **Arch Linux** and **Windows 11**:

```
                       ┌────────────────────────────────────────────────────────┐
                       │                       HOST MACHINE                     │
                       │               (Arch Linux / Windows 11)                │
                       └───────────────────▲─────────────────▲──────────────────┘
                                           │                 │
                           Port 3000 (HTTP)│                 │Port 8000 (API/Docs)
                                           ▼                 ▼
             ┌───────────────────────────────────────────────┬───────────────────────────────┐
             │ 24fps-frontend (Nginx Container)              │ 24fps-backend (FastAPI)       │
             │                                               │                               │
             │ - React 19 + TypeScript SPA (Port 3000)       │ - Python 3.12 + FastAPI       │
             │ - Nginx reverse-proxies /api/ to backend:8000 │ - FFmpeg & FFprobe (media)    │
             │ - Reverse-proxies /docs & /openapi.json       │ - PyTorch + Ultralytics YOLO  │
             │ - Unlimited body size for disk image uploads  │ - OpenCV (headless + GUI)     │
             │ - Gzip compression & client asset caching     │ - LibEWF (E01/Ex01 images)    │
             └───────────────────────┬───────────────────────┴───────────────┬───────────────┘
                                     │                                       │
                                     │ internal network                      │ volume mount
                                     └───────────────────────────────────────► ./backend/data
                                                                               ├── case_metadata.db
                                                                               ├── evidence/
                                                                               ├── artifacts/
                                                                               ├── reports/
                                                                               ├── models/
                                                                               └── logs/
```

### Key Highlights
- **Identical across OS**: Runs in Linux containers via Docker on Arch Linux and Docker Desktop / WSL2 on Windows 11.
- **Data Persistence**: Case evidence, SQLite database (`case_metadata.db`), reports, logs, and AI models reside in `./backend/data` on the host, surviving container stops, restarts, and updates.
- **Zero-Config Reverse Proxy**: Frontend Nginx proxies `/api/` directly to backend, preventing CORS complications.
- **Large Forensic File Uploads**: `client_max_body_size` is unrestricted (`0`) to support gigabyte-scale DVR/NVR forensic disk images and video files.
- **Automatic Schema Migrations**: Backend automatically initializes and updates SQLite database tables via Alembic on startup.
- **Default Admin Provisioning**: On a fresh database, an administrator account is seeded automatically (`admin` / `admin`).

---

## 2. Quick Start

### On Windows 11

#### Prerequisites:
1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) (select WSL 2 backend during installation).
2. Start Docker Desktop and confirm the whale icon indicates "Engine running" in the system tray.

#### Run with Launcher Script:
- **Option A (Batch)**: Double-click `run-docker.bat` (or run it in CMD).
- **Option B (PowerShell)**: In PowerShell:
  ```powershell
  .\run-docker.ps1
  ```
- **Option C (Standard Docker Compose CLI)**:
  ```powershell
  docker compose up --build -d
  ```

Once running, the web portal automatically opens at **http://localhost:3000**.

---

### On Arch Linux

#### Prerequisites:
1. Install Docker and Docker Compose:
   ```bash
   sudo pacman -S docker docker-compose
   ```
2. Enable and start the Docker systemd service:
   ```bash
   sudo systemctl enable --now docker
   ```
3. (Optional but recommended) Add your user to the `docker` group so you do not need `sudo`:
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

#### Run with Launcher Script:
```bash
chmod +x run-docker.sh
./run-docker.sh
```

#### Or Run Directly with Docker Compose:
```bash
docker compose up --build -d
```

---

## 3. Accessing the Platform

| Service | URL | Description |
|---|---|---|
| **Web Portal** | [http://localhost:3000](http://localhost:3000) | Full 24FPS Forensic Web GUI |
| **Backend API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI |
| **Alternative Docs** | [http://localhost:3000/docs](http://localhost:3000/docs) | Swagger UI via Frontend Proxy |
| **Health Check** | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | Backend health status JSON |

### Default Credentials
- **Username**: `admin`
- **Password**: `admin`
- **Role**: `admin` (Full access to cases, evidence ingestion, AI models, and user management)

*(You can customize these by setting `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `docker-compose.yml` or `.env`)*.

---

## 4. Useful Management Commands

### Viewing Logs
```bash
# View logs from all services in real time
docker compose logs -f

# View only backend forensic logs
docker compose logs -f backend

# View frontend / Nginx access logs
docker compose logs -f frontend
```

### Stopping & Restarting
```bash
# Stop containers without losing data
docker compose down

# Restart containers
docker compose restart

# Rebuild images after changing code or dependencies
docker compose up --build -d
```

---

## 5. Advanced Configurations

### Option A: NVIDIA GPU Acceleration (Linux & Windows WSL2)
If your friend's laptop or your Arch Linux machine has an NVIDIA GeForce / RTX GPU:

1. Ensure the NVIDIA Container Toolkit is installed (on Windows, this is included in Docker Desktop with WSL2; on Arch, install `nvidia-container-toolkit`).
2. Launch with the GPU overlay:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
   ```
3. PyTorch and Ultralytics YOLO will automatically detect and utilize the GPU for frame analysis and object tracking.

### Option B: Active Development Mode (Live Hot Reloading)
If you or your friend want to modify frontend TypeScript or backend Python code with live hot-reloading inside Docker:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Option C: Single Unified Container (Without Compose)
If you prefer running a single self-contained container:
```bash
# Build the unified image
docker build -t 24fps .

# Run the container (mounting host data)
docker run -d \
  --name 24fps \
  -p 3000:3000 \
  -p 8000:8000 \
  -v "$(pwd)/backend/data:/app/backend/data" \
  24fps
```

---

## 6. Troubleshooting

### Port Conflict (Port 3000 or 8000 already in use)
If port 3000 or 8000 is occupied by another local service on your machine:
Edit `docker-compose.yml` and change the host port mapping:
```yaml
ports:
  - "3001:3000"  # Access frontend at http://localhost:3001
```

### Windows Line Endings (`\r\n` / CRLF) Error
If Git on Windows converted shell scripts to CRLF, you might see `/bin/bash^M: bad interpreter`.
- The repository `.gitattributes` and Dockerfiles already enforce LF endings and execute `sed -i 's/\r$//'` to neutralize CRLF.
- If you edit `.sh` files on Windows, ensure your editor saves with **LF** line endings.

### Permission Denied on Arch Linux (`unix:///var/run/docker.sock`)
Ensure your user is in the `docker` group:
```bash
sudo usermod -aG docker $USER
newgrp docker
```
Or execute with `sudo ./run-docker.sh`.

### Resetting to a Clean State
To wipe all container data and start fresh:
```bash
docker compose down -v
# Optionally backup/remove local SQLite database:
# rm backend/data/case_metadata.db
```
