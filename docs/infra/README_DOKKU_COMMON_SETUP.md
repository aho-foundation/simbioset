# Общий сценарий развертывания для Dokku

## Связанные документы

- [WEAVIATE_DOKKU_SETUP.md](WEAVIATE_DOKKU_SETUP.md) - Развертывание Weaviate в Dokku
- [WEAVIATE_APP_LINKING.md](WEAVIATE_APP_LINKING.md) - Подключение приложений к Weaviate

## Проблема

Нужно автоматически настраивать общий кеш для всех Dokku приложений при создании и деплое.

## Решение

Создан общий скрипт `dokku_common_setup.sh`, который:
- Настраивает Persistent Storage mounts для общего кеша
- Устанавливает переменные окружения
- Может применяться ко всем приложениям или к конкретному

## Использование

### 1. Настройка всех существующих приложений

```bash
# Скопировать скрипт на сервер
scp scripts/dokku_common_setup.sh root@yourserver.com:/tmp/

# Выполнить на сервере (настроит ВСЕ приложения)
ssh root@yourserver.com "bash /tmp/dokku_common_setup.sh"
```

### 2. Настройка конкретного приложения

```bash
ssh root@yourserver.com "bash /tmp/dokku_common_setup.sh simbioset-website"
```

### 3. Автоматическая настройка новых приложений

```bash
# Установить Dokku hooks для автоматической настройки
scp scripts/install_dokku_hooks.sh root@yourserver.com:/tmp/
ssh root@yourserver.com "bash /tmp/install_dokku_hooks.sh"
```

После установки hooks, при создании нового приложения (`dokku apps:create APP_NAME`) автоматически будут настроены:
- Persistent Storage mounts для общего кеша
- Переменные окружения для использования кешей

## Что настраивается

### Persistent Storage mounts

**Все кеши в `/root/.cache/*`:**

```
/var/lib/dokku/data/shared/
├── pip/              → /root/.cache/pip
├── uv/               → /root/.cache/uv и /root/.local/share/uv
├── pypoetry/         → /root/.cache/pypoetry
├── npm/              → /root/.cache/npm
├── yarn/             → /root/.cache/yarn
├── pnpm/             → /root/.cache/pnpm
├── cargo/            → /root/.cache/cargo
└── ms-playwright/    → /root/.cache/ms-playwright
```

### Переменные окружения

Все переменные указывают на пути в `/root/.cache/*`:

- `PIP_CACHE_DIR=/root/.cache/pip`
- `UV_CACHE_DIR=/root/.cache/uv`
- `CARGO_HOME=/root/.cache/cargo`
- `NPM_CONFIG_CACHE=/root/.cache/npm`
- `YARN_CACHE_FOLDER=/root/.cache/yarn`
- `PNPM_HOME=/root/.cache/pnpm`
- `PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright`

## Проверка

```bash
# Проверить storage mounts
dokku storage:report APP_NAME

# Проверить переменные окружения
dokku config:show APP_NAME | grep CACHE

# Проверить размер общего кеша
du -sh /var/lib/dokku/data/shared/*
```

## Структура скриптов

- `dokku_common_setup.sh` - основной скрипт настройки (можно применять к любому приложению)
- `install_dokku_hooks.sh` - установка Dokku hooks для автоматической настройки новых приложений

## Dokku Hooks

После установки hooks, скрипт автоматически выполняется при:
- `dokku apps:create APP_NAME` - создание нового приложения

Hook находится в: `/var/lib/dokku/core-plugins/available/apps/post-app-create/shared-cache`

## Единая структура кешей

Все кеши используют единую структуру `/root/.cache/*`, что упрощает управление и обеспечивает консистентность между разными инструментами.
