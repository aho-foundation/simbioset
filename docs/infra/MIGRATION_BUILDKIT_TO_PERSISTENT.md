# Миграция с BuildKit Cache на Persistent Storage

## Что изменилось

### Проблема
BuildKit cache mounts (`--mount=type=cache`) раздували build cache в `/var/lib/docker/buildkit/cache` до десятков гигабайт, что приводило к ошибке "no space left on device".

### Решение
Убрали BuildKit cache mounts из Dockerfile. Теперь используем только **Persistent Storage через Dokku** для общего кеша всех приложений.

## Преимущества

✅ **Кеши не попадают в Docker build cache** - хранятся в `/var/lib/dokku/data/shared`  
✅ **Все приложения используют один кеш** - экономия места и ускорение сборки  
✅ **Кеши сохраняются между пересборками** - не теряются при очистке Docker  
✅ **Меньше размер build cache** - освобождается место на диске  

## Что нужно сделать на сервере

### 1. Настроить общий кеш для всех приложений

```bash
# Скопировать скрипт на сервер
scp scripts/setup_dokku_shared_cache.sh root@yourserver.com:/tmp/

# Выполнить на сервере (настроит кеши для ВСЕХ приложений)
ssh root@yourserver.com "bash /tmp/setup_dokku_shared_cache.sh"
```

Скрипт автоматически:
- Создаст общие директории кешей в `/var/lib/dokku/data/shared`
- Настроит Persistent Storage mounts для всех существующих приложений
- Установит переменные окружения для использования кешей

### 2. Очистить старый build cache

```bash
# Подключиться к серверу
ssh root@yourserver.com

# Остановить все контейнеры
docker stop $(docker ps -aq) 2>/dev/null || true

# Удалить build cache
rm -rf /var/lib/docker/buildkit/cache/* 2>/dev/null || true
rm -rf /var/lib/docker/buildkit/executor/* 2>/dev/null || true

# Перезапустить Docker
systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || true

# Проверить результат
docker builder du
df -h /var/lib/docker
```

### 3. Пересобрать приложения

После настройки Persistent Storage и очистки build cache, пересоберите приложения:

```bash
# Для каждого приложения
dokku ps:rebuild APP_NAME
```

## Проверка

```bash
# Проверить монтирование storage
dokku storage:report APP_NAME

# Проверить переменные окружения
dokku config:show APP_NAME | grep CACHE

# Проверить размер общего кеша
du -sh /var/lib/dokku/data/shared/*

# Проверить размер build cache (должен быть намного меньше)
docker builder du
```

## Структура общего кеша

```
/var/lib/dokku/data/shared/
├── pip/              # Python pip кеш (общий для всех приложений)
├── uv/               # Python uv кеш (общий для всех приложений)
├── npm/              # Node.js npm кеш (общий для всех приложений)
├── ms-playwright/    # Playwright браузеры (общий для всех приложений)
└── rust/             # Rust cargo кеш (общий для всех приложений)
```

## Переменные окружения

Переменные окружения уже установлены в Dockerfile и используются через Persistent Storage:

- `PIP_CACHE_DIR=/root/.cache/pip`
- `UV_CACHE_DIR=/root/.cache/uv`
- `CARGO_HOME=/root/.cargo`
- `NPM_CONFIG_CACHE=/root/.cache/npm`
- `PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright`

Эти переменные работают во время выполнения контейнера, когда Persistent Storage уже смонтирован.

## Docker Layer Caching

Docker автоматически кеширует слои, если они не изменились:
- Если `package.json` не изменился → слой с `npm ci` кешируется
- Если `requirements.txt` не изменился → слой с `pip install` кешируется

Это работает без BuildKit cache mounts и не раздувает build cache.
