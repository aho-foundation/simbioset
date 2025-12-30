# Анализ мест сохранения данных в приложении

## Обзор

Документ анализирует все места, где происходит сохранение данных в приложении:
- Загрузка файлов
- Сохранение в диалоге чата
- Другие места сохранения

## 1. Загрузка файлов

### 1.1. ConceptDropZone.tsx
**Путь**: `src/components/chat/ConceptDropZone.tsx`

**Что делает**:
- Drag&drop загрузка файлов
- Читает содержимое файла через `file.text()`
- Создает узлы через `kb.createNode()` (KnowledgeBaseContext)

**Как сохраняется**:
```typescript
// Создает родительский узел с именем файла
const concept = await kb.createNode({
  parentId: null,
  content: `File: ${file.name}`,
  role: 'user'
})

// Создает дочерний узел с содержимым файла (первые 500 символов)
await kb.createNode({
  parentId: concept.id,
  content: `${text.substring(0, 500)}...`,
  role: 'user'
})
```

**Проблемы**:
- ❌ Ограничение в 500 символов - теряется большая часть файла
- ❌ Нет парсинга файла на параграфы
- ❌ Нет сохранения в таблицу `documents` и `paragraphs`
- ❌ Нет создания векторов для FAISS поиска

**Рекомендации**:
- ✅ Парсить файл на параграфы
- ✅ Сохранять в `documents` таблицу
- ✅ Создавать `paragraphs` для каждого параграфа
- ✅ Генерировать векторы для FAISS поиска

### 1.2. DragDropUpload.tsx
**Путь**: `src/components/chat/DragDropUpload.tsx`

**Что делает**:
- Компонент для drag&drop загрузки файлов
- Вызывает callback `onFilesDrop(files: File[])`

**Статус**: 
- ⚠️ Компонент существует, но не используется напрямую
- Используется только через ConceptDropZone

## 2. Сохранение в диалоге чата

### 2.1. API: send_chat_message
**Путь**: `api/chat/routes.py` → `send_chat_message()`

**Что сохраняется**:
1. **Сессия пользователя** (Redis через `session_manager`):
   - Создается через `session_manager.create_session()` или `get_or_create_telegram_session()`
   - Хранится в Redis с TTL 30 дней
   - Обновляется через `session_manager.increment_message_count()`

2. **Корневой узел сессии** (JSON через `service.add_concept()`):
   - Создается если не существует: `service.add_concept(parent_id=None, content="Auto-created chat session", role="system", node_type="message")`
   - Сохраняется в `data/knowledge_base.json` через `JSONNodeRepository`

3. **Сообщение пользователя** (JSON через `service.add_concept()`):
   - `service.add_concept(parent_id=actual_session_id, content=message_data.message, role="user", node_type="message")`
   - Сохраняется в `data/knowledge_base.json`

4. **Ответ AI** (JSON через `service.add_concept()`):
   - `service.add_concept(parent_id=user_message_node.id, content=response_content, role="assistant", node_type="message")`
   - Сохраняется в `data/knowledge_base.json`

5. **Наблюдения пользователя** (JSON через `user_metrics_service.save_user_observation()`):
   - Сохраняется если сообщение содержит ключевые слова (локация, наблюдение, экосистема и т.д.)
   - Создает узел типа `user_observation` через `kb_service.add_concept()`

**Проблемы**:
- ❌ Все сообщения сохраняются только в JSON файл (`knowledge_base.json`)
- ❌ Нет парсинга сообщений на параграфы
- ❌ Нет сохранения в таблицу `paragraphs` для FAISS поиска
- ❌ Нет создания векторов для диалогов

**Рекомендации**:
- ✅ Парсить сообщения на параграфы
- ✅ Сохранять параграфы в таблицу `paragraphs` с `document_type='chat'`
- ✅ Генерировать векторы для каждого параграфа
- ✅ Использовать новую схему SQLite вместо JSON

### 2.2. Repository: JSONNodeRepository
**Путь**: `api/kb/repository.py` → `JSONNodeRepository`

**Что делает**:
- Сохраняет все узлы знаний в JSON файл `data/knowledge_base.json`
- Использует file locking (`fcntl`) для thread safety
- Имеет простой in-memory кэш (TTL 5 секунд)

**Методы сохранения**:
- `create(node: dict)` - создание узла
- `update(node_id: str, updates: dict)` - обновление узла
- `delete(node_id: str, cascade: bool)` - удаление узла

**Проблемы**:
- ❌ JSON файл не масштабируется
- ❌ Нет поддержки транзакций
- ❌ Нет индексов для быстрого поиска
- ❌ Нет связи с параграфами и векторами

**Рекомендации**:
- ✅ Мигрировать на SQLite используя схему `schema.sql`
- ✅ Использовать таблицу `knowledge_nodes` вместо JSON
- ✅ Связать с `paragraphs` и `vectors` для FAISS поиска

### 2.3. Service: KBService
**Путь**: `api/kb/service.py` → `KBService`

**Что делает**:
- Бизнес-логика для работы с узлами знаний
- Использует `JSONNodeRepository` для сохранения
- Методы: `add_concept()`, `update_node()`, `delete_node()`, `get_node()`

**Используется в**:
- `api/chat/routes.py` - сохранение сообщений чата
- `api/kb/routes.py` - API endpoints для работы с узлами
- `api/kb/user_metrics.py` - сохранение наблюдений пользователей

### 2.4. Bot Handler: MessageProcessor
**Путь**: `api/bot/handler.py` → `MessageProcessor._store_message()`

**Что делает**:
- Сохраняет сообщения Telegram бота
- Вызывает `self.storage.save_message(message_data)`
- Индексирует сообщения для векторного поиска через `self.vector_search.add_messages()`

