# Weaviate Testing Guide

## Обзор

Тестовая инфраструктура для Weaviate включает unit тесты, интеграционные тесты и E2E тесты для проверки полной функциональности.

## Запуск тестов

### Unit тесты (без Weaviate)
```bash
pytest tests/test_weaviate_unit.py -v
```

### Интеграционные тесты (с Weaviate)
```bash
# С существующим Weaviate
pytest tests/test_weaviate_integration.py -v

# С локальным Weaviate (требует установленного бинарника)
pytest tests/test_weaviate_integration.py --weaviate-local -v
```

### E2E тесты (полный цикл)
```bash
pytest tests/test_weaviate_e2e.py -v
```

### Frontend E2E тесты
```bash
# Запустить dev server
npm run dev

# В другом терминале
npx playwright test tests/test_frontend_weaviate.spec.ts
```

## Тестовые фикстуры

### `weaviate_server`
- Автоматически запускает Weaviate если доступен
- Использует `--weaviate-local` для локального запуска
- Очищает тестовые данные после тестов

### `weaviate_storage`
- Создает WeaviateStorage с изолированным тестовым классом
- Автоматически очищает данные после тестов

## Структура тестов

### Unit тесты (`test_weaviate_unit.py`)
- ✅ Тестирование схемы (автогенерация свойств)
- ✅ Тестирование типов данных Weaviate
- ✅ Тестирование преобразования Paragraph ↔ Weaviate объекты
- ✅ Тестирование генерации эмбеддингов

### Интеграционные тесты (`test_weaviate_integration.py`)
- ✅ CRUD операции (create, read, update, delete)
- ✅ Поиск с фильтрацией (теги, локации, экосистемы)
- ✅ Batch операции
- ✅ Асинхронные операции
- ✅ Обработка ошибок

### E2E тесты (`test_weaviate_e2e.py`)
- ✅ Полный жизненный цикл контента
- ✅ Интеграция классификации + NER
- ✅ Производительность и масштабируемость
- ✅ Обработка ошибок и восстановление

### Frontend тесты (`test_frontend_weaviate.spec.ts`)
- ✅ Рендеринг компонентов
- ✅ Взаимодействие с UI
- ✅ API интеграция
- ✅ Адаптивный дизайн
- ✅ Обработка ошибок

## Переменные окружения для тестов

```bash
# Weaviate подключение
WEAVIATE_URL=http://localhost:8080
WEAVIATE_GRPC_URL=localhost:50051

# Тестовые настройки
WEAVIATE_AUTO_SCHEMA=true
ENABLE_AUTOMATIC_DETECTORS=true

# Playwright
PLAYWRIGHT_BROWSERS_PATH=/tmp/playwright-browsers
```

## Локальный запуск Weaviate

### С бинарником
```bash
# Скачать и установить Weaviate бинарник
curl -L https://github.com/weaviate/weaviate/releases/download/v1.24.0/weaviate-v1.24.0-linux-amd64.tar.gz | tar xz
sudo mv weaviate /usr/local/bin/

# Запустить тесты
pytest tests/test_weaviate_integration.py --weaviate-local -v
```

### С Docker
```bash
# Запустить Weaviate в фоне
docker run -d --name weaviate-test \
  -p 8080:8080 -p 50051:50051 \
  weaviate/weaviate:latest

# Запустить тесты
WEAVIATE_URL=http://localhost:8080 pytest tests/test_weaviate_integration.py -v

# Остановить
docker stop weaviate-test && docker rm weaviate-test
```

## Профилирование производительности

```bash
# Тест производительности
pytest tests/test_weaviate_e2e.py::TestWeaviateE2E::test_performance_and_scalability -v -s

# С измерением времени
pytest tests/ --durations=10
```

## Отладка тестов

### Логирование
```bash
# Детальное логирование
pytest tests/ -v -s --log-cli-level=DEBUG

# Логи в файл
pytest tests/ --log-file=test.log --log-file-level=DEBUG
```

### Отладка API
```bash
# Проверка доступности Weaviate
curl http://localhost:8080/v1/meta

# Проверка схемы
curl http://localhost:8080/v1/schema
```

## CI/CD интеграция

### GitHub Actions пример
```yaml
- name: Run Weaviate tests
  run: |
    docker run -d --name weaviate \
      -p 8080:8080 -p 50051:50051 \
      weaviate/weaviate:latest
    sleep 10
    pytest tests/test_weaviate_integration.py -v
    docker stop weaviate
```

## Расширение тестов

### Добавление новых unit тестов
```python
def test_new_functionality(self):
    # Тест новой функциональности
    pass
```

### Добавление новых E2E сценариев
```python
def test_new_e2e_scenario(self, e2e_storage):
    # Новый E2E сценарий
    pass
```

### Добавление frontend тестов
```typescript
test('new frontend feature', async ({ page }) => {
  // Новый frontend тест
})
```

## Метрики покрытия

```bash
# С покрытием
pytest tests/ --cov=api --cov-report=html

# Отчет в HTML
open htmlcov/index.html
```

## Troubleshooting

### Тесты не запускаются
- Проверьте переменные окружения
- Убедитесь, что Weaviate доступен
- Проверьте зависимости: `pip install -r requirements.txt`

### Ошибки подключения
- Проверьте `WEAVIATE_URL` и `WEAVIATE_GRPC_URL`
- Убедитесь, что порты не заняты
- Проверьте логи Weaviate

### Медленные тесты
- Уменьшите размер тестовых данных
- Используйте `--durations` для поиска bottleneck'ов
- Оптимизируйте batch размеры

### Frontend тесты падают
- Проверьте, что dev server запущен
- Убедитесь, что API доступен
- Проверьте селекторы в тестах