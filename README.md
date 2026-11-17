# 24fps
Multi-vendor DVR/NVR forensic analysis platform for evidence acquisition, recovery, timeline analysis, AI analytics, integrity validation, and standardized reporting.

---

## Quick Start with Docker (Arch Linux & Windows 11)

24FPS provides ready-to-use Docker containers that run identically across **Arch Linux** and **Windows 11** (via Docker Desktop / WSL2).

### 🚀 Running on Windows 11
1. Open Docker Desktop.
2. Double-click `run-docker.bat` (or run `.\run-docker.ps1` in PowerShell).
3. The platform opens automatically at [http://localhost:3000](http://localhost:3000).

### 🚀 Running on Arch Linux
1. Ensure the Docker daemon is active (`sudo systemctl enable --now docker`).
2. Run:
   ```bash
   ./run-docker.sh
   ```
3. Open [http://localhost:3000](http://localhost:3000).

### 🔑 Default Credentials
- **Username:** `admin`
- **Password:** `admin`

For architecture details, GPU acceleration, live development mode, and troubleshooting, read the **[Docker Guide](DOCKER_GUIDE.md)**.

