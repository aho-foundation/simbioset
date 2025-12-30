# Интеграционные тесты для Weaviate

## Быстрый старт

### 1. Запуск Weaviate локально

**Вариант A: Использовать скрипт (рекомендуется)**

```bash
# Запуск
./scripts/start_weaviate_local.sh

# В другом терминале запустите тесты
pytest tests/test_weaviate_integration.py

# Остановка
./scripts/stop_weaviate_local.sh
```

**Вариант B: Автоматический запуск в тестах**

```bash
# Тесты автоматически запустят Weaviate, если доступен бинарник
pytest tests/test_weaviate_integration.py --weaviate-local
```

**Вариант C: Использовать существующий Weaviate**

```bash
# Установите переменные окружения
export WEAVIATE_URL=http://localhost:8080
export WEAVIATE_GRPC_URL=localhost:50051

# Запустите тесты
pytest tests/test_weaviate_integration.py
```

### 2. Запуск тестов

```bash
# Все интеграционные тесты
pytest tests/test_weaviate_integration.py

# Конкретный тест
pytest tests/test_weaviate_integration.py::TestWeaviateStorageIntegration::test_search_similar

# С подробным выводом
pytest tests/test_weaviate_integration.py -v

# С покрытием
pytest tests/test_weaviate_integration.py --cov=api.storage.weaviate_storage
```

## Требования

- Python 3.12+
- Weaviate (бинарник или Docker)
- Зависимости из `requirements.txt`

## Установка Weaviate

См. подробную инструкцию: [docs/infra/WEAVIATE_LOCAL_SETUP.md](../../docs/infra/WEAVIATE_LOCAL_SETUP.md)

## Структура тестов

- `test_add_documents` - добавление документов
- `test_add_chat_messages` - добавление чат-сообщений
- `test_search_similar` - базовый поиск
- `test_search_similar_paragraphs` - асинхронный поиск
- `test_search_with_filters` - поиск с фильтрацией
- `test_get_paragraph_by_id` - получение по ID
- `test_update_paragraph` - обновление параграфа
- `test_delete_paragraph` - удаление параграфа
- `test_get_all_documents` - список документов
- `test_search_with_ecosystem_filter` - фильтр по экосистеме
- `test_search_with_organism_ids_filter` - фильтр по organism_ids

## Устранение проблем

### Weaviate не запускается

1. Проверьте, установлен ли бинарник:
   ```bash
   which weaviate
   ```

2. Проверьте, не занят ли порт:
   ```bash
   lsof -i :8080
   ```

3. Используйте Docker как альтернативу:
   ```bash
   docker run -d -p 8080:8080 semitechnologies/weaviate:latest
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

3. Используйте флаг `--weaviate-local`:
   ```bash
   pytest tests/test_weaviate_integration.py --weaviate-local
   ```

## CI/CD

В CI/CD можно использовать Docker:

```yaml
services:
  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
      - 8080:8080
```
