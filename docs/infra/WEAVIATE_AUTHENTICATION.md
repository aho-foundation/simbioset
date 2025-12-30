# Настройка аутентификации Weaviate

## Обзор

Weaviate поддерживает несколько методов аутентификации:
- **API Key** - простой метод для production
- **OIDC** - для интеграции с внешними провайдерами
- **Anonymous Access** - только для разработки (не рекомендуется для production)

## Настройка API Key аутентификации

### 1. Настройка на стороне Weaviate

#### Для Docker / Dokku

Установите следующие переменные окружения:

```bash
# Отключить анонимный доступ (рекомендуется для production)
AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false

# Включить API Key аутентификацию
AUTHENTICATION_APIKEY_ENABLED=true

# Список разрешенных API ключей (через запятую)
AUTHENTICATION_APIKEY_ALLOWED_KEYS=your-secret-key-1,your-secret-key-2

# Список пользователей, соответствующих ключам (через запятую)
# Количество должно совпадать с количеством ключей
AUTHENTICATION_APIKEY_USERS=user1,user2
```

**Важно:**
- Количество ключей должно **точно совпадать** с количеством пользователей
- Ключи должны быть достаточно сложными (минимум 32 символа)
- Не храните ключи в открытом виде в коде или конфигах

#### Пример для Dokku

```bash
# Генерация безопасного ключа
API_KEY=$(openssl rand -hex 32)

# Установка переменных окружения
dokku config:set weaviate \
  AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false \
  AUTHENTICATION_APIKEY_ENABLED=true \
  AUTHENTICATION_APIKEY_ALLOWED_KEYS="$API_KEY" \
  AUTHENTICATION_APIKEY_USERS="simbioset-api"

# Перезапуск Weaviate
dokku ps:restart weaviate
```

#### Пример для docker-compose.yml

```yaml
services:
  weaviate:
    image: cr.weaviate.io/semitechnologies/weaviate:1.35.2
    environment:
      - AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false
      - AUTHENTICATION_APIKEY_ENABLED=true
      - AUTHENTICATION_APIKEY_ALLOWED_KEYS=your-secret-key-1,your-secret-key-2
      - AUTHENTICATION_APIKEY_USERS=user1,user2
    ports:
      - "8080:8080"
      - "50051:50051"
```

### 2. Настройка клиента (Python v4)

#### Использование в коде

```python
import weaviate
from weaviate.auth import AuthApiKey
from weaviate.connect.base import ConnectionParams

# Получаем настройки из переменных окружения
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

# Парсим URL
url_parts = WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")
host = url_parts[0] if url_parts else "localhost"
port = int(url_parts[1]) if len(url_parts) > 1 else 8080
secure = WEAVIATE_URL.startswith("https://")

# Создаем клиент с аутентификацией
client = weaviate.WeaviateClient(
    connection_params=ConnectionParams.from_params(
        http_host=host,
        http_port=port,
        http_secure=secure,
        grpc_host=host,
        grpc_port=50051,
        grpc_secure=secure,
    ),
    auth_client_secret=AuthApiKey(api_key=WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None,
)

# Подключаемся
client.connect()

# Проверка подключения
meta = client.get_meta()
print(f"✅ Подключено к Weaviate {meta.get('version', 'unknown')}")

# Не забудьте закрыть соединение
client.close()
```

#### Текущая реализация в проекте

В `api/storage/weaviate_storage.py` уже используется правильный подход:

```python
from weaviate.auth import AuthApiKey
from weaviate.connect.base import ConnectionParams

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
```

### 3. Настройка переменных окружения в приложении

#### Для Dokku

```bash
APP_NAME="simbioset-website"

# Установите API ключ (должен совпадать с одним из AUTHENTICATION_APIKEY_ALLOWED_KEYS)
dokku config:set "$APP_NAME" \
  WEAVIATE_URL=http://weaviate:8080 \
  WEAVIATE_API_KEY="your-secret-key-1"

# Перезапустите приложение
dokku ps:restart "$APP_NAME"
```

#### Для локальной разработки

```bash
# .env файл
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=your-secret-key-1
```

### 4. Проверка аутентификации

#### Через curl

```bash
# Без ключа (должна быть ошибка 401)
curl http://localhost:8080/v1/meta

# С ключом (должен вернуть метаданные)
curl -H "X-Weaviate-Api-Key: your-secret-key-1" \
     http://localhost:8080/v1/meta
```

#### Через Python

```python
import weaviate
from weaviate.auth import AuthApiKey

try:
    client = weaviate.WeaviateClient(
        connection_params=ConnectionParams.from_params(
            http_host="localhost",
            http_port=8080,
            http_secure=False,
            grpc_host="localhost",
            grpc_port=50051,
            grpc_secure=False,
        ),
        auth_client_secret=AuthApiKey(api_key="your-secret-key-1"),
    )
    client.connect()
    meta = client.get_meta()
    print(f"✅ Аутентификация успешна! Версия: {meta.get('version')}")
    client.close()
except Exception as e:
    print(f"❌ Ошибка аутентификации: {e}")
```

## Управление пользователями через API (v1.30+)

Начиная с версии v1.30, Weaviate предоставляет API для управления пользователями, ролями и API ключами. Это предпочтительный метод вместо переменных окружения.

### Создание пользователя и API ключа

```python
import weaviate
from weaviate.auth import AuthApiKey

# Подключение с правами администратора
admin_client = weaviate.WeaviateClient(
    connection_params=ConnectionParams.from_params(...),
    auth_client_secret=AuthApiKey(api_key="admin-key"),
)
admin_client.connect()

# Создание пользователя
user = admin_client.users.create(
    username="new-user",
    password="secure-password",
)

# Создание API ключа для пользователя
api_key = admin_client.api_keys.create(
    username="new-user",
    key_name="my-api-key",
)

print(f"API Key: {api_key.key}")
```

### Рекомендации

1. **Используйте API для управления** (v1.30+) вместо переменных окружения
2. **Ротация ключей**: регулярно обновляйте API ключи
3. **Минимальные права**: создавайте пользователей с минимально необходимыми правами
4. **Мониторинг**: отслеживайте использование API ключей
5. **Безопасное хранение**: используйте секреты Kubernetes, HashiCorp Vault или аналоги

## Troubleshooting

### Ошибка 401 Unauthorized

```bash
# Проверьте, что API ключ установлен
echo $WEAVIATE_API_KEY

# Проверьте, что ключ совпадает с одним из AUTHENTICATION_APIKEY_ALLOWED_KEYS
dokku config:show weaviate | grep AUTHENTICATION_APIKEY_ALLOWED_KEYS

# Проверьте логи Weaviate
dokku logs weaviate --tail 50 | grep -i auth
```

### Ошибка: количество ключей не совпадает с пользователями

```bash
# Проверьте количество
KEYS=$(dokku config:get weaviate AUTHENTICATION_APIKEY_ALLOWED_KEYS | tr ',' '\n' | wc -l)
USERS=$(dokku config:get weaviate AUTHENTICATION_APIKEY_USERS | tr ',' '\n' | wc -l)

echo "Ключей: $KEYS, Пользователей: $USERS"
# Должны быть равны!
```

### Проверка настроек аутентификации

```bash
# Проверьте все настройки аутентификации
dokku config:show weaviate | grep AUTHENTICATION

# Должны быть установлены:
# AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false
# AUTHENTICATION_APIKEY_ENABLED=true
# AUTHENTICATION_APIKEY_ALLOWED_KEYS=...
# AUTHENTICATION_APIKEY_USERS=...
```

## Ссылки

- [Официальная документация Weaviate: Authentication](https://docs.weaviate.io/deploy/configuration/authentication)
- [Weaviate Python Client v4: Authentication](https://weaviate.io/developers/weaviate/client-libraries/python#authentication)
- [Weaviate User Management API](https://docs.weaviate.io/deploy/configuration/authentication#user-management-api)
