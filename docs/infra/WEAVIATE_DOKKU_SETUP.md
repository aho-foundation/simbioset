# Развертывание Weaviate в Dokku

## Обзор

Weaviate развертывается как отдельное Dokku приложение с использованием Docker образа. Это позволяет:
- Управлять Weaviate через стандартные Dokku команды
- Использовать Persistent Storage для данных
- Легко масштабировать и обновлять
- Подключать другие приложения через переменные окружения

## Предварительные требования

- Dokku установлен на сервере
- Доступ к серверу (yourserver.com)
- Docker установлен (обычно уже есть с Dokku)

## Быстрое развертывание (минимум команд)

Всего нужно выполнить несколько команд:

```bash
# 1. Создать приложение
dokku apps:create weaviate

# 2. Настроить storage (2 команды)
dokku storage:ensure-directory weaviate
dokku storage:mount weaviate /var/lib/dokku/data/storage/weaviate:/var/lib/weaviate

# 3. Настроить переменные окружения
dokku config:set weaviate \
  AUTOSCHEMA_ENABLED=true \
  QUERY_DEFAULTS_LIMIT=25 \
  PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  CLUSTER_HOSTNAME=node1

# 4. Установить docker-options plugin (если еще не установлен)
dokku plugin:install https://github.com/dokku/dokku-docker-options.git

# 5. Добавить docker-options для портов
dokku docker-options:add weaviate deploy,run "--publish=8080:8080"
dokku docker-options:add weaviate deploy,run "--publish=50051:50051"

# 6. Создать минимальный Dockerfile и запустить
mkdir -p /tmp/weaviate-dokku
cd /tmp/weaviate-dokku
cat > Dockerfile << 'EOF'
FROM cr.weaviate.io/semitechnologies/weaviate:1.35.1
EXPOSE 8080 50051
EOF
git init
git add Dockerfile
git commit -m "Initial commit"
git remote add dokku dokku@yourserver.com:weaviate
git push dokku main

# 7. Проверить работу
curl http://weaviate:8080/v1/meta
```

Готово! Weaviate развернут и работает.

## Детальное описание шагов

### Шаг 1: Создание Dokku приложения для Weaviate

```bash
# Подключитесь к серверу
ssh root@yourserver.com

# Создайте приложение для Weaviate
dokku apps:create weaviate

# Проверьте, что приложение создано
dokku apps:list
```

### Шаг 2: Настройка Persistent Storage

Weaviate требует персистентное хранилище для данных. Всего 2 команды:

```bash
# Создать директорию и смонтировать storage
dokku storage:ensure-directory weaviate
dokku storage:mount weaviate /var/lib/dokku/data/storage/weaviate:/var/lib/weaviate
```

Готово! Persistent Storage настроен.

### Шаг 3: Настройка переменных окружения

```bash
# Базовые настройки Weaviate
dokku config:set weaviate \
  QUERY_DEFAULTS_LIMIT=25 \
  AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  CLUSTER_HOSTNAME=node1 \
  AUTOSCHEMA_ENABLED=true

# Auto-schema включен для удобства разработки
# Weaviate автоматически создаст классы и свойства при добавлении данных
# Это удобно для прототипирования и быстрой разработки

# Для production рекомендуется отключить anonymous access:
# См. подробную документацию: docs/infra/WEAVIATE_AUTHENTICATION.md
# dokku config:set weaviate \
#   AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false \
#   AUTHENTICATION_APIKEY_ENABLED=true \
#   AUTHENTICATION_APIKEY_ALLOWED_KEYS=your-api-key-here \
#   AUTHENTICATION_APIKEY_USERS=weaviate-user
```
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
read_file

### Шаг 4: Запуск Weaviate через Dockerfile

Самый надежный способ - создать минимальный Dockerfile и использовать стандартный git push:

```bash
# Установите docker-options plugin (если еще не установлен)
dokku plugin:install https://github.com/dokku/dokku-docker-options.git

# Добавьте docker-options для портов
dokku docker-options:add weaviate deploy,run "--publish=8080:8080"
dokku docker-options:add weaviate deploy,run "--publish=50051:50051"

# Создайте временную директорию с Dockerfile
mkdir -p /tmp/weaviate-dokku
cd /tmp/weaviate-dokku

# Создайте минимальный Dockerfile
cat > Dockerfile << 'EOF'
FROM cr.weaviate.io/semitechnologies/weaviate:1.35.1
EXPOSE 8080 50051
EOF

# Инициализируйте git репозиторий и задеплойте
git init
git add Dockerfile
git commit -m "Initial commit"
git remote add dokku dokku@yourserver.com:weaviate
git push dokku main
```

**Готово!** Weaviate запущен. 

**Примечание:** 
- Weaviate автоматически запустится с параметрами `--host=0.0.0.0 --port=8080 --scheme=http` по умолчанию
- После первого деплоя можно обновлять версию, изменив версию в Dockerfile и сделав `git push dokku main`

### Шаг 5: Проверка работы

```bash
# Проверьте статус приложения
dokku ps:report weaviate

# Проверьте логи
dokku logs weaviate --tail 50

# Проверьте доступность API
curl http://localhost:8080/v1/meta

# Или через внешний IP (если настроен домен)
curl http://weaviate.yourserver.com/v1/meta
```

## Дополнительные настройки

### Настройка домена (опционально)

```bash
# Установите домен для Weaviate
dokku domains:set weaviate weaviate.yourserver.com

# Настройте SSL (если есть Let's Encrypt plugin)
dokku letsencrypt:enable weaviate
```

## GraphQL Schema-First для фронтенда

Weaviate предоставляет GraphQL API, и для генерации TypeScript типов на фронтенде нужна GraphQL схема. Есть два подхода:

### Подход 1: Получение схемы из запущенного Weaviate (рекомендуется)

Weaviate автоматически генерирует GraphQL схему на основе данных. Можно получить её через introspection:

```bash
# Получить GraphQL схему через introspection query
curl -X POST http://weaviate:8080/v1/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query IntrospectionQuery { __schema { types { name kind fields { name type { name kind ofType { name kind } } } } } }"
  }'
```

Или использовать GraphQL Code Generator для автоматической генерации типов:

```yaml
# codegen.yml
schema: http://weaviate:8080/v1/graphql
generates:
  src/generated/weaviate-types.ts:
    plugins:
      - typescript
      - typescript-operations
```

### Подход 2: Определение схемы данных заранее

Можно определить схему данных в Weaviate заранее, тогда GraphQL схема будет доступна сразу:

```python
# Пример создания схемы (v4 API)
# В реальном проекте используется api/storage/weaviate_schema.py
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

# Создаем класс (если еще не существует)
if not client.collections.exists("Paragraph"):
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
    print("✅ Схема создана")
else:
    print("ℹ️  Схема уже существует")

client.close()
```

См. также: `api/storage/weaviate_schema.py` (будет создан в процессе миграции)

## Подключение приложений к Weaviate

См. документ [WEAVIATE_APP_LINKING.md](WEAVIATE_APP_LINKING.md) для детальных инструкций.

## Обновление Weaviate

```bash
# Обновите версию в Dockerfile
cd /tmp/weaviate-dokku
sed -i 's/weaviate:1.35.1/weaviate:1.36.0/' Dockerfile

# Закоммитьте и задеплойте
git add Dockerfile
git commit -m "Update to Weaviate 1.36.0"
git push dokku main
```

## Резервное копирование

```bash
# Создайте резервную копию данных
tar -czf weaviate-backup-$(date +%Y%m%d).tar.gz /var/lib/dokku/data/storage/weaviate

# Восстановление
tar -xzf weaviate-backup-YYYYMMDD.tar.gz -C /
```

## Мониторинг

```bash
# Проверка использования ресурсов
dokku resource:report weaviate

# Логи в реальном времени
dokku logs weaviate -t

# Проверка здоровья
curl http://localhost:8080/v1/meta
```

## Troubleshooting

### Weaviate не запускается

```bash
# Проверьте логи
dokku logs weaviate --tail 100

# Проверьте права доступа к storage
ls -la /var/lib/dokku/data/storage/weaviate
chown -R dokku:dokku /var/lib/dokku/data/storage/weaviate
```

### Проблемы с портами

```bash
# Проверьте, не заняты ли порты
netstat -tulpn | grep -E '8080|50051'

# Если заняты, измените порты в docker-options
dokku docker-options:remove weaviate deploy,run "--publish=8080:8080"
dokku docker-options:remove weaviate deploy,run "--publish=50051:50051"
dokku docker-options:add weaviate deploy,run "--publish=8081:8080"
dokku docker-options:add weaviate deploy,run "--publish=50052:50051"
dokku ps:rebuild weaviate
```

### Проблемы с персистентностью

```bash
# Проверьте монтирование storage
dokku storage:report weaviate

# Проверьте содержимое директории
ls -la /var/lib/dokku/data/storage/weaviate
```

## Связанные документы

- [WEAVIATE_GRAPHQL_TYPES.md](WEAVIATE_GRAPHQL_TYPES.md) - GraphQL Schema-First для генерации типов фронтенда
- [WEAVIATE_SCHEMA_FIRST.md](WEAVIATE_SCHEMA_FIRST.md) - Schema-First подход для данных
- [WEAVIATE_APP_LINKING.md](WEAVIATE_APP_LINKING.md) - Подключение приложений к Weaviate
- [WEAVIATE_AUTHENTICATION.md](WEAVIATE_AUTHENTICATION.md) - Настройка аутентификации Weaviate

## Ссылки

- [Официальная документация Weaviate Docker](https://docs.weaviate.io/deploy/installation-guides/docker-installation)
- [Weaviate Schema Documentation](https://weaviate.io/developers/weaviate/manage-data/schema)
- [Weaviate Best Practices](https://weaviate.io/developers/weaviate/best-practices)
- [Dokku Docker Options Plugin](https://github.com/dokku/dokku-docker-options)
- [Dokku Storage Plugin](https://github.com/dokku/dokku-storage)
