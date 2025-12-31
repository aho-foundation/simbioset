# syntax=docker/dockerfile:1.4
FROM ghcr.io/astral-sh/uv:debian AS base

# Install Node.js and setup uv venv
RUN apt-get update && apt-get install -y curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs

# Setup uv venv
RUN uv venv /opt/venv

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
        uv pip install --cache-dir=/app/.cache/pip --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt && \
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
RUN apt-get update && apt-get install -y git || echo "git already installed"

# Set cache directories for build stage
ENV NPM_CONFIG_CACHE=/app/.cache/npm \
    npm_config_cache=/app/.cache/npm \
    npm_config_registry=https://registry.npmmirror.com \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

# Create cache directories if not mounted
RUN mkdir -p /app/.cache/npm /app/.cache/ms-playwright || true

# Copy package files and install all dependencies (including dev)
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund && \
    echo "Checking Playwright browsers in $PLAYWRIGHT_BROWSERS_PATH..." && \
    if ! find $PLAYWRIGHT_BROWSERS_PATH -maxdepth 1 -type d -name "chromium-*" 2>/dev/null | grep -q .; then \
        echo "Installing Playwright chromium browser (only, needed for E2E tests)..." && \
        npx playwright install --with-deps chromium; \
    else \
        echo "✅ Chromium browser already exists, skipping installation"; \
    fi && \
    echo "Playwright browsers installed:" && \
    ls -la $PLAYWRIGHT_BROWSERS_PATH/ && \
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
RUN apt-get update && apt-get install -y curl || echo "curl already available"

# Copy Python virtual environment from python-deps stage
COPY --from=python-deps /opt/venv /opt/venv

# Install Playwright browsers for crawl4ai (required in production)
# Устанавливаем системные зависимости для Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1 \
    || echo "Some packages may already be installed"

# Copy Node.js runtime deps and built assets
COPY --from=node-deps /app/node_modules ./node_modules
COPY package.json package-lock.json* ./

# Install Playwright browsers for crawl4ai (always install in production to ensure availability)
# Устанавливаем playwright как зависимость, чтобы он был доступен в runtime
RUN mkdir -p /app/.cache/ms-playwright && \
    echo "Installing Playwright for crawl4ai..." && \
    npm install playwright --save --no-audit --no-fund && \
    echo "Installing Playwright chromium browser..." && \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright npx playwright install chromium && \
    echo "✅ Playwright chromium browser installed" && \
    echo "Verifying chromium browser installation..." && \
    if find /app/.cache/ms-playwright -maxdepth 1 -type d -name "chromium-*" 2>/dev/null | head -1 | xargs test -d 2>/dev/null; then \
        echo "✅ Chromium browser verified"; \
        CHROMIUM_DIR=$(find /app/.cache/ms-playwright -maxdepth 1 -type d -name "chromium-*" | head -1); \
        echo "Chromium directory: $CHROMIUM_DIR"; \
        if [ -f "$CHROMIUM_DIR/chrome-linux64/chrome" ] || [ -f "$CHROMIUM_DIR/chrome-linux/chrome" ]; then \
            echo "✅ Chromium executable found"; \
        else \
            echo "⚠️ Chromium executable not found, listing directory:"; \
            find "$CHROMIUM_DIR" -type f -name "chrome" 2>/dev/null | head -5; \
        fi; \
    else \
        echo "❌ Chromium browser not found!"; \
        exit 1; \
    fi && \
    echo "Playwright browsers location:" && \
    ls -la /app/.cache/ms-playwright/ && \
    find /app/.cache/ms-playwright -maxdepth 2 -type d | head -10 && \
    echo "Verifying playwright is in node_modules:" && \
    test -d node_modules/playwright && echo "✅ playwright found in node_modules" || echo "❌ playwright not in node_modules" && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run application
CMD ["python3", "-m", "granian", "api.main:app", "--host", "0.0.0.0", "--port", "5000", "--interface", "ASGI"]