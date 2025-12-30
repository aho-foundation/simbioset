# Подключение приложений Dokku к Weaviate

## Обзор

После развертывания Weaviate в Dokku, другие приложения могут подключаться к нему через:
- HTTP API (порт 8080)
- gRPC API (порт 50051)
- Переменные окружения для конфигурации

## Предварительные требования

- Weaviate развернут в Dokku (см. [WEAVIATE_DOKKU_SETUP.md](WEAVIATE_DOKKU_SETUP.md))
- Приложение, которое нужно подключить к Weaviate

## Способы подключения

### Способ 1: Через внутреннюю сеть Dokku (рекомендуется)

Dokku создает внутреннюю Docker сеть для всех приложений. Приложения могут обращаться друг к другу по имени.

#### Настройка переменных окружения

```bash
# Для приложения simbioset-website (или другого)
APP_NAME="simbioset-website"

# Установите URL Weaviate
# Если Weaviate на том же сервере, используйте внутренний адрес
dokku config:set "$APP_NAME" \
  WEAVIATE_URL=http://weaviate:8080 \
  WEAVIATE_GRPC_URL=weaviate:50051

# Или если используется домен
dokku config:set "$APP_NAME" \
  WEAVIATE_URL=http://weaviate.yourserver.com \
  WEAVIATE_GRPC_URL=grpc-weaviate.yourserver.com:50051
```

#### Использование в коде

```python
# api/settings.py
import os

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_GRPC_URL = os.getenv("WEAVIATE_GRPC_URL", "localhost:50051")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", None)  # Если используется аутентификация
```

```python
# api/storage/weaviate_storage.py
import weaviate
from weaviate.auth import AuthApiKey
from weaviate.connect.base import ConnectionParams
from api.settings import WEAVIATE_URL, WEAVIATE_API_KEY

class WeaviateStorage:
    def __init__(self):
        # Парсим URL
        url_parts = WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")
        host = url_parts[0] if url_parts else "localhost"
        port = int(url_parts[1]) if len(url_parts) > 1 else 8080
        secure = WEAVIATE_URL.startswith("https://")
        
        auth_config = None
        if WEAVIATE_API_KEY:
            auth_config = AuthApiKey(api_key=WEAVIATE_API_KEY)
        
        self.client = weaviate.WeaviateClient(
            connection_params=ConnectionParams.from_params(
                http_host=host,
                http_port=port,
                http_secure=secure,
                grpc_host=host,
                grpc_port=50051,
                grpc_secure=secure,
            ),
            auth_client_secret=auth_config,
        )
        self.client.connect()
```

### Способ 2: Через внешний URL (если настроен домен)

Если для Weaviate настроен домен (например, `weaviate.yourserver.com`):

```bash
APP_NAME="simbioset-website"

dokku config:set "$APP_NAME" \
  WEAVIATE_URL=https://weaviate.yourserver.com \
  WEAVIATE_GRPC_URL=grpc-weaviate.yourserver.com:50051
```

### Способ 3: Через локальный порт (не рекомендуется для production)

Если нужно подключиться через localhost:

```bash
APP_NAME="simbioset-website"

dokku config:set "$APP_NAME" \
  WEAVIATE_URL=http://localhost:8080 \
  WEAVIATE_GRPC_URL=localhost:50051
```

**Внимание:** Этот способ работает только если приложения на одном хосте и порты проброшены.

## Настройка для конкретного приложения

### Пример: Подключение simbioset-website к Weaviate

```bash
# 1. Подключитесь к серверу
ssh root@yourserver.com

# 2. Установите переменные окружения
APP_NAME="simbioset-website"

dokku config:set "$APP_NAME" \
  WEAVIATE_URL=http://weaviate:8080 \
  WEAVIATE_GRPC_URL=weaviate:50051

# WEAVIATE_CLASS_NAME опциональна - по умолчанию "Paragraph"
# Нужна только если используете другой класс для тестирования/миграций
# dokku config:set "$APP_NAME" WEAVIATE_CLASS_NAME="Paragraph_v2"

# 3. Проверьте настройки
dokku config:show "$APP_NAME" | grep WEAVIATE

# 4. Перезапустите приложение для применения изменений
dokku ps:restart "$APP_NAME"
```

