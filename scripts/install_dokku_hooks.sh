#!/bin/bash
# Установка Dokku hooks для автоматической настройки общего кеша
# Выполнить на сервере: bash scripts/install_dokku_hooks.sh

set -e

echo "🔧 Установка Dokku hooks для автоматической настройки..."

# Создаем директорию для плагина
PLUGIN_DIR="/var/lib/dokku/plugins/shared-cache"
mkdir -p "$PLUGIN_DIR"

# Копируем скрипт настройки в плагин
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/dokku_common_setup.sh"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Скрипт $SCRIPT_PATH не найден!"
    exit 1
fi

# Создаем скрипт установки в плагине
cat > "$PLUGIN_DIR/install" << 'EOF'
#!/bin/bash
# Автоматическая настройка общего кеша при создании приложения
# Все кеши в /root/.cache/*
APP="$1"
CACHE_BASE="/var/lib/dokku/data/shared"

if [ -z "$APP" ]; then
    exit 0
fi

# Создаем директории для кешей (все в .cache)
mkdir -p "$CACHE_BASE"/{pip,uv,pypoetry,npm,yarn,pnpm,cargo,ms-playwright}
chown -R dokku:dokku "$CACHE_BASE"
chmod -R 755 "$CACHE_BASE"

# Все кеши в /root/.cache/*
dokku storage:mount "$APP" "$CACHE_BASE/pip:/root/.cache/pip" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/uv:/root/.cache/uv" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/uv:/root/.local/share/uv" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/pypoetry:/root/.cache/pypoetry" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/npm:/root/.cache/npm" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/yarn:/root/.cache/yarn" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/pnpm:/root/.cache/pnpm" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/cargo:/root/.cache/cargo" 2>/dev/null || true
dokku storage:mount "$APP" "$CACHE_BASE/ms-playwright:/root/.cache/ms-playwright" 2>/dev/null || true

# Переменные окружения (все в .cache)
dokku config:set "$APP" \
    PIP_CACHE_DIR=/root/.cache/pip \
    UV_CACHE_DIR=/root/.cache/uv \
    CARGO_HOME=/root/.cache/cargo \
    NPM_CONFIG_CACHE=/root/.cache/npm \
    YARN_CACHE_FOLDER=/root/.cache/yarn \
    PNPM_HOME=/root/.cache/pnpm \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright 2>/dev/null || true
EOF

chmod +x "$PLUGIN_DIR/install"

# Создаем hook для post-app-create (после создания приложения)
HOOK_DIR="/var/lib/dokku/core-plugins/available/apps/post-app-create"
mkdir -p "$HOOK_DIR"

cat > "$HOOK_DIR/shared-cache" << 'EOF'
#!/bin/bash
# Хук для автоматической настройки кешей при создании приложения
/var/lib/dokku/plugins/shared-cache/install "$APP"
EOF

chmod +x "$HOOK_DIR/shared-cache"

echo "✅ Dokku hooks установлены!"
echo ""
echo "Теперь при создании нового приложения автоматически будут настроены:"
echo "  - Persistent Storage mounts для общего кеша"
echo "  - Переменные окружения для использования кешей"
echo ""
echo "Для применения к существующим приложениям выполните:"
echo "  bash scripts/dokku_common_setup.sh"
