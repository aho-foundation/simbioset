# Интеграция продвинутых возможностей Weaviate на фронтенде

## Обзор

Все продвинутые возможности Weaviate теперь доступны на фронтенде через обновленный компонент `ParagraphSearch` и клиент `WeaviateClient`.

## Компонент ParagraphSearch

### Базовое использование

```tsx
import ParagraphSearch from '~/components/ParagraphSearch'

// Простой поиск
<ParagraphSearch limit={10} />

// С расширенными опциями
<ParagraphSearch 
  documentId="session_123"
  limit={20}
  showAdvanced={true}
  useHybrid={true}
  hybridAlpha={0.5}
  useReranking={false}
/>
```

### Пропсы

- `documentId?: string` - ID документа для фильтрации
- `limit?: number` - Количество результатов (по умолчанию: 10)
- `showAdvanced?: boolean` - Показать расширенные опции по умолчанию
- `useHybrid?: boolean` - Использовать Hybrid Search (по умолчанию: true)
- `hybridAlpha?: number` - Баланс BM25/векторный (0-1, по умолчанию: 0.5)
- `useReranking?: boolean` - Использовать reranking (по умолчанию: false)

### Расширенные опции в UI

Компонент предоставляет UI для настройки:

1. **Фильтр по тегам (OR логика)**
   - Добавление тегов через input
   - Отображение выбранных тегов
   - Удаление тегов

2. **Исключение тегов (NOT логика)**
   - Добавление тегов для исключения
   - Визуальное отличие (красный цвет)

3. **Hybrid Search Alpha**
   - Слайдер для настройки баланса (0-1)
   - Подсказка с объяснением значений

4. **Cross-Encoder Reranking**
   - Чекбокс для включения/выключения
   - Подсказка о влиянии на производительность

## WeaviateClient API

### Метод searchParagraphs

```typescript
const client = new WeaviateClient()

const results = await client.searchParagraphs({
  query: "дуб и микориза",
  document_id: "session_123",
  limit: 10,
  tags: ["ecosystem_risk", "ecosystem_vulnerability"],  // OR фильтр
  exclude_tags: ["deprecated"],  // NOT фильтр
  location: "Москва",
  ecosystem_id: "eco_1",
  use_hybrid: true,
  hybrid_alpha: 0.5,
  use_reranking: false,
  timestamp_from: 1704067200,  // Unix timestamp
  timestamp_to: 1704153600,
})
```

### Параметры

- `query: string` - Поисковый запрос (обязательно)
- `document_id?: string` - Фильтр по ID документа
- `limit?: number` - Количество результатов (1-50)
- `tags?: string[]` - Фильтр по тегам (OR логика - любой из тегов)
- `exclude_tags?: string[]` - Исключить теги (NOT логика)
- `location?: string` - Фильтр по локации
- `ecosystem_id?: string` - Фильтр по ID экосистемы
- `use_hybrid?: boolean` - Использовать Hybrid Search
- `hybrid_alpha?: number` - Баланс BM25/векторный (0-1)
- `use_reranking?: boolean` - Использовать Cross-Encoder reranking
- `timestamp_from?: number` - Минимальный timestamp (Unix)
- `timestamp_to?: number` - Максимальный timestamp (Unix)

## SolidJS Hook: createParagraphSearch

### Использование

```typescript
import { createParagraphSearch } from '~/lib/weaviate'

const [query, setQuery] = createSignal('')
const [tags, setTags] = createSignal<string[]>([])

// Реактивный поиск
const [searchData] = createParagraphSearch(
  query,
  () => ({
    document_id: props.documentId,
    limit: 10,
    tags: tags().length > 0 ? tags() : undefined,
    use_hybrid: true,
    hybrid_alpha: 0.5,
  })
)

// Использование результатов
<Show when={searchData.loading}>
  <div>Поиск...</div>
</Show>

<Show when={searchData.error}>
  <div>Ошибка: {searchData.error.message}</div>
</Show>

<Show when={searchData()}>
  <For each={searchData()!.results}>
    {(result) => (
      <div>
        {result.paragraph.content}
        <span>Score: {result.score}</span>
      </div>
    )}
  </For>
</Show>
```

### Реактивность

Hook автоматически обновляется при изменении:
- Запроса (`query()`)
- Параметров поиска (если передана функция)

## Примеры использования

### Пример 1: Поиск с фильтрацией по тегам

```tsx
const ParagraphSearchWithTags = () => {
  const [query, setQuery] = createSignal('')
  const [selectedTags, setSelectedTags] = createSignal<string[]>(['ecosystem_risk'])

  const [searchData] = createParagraphSearch(query, {
    tags: selectedTags(),
    use_hybrid: true,
  })

  return (
    <div>
      <input 
        value={query()} 
        onInput={(e) => setQuery(e.currentTarget.value)} 
      />
      <button onClick={() => setQuery(query())}>Искать</button>
      
      <Show when={searchData()}>
        <For each={searchData()!.results}>
          {(result) => <div>{result.paragraph.content}</div>}
        </For>
      </Show>
    </div>
  )
}
```

### Пример 2: Поиск с исключением тегов

```tsx
const [searchData] = createParagraphSearch(query, {
  exclude_tags: ['deprecated', 'outdated'],
  use_hybrid: true,
  hybrid_alpha: 0.3,  // Больше BM25 для точных терминов
})
```

### Пример 3: Поиск с reranking для максимальной точности

```tsx
const [searchData] = createParagraphSearch(query, {
  use_hybrid: true,
  hybrid_alpha: 0.5,
  use_reranking: true,  // Включить reranking для лучшей точности
})
```

### Пример 4: Поиск по временному диапазону

```tsx
import { createSignal } from 'solid-js'

const [dateFrom, setDateFrom] = createSignal<Date | null>(null)
const [dateTo, setDateTo] = createSignal<Date | null>(null)

const timestampFrom = () => dateFrom() ? Math.floor(dateFrom()!.getTime() / 1000) : undefined
const timestampTo = () => dateTo() ? Math.floor(dateTo()!.getTime() / 1000) : undefined

const [searchData] = createParagraphSearch(query, {
  timestamp_from: timestampFrom(),
  timestamp_to: timestampTo(),
})
```

## API Endpoint

### GET /api/search

Поддерживает все параметры через query string:

```
GET /api/search?q=дуб&tags=ecosystem_risk,ecosystem_vulnerability&exclude_tags=deprecated&use_hybrid=true&hybrid_alpha=0.5&use_reranking=false&limit=10
```

**Параметры:**
- `q` - Поисковый запрос (обязательно)
- `document_id` - Фильтр по ID документа
- `limit` - Количество результатов (1-50)
- `tags` - Теги через запятую (OR логика)
- `exclude_tags` - Теги для исключения через запятую (NOT логика)
- `location` - Фильтр по локации
- `ecosystem_id` - Фильтр по ID экосистемы
- `use_hybrid` - true/false (использовать Hybrid Search)
- `hybrid_alpha` - 0.0-1.0 (баланс BM25/векторный)
- `use_reranking` - true/false (использовать reranking)
- `timestamp_from` - Минимальный timestamp (Unix)
- `timestamp_to` - Максимальный timestamp (Unix)

## Стилизация

Все стили находятся в `ParagraphSearch.module.css`:

- `.advancedSection` - Секция расширенных опций
- `.advancedOptions` - Контейнер опций
- `.filterGroup` - Группа фильтров
- `.tag` - Стиль тега
- `.excludeTag` - Стиль исключенного тега
- `.rangeInput` - Слайдер для alpha
- `.checkbox` - Чекбокс для reranking

## Обратная совместимость

Все изменения обратно совместимы:

```tsx
// Старый код продолжает работать
<ParagraphSearch limit={10} />

// Новые возможности опциональны
<ParagraphSearch 
  limit={10}
  showAdvanced={true}  // Новое
/>
```

## Производительность

### Рекомендации

1. **Для большинства запросов:**
   - Hybrid Search включен (alpha=0.5)
   - Reranking выключен (для скорости)

2. **Для критических запросов:**
   - Hybrid Search включен
   - Reranking включен (для максимальной точности)

3. **Для точных терминов:**
   - Hybrid Search с alpha=0.3 (больше BM25)

4. **Для концептуальных запросов:**
   - Hybrid Search с alpha=0.7 (больше векторного поиска)

## Troubleshooting

### Поиск не обновляется при изменении параметров

**Проблема:** Параметры не реактивны

**Решение:** Используйте функцию для параметров:

```tsx
// ❌ Не работает
const [searchData] = createParagraphSearch(query, {
  tags: tags(),  // Не реактивно
})

// ✅ Работает
const [searchData] = createParagraphSearch(query, () => ({
  tags: tags(),  // Реактивно
}))
```

### Hybrid Search не работает

**Проблема:** Ошибка при использовании Hybrid Search

**Решение:**
1. Проверить версию Weaviate (нужна 1.24+)
2. Проверить логи на наличие ошибок
3. Система автоматически fallback на векторный поиск

### Reranking медленный

**Проблема:** Reranking добавляет задержку

**Решение:**
1. Использовать reranking только для критических запросов
2. Уменьшить количество кандидатов (через настройки бэкенда)
