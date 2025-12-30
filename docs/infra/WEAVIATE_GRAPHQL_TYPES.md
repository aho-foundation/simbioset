# GraphQL Schema-First для генерации типов фронтенда

## Обзор

Weaviate предоставляет GraphQL API, и для генерации TypeScript типов на фронтенде нужна GraphQL схема. Weaviate автоматически генерирует GraphQL схему на основе схемы данных (классов и свойств).

## Два подхода

### Подход 1: Получение схемы из запущенного Weaviate (рекомендуется)

Weaviate автоматически создает GraphQL схему на основе данных. Можно получить её через introspection query и использовать для генерации типов.

### Подход 2: Определение схемы данных заранее

Определить схему данных в Weaviate заранее, тогда GraphQL схема будет доступна сразу для генерации типов.

## Auto-Schema для данных

**Важно:** Auto-schema в Weaviate - это про автоматическое создание схемы **данных** (классов и свойств), а не про GraphQL schema-first.

### Использование Auto-Schema

**Для разработки:**
```bash
# Включаем auto-schema для удобства разработки
dokku config:set weaviate AUTOSCHEMA_ENABLED=true
```

**Для production:**
```bash
# Отключаем auto-schema для стабильности
dokku config:set weaviate AUTOSCHEMA_ENABLED=false
```

### Когда использовать Auto-Schema?

**Используйте Auto-Schema если:**
- ✅ Прототипирование и быстрая разработка
- ✅ Схема часто меняется
- ✅ Нужна гибкость при добавлении данных

**Не используйте Auto-Schema если:**
- ❌ Production окружение (нужна стабильность)
- ❌ Критична предсказуемость схемы
- ❌ Нужен контроль над типами данных

### Workflow с Auto-Schema

1. **Разработка:** Включаем auto-schema, добавляем данные, схема создается автоматически
2. **Миграция:** Экспортируем созданную схему из Weaviate
3. **Production:** Отключаем auto-schema, используем явную схему

```bash
# 1. Разработка с auto-schema
dokku config:set weaviate AUTOSCHEMA_ENABLED=true
# Добавляем данные, схема создается автоматически

# 2. Экспортируем схему
curl http://weaviate:8080/v1/schema > schema/weaviate-schema.json

# 3. Production - используем явную схему
dokku config:set weaviate AUTOSCHEMA_ENABLED=false
# Создаем схему явно из экспортированного файла
```

Auto-schema позволяет:
- Автоматически создавать классы при добавлении данных
- Автоматически определять типы свойств
- Упрощает прототипирование
- **Но для production лучше использовать явную схему**

## Получение GraphQL схемы

### Через Introspection Query

```bash
# Получить полную GraphQL схему
curl -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query IntrospectionQuery { __schema { queryType { name } types { name kind description fields { name description type { name kind ofType { name kind } } } } } }"
  }'
```

### Через GraphQL Playground

Откройте `http://weaviate:8080/v1/graphql` в браузере и используйте встроенный GraphQL Playground для просмотра схемы.

### Программно (Python)

```python
import weaviate
import json

client = weaviate.Client("http://weaviate:8080")

# Introspection query
introspection_query = """
query IntrospectionQuery {
  __schema {
    types {
      name
      kind
      fields {
        name
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
      }
    }
  }
}
"""

# Выполняем запрос
result = client.query.raw(introspection_query)
schema = result.get("data", {}).get("__schema", {})

# Сохраняем схему в файл
with open("weaviate-schema.json", "w") as f:
    json.dump(schema, f, indent=2)
```

## Генерация TypeScript типов

### Использование GraphQL Code Generator

#### Установка

```bash
npm install -D @graphql-codegen/cli @graphql-codegen/typescript @graphql-codegen/typescript-operations
```

#### Конфигурация `codegen.yml`

```yaml
schema: http://weaviate:8080/v1/graphql
documents: 'src/**/*.graphql'
generates:
  src/generated/weaviate-types.ts:
    plugins:
      - typescript
      - typescript-operations
    config:
      scalars:
        Date: string
        Int: number
        Float: number
        Boolean: boolean
        String: string
```

