# Использование Weaviate GraphQL в SolidJS

## Обзор

SolidJS не требует заранее сгенерированных типов - код более компактный. Но нужна runtime валидация для проверки типов данных из Weaviate.

## Подход для SolidJS

### Почему не нужны заранее сгенерированные типы?

- ✅ Код более компактный без типов
- ✅ Меньше файлов в проекте
- ✅ Нет необходимости перегенерировать при изменении схемы
- ⚠️ Но нужна runtime валидация для безопасности

### Рекомендуемый подход: Runtime валидация с Zod

## Установка зависимостей

```bash
npm install graphql-request zod
npm install -D @types/node
```

## Базовый пример

### 1. Определяем схемы валидации

```typescript
// src/lib/weaviate/schemas.ts
import { z } from 'zod';

// Схема для Paragraph из Weaviate
export const ParagraphSchema = z.object({
  content: z.string(),
  document_id: z.string().nullable(),
  node_id: z.string().nullable(),
  document_type: z.string(),
  session_id: z.string().nullable(),
  organism_ids: z.array(z.string()).optional(),
  ecosystem_id: z.string().nullable(),
  location: z.string().nullable(),
  tags: z.array(z.string()),
  timestamp: z.string().nullable(),
  author: z.string().nullable(),
  author_id: z.number().nullable(),
  metadata: z.record(z.unknown()).nullable(),
  _additional: z.object({
    id: z.string(),
    distance: z.number().optional(),
    certainty: z.number().optional(),
  }).optional(),
});

export type Paragraph = z.infer<typeof ParagraphSchema>;

// Схема для ответа Get
export const GetParagraphsResponseSchema = z.object({
  Get: z.object({
    Paragraph: z.array(ParagraphSchema),
  }),
});
```

### 2. Создаем клиент Weaviate

