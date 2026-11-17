FROM python:3.12-slim-bookworm

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Install system dependencies:
# - build-essential, python3-dev: for compiling C-extensions (lap, libewf)
# - ffmpeg: DVR/NVR video inspection, demuxing, and transcoding
# - libgl1, libglib2.0-0: for OpenCV headless and GUI operations
# - curl: for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Use uv for ultra-fast and reliable Python wheel resolution and installation
RUN pip install --no-cache-dir uv

# Copy dependency specifications first to leverage Docker layer caching
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# Copy backend codebase
COPY . .

# Normalize line endings and ensure entrypoint script is executable
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

# Container healthcheck using backend /api/v1/health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