#### GraphQL запросы в `src/queries/paragraphs.graphql`

```graphql
query GetParagraphs($limit: Int, $where: ParagraphWhereInput) {
  Get {
    Paragraph(limit: $limit, where: $where) {
      content
      document_id
      node_id
      document_type
      session_id
      organism_ids
      ecosystem_id
      location
      tags
      timestamp
      author
      author_id
      _additional {
        id
        distance
      }
    }
  }
}

query SearchParagraphs($nearText: Txt2VecOpenAIGetObjectsTextMove) {
  Get {
    Paragraph(nearText: $nearText) {
      content
      document_id
      tags
      _additional {
        id
        distance
        certainty
      }
    }
  }
}
```

#### Генерация типов

```bash
# Добавить в package.json
"scripts": {
  "codegen": "graphql-codegen --config codegen.yml",
  "codegen:watch": "graphql-codegen --config codegen.yml --watch"
}

# Запустить генерацию
npm run codegen
```

#### Использование в коде

```typescript
// src/generated/weaviate-types.ts будет содержать типы
import { GetParagraphsQuery, SearchParagraphsQuery } from './generated/weaviate-types';

// Использование типов
const query: GetParagraphsQuery = {
  Get: {
    Paragraph: {
      content: "...",
      document_id: "...",
      // TypeScript будет проверять типы!
    }
  }
};
```

### Использование Apollo Client

```typescript
// src/lib/weaviate-client.ts
import { ApolloClient, InMemoryCache, gql } from '@apollo/client';

const client = new ApolloClient({
  uri: 'http://weaviate:8080/v1/graphql',
  cache: new InMemoryCache(),
});

// Запрос с типами
const GET_PARAGRAPHS = gql`
  query GetParagraphs($limit: Int) {
    Get {
      Paragraph(limit: $limit) {
        content
        document_id
        tags
      }
    }
  }
`;

// TypeScript типы будут автоматически сгенерированы
```

### Использование urql

```typescript
// src/lib/weaviate-client.ts
import { Client, cacheExchange, fetchExchange } from 'urql';

const client = new Client({
  url: 'http://weaviate:8080/v1/graphql',
  exchanges: [cacheExchange, fetchExchange],
});

// Запросы с типами
const GET_PARAGRAPHS_QUERY = `
  query GetParagraphs($limit: Int) {
    Get {
      Paragraph(limit: $limit) {
        content
        document_id
        tags
      }
    }
  }
`;
```

## Пример полной настройки

### 1. Создать схему данных в Weaviate

```python
# scripts/create_weaviate_schema.py
import weaviate

client = weaviate.Client("http://weaviate:8080")

schema = {
    "class": "Paragraph",
    "vectorizer": "none",
    "properties": [
        {"name": "content", "dataType": ["text"]},
        {"name": "document_id", "dataType": ["string"]},
        {"name": "tags", "dataType": ["string[]"]},
        # ... остальные свойства
    ]
}

client.schema.create_class(schema)
```

### 2. Получить GraphQL схему

```bash
# Сохранить схему в файл
curl -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query IntrospectionQuery { __schema { types { name kind } } }"}' \
  > weaviate-schema.json
```

### 3. Настроить codegen

```yaml
# codegen.yml
schema: http://weaviate:8080/v1/graphql
generates:
  src/generated/weaviate-types.ts:
    plugins:
      - typescript
      - typescript-operations
```

### 4. Генерировать типы

```bash
npm run codegen
```

### 5. Использовать в коде

```typescript
import { GetParagraphsQuery } from './generated/weaviate-types';

// TypeScript будет проверять типы!
```

## CI/CD интеграция

### Генерация типов при деплое (рекомендуется)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      
      # Генерируем типы перед деплоем
      - name: Generate GraphQL types
        run: npm run codegen
        env:
          WEAVIATE_URL: ${{ secrets.WEAVIATE_URL }}
      
      # Проверяем, изменились ли типы
      - name: Check for type changes
        run: |
          if [ -n "$(git status --porcelain src/generated/)" ]; then
            echo "⚠️  GraphQL типы изменились!"
            git diff src/generated/
            exit 1
          fi
      
      # Деплой...
```

### Отдельный workflow для генерации типов

```yaml
# .github/workflows/codegen.yml
name: Generate GraphQL Types

on:
  workflow_dispatch:  # Ручной запуск
  schedule:
    - cron: '0 0 * * *'  # Ежедневно в полночь

jobs:
  generate-types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      
      - name: Generate GraphQL types
        run: npm run codegen
        env:
          WEAVIATE_URL: ${{ secrets.WEAVIATE_URL }}
      
      - name: Commit generated types
        uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: 'chore: update GraphQL types [skip ci]'
          file_pattern: 'src/generated/**'
```

## Когда перегенерировать типы?

### Частота изменений схемы

Схема данных в Weaviate меняется когда:
- ✅ Добавляются новые классы (например, новый класс `Ecosystem`)
- ✅ Добавляются новые свойства к существующим классам (например, `updated_at` к `Paragraph`)
- ✅ Изменяются типы свойств (редко, обычно требует удаления класса)
- ✅ Добавляются новые связи между классами

### Влияние на GraphQL схему

**Важно:** GraphQL схема в Weaviate автоматически обновляется при изменении схемы данных:
- Новый класс → новый тип в GraphQL
- Новое свойство → новое поле в GraphQL типе
- Изменение типа свойства → изменение типа поля в GraphQL

### Когда перегенерировать типы фронтенда?

**Обязательно перегенерировать:**
1. После добавления нового класса в Weaviate
2. После добавления нового свойства к классу
3. После изменения типов свойств
4. Перед каждым деплоем (в CI/CD)

**Можно не перегенерировать:**
- При добавлении только данных (без изменения схемы)
- При изменении только векторов (без изменения метаданных)

### Автоматизация перегенерации

#### Вариант 1: При каждом деплое (рекомендуется)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      
      # Генерируем типы перед деплоем
      - name: Generate GraphQL types
        run: npm run codegen
        env:
          WEAVIATE_URL: ${{ secrets.WEAVIATE_URL }}
      
      - name: Commit generated types
        uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: 'chore: update GraphQL types'
      
      # Деплой...
```

#### Вариант 2: Watch mode в разработке

```json
// package.json
{
  "scripts": {
    "codegen": "graphql-codegen --config codegen.yml",
    "codegen:watch": "graphql-codegen --config codegen.yml --watch"
  }
}
```

Запускайте в отдельном терминале:
```bash
npm run codegen:watch
```

#### Вариант 3: Pre-commit hook

```bash
# .husky/pre-commit
#!/bin/sh
npm run codegen
git add src/generated/weaviate-types.ts
```

#### Вариант 4: Проверка изменений схемы

```bash
# scripts/check-schema-changes.sh
#!/bin/bash

# Получаем текущую схему
CURRENT_SCHEMA=$(curl -s -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { __schema { types { name } } }"}' | jq -c .)

# Сравниваем с сохраненной
SAVED_SCHEMA=$(cat .weaviate-schema.json 2>/dev/null || echo "{}")

if [ "$CURRENT_SCHEMA" != "$SAVED_SCHEMA" ]; then
  echo "⚠️  Схема изменилась! Нужно перегенерировать типы."
  echo "$CURRENT_SCHEMA" > .weaviate-schema.json
  npm run codegen
  exit 1
else
  echo "✅ Схема не изменилась"
fi
```

### Workflow разработки

#### 1. Разработка с auto-schema

```bash
# 1. Добавляете данные в Weaviate (auto-schema создаст схему автоматически)
python scripts/add_test_data.py

# 2. Проверяете, изменилась ли схема
npm run codegen:check

# 3. Если изменилась - перегенерируете типы
npm run codegen
```

#### 2. Production с явной схемой

```bash
# 1. Определяете схему явно
python scripts/create_schema.py

# 2. Генерируете типы
npm run codegen

# 3. Коммитите типы в репозиторий
git add src/generated/weaviate-types.ts
git commit -m "chore: update GraphQL types"
```

### Версионирование схемы

