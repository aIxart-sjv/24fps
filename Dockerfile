# Unified Single-Container Dockerfile for 24FPS Platform
# Builds both Frontend and Backend into a single self-contained container.

# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# Stage 2: Runtime Environment with Python 3.12, Nginx, and FFmpeg
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8000

# Install system dependencies + Nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python dependency installation
RUN pip install --no-cache-dir uv

WORKDIR /app/backend

# Copy backend requirements and install dependencies
COPY backend/pyproject.toml backend/requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy compiled frontend from Stage 1 into Nginx web root
COPY --from=frontend-builder /build/dist /usr/share/nginx/html

# Configure Nginx for unified single-container routing
COPY nginx.unified.conf /etc/nginx/conf.d/default.conf

# Copy container startup script
COPY start-container.sh /app/start-container.sh
RUN sed -i 's/\r$//' /app/start-container.sh && chmod +x /app/start-container.sh

# Expose Frontend (3000) and Backend API (8000)
EXPOSE 3000 8000

# Healthcheck
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["/app/start-container.sh"]