## Проверка подключения

### Из приложения

```python
# Тестовый скрипт для проверки подключения
import weaviate
from api.settings import WEAVIATE_URL, WEAVIATE_API_KEY

try:
    auth_config = None
    if WEAVIATE_API_KEY:
        auth_config = weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY)
    
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=auth_config
    )
    
    # Проверка подключения
    meta = client.get_meta()
    print(f"✅ Подключение успешно! Версия Weaviate: {meta.get('version', 'unknown')}")
    
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
```

### Через curl из контейнера

```bash
# Зайдите в контейнер приложения
dokku enter simbioset-website

# Проверьте подключение к Weaviate
curl http://weaviate:8080/v1/meta

# Или через переменную окружения
curl $WEAVIATE_URL/v1/meta
```

### Через Dokku команды

```bash
# Проверьте переменные окружения
dokku config:show simbioset-website | grep WEAVIATE

# Проверьте логи приложения на наличие ошибок подключения
dokku logs simbioset-website --tail 100 | grep -i weaviate
```

## Настройка аутентификации

Если в Weaviate включена аутентификация (см. [WEAVIATE_AUTHENTICATION.md](WEAVIATE_AUTHENTICATION.md)):

```bash
# 1. Убедитесь, что в Weaviate настроена аутентификация
dokku config:show weaviate | grep AUTHENTICATION_APIKEY_ALLOWED_KEYS

# 2. Установите API ключ в приложении
# Ключ должен совпадать с одним из AUTHENTICATION_APIKEY_ALLOWED_KEYS
APP_NAME="simbioset-website"
WEAVIATE_API_KEY="your-secret-api-key-here"

dokku config:set "$APP_NAME" \
  WEAVIATE_API_KEY="$WEAVIATE_API_KEY"

# 3. Перезапустите приложение
dokku ps:restart "$APP_NAME"
```

**Подробная документация:** [WEAVIATE_AUTHENTICATION.md](WEAVIATE_AUTHENTICATION.md)

## Использование в коде приложения

### Python (weaviate-client)

```python
# requirements.txt
weaviate-client>=4.0.0

# api/storage/weaviate_storage.py
import weaviate
from weaviate.auth import AuthApiKey
from weaviate.connect.base import ConnectionParams
from api.settings import WEAVIATE_URL, WEAVIATE_API_KEY, WEAVIATE_CLASS_NAME
from api.logger import root_logger

log = root_logger.debug

class WeaviateStorage:
    def __init__(self):
        """Инициализация подключения к Weaviate (v4 API)"""
        try:
            # Парсим URL
            url_parts = WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")
            host = url_parts[0] if url_parts else "localhost"
            port = int(url_parts[1]) if len(url_parts) > 1 else 8080
            secure = WEAVIATE_URL.startswith("https://")
            
            auth_config = None
            if WEAVIATE_API_KEY:
                auth_config = AuthApiKey(api_key=WEAVIATE_API_KEY)
            
            self.client = weaviate.WeaviateClient(
                connection_params=ConnectionParams.from_params(
                    http_host=host,
                    http_port=port,
                    http_secure=secure,
                    grpc_host=host,
                    grpc_port=50051,
                    grpc_secure=secure,
                ),
                auth_client_secret=auth_config,
            )
            
            # Подключаемся
            self.client.connect()
            
            # Проверка подключения
            meta = self.client.get_meta()
            log(f"✅ Подключено к Weaviate {meta.get('version', 'unknown')} на {WEAVIATE_URL}")
            
        except Exception as e:
            log(f"❌ Ошибка подключения к Weaviate: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Проверка готовности Weaviate"""
        try:
            return self.client.is_ready()
        except:
            return False
```

### JavaScript/TypeScript (weaviate-ts-client)