```bash
# Сохраняйте GraphQL схему в репозиторий
curl -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query IntrospectionQuery { __schema { types { name } } }"}' \
  > schema/weaviate-schema-$(date +%Y%m%d).json

# Или используйте git для отслеживания изменений
git add schema/weaviate-schema-*.json
```

## Best Practices

1. **Генерируйте типы автоматически** - не создавайте их вручную
2. **Версионируйте схему** - сохраняйте GraphQL схему в репозиторий
3. **Проверяйте типы в CI** - запускайте codegen в CI/CD перед деплоем
4. **Используйте auto-schema для данных** - упрощает разработку
5. **Документируйте GraphQL запросы** - используйте комментарии в .graphql файлах
6. **Автоматизируйте перегенерацию** - используйте watch mode или pre-commit hooks
7. **Проверяйте изменения схемы** - перед деплоем проверяйте, не изменилась ли схема

## Подход 2: Runtime типизация (без codegen) - Рекомендуется для SolidJS

**Важно для SolidJS:** SolidJS работает без заранее сгенерированных типов - код более компактный. Но нужна runtime валидация для проверки типов.

### SolidJS с runtime валидацией (рекомендуется)

SolidJS не требует заранее сгенерированных типов - код более компактный. Но нужна runtime валидация:

```typescript
// src/lib/weaviate-solid.ts
import { createResource } from 'solid-js';
import { GraphQLClient } from 'graphql-request';
import { z } from 'zod';

const client = new GraphQLClient('http://weaviate:8080/v1/graphql');

// Определяем схему валидации через Zod
const ParagraphSchema = z.object({
  content: z.string(),
  document_id: z.string().nullable(),
  tags: z.array(z.string()),
  _additional: z.object({
    id: z.string(),
    distance: z.number().optional(),
  }),
});

type Paragraph = z.infer<typeof ParagraphSchema>;

// Функция с runtime валидацией
async function getParagraphs(limit: number = 10): Promise<Paragraph[]> {
  const query = `
    query GetParagraphs($limit: Int) {
      Get {
        Paragraph(limit: $limit) {
          content
          document_id
          tags
          _additional {
            id
            distance
          }
        }
      }
    }
  `;

  const data = await client.request<{
    Get: { Paragraph: unknown[] };
  }>(query, { limit });

  // Runtime валидация - проверяем типы
  const validated = z.array(ParagraphSchema).parse(data.Get.Paragraph);
  
  return validated;
}

// Использование в SolidJS компоненте
export function ParagraphsList() {
  const [paragraphs] = createResource(() => getParagraphs(10));

  return (
    <Show when={paragraphs()} fallback={<div>Loading...</div>}>
      <For each={paragraphs()}>
        {(para) => (
          <div>
            <p>{para.content}</p>
            <p>Tags: {para.tags.join(', ')}</p>
          </div>
        )}
      </For>
    </Show>
  );
}
```

### Использование graphql-request с runtime валидацией

```typescript
// src/lib/weaviate-runtime.ts
import { GraphQLClient } from 'graphql-request';

const client = new GraphQLClient('http://weaviate:8080/v1/graphql');

// Типы определяются в runtime через as
export async function getParagraphs(limit: number = 10) {
  const query = `
    query GetParagraphs($limit: Int) {
      Get {
        Paragraph(limit: $limit) {
          content
          document_id
          tags
          _additional {
            id
            distance
          }
        }
      }
    }
  `;

  const data = await client.request<{
    Get: {
      Paragraph: Array<{
        content: string;
        document_id: string;
        tags: string[];
        _additional: {
          id: string;
          distance: number;
        };
      }>;
    };
  }>(query, { limit });

  return data.Get.Paragraph;
}
```

### Автоматическая валидация на основе схемы Weaviate

Можно автоматически генерировать Zod схемы из GraphQL схемы Weaviate:

```typescript
// src/lib/weaviate-validated.ts
import { z } from 'zod';
import { GraphQLClient } from 'graphql-request';

const client = new GraphQLClient('http://weaviate:8080/v1/graphql');

// Загружаем схему и создаем Zod схемы автоматически
async function createZodSchemaFromWeaviate() {
  const introspectionQuery = `
    query IntrospectionQuery {
      __schema {
        types {
          name
          kind
          fields {
            name
            type {
              name
              kind
              ofType {
                name
                kind
              }
            }
          }
        }
      }
    }
  `;

  const schema = await client.request(introspectionQuery);
  
  // Преобразуем GraphQL типы в Zod схемы
  // (упрощенная версия, можно расширить)
  return {
    Paragraph: z.object({
      content: z.string(),
      document_id: z.string().nullable(),
      tags: z.array(z.string()),
      // ... остальные поля на основе схемы
    }),
  };
}

// Использование
const schemas = await createZodSchemaFromWeaviate();
const validated = schemas.Paragraph.parse(data);
```

### Простая валидация для SolidJS

Для SolidJS достаточно простой валидации без сложных типов:

```typescript
// src/lib/weaviate-simple.ts
import { GraphQLClient } from 'graphql-request';

const client = new GraphQLClient('http://weaviate:8080/v1/graphql');

// Простая проверка структуры без Zod
function validateParagraph(data: unknown): data is {
  content: string;
  document_id: string | null;
  tags: string[];
} {
  return (
    typeof data === 'object' &&
    data !== null &&
    'content' in data &&
    typeof (data as any).content === 'string' &&
    'tags' in data &&
    Array.isArray((data as any).tags)
  );
}

export async function getParagraphs(limit: number = 10) {
  const query = `
    query GetParagraphs($limit: Int) {
      Get {
        Paragraph(limit: $limit) {
          content
          document_id
          tags
        }
      }
    }
  `;

  const data = await client.request(query, { limit });
  const paragraphs = (data as any).Get?.Paragraph || [];
  
  // Валидация
  return paragraphs.filter(validateParagraph);
}
```

### Динамическая загрузка схемы и генерация типов в runtime

```typescript
// src/lib/weaviate-dynamic.ts
import { GraphQLClient, gql } from 'graphql-request';

const client = new GraphQLClient('http://weaviate:8080/v1/graphql');

// Загружаем схему в runtime
async function getSchema() {
  const introspectionQuery = gql`
    query IntrospectionQuery {
      __schema {
        types {
          name
          kind
          fields {
            name
            type {
              name
              kind
              ofType {
                name
                kind
              }
            }
          }
        }
      }
    }
  `;

  return await client.request(introspectionQuery);
}

// Создаем типы на основе схемы
async function createTypedQuery<T>(
  query: string,
  variables?: Record<string, any>
): Promise<T> {
  // Валидация на основе загруженной схемы
  const schema = await getSchema();
  
  // Здесь можно добавить runtime валидацию
  // на основе схемы
  
  return await client.request<T>(query, variables);
}

// Использование
export async function getParagraphs(limit: number = 10) {
  const query = gql`
    query GetParagraphs($limit: Int) {
      Get {
        Paragraph(limit: $limit) {
          content
          document_id
          tags
        }
      }
    }
  `;

  return createTypedQuery<{
    Get: {
      Paragraph: Array<{
        content: string;
        document_id: string;
        tags: string[];
      }>;
    };
  }>(query, { limit });
}
```

### Использование TypeScript template literal types (частичная типизация)

```typescript
// src/lib/weaviate-typed.ts
type WeaviateQuery<T extends string> = T;

// Типы для известных полей
type ParagraphFields = {
  content: string;
  document_id: string;
  tags: string[];
};

// Функция с частичной типизацией
export async function queryWeaviate<
  TClass extends string,
  TFields extends keyof ParagraphFields
>(
  class: TClass,
  fields: TFields[]
): Promise<Array<Pick<ParagraphFields, TFields>>> {
  const query = `
    query {
      Get {
        ${class}(limit: 10) {
          ${fields.join('\n')}
        }
      }
    }
  `;

  const client = new GraphQLClient('http://weaviate:8080/v1/graphql');
  const data = await client.request<{
    Get: Record<TClass, Array<Pick<ParagraphFields, TFields>>>;
  }>(query);

  return data.Get[class];
}

// Использование с частичной типизацией
const paragraphs = await queryWeaviate('Paragraph', ['content', 'tags']);
// paragraphs: Array<{ content: string; tags: string[] }>
```

