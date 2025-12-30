# Настройка кеширования для Dockerfile

## Проблема

При каждой сборке Docker образа все пакеты (npm, pip, Playwright браузеры) скачиваются заново, даже если они уже были установлены ранее.

## Решение

Используем два уровня кеширования:

### 1. BuildKit Cache Mounts (во время сборки)

BuildKit cache mounts сохраняют кеш между сборками Docker образа на том же хосте. Это работает автоматически при использовании Docker BuildKit.

**В Dockerfile:**
```dockerfile
# syntax=docker/dockerfile:1.4
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund
```

### 2. Persistent Storage (во время выполнения)

Dokku persistent storage монтируется в контейнер во время выполнения и сохраняется между перезапусками.

**Настройка через скрипты:**
```bash
# На сервере
bash scripts/setup_dokku_shared_cache.sh
# или для конкретного приложения
bash scripts/apply_dokku_cache.sh APP_NAME
```

## Пути кешей

### Node.js
- **npm**: `/root/.npm` (переменная `NPM_CONFIG_CACHE`)
- **yarn**: `/root/.yarn` (переменная `YARN_CACHE_FOLDER`)
- **pnpm**: `/root/.pnpm-store` (переменная `PNPM_HOME`)

### Python
- **pip**: `/root/.cache/pip` (переменная `PIP_CACHE_DIR`)
- **uv**: `/root/.cache/uv` и `/root/.local/share/uv` (переменная `UV_CACHE_DIR`)

### Rust
- **cargo**: `/root/.cargo` (переменная `CARGO_HOME`)

### Playwright (нужен для продакшена - используется crawl4ai для веб-краулинга)
- **браузеры**: `/root/.cache/ms-playwright` (переменная `PLAYWRIGHT_BROWSERS_PATH`)
- Устанавливается только Chromium (`npx playwright install --with-deps chromium`) для минимизации размера образа

## Проверка

```bash
# Проверить монтирование storage
dokku storage:report APP_NAME

# Проверить переменные окружения
dokku config:show APP_NAME

# Проверить использование BuildKit (в логах сборки должно быть видно использование кешей)
dokku logs APP_NAME
```

## Важно

1. **BuildKit должен быть включен** - Docker автоматически использует BuildKit при наличии `# syntax=docker/dockerfile:1.4` в начале Dockerfile
2. **Пути должны совпадать** - пути в Dockerfile, скриптах настройки и переменных окружения должны быть одинаковыми
3. **Права доступа** - директории кешей должны иметь правильные права (dokku:dokku, 755)

## Troubleshooting

Если кеши не работают:

1. Проверьте, что BuildKit включен:
   ```bash
   DOCKER_BUILDKIT=1 docker build .
   ```

2. Проверьте монтирование storage:
   ```bash
   dokku storage:report APP_NAME
   ```

3. Проверьте переменные окружения:
   ```bash
   dokku config:show APP_NAME | grep CACHE
   ```

4. Проверьте логи сборки на наличие использования кешей:
   ```bash
   dokku logs APP_NAME | grep -i cache
   ```
