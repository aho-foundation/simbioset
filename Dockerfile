# syntax=docker/dockerfile:1.4

# Use Python with Node.js pre-installed to avoid network issues
FROM ghcr.io/astral-sh/uv:debian AS base

# Install Node.js and setup uv venv
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && uv venv /opt/venv

FROM base AS node-base

# Python and Node.js already installed
RUN node --version && npm --version

# Python dependencies stage
FROM base AS python-deps

WORKDIR /app

# Set cache directories and environment
ENV UV_CACHE_DIR=/app/.cache/uv \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_WARN_SCRIPT_LOCATION=1 \
    UV_IPV4=true \
    UV_REQUEST_TIMEOUT=300

# DNS should be handled by Docker daemon configuration

# Create cache directories (will be mounted from persistent storage in Dokku)
RUN mkdir -p /app/.cache/pip /app/.cache/npm /app/.cache/ms-playwright /app/.cache/cargo && \
    mkdir -p /app/.cache/uv || true  # Ignore if already exists (from Dokku mount)

# Copy and install Python dependencies
COPY requirements.txt .
RUN if [ -d "/app/.cache/venv" ] && [ -f "/app/.cache/venv/bin/activate" ]; then \
        echo "🔗 Using shared venv from /app/.cache/venv..." && \
        ln -sf /app/.cache/venv /opt/venv && \
        echo "✅ Shared venv linked to /opt/venv"; \
    else \
        echo "📦 Installing packages via pip..." && \
        . /opt/venv/bin/activate && \
        pip install --cache-dir=/app/.cache/pip --no-cache-dir --index-url http://151.101.1.63/simple --trusted-host 151.101.1.63 --retries 50 --timeout 300 -r requirements.txt && \
        echo "✅ Fresh venv created in /opt/venv"; \
    fi

# Node.js runtime dependencies stage
FROM node-base AS node-deps

WORKDIR /app

# Set cache directories (will be mounted from persistent storage in Dokku)
ENV NPM_CONFIG_CACHE=/app/.cache/npm \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright \
    npm_config_cache=/app/.cache/npm \
    npm_config_registry=https://registry.npmmirror.com

RUN mkdir -p /app/.cache/npm /app/.cache/ms-playwright || true

# Copy package files
COPY package.json package-lock.json* ./

# Install runtime Node.js dependencies (production only)
RUN npm ci --no-audit --no-fund --only=production && \
    npm cache clean --force && \
    rm -rf /tmp/* /root/.npm

# Runtime stage - combine everything
FROM base AS runtime

WORKDIR /usr/src/app

# Copy Node.js dependencies (venv will be handled in production stage)
COPY --from=node-deps /app/node_modules ./node_modules
COPY --from=node-deps /app/.cache/ms-playwright /app/.cache/ms-playwright

# Build stage - compile frontend
FROM base AS build-stage

WORKDIR /app

# Install git if needed (Node.js image might have it)
RUN apk add --no-cache git || echo "git already installed"

# Set cache directories for build stage
ENV NPM_CONFIG_CACHE=/app/.cache/npm \
    npm_config_cache=/app/.cache/npm \
    npm_config_registry=https://registry.npmmirror.com

# Create cache directory if not mounted
RUN mkdir -p /app/.cache/npm || true

# Copy package files and install all dependencies (including dev)
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund && \
    npm cache clean --force

# Copy source code
COPY src ./src
COPY public ./public
COPY index.html ./
COPY vite.config.ts ./
COPY tsconfig.json ./

# Build frontend
ENV NODE_ENV=production
RUN npm run build && \
    npm cache clean --force && \
    rm -rf /tmp/* /root/.npm

# Production stage - final minimal image
FROM base AS production

WORKDIR /usr/src/app

# Install curl if needed for healthchecks
RUN apk add --no-cache curl || echo "curl already available"

# Copy Python virtual environment from python-deps stage
COPY --from=python-deps /opt/venv /opt/venv

# Copy Node.js runtime deps and built assets
COPY --from=node-deps /app/node_modules ./node_modules

# Create directory for venv symlink (symlink will be created at runtime)
RUN mkdir -p /opt
COPY --from=build-stage /app/dist ./dist
COPY api ./api

# Set runtime environment
ENV PYTHONUNBUFFERED=1 \
    PORT=5000 \
    PATH="/opt/venv/bin:$PATH" \
    NODE_ENV=production \
    UV_CACHE_DIR=/app/.cache/uv \
    PIP_CACHE_DIR=/app/.cache/pip \
    NPM_CONFIG_CACHE=/app/.cache/npm \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

EXPOSE 5000

# Run application
CMD ["python3", "-m", "granian", "api.main:app", "--host", "0.0.0.0", "--port", "5000", "--interface", "ASGI"]