# Schema-First подход для данных в Weaviate

## Обзор

**Важно:** Это про схему **данных** (классов и свойств), а не про GraphQL schema-first для фронтенда.

Для GraphQL schema-first и генерации типов см. [WEAVIATE_GRAPHQL_TYPES.md](WEAVIATE_GRAPHQL_TYPES.md).

Weaviate поддерживает **schema-first** подход для данных, что означает явное определение схемы данных перед добавлением объектов. Это рекомендуемый подход для production окружений, но для разработки можно использовать auto-schema (`AUTOSCHEMA_ENABLED=true`).

## Преимущества Schema-First

1. **Предсказуемость** - схема известна заранее, нет неожиданных свойств
2. **Надежность** - предотвращает создание некорректных свойств из-за опечаток
3. **Контроль типов** - явное определение типов данных для каждого свойства
4. **Валидация** - Weaviate проверяет данные на соответствие схеме
5. **Документация** - схема служит документацией структуры данных

## Настройка Schema-First режима

### Auto-Schema vs Schema-First

**Auto-Schema** (`AUTOSCHEMA_ENABLED=true`):
- ✅ Удобно для разработки и прототипирования
- ✅ Автоматически создает классы и свойства
- ⚠️ Может создавать неожиданные свойства из-за опечаток

**Schema-First** (`AUTOSCHEMA_ENABLED=false`):
- ✅ Рекомендуется для production
- ✅ Предсказуемость и контроль
- ⚠️ Нужно определять схему заранее

### Отключение Auto-Schema (для production)

В настройках Weaviate установите:

```bash
dokku config:set weaviate AUTOSCHEMA_ENABLED=false
```

Или в docker-compose:

```yaml
environment:
  AUTOSCHEMA_ENABLED: 'false'
```

**Для разработки** можно оставить `AUTOSCHEMA_ENABLED=true` для удобства.

### Проверка режима

```python
import weaviate
from weaviate.connect.base import ConnectionParams

client = weaviate.WeaviateClient(
    connection_params=ConnectionParams.from_params(
        http_host="weaviate",
        http_port=8080,
        http_secure=False,
        grpc_host="weaviate",
        grpc_port=50051,
        grpc_secure=False,
    ),
)
client.connect()

# Проверяем настройки
meta = client.get_meta()
print(f"Auto-schema enabled: {meta.get('modules', {}).get('autoSchema', {}).get('enabled', 'unknown')}")

client.close()
```

## Создание схемы

### Базовый пример (v4 API)

```python
import weaviate
from weaviate.connect.base import ConnectionParams
from weaviate.classes.config import Configure, Property, DataType

client = weaviate.WeaviateClient(
    connection_params=ConnectionParams.from_params(
        http_host="weaviate",
        http_port=8080,
        http_secure=False,
        grpc_host="weaviate",
        grpc_port=50051,
        grpc_secure=False,
    ),
)
client.connect()

# Проверяем, существует ли класс
if not client.collections.exists("Paragraph"):
    # Создаем класс (v4 API)
    client.collections.create(
        name="Paragraph",
        description="Параграф документа для векторного поиска",
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="content", data_type=DataType.TEXT),
            Property(name="document_id", data_type=DataType.TEXT),
            Property(name="node_id", data_type=DataType.TEXT),
            Property(name="document_type", data_type=DataType.TEXT),
            Property(name="session_id", data_type=DataType.TEXT),
            Property(name="organism_ids", data_type=DataType.TEXT_ARRAY),
            Property(name="ecosystem_id", data_type=DataType.TEXT),
            Property(name="location", data_type=DataType.TEXT),
            Property(name="tags", data_type=DataType.TEXT_ARRAY),
            Property(name="timestamp", data_type=DataType.DATE),
            Property(name="author", data_type=DataType.TEXT),
            Property(name="author_id", data_type=DataType.INT),
            Property(name="metadata", data_type=DataType.TEXT),  # JSON строка
        ],
    )
    print("✅ Схема класса Paragraph создана")
else:
    print("ℹ️  Схема уже существует")

client.close()
```

### С индексацией для быстрого поиска

```python
schema = {
    "class": "Paragraph",
    "vectorizer": "none",
    "properties": [
        {
            "name": "document_id",
            "dataType": ["string"],
            "indexInverted": True,  # Индекс для быстрого поиска
            "tokenization": "word"  # Токенизация для поиска
        },
        {
            "name": "ecosystem_id",
            "dataType": ["string"],
            "indexInverted": True  # Индекс для фильтрации
        },
        {
            "name": "tags",
            "dataType": ["string[]"],
            "indexInverted": True  # Индекс для фильтрации по тегам
        },
        # ... остальные свойства
    ]
}
```

## Проверка существующей схемы (v4 API)

```python
import weaviate
from weaviate.connect.base import ConnectionParams

client = weaviate.WeaviateClient(
    connection_params=ConnectionParams.from_params(...),
)
client.connect()

# Получить все классы
collections = client.collections.list_all()
print("Существующие классы:", [c.name for c in collections])

# Получить схему конкретного класса
if client.collections.exists("Paragraph"):
    collection = client.collections.get("Paragraph")
    config = collection.config.get()
    print("Схема Paragraph:", config)
else:
    print("Класс Paragraph не найден")

client.close()
```

## Обновление схемы

**Важно:** Weaviate не поддерживает изменение существующих свойств. Можно только:
- Добавлять новые свойства
- Удалять класс и создавать заново (с потерей данных!)

### Добавление нового свойства (v4 API)

```python
from weaviate.classes.config import Property, DataType

# Добавляем новое свойство к существующему классу
collection = client.collections.get("Paragraph")
collection.config.add_property(
    Property(
        name="updated_at",
        data_type=DataType.DATE,
    )
)
print("✅ Свойство добавлено")
```

### Удаление класса (осторожно!) (v4 API)

```python
# Удаление класса удаляет ВСЕ данные!
# Используйте только для разработки/тестирования

if client.collections.exists("Paragraph"):
    client.collections.delete("Paragraph")
    print("⚠️  Класс удален (все данные потеряны!)")
else:
    print("Класс не существует")
```

## Миграция схемы

Для обновления схемы в production:

1. **Создайте новый класс** с обновленной схемой
2. **Мигрируйте данные** из старого класса в новый
3. **Обновите код** для использования нового класса
4. **Удалите старый класс** после проверки

```python
# Пример миграции
old_class = "Paragraph_v1"
new_class = "Paragraph_v2"

# 1. Создаем новую схему
new_schema = {
    "class": new_class,
    # ... обновленная схема
}
client.schema.create_class(new_schema)

# 2. Мигрируем данные (батч-копирование)
# ... код миграции ...

# 3. После проверки удаляем старый класс
# client.schema.delete_class(old_class)
```

## Использование в коде проекта

### Файл: `api/storage/weaviate_schema.py` (v4 API)

```python
"""Схема Weaviate для класса Paragraph (v4 API)"""

import weaviate
from api.settings import WEAVIATE_CLASS_NAME
from api.logger import root_logger

log = root_logger.debug


def create_schema_if_not_exists(client: weaviate.WeaviateClient) -> None:
    """Создает схему Paragraph, если она еще не существует (v4 API)"""
    try:
        # Проверяем, существует ли класс
        if client.collections.exists(WEAVIATE_CLASS_NAME):
            log(f"ℹ️  Схема {WEAVIATE_CLASS_NAME} уже существует")
            return
        
        # Создаем класс (v4 API)
        from weaviate.classes.config import Configure, Property, DataType
        
        client.collections.create(
            name=WEAVIATE_CLASS_NAME,
            description="Параграф документа для векторного поиска",
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="content", data_type=DataType.TEXT),
                Property(name="document_id", data_type=DataType.TEXT),
                # ... остальные свойства
            ],
        )
        log(f"✅ Схема {WEAVIATE_CLASS_NAME} создана")
        
    except Exception as e:
        log(f"❌ Ошибка при создании схемы: {e}")
        raise
```

### Использование в WeaviateStorage

```python
# api/storage/weaviate_storage.py
from api.storage.weaviate_schema import create_schema_if_not_exists

class WeaviateStorage:
    def __init__(self):
        # ... инициализация клиента ...
        
        # Создаем схему при инициализации
        create_schema_if_not_exists(self.client)
```

## Best Practices

1. **Всегда используйте schema-first** в production
2. **Определяйте схему в коде** (не через API вручную)
3. **Версионируйте схему** при значительных изменениях
4. **Документируйте свойства** через `description`
5. **Используйте индексы** для часто используемых полей фильтрации
6. **Тестируйте миграции** на тестовых данных перед production

## Связанные документы

- [WEAVIATE_GRAPHQL_TYPES.md](WEAVIATE_GRAPHQL_TYPES.md) - GraphQL Schema-First для генерации типов фронтенда
- [WEAVIATE_DOKKU_SETUP.md](WEAVIATE_DOKKU_SETUP.md) - Развертывание Weaviate

## Ссылки

- [Weaviate Schema Documentation](https://weaviate.io/developers/weaviate/manage-data/schema)
- [Weaviate Auto Schema](https://deepwiki.com/weaviate/weaviate/4.3-auto-schema)
- [Weaviate Best Practices](https://weaviate.io/developers/weaviate/best-practices)
