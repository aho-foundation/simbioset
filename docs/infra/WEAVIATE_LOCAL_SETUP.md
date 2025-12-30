# Локальный запуск Weaviate без Docker

## Обзор

Для разработки и тестирования можно запускать Weaviate локально без Docker, используя бинарник Weaviate.

## Установка Weaviate

### Способ 1: Скачать бинарник (рекомендуется)

```bash
# Определяем ОС и архитектуру
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

# Для macOS ARM
if [ "$OS" = "darwin" ] && [ "$ARCH" = "arm64" ]; then
    ARCH="arm64"
elif [ "$OS" = "darwin" ]; then
    ARCH="amd64"
fi

# Скачиваем последнюю версию
VERSION=$(curl -s https://api.github.com/repos/weaviate/weaviate/releases/latest | grep tag_name | cut -d '"' -f 4)
wget "https://github.com/weaviate/weaviate/releases/download/${VERSION}/weaviate-${OS}-${ARCH}" -O weaviate
chmod +x weaviate
sudo mv weaviate /usr/local/bin/
```

### Способ 2: Homebrew (macOS)

```bash
brew install weaviate
```

### Способ 3: Использовать Docker (если бинарник недоступен)

```bash
docker run -d \
  --name weaviate \
  -p 8080:8080 \
  -p 50051:50051 \
  -v "$(pwd)/.weaviate-data:/var/lib/weaviate" \
  semitechnologies/weaviate:latest
```

## Запуск

### Автоматический запуск через скрипт

```bash
# Запуск
./scripts/start_weaviate_local.sh

# Остановка
./scripts/stop_weaviate_local.sh
```

### Ручной запуск

```bash
# Создаем директорию для данных
mkdir -p .weaviate-data

# Запускаем Weaviate
weaviate \
  --host 127.0.0.1 \
  --port 8080 \
  --scheme http \
  --persistence-data-path ./.weaviate-data \
  --default-vectorizer-module none \
  --enable-modules ""
```

## Настройка переменных окружения

```bash
export WEAVIATE_URL=http://localhost:8080
export WEAVIATE_GRPC_URL=localhost:50051
```

Или создайте файл `.env`:

```env
WEAVIATE_URL=http://localhost:8080
WEAVIATE_GRPC_URL=localhost:50051
```

## Проверка работы

```bash
# Проверка API
curl http://localhost:8080/v1/meta

# Проверка GraphQL
curl -X POST http://localhost:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ Get { Paragraph { content } } }"}'
```

## Использование в тестах

### Запуск тестов с локальным Weaviate

```bash
# Запуск всех интеграционных тестов
pytest tests/test_weaviate_integration.py

# Запуск с автоматическим запуском локального Weaviate
pytest tests/test_weaviate_integration.py --weaviate-local

# Запуск конкретного теста
pytest tests/test_weaviate_integration.py::TestWeaviateStorageIntegration::test_search_similar
```

### Настройка для CI/CD

В CI/CD можно использовать Docker:

```yaml
# .github/workflows/test.yml
services:
  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
      - 8080:8080
      - 50051:50051
    env:
      PERSISTENCE_DATA_PATH: /var/lib/weaviate
      DEFAULT_VECTORIZER_MODULE: none
      ENABLE_MODULES: ""
```

## Устранение проблем

### Weaviate не запускается

1. Проверьте, не занят ли порт 8080:
   ```bash
   lsof -i :8080
   ```

2. Проверьте права на директорию данных:
   ```bash
   chmod -R 755 .weaviate-data
   ```

3. Проверьте логи:
   ```bash
   weaviate --help
   ```

### Тесты не проходят

1. Убедитесь, что Weaviate запущен:
   ```bash
   curl http://localhost:8080/v1/meta
   ```

2. Проверьте переменные окружения:
   ```bash
   echo $WEAVIATE_URL
   ```

3. Используйте флаг `--weaviate-local` для автоматического запуска:
   ```bash
   pytest tests/test_weaviate_integration.py --weaviate-local
   ```

## Альтернативы

Если бинарник Weaviate недоступен, можно использовать:

1. **Docker Compose** (см. `docs/infra/WEAVIATE_DOKKU_SETUP.md`)
2. **Embedded Weaviate** (если будет доступен в будущих версиях)
3. **Удаленный Weaviate** (для разработки можно использовать тестовый инстанс)
