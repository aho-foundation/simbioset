# Развертывание Weaviate с AutoSchema в Dokku

## Быстрый старт

### 0. Диагностика портов (если ошибка "port already allocated")
```bash
# Проверить что использует порт 8080
sudo netstat -tulpn | grep :8080
sudo lsof -i :8080

# Найти и остановить конфликтующее приложение
docker ps | grep 8080
docker stop <container_id>

# Или изменить порт для Weaviate (на 8081)
# Тогда в настройках использовать WEAVIATE_URL=http://weaviate:8081
```

### 1. Создание приложения
```bash
# Создать приложение в Dokku
dokku apps:create weaviate

# Настроить хранение (важно для данных)
dokku storage:ensure-directory weaviate
dokku storage:mount weaviate /var/lib/weaviate:/opt/weaviate/data
```

### 2. Включение AutoSchema

#### Настройка Weaviate сервера
```bash
# Основные настройки AutoSchema для Weaviate
dokku config:set weaviate AUTOSCHEMA_ENABLED=true
dokku config:set weaviate AUTOSCHEMA_DEFAULT_NUMBER=number
dokku config:set weaviate AUTOSCHEMA_DEFAULT_DATE=date

# Опциональные настройки для производительности
dokku config:set weaviate PERSISTENCE_DATA_PATH=/opt/weaviate/data
dokku config:set weaviate QUERY_DEFAULTS_LIMIT=1000
dokku config:set weaviate AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
```

#### Настройка приложения Симбиосети
```bash
# Включить использование встроенной AutoSchema (по умолчанию уже включено)
dokku config:set simbioset-website WEAVIATE_USE_BUILTIN_AUTOSCHEMA=true

# Опционально: настройки типов данных для AutoSchema
dokku config:set simbioset-website WEAVIATE_AUTOSCHEMA_DEFAULT_NUMBER=number
dokku config:set simbioset-website WEAVIATE_AUTOSCHEMA_DEFAULT_DATE=date
```

### 3. Развертывание
```bash
# Использовать официальный образ Weaviate
# ВАЖНО: Использовать docker-options для передачи переменных окружения
dokku docker-options:add weaviate deploy "-e AUTOSCHEMA_ENABLED=true"
dokku docker-options:add weaviate deploy "-e AUTOSCHEMA_DEFAULT_NUMBER=number"
dokku docker-options:add weaviate deploy "-e AUTOSCHEMA_DEFAULT_DATE=date"
dokku docker-options:add weaviate deploy "-e PERSISTENCE_DATA_PATH=/opt/weaviate/data"

# Развернуть через Docker образ
dokku git:from-image weaviate semitechnologies/weaviate:latest

# Открыть порты (изменить если 8080 занят)
dokku proxy:ports-set weaviate http:80:8080 grpc:50051:50051

# Проверить статус
dokku apps:report weaviate
```

### Альтернативный порт (если 8080 занят)
```bash
# Использовать порт 8081 для Weaviate
dokku proxy:ports-set weaviate http:80:8081 grpc:50052:50051

# Обновить настройки приложения
dokku config:set simbioset-website WEAVIATE_URL=http://weaviate:8081
dokku config:set simbioset-website WEAVIATE_GRPC_URL=weaviate:50052
```

## Полная конфигурация

### Переменные окружения для AutoSchema
```bash
# Обязательные
AUTOSCHEMA_ENABLED=true                    # Включить AutoSchema
AUTOSCHEMA_DEFAULT_NUMBER=number           # Тип для чисел (number/int)
AUTOSCHEMA_DEFAULT_DATE=date               # Тип для дат

# Опциональные для симбиосети
AUTOSCHEMA_DEFAULT_STRING=text             # Тип для строк
DISABLE_LAZY_LOAD_SHARDS=true              # Быстрая загрузка для prod
MEMORY_WARNING_PERCENTAGE=80               # Предупреждение при 80% памяти
DISK_WARNING_PERCENTAGE=85                 # Предупреждение при 85% диска
```

### Порты и сеть
```bash
# Порты в Dokku
dokku proxy:ports-add weaviate http:80:8080
dokku proxy:ports-add weaviate grpc:50051:50051

# Проверка доступности
curl http://your-domain.com/v1/meta
curl http://your-domain.com/v1/schema
```

## Настройка приложения Симбиосеть

### Переменные окружения для приложения
```bash
# Weaviate подключение
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_GRPC_URL=weaviate:50051

# Настройки приложения
WEAVIATE_USE_BUILTIN_AUTOSCHEMA=true      # Использовать встроенную AutoSchema Weaviate (по умолчанию: true)
WEAVIATE_AUTOSCHEMA_DEFAULT_NUMBER=number # Тип для чисел в AutoSchema (опционально)
WEAVIATE_AUTOSCHEMA_DEFAULT_DATE=date     # Тип для дат в AutoSchema (опционально)
ENABLE_AUTOMATIC_DETECTORS=true           # Включить NER и классификацию
WEAVIATE_BATCH_SIZE=500                   # Размер батча для импорта
```

### Сетевые связи
```bash
# Связать приложения в Dokku
dokku network:create simbioset-network
dokku network:set weaviate attach-post-deploy simbioset-network
dokku network:set simbioset-website attach-post-deploy simbioset-network
```

## Проверка работы

### Тест AutoSchema
```bash
# 1. Проверить что Weaviate работает
curl http://your-domain.com/v1/meta

# 2. Проверить что AutoSchema включен
curl http://your-domain.com/v1/schema | jq '.classes | length'
# Должен вернуть 0 (пустая схема изначально)

# 3. Добавить тестовые данные через API симбиосети
curl -X POST http://your-app.com/api/documents \
  -H "Content-Type: application/json" \
  -d '{"documents": [{"text": "Тест симбиоза дуба и грибов"}]}'

# 4. Проверить что схема создалась
curl http://your-domain.com/v1/schema | jq '.classes[0]'
```

### Мониторинг
```bash
# Логи Weaviate
dokku logs weaviate -t

# Статус приложения
dokku apps:report weaviate

# Использование ресурсов
dokku ps:inspect weaviate
```

## Troubleshooting

### Порт уже занят ("port is already allocated")

**Ошибка:** `Bind for 0.0.0.0:8080 failed: port is already allocated`

**Решение:**
```bash
# 1. Найти что использует порт 8080
sudo netstat -tulpn | grep :8080
sudo lsof -i :8080

# 2. Проверить Docker контейнеры
docker ps | grep 8080

# 3. Остановить конфликтующий контейнер
docker stop <container_name>

# 4. Или изменить порт для Weaviate
dokku proxy:ports-set weaviate http:80:8081 grpc:50052:50051
dokku config:set simbioset-website WEAVIATE_URL=http://weaviate:8081
dokku config:set simbioset-website WEAVIATE_GRPC_URL=weaviate:50052
```

### AutoSchema не работает
```bash
# Проверить переменные
dokku config:show weaviate | grep AUTOSCHEMA

# Проверить логи
dokku logs weaviate | grep -i autoschema

# Перезапустить
dokku ps:restart weaviate
```

### Ошибки подключения
```bash
# Проверить сеть
dokku network:report simbioset-network

# Проверить DNS
dokku run weaviate ping simbioset-website

# Проверить переменные приложения
dokku config:show simbioset-website | grep WEAVIATE
```

### Проблемы с данными
```bash
# Очистить данные (осторожно!)
dokku run weaviate rm -rf /opt/weaviate/data/*

# Перезапустить
dokku ps:restart weaviate
```

## Производственная настройка

### Масштабирование
```bash
# Для высокой нагрузки
dokku config:set weaviate QUERY_MAXIMUM_RESULTS=10000
dokku config:set weaviate QUERY_DEFAULTS_LIMIT=1000

# Кластеризация (если нужно)
dokku config:set weaviate CLUSTER_HOSTNAME=weaviate-cluster
```

### Безопасность
```bash
# Отключить анонимный доступ в продакшене
dokku config:set weaviate AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false

# Настроить аутентификацию
dokku config:set weaviate AUTHENTICATION_APIKEY_ENABLED=true
dokku config:set weaviate AUTHENTICATION_APIKEY_ALLOWED_KEYS=your-api-key
```

### Бэкапы
```bash
# Настроить регулярные бэкапы
dokku config:set weaviate BACKUP_FILESYSTEM_PATH=/opt/weaviate/backups

# Ручной бэкап
dokku run weaviate weaviate backup create --name daily-backup
```

## Миграция с существующей схемы

Если у вас уже есть данные в Weaviate без AutoSchema:

1. **Создать бэкап** существующих данных
2. **Включить AutoSchema** настройками выше
3. **Перезапустить** Weaviate
4. **Проверить** что новые данные создают схему автоматически
5. **Миграция данных** (если нужно) через API

## Связанная документация

- [Weaviate AutoSchema](https://docs.weaviate.io/weaviate/config-refs/collections#auto-schema)
- [Dokku Storage](https://dokku.com/docs/deployment/methods/git/#persistent-storage)
- [Network Management](https://dokku.com/docs/networking/)
- [AutoSchema Setup](WEAVIATE_AUTOSCHEMA_SETUP.md)