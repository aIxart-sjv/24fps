# Multi-stage Dockerfile for 24FPS Frontend
# Stage 1: Build static assets with Node.js
FROM node:20-alpine AS build

WORKDIR /app

# Cache dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source files
COPY . .

# Set API URL for the production build
# Using relative path "/api/v1" allows Nginx reverse proxy to forward seamlessly without CORS
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build optimized production bundle
RUN npm run build

# Stage 2: Serve static bundle using Nginx
FROM nginx:alpine

# Replace default configuration with custom reverse-proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts from previous stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