```typescript
// src/lib/weaviate.ts
import weaviate, { WeaviateClient } from 'weaviate-ts-client';

const WEAVIATE_URL = import.meta.env.VITE_WEAVIATE_URL || 'http://localhost:8080';
const WEAVIATE_API_KEY = import.meta.env.VITE_WEAVIATE_API_KEY;

export const weaviateClient: WeaviateClient = weaviate.client({
  scheme: 'http',
  host: new URL(WEAVIATE_URL).hostname,
  port: new URL(WEAVIATE_URL).port || '8080',
  apiKey: WEAVIATE_API_KEY ? new weaviate.ApiKey(WEAVIATE_API_KEY) : undefined,
});
```

## Настройка для нескольких приложений

Если несколько приложений должны использовать один Weaviate:

```bash
# Для каждого приложения установите одинаковые переменные
for APP in app1 app2 app3; do
  dokku config:set "$APP" \
    WEAVIATE_URL=http://weaviate:8080 \
    WEAVIATE_GRPC_URL=weaviate:50051
done
```

## Troubleshooting

### Ошибка подключения: Connection refused

```bash
# Проверьте, что Weaviate запущен
dokku ps:report weaviate

# Проверьте логи Weaviate
dokku logs weaviate --tail 50

# Проверьте, что приложение видит Weaviate в сети
dokku enter simbioset-website
ping weaviate
```

### Ошибка: Name resolution failed

```bash
# Убедитесь, что используете правильное имя приложения Weaviate
dokku apps:list | grep weaviate

# Проверьте, что оба приложения в одной сети Dokku
dokku network:report weaviate
dokku network:report simbioset-website
```

### Ошибка аутентификации

```bash
# Проверьте API ключ
dokku config:show simbioset-website | grep WEAVIATE_API_KEY

# Проверьте настройки аутентификации в Weaviate
dokku config:show weaviate | grep AUTHENTICATION
```

### Проверка доступности портов

```bash
# Из контейнера приложения проверьте доступность Weaviate
dokku enter simbioset-website
curl -v http://weaviate:8080/v1/meta

# Или через telnet
telnet weaviate 8080
```

## Пример полной настройки

```bash
#!/bin/bash
# Скрипт для подключения приложения к Weaviate

APP_NAME="${1:-simbioset-website}"
WEAVIATE_APP="weaviate"

echo "🔗 Подключение $APP_NAME к Weaviate..."

# Проверка, что Weaviate запущен
if ! dokku ps:report "$WEAVIATE_APP" | grep -q "running"; then
    echo "❌ Weaviate не запущен. Запустите его сначала."
    exit 1
fi

# Установка переменных окружения
dokku config:set "$APP_NAME" \
  WEAVIATE_URL=http://weaviate:8080 \
  WEAVIATE_GRPC_URL=weaviate:50051

# WEAVIATE_CLASS_NAME опциональна (по умолчанию "Paragraph")
# Используйте только если нужен другой класс для тестирования/миграций

echo "✅ Переменные окружения установлены"

# Перезапуск приложения
dokku ps:restart "$APP_NAME"

echo "✅ Приложение перезапущено"
echo "📋 Проверка подключения..."
sleep 5

# Проверка логов
dokku logs "$APP_NAME" --tail 20 | grep -i weaviate || echo "⚠️  Проверьте логи вручную"
```

## Связанные документы

- [WEAVIATE_DOKKU_SETUP.md](WEAVIATE_DOKKU_SETUP.md) - Развертывание Weaviate
- [WEAVIATE_AUTHENTICATION.md](WEAVIATE_AUTHENTICATION.md) - Настройка аутентификации
- [WEAVIATE_SCHEMA_FIRST.md](WEAVIATE_SCHEMA_FIRST.md) - Schema-First подход

## Ссылки

- [Weaviate Python Client](https://weaviate.io/developers/weaviate/client-libraries/python)
- [Weaviate JavaScript Client](https://weaviate.io/developers/weaviate/client-libraries/javascript)
- [Weaviate Schema Documentation](https://weaviate.io/developers/weaviate/manage-data/schema)
- [Dokku Networking](http://dokku.viewdocs.io/dokku/networking/)
