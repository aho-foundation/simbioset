# Быстрая настройка общего кеша для Dokku

## Выполнение на сервере yourserver.com

```bash
# 1. Подключитесь к серверу
ssh root@yourserver.com

# 2. Создайте директории для кешей
CACHE_BASE="/var/lib/dokku/data/shared"
mkdir -p "$CACHE_BASE"/{pip,uv,rust,npm}
chown -R dokku:dokku "$CACHE_BASE"
chmod -R 755 "$CACHE_BASE"

# 3. Для каждого приложения выполните (замените APP_NAME):
APP_NAME="your-app-name"

# Python
dokku storage:mount "$APP_NAME" "$CACHE_BASE/pip:/root/.cache/pip"
dokku storage:mount "$APP_NAME" "$CACHE_BASE/phon/uv:/root/.cache/uv"
dokku storage:mount "$APP_NAME" "$CACHE_BASE/uv:/root/.local/share/uv"

# Rust
dokku storage:mount "$APP_NAME" "$CACHE_BASE/rust:/root/.cargo"

# Node.js
dokku storage:mount "$APP_NAME" "$CACHE_BASE/npm:/root/.npm"

# Переменные окружения
dokku config:set "$APP_NAME" \
    PIP_CACHE_DIR=/root/.cache/pip \
    UV_CACHE_DIR=/root/.cache/uv \
    CARGO_HOME=/root/.cargo \
    NPM_CONFIG_CACHE=/root/.npm
```

## Или используйте скрипт

```bash
# Скопируйте скрипт на сервер
scp scripts/dokku_common_setup.sh root@yourserver.com:/tmp/

# На сервере выполните для всех приложений:
ssh root@yourserver.com "bash /tmp/dokku_common_setup.sh"

# Или для конкретного приложения:
ssh root@yourserver.com "bash /tmp/dokku_common_setup.sh APP_NAME"
```

## Проверка

```bash
dokku storage:report APP_NAME
dokku config:show APP_NAME
```