**Проблемы**:
- ❌ `self.storage` передается извне, но в `api/bot/main.py` установлен как `None`
- ❌ `storage.save_message()` не реализован (storage = None)
- ❌ Сообщения индексируются в FAISS, но не сохраняются в базу знаний
- ❌ Нет связи между Telegram сообщениями и узлами знаний

**Рекомендации**:
- ✅ Реализовать storage для Telegram сообщений
- ✅ Сохранять сообщения в таблицу `paragraphs` с `document_type='chat'`
- ✅ Связывать с узлами знаний через `node_id`
- ✅ Интегрировать с новой схемой SQLite

## 3. Другие места сохранения

### 3.1. Projects Repository
**Путь**: `api/projects/repository.py` → `ProjectsRepository`

**Что сохраняет**:
- Проекты и идеи в JSON файл `data/projects.json`
- Использует file locking для thread safety

**Статус**: 
- ✅ Работает, но можно мигрировать на SQLite для консистентности

### 3.2. User Metrics Service
**Путь**: `api/kb/user_metrics.py` → `UserMetricsService.save_user_observation()`

**Что сохраняет**:
- Наблюдения пользователей через `kb_service.add_concept()`
- Создает узлы типа `user_observation`
- Сохраняется в `data/knowledge_base.json`

**Статус**:
- ✅ Работает, но использует JSON репозиторий

## 4. Текущая архитектура сохранения

### Схема данных:

```
┌─────────────────────────────────────────────────────────┐
│                    Сохранение данных                     │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Redis      │    │  JSON Files  │    │   SQLite     │
│              │    │              │    │  (schema.sql) │
│ - Sessions   │    │ - knowledge_ │    │  (НЕ ИСПОЛЬЗ) │
│ - User data  │    │   base.json  │    │              │
│              │    │ - projects.   │    │              │
│              │    │   json       │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Потоки данных:

1. **Чат сообщения**:
   ```
   User → API → KBService → JSONNodeRepository → knowledge_base.json
   ```

2. **Загрузка файлов**:
   ```
   File → Frontend → API → KBService → JSONNodeRepository → knowledge_base.json
   ```

3. **Telegram бот**:
   ```
   Telegram → Bot Handler → storage.save_message() → ???
   ```

## 5. Проблемы и рекомендации

### Критические проблемы:

1. **Нет парсинга на параграфы**:
   - ❌ Файлы не парсятся на параграфы
   - ❌ Сообщения чата не парсятся на параграфы
   - ❌ Нет связи с FAISS для векторного поиска

2. **Дублирование хранилищ**:
   - ❌ JSON файлы для узлов знаний
   - ❌ SQLite схема создана, но не используется
   - ❌ Нет единой точки сохранения

3. **Нет векторизации**:
   - ❌ Сообщения не векторизуются для поиска
   - ❌ Файлы не векторизуются
   - ❌ FAISS используется только для индексации сообщений Telegram

### Рекомендации:

1. **Миграция на SQLite**:
   - ✅ Использовать схему `schema.sql` для всех данных
   - ✅ Мигрировать `knowledge_base.json` → `knowledge_nodes`
   - ✅ Создать репозиторий на основе `BaseStorage`

2. **Парсинг на параграфы**:
   - ✅ Парсить файлы на параграфы при загрузке
   - ✅ Парсить сообщения чата на параграфы
   - ✅ Сохранять в таблицу `paragraphs`

3. **Векторизация**:
   - ✅ Генерировать векторы для всех параграфов
   - ✅ Сохранять в таблицу `vectors`
   - ✅ Интегрировать с FAISS для поиска

4. **Единая архитектура**:
   ```
   User/File → API → Service → SQLite Repository
                                      │
                                      ├─→ knowledge_nodes
                                      ├─→ paragraphs
                                      └─→ vectors → FAISS
   ```

## 6. План миграции

### Этап 1: Создание SQLite репозитория
- [ ] Создать `SQLiteNodeRepository` на основе `BaseStorage`
- [ ] Реализовать методы: `create()`, `get()`, `update()`, `delete()`
- [ ] Мигрировать данные из JSON в SQLite

### Этап 2: Парсинг на параграфы
- [ ] Добавить парсинг файлов на параграфы
- [ ] Добавить парсинг сообщений чата на параграфы
- [ ] Сохранять параграфы в таблицу `paragraphs`

### Этап 3: Векторизация
- [ ] Генерировать векторы для параграфов
- [ ] Сохранять в таблицу `vectors`
- [ ] Интегрировать с FAISS

### Этап 4: Интеграция
- [ ] Обновить `KBService` для использования SQLite
- [ ] Обновить API endpoints
- [ ] Удалить JSON репозиторий


## Обзор

Полная миграция векторного хранилища с FAISS на Weaviate для получения:
- ✅ Персистентности индексов
- ✅ Фильтрации по метаданным в запросе
- ✅ **Автоматической классификации** (единственная векторная БД с этой фишкой!)
- ✅ **NER модулей** (автоматическое извлечение сущностей)
- ✅ Масштабируемости
- ✅ GraphQL API

**Подробный план:** `.cursor/plans/миграция_на_weaviate_3bb53f3d.plan.md`

**Сравнение с конкурентами:** `docs/vector_db_comparison.md`

## Почему Weaviate?

**Ключевое преимущество:** Weaviate - единственная open-source векторная БД с встроенной автоматической классификацией и NER модулями.

**Сравнение:**
- ❌ Qdrant - нет встроенной классификации, нет NER
- ❌ Milvus - нет встроенной классификации, нет NER  
- ❌ Chroma - нет встроенной классификации, нет NER
- ❌ Pinecone - нет встроенной классификации, нет NER (и не open-source)
