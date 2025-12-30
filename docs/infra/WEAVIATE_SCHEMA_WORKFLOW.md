# Workflow работы со схемой Weaviate

## Обзор

Документ описывает workflow работы со схемой данных в Weaviate и синхронизацию типов фронтенда.

**Примечание:** Если используете runtime типизацию (без codegen), перегенерация типов не требуется - типы загружаются динамически из схемы. См. [WEAVIATE_GRAPHQL_TYPES.md](WEAVIATE_GRAPHQL_TYPES.md) раздел "Подход 2: Runtime типизация".

## Частота изменений схемы

### Когда меняется схема данных?

Схема данных в Weaviate меняется в следующих случаях:

1. **Добавление нового класса** (редко)
   - Пример: добавление класса `Ecosystem` для хранения экосистем
   - Частота: при добавлении новых сущностей в систему

2. **Добавление нового свойства** (часто)
   - Пример: добавление `updated_at` к классу `Paragraph`
   - Частота: при расширении функциональности

3. **Изменение типа свойства** (очень редко)
   - Пример: изменение `tags` с `string[]` на `object[]`
   - Частота: только при рефакторинге

4. **Добавление связей** (редко)
   - Пример: добавление связи `Paragraph` → `Ecosystem`
   - Частота: при моделировании новых отношений

### Типичная частота изменений

- **Разработка:** 1-5 раз в неделю (при активной разработке)
- **Production:** 1-2 раза в месяц (при добавлении новых фич)
- **Стабильная система:** 1 раз в квартал (редкие улучшения)

## Влияние на GraphQL схему

### Автоматическое обновление

Weaviate **автоматически** обновляет GraphQL схему при изменении схемы данных:

```
Изменение схемы данных → Автоматическое обновление GraphQL схемы
```

**Пример:**
```python
# Добавляем новое свойство
client.schema.property.create("Paragraph", {
    "name": "updated_at",
    "dataType": ["date"]
})

# GraphQL схема автоматически обновляется:
# type Paragraph {
#   content: String
#   document_id: String
#   updated_at: Date  # ← Новое поле появилось автоматически!
# }
```

### Когда нужно перегенерировать типы фронтенда?

**Для Code Generation (статическая типизация):**

**Обязательно перегенерировать:**
- ✅ После добавления нового класса
- ✅ После добавления нового свойства
- ✅ После изменения типа свойства
- ✅ После добавления связей
- ✅ Перед каждым деплоем (в CI/CD)

**Не нужно перегенерировать:**
- ❌ При добавлении только данных (без изменения схемы)
- ❌ При изменении только векторов
- ❌ При изменении только метаданных (без изменения структуры)

**Для Runtime типизации (динамическая):**

**Не нужно перегенерировать!** Типы загружаются динамически из схемы в runtime. Схема всегда актуальна автоматически.

## Workflow разработки

### Вариант 1: Auto-schema (рекомендуется для разработки)

```bash
# 1. Включаем auto-schema
dokku config:set weaviate AUTOSCHEMA_ENABLED=true

# 2. Добавляем данные (схема создается автоматически)
python scripts/add_test_data.py

# 3. Проверяем схему
curl http://weaviate:8080/v1/schema

# 4. Генерируем типы фронтенда
npm run codegen

# 5. Коммитим типы
git add src/generated/weaviate-types.ts
git commit -m "chore: update GraphQL types after schema changes"
```

### Вариант 2: Явная схема (рекомендуется для production)

```bash
# 1. Отключаем auto-schema
dokku config:set weaviate AUTOSCHEMA_ENABLED=false

# 2. Определяем схему явно
python scripts/create_schema.py

# 3. Генерируем типы
npm run codegen

# 4. Коммитим схему и типы
git add schema/weaviate-schema.json src/generated/weaviate-types.ts
git commit -m "feat: add updated_at field to Paragraph schema"
```

## Автоматизация

### Pre-commit hook

```bash
# .husky/pre-commit
#!/bin/sh

# Генерируем типы перед коммитом
npm run codegen

# Добавляем сгенерированные типы
git add src/generated/weaviate-types.ts
```

### Watch mode в разработке

```bash
# Запускаем в отдельном терминале
npm run codegen:watch

# Теперь типы обновляются автоматически при изменении схемы
```

### CI/CD проверка