```typescript
// src/lib/weaviate/client.ts
import { GraphQLClient } from 'graphql-request';
import { ParagraphSchema, GetParagraphsResponseSchema, type Paragraph } from './schemas';

const WEAVIATE_URL = import.meta.env.VITE_WEAVIATE_URL || 'http://localhost:8080/v1/graphql';

const client = new GraphQLClient(WEAVIATE_URL, {
  headers: {
    // Добавьте API ключ, если используется
    // 'Authorization': `Bearer ${import.meta.env.VITE_WEAVIATE_API_KEY}`,
  },
});

export async function getParagraphs(limit: number = 10): Promise<Paragraph[]> {
  const query = `
    query GetParagraphs($limit: Int) {
      Get {
        Paragraph(limit: $limit) {
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
          metadata
          _additional {
            id
            distance
            certainty
          }
        }
      }
    }
  `;

  try {
    const data = await client.request<{ Get: { Paragraph: unknown[] } }>(query, { limit });
    
    // Runtime валидация - проверяем типы
    const validated = GetParagraphsResponseSchema.parse(data);
    
    return validated.Get.Paragraph;
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error('Validation error:', error.errors);
      throw new Error(`Invalid data from Weaviate: ${error.message}`);
    }
    throw error;
  }
}

export async function searchParagraphs(
  queryText: string,
  limit: number = 10
): Promise<Paragraph[]> {
  const query = `
    query SearchParagraphs($query: Txt2VecOpenAIGetObjectsTextMove, $limit: Int) {
      Get {
        Paragraph(
          nearText: $query
          limit: $limit
        ) {
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
  `;

  const data = await client.request<{ Get: { Paragraph: unknown[] } }>(query, {
    query: {
      concepts: [queryText],
    },
    limit,
  });

  const validated = GetParagraphsResponseSchema.parse(data);
  return validated.Get.Paragraph;
}
```

### 3. Использование в SolidJS компонентах

```typescript
// src/components/ParagraphsList.tsx
import { createResource, For, Show } from 'solid-js';
import { getParagraphs, type Paragraph } from '../lib/weaviate/client';

export function ParagraphsList() {
  const [paragraphs] = createResource(() => getParagraphs(10));

  return (
    <Show when={paragraphs()} fallback={<div>Loading...</div>}>
      <div class="paragraphs-list">
        <For each={paragraphs()}>
          {(para) => (
            <div class="paragraph">
              <p>{para.content}</p>
              <Show when={para.tags.length > 0}>
                <div class="tags">
                  <For each={para.tags}>
                    {(tag) => <span class="tag">{tag}</span>}
                  </For>
                </div>
              </Show>
              <Show when={para.location}>
                <p class="location">📍 {para.location}</p>
              </Show>
            </div>
          )}
        </For>
      </div>
    </Show>
  );
}
```

### 4. Поиск с фильтрацией

```typescript
// src/lib/weaviate/search.ts
import { GraphQLClient } from 'graphql-request';
import { ParagraphSchema, type Paragraph } from './schemas';

const client = new GraphQLClient(WEAVIATE_URL);

export async function searchParagraphsWithFilters(
  queryText: string,
  filters: {
    ecosystem_id?: string;
    organism_ids?: string[];
    tags?: string[];
    location?: string;
  },
  limit: number = 10
): Promise<Paragraph[]> {
  // Строим фильтр для Weaviate
  const where: any = {};
  
  if (filters.ecosystem_id) {
    where.path = ['ecosystem_id'];
    where.operator = 'Equal';
    where.valueString = filters.ecosystem_id;
  }
  
  if (filters.organism_ids && filters.organism_ids.length > 0) {
    where.operator = 'And';
    where.operands = filters.organism_ids.map(id => ({
      path: ['organism_ids'],
      operator: 'ContainsAny',
      valueString: [id],
    }));
  }

  const query = `
    query SearchParagraphs(
      $query: Txt2VecOpenAIGetObjectsTextMove
      $where: ParagraphWhereInput
      $limit: Int
    ) {
      Get {
        Paragraph(
          nearText: $query
          where: $where
          limit: $limit
        ) {
          content
          document_id
          tags
          ecosystem_id
          location
          _additional {
            id
            distance
          }
        }
      }
    }
  `;

  const data = await client.request<{ Get: { Paragraph: unknown[] } }>(query, {
    query: {
      concepts: [queryText],
    },
    where: Object.keys(where).length > 0 ? where : undefined,
    limit,
  });

  const validated = GetParagraphsResponseSchema.parse(data);
  return validated.Get.Paragraph;
}
```

## Автоматическое обновление схем валидации

Можно автоматически обновлять Zod схемы при изменении схемы Weaviate:

```typescript
// scripts/update-schemas.ts
import { GraphQLClient } from 'graphql-request';
import { writeFileSync } from 'fs';

const client = new GraphQLClient('http://weaviate:8080/v1/graphql');

async function updateSchemas() {
  // Получаем схему через introspection
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
  
  // Генерируем Zod схемы на основе GraphQL схемы
  // (упрощенная версия, можно расширить)
  const zodSchemas = generateZodSchemas(schema);
  
  // Сохраняем в файл
  writeFileSync('src/lib/weaviate/schemas.ts', zodSchemas);
}

// Запускаем при изменении схемы
updateSchemas();
```

## Best Practices для SolidJS

1. **Используйте Zod для валидации** - проверяйте данные в runtime
2. **Не генерируйте типы заранее** - код более компактный
3. **Валидируйте на границе** - при получении данных из Weaviate
4. **Обрабатывайте ошибки валидации** - показывайте понятные сообщения
5. **Кешируйте схемы** - не загружайте схему при каждом запросе

## Пример полного компонента

```typescript
// src/components/SearchParagraphs.tsx
import { createSignal, createResource, For, Show } from 'solid-js';
import { searchParagraphsWithFilters, type Paragraph } from '../lib/weaviate/search';

export function SearchParagraphs() {
  const [query, setQuery] = createSignal('');
  const [filters, setFilters] = createSignal({
    ecosystem_id: '',
    tags: [] as string[],
  });

  const [results] = createResource(
    () => ({ query: query(), filters: filters() }),
    async ({ query, filters }) => {
      if (!query()) return [];
      return await searchParagraphsWithFilters(query(), filters, 10);
    }
  );

  return (
    <div class="search-paragraphs">
      <input
        type="text"
        value={query()}
        onInput={(e) => setQuery(e.currentTarget.value)}
        placeholder="Search paragraphs..."
      />
      
      <Show when={results.loading}>
        <div>Searching...</div>
      </Show>
      
      <Show when={results.error}>
        <div class="error">
          Error: {results.error.message}
        </div>
      </Show>
      
      <Show when={results()}>
        <div class="results">
          <For each={results()}>
            {(para) => (
              <div class="result">
                <p>{para.content}</p>
                <Show when={para.tags.length > 0}>
                  <div class="tags">
                    <For each={para.tags}>
                      {(tag) => <span class="tag">{tag}</span>}
                    </For>
                  </div>
                </Show>
              </div>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}
```

## Ссылки

- [WEAVIATE_GRAPHQL_TYPES.md](WEAVIATE_GRAPHQL_TYPES.md) - Общая информация о типах
- [WEAVIATE_SCHEMA_WORKFLOW.md](WEAVIATE_SCHEMA_WORKFLOW.md) - Workflow работы со схемой
- [Zod Documentation](https://zod.dev/)
- [GraphQL Request](https://github.com/jasonkuhrt/graphql-request)
