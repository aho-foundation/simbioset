# Настройка общего кеша пакетов для Dokku

## Выполнение на сервере

Подключитесь к серверу и выполните:

```bash
# 1. Скопируйте скрипт на сервер
scp scripts/dokku_common_setup.sh root@yourserver.com:/tmp/

# 2. Выполните скрипт (настроит ВСЕ приложения)
ssh root@yourserver.com "bash /tmp/dokku_common_setup.sh"

# Или для конкретного приложения
ssh root@yourserver.com "bash /tmp/dokku_common_setup.sh APP_NAME"
```

Или выполните команды вручную:

```bash
# Создаем директории для кешей
CACHE_BASE="/var/lib/dokku/data/shared"
mkdir -p "$CACHE_BASE"/{python,rust,nodejs}
chown -R dokku:dokku "$CACHE_BASE"
chmod -R 755 "$CACHE_BASE"

# Для каждого приложения (замените APP_NAME на имя вашего приложения)
APP_NAME="your-app-name"

# Python кеш
dokku storage:mount "$APP_NAME" "$CACHE_BASE/python:/root/.cache/pip"
dokku storage:mount "$APP_NAME" "$CACHE_BASE/python:/root/.cache/uv"
dokku storage:mount "$APP_NAME" "$CACHE_BASE/python:/root/.local/share/uv"

# Rust кеш
dokku storage:mount "$APP_NAME" "$CACHE_BASE/rust:/root/.cargo"

# Node.js кеш
dokku storage:mount "$APP_NAME" "$CACHE_BASE/nodejs:/root/.npm"
dokku storage:mount "$APP_NAME" "$CACHE_BASE/nodejs:/root/.yarn"
dokku storage:mount "$APP_NAME" "$CACHE_BASE/nodejs:/root/.pnpm-store"

# Переменные окружения
dokku config:set "$APP_NAME" \
    PIP_CACHE_DIR=/root/.cache/pip \
    UV_CACHE_DIR=/root/.cache/uv \
    CARGO_HOME=/root/.cargo \
    NPM_CONFIG_CACHE=/root/.npm \
    YARN_CACHE_FOLDER=/root/.yarn/cache \
    PNPM_HOME=/root/.pnpm-store
```

## Проверка

```bash
# Проверить монтирование storage
dokku storage:report APP_NAME

# Проверить переменные окружения
dokku config:show APP_NAME
```