```yaml
# .github/workflows/check-schema.yml
name: Check Schema Changes

on:
  pull_request:
    branches: [main]

jobs:
  check-schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      
      # Генерируем типы
      - name: Generate types
        run: npm run codegen
        env:
          WEAVIATE_URL: ${{ secrets.WEAVIATE_URL }}
      
      # Проверяем, что типы актуальны
      - name: Check types are up to date
        run: |
          if [ -n "$(git status --porcelain src/generated/)" ]; then
            echo "❌ GraphQL типы устарели! Запустите 'npm run codegen'"
            git diff src/generated/
            exit 1
          fi
          echo "✅ GraphQL типы актуальны"
```

## Версионирование схемы

### Сохранение схемы в репозиторий

```bash
# scripts/save-schema.sh
#!/bin/bash

# Получаем текущую схему
curl -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query IntrospectionQuery { __schema { types { name kind } } }"}' \
  > schema/weaviate-schema-$(date +%Y%m%d-%H%M%S).json

# Сохраняем последнюю версию
cp schema/weaviate-schema-*.json schema/weaviate-schema-latest.json

echo "✅ Схема сохранена"
```

### Сравнение версий

```bash
# scripts/compare-schema.sh
#!/bin/bash

# Получаем текущую схему
CURRENT=$(curl -s -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { __schema { types { name } } }"}' | jq -c .)

# Загружаем сохраненную
SAVED=$(cat schema/weaviate-schema-latest.json 2>/dev/null || echo "{}")

if [ "$CURRENT" != "$SAVED" ]; then
  echo "⚠️  Схема изменилась!"
  echo "Текущая: $CURRENT"
  echo "Сохраненная: $SAVED"
  exit 1
else
  echo "✅ Схема не изменилась"
fi
```

## Best Practices

1. **Генерируйте типы автоматически** - не создавайте вручную
2. **Коммитьте типы в репозиторий** - версионируйте вместе с кодом
3. **Проверяйте в CI** - убедитесь, что типы актуальны перед деплоем
4. **Используйте watch mode** - в разработке для автоматического обновления
5. **Версионируйте схему** - сохраняйте GraphQL схему в репозиторий
6. **Документируйте изменения** - описывайте изменения схемы в коммитах
7. **Тестируйте типы** - проверяйте, что TypeScript компилируется без ошибок

## Примеры сценариев

### Сценарий 1: Добавление нового свойства

```bash
# 1. Добавляем свойство в Weaviate
python -c "
import weaviate
client = weaviate.Client('http://weaviate:8080')
client.schema.property.create('Paragraph', {
    'name': 'updated_at',
    'dataType': ['date']
})
"

# 2. Генерируем типы
npm run codegen

# 3. Обновляем код фронтенда
# Теперь TypeScript знает про updated_at!

# 4. Коммитим
git add src/generated/weaviate-types.ts
git commit -m "feat: add updated_at field to Paragraph"
```

### Сценарий 2: Добавление нового класса

```bash
# 1. Создаем новый класс
python scripts/create_ecosystem_class.py

# 2. Генерируем типы
npm run codegen

# 3. Используем новый тип в коде
# import { GetEcosystemsQuery } from './generated/weaviate-types';

# 4. Коммитим
git add src/generated/weaviate-types.ts
git commit -m "feat: add Ecosystem class to schema"
```

### Сценарий 3: Массовое обновление

```bash
# 1. Обновляем несколько классов
python scripts/migrate_schema.py

# 2. Генерируем типы
npm run codegen

# 3. Проверяем, что все компилируется
npm run typecheck

# 4. Коммитим
git add src/generated/weaviate-types.ts
git commit -m "refactor: update schema for multiple classes"
```

## Troubleshooting

### Типы не обновляются

```bash
# Удалите старые типы и сгенерируйте заново
rm -rf src/generated/
npm run codegen
```

### Ошибки компиляции TypeScript

```bash
# Проверьте актуальность схемы
curl http://weaviate:8080/v1/schema

# Перегенерируйте типы
npm run codegen

# Проверьте компиляцию
npm run typecheck
```

### Схема изменилась, но типы не обновились

```bash
# Принудительная перегенерация
npm run codegen -- --force

# Или удалите кеш
rm -rf .graphql-codegen/
npm run codegen
```

## Ссылки

- [WEAVIATE_GRAPHQL_TYPES.md](WEAVIATE_GRAPHQL_TYPES.md) - Генерация типов
- [WEAVIATE_SCHEMA_FIRST.md](WEAVIATE_SCHEMA_FIRST.md) - Schema-First для данных
- [WEAVIATE_DOKKU_SETUP.md](WEAVIATE_DOKKU_SETUP.md) - Развертывание