### Использование библиотеки для runtime валидации GraphQL

```typescript
// src/lib/weaviate-validated.ts
import { GraphQLClient } from 'graphql-request';
import { validate } from 'graphql/validation';
import { buildClientSchema, getIntrospectionQuery } from 'graphql';

let schema: any = null;

async function getWeaviateSchema() {
  if (schema) return schema;

  const client = new GraphQLClient('http://weaviate:8080/v1/graphql');
  const introspectionResult = await client.request(getIntrospectionQuery());
  schema = buildClientSchema(introspectionResult);
  
  return schema;
}

export async function validatedQuery<T>(
  query: string,
  variables?: Record<string, any>
): Promise<T> {
  const schema = await getWeaviateSchema();
  
  // Валидация запроса
  const errors = validate(schema, query);
  if (errors.length > 0) {
    throw new Error(`GraphQL validation errors: ${errors.join(', ')}`);
  }

  const client = new GraphQLClient('http://weaviate:8080/v1/graphql');
  return client.request<T>(query, variables);
}
```

## Сравнение подходов

| Критерий | Code Generation | Runtime типизация | Гибридный |
|----------|----------------|-------------------|-----------|
| **Типизация** | ✅ Полная (compile-time) | ⚠️ Частичная (runtime) | ✅ Полная для стабильных частей |
| **Автодополнение** | ✅ Да | ❌ Нет | ✅ Да (для стабильных) |
| **Обнаружение ошибок** | ✅ Compile-time | ⚠️ Runtime | ✅ Compile-time + Runtime |
| **Актуальность** | ⚠️ Нужна перегенерация | ✅ Всегда актуальна | ✅ Всегда актуальна |
| **Производительность** | ✅ Нет overhead | ⚠️ Overhead валидации | ⚠️ Небольшой overhead |
| **Сложность** | 🟡 Средняя | 🟢 Низкая | 🔴 Высокая |

## Рекомендации

### Используйте Code Generation если:
- ✅ Нужна полная типизация
- ✅ Важна производительность
- ✅ Схема меняется редко
- ✅ Нужно автодополнение в IDE

### Используйте Runtime типизацию если:
- ✅ Схема меняется часто
- ✅ Нужна гибкость
- ✅ Можно пожертвовать автодополнением
- ✅ Нужна валидация в runtime

### Используйте Гибридный подход если:
- ✅ Есть стабильные и динамические части схемы
- ✅ Нужна максимальная гибкость
- ✅ Готовы поддерживать сложность

## Troubleshooting

### Схема не генерируется

```bash
# Проверьте, что Weaviate запущен
curl http://weaviate:8080/v1/meta

# Проверьте, что есть классы
curl http://weaviate:8080/v1/schema
```

### Типы не обновляются (Code Generation)

```bash
# Удалите старые типы и сгенерируйте заново
rm -rf src/generated/
npm run codegen
```

### Ошибки типов (Runtime)

```typescript
// Добавьте обработку ошибок
try {
  const data = await getParagraphs();
} catch (error) {
  if (error instanceof z.ZodError) {
    console.error('Validation errors:', error.errors);
  }
}
```

### Проверка актуальности схемы

```bash
# Проверьте актуальность схемы
curl -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { __schema { types { name } } }"}'
```

## Связанные документы

- [WEAVIATE_SOLIDJS.md](WEAVIATE_SOLIDJS.md) - Использование Weaviate в SolidJS (runtime валидация)
- [WEAVIATE_SCHEMA_WORKFLOW.md](WEAVIATE_SCHEMA_WORKFLOW.md) - Workflow работы со схемой
- [WEAVIATE_DOKKU_SETUP.md](WEAVIATE_DOKKU_SETUP.md) - Развертывание Weaviate

## Ссылки

- [Weaviate GraphQL API](https://weaviate.io/developers/weaviate/api/graphql)
- [GraphQL Code Generator](https://the-guild.dev/graphql/codegen)
- [Weaviate Introspection](https://weaviate.io/developers/weaviate/api/graphql#introspection)
