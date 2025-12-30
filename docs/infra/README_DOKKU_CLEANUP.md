# Очистка Docker на Dokku сервере

## Проблема

При деплое возникает ошибка:
```
ERROR: failed to build: failed to solve: ResourceExhausted: failed to prepare ...: no space left on device
```

Это означает, что диск на сервере заполнен, обычно в `/var/lib/docker/overlay2/`.

## Решение

Используйте скрипт для очистки неиспользуемых Docker ресурсов:

```bash
# 1. Скопируйте скрипт на сервер
scp scripts/cleanup_dokku_docker.sh root@yourserver.com:/tmp/

# 2. Подключитесь к серверу
ssh root@yourserver.com

# 3. Выполните скрипт (укажите имя приложения)
bash /tmp/cleanup_dokku_docker.sh simbioset-website
```

## Что делает скрипт

1. **Удаляет остановленные контейнеры** - освобождает место
2. **Удаляет неиспользуемые образы** - старые версии приложений
3. **Удаляет неиспользуемые volumes** - неиспользуемые данные
4. **Очищает build cache** - кеш сборки Docker образов
5. **Удаляет старые образы приложения** - оставляет только последние 3 версии
6. **Полная очистка системы** - агрессивная очистка всего неиспользуемого

## Ручная очистка (если скрипт недоступен)

```bash
# Подключитесь к серверу
ssh root@yourserver.com

# Проверьте использование диска
df -h /var/lib/docker

# Очистка Docker
docker container prune -f
docker image prune -a -f
docker volume prune -f
docker builder prune -a -f
docker system prune -a -f --volumes

# Удаление старых образов конкретного приложения
docker images | grep "dokku/simbioset-website" | tail -n +4 | awk '{print $3}' | xargs docker rmi -f
```

## Анализ использования диска

Перед очисткой полезно понять, что занимает больше всего места:

```bash
# Скопируйте скрипт анализа на сервер
scp scripts/disk_usage_map.sh root@yourserver.com:/tmp/

# Выполните на сервере
ssh root@yourserver.com "bash /tmp/disk_usage_map.sh"

# Или визуальная карта в виде дерева
scp scripts/disk_usage_tree.sh root@yourserver.com:/tmp/
ssh root@yourserver.com "bash /tmp/disk_usage_tree.sh"
```

Скрипты показывают:
- Общее использование диска
- Топ-20 самых больших директорий
- Детализацию Docker (buildkit, overlay2, images, volumes)
- Детализацию Dokku (storage, кеши)
- Размер логов
- Список Docker images и containers
- Build cache статистику

## Проверка после очистки

```bash
# Проверка использования диска
df -h /var/lib/docker

# Размер Docker данных
du -sh /var/lib/docker

# Список образов
docker images

# Или используйте скрипт анализа
bash /tmp/disk_usage_map.sh
```

## Профилактика

1. **Настройте автоматическую очистку** через cron:
```bash
# Добавьте в crontab (root)
0 3 * * 0 docker system prune -a -f --volumes
```

2. **Мониторинг диска** - настройте алерты при заполнении > 80%

3. **Используйте кеширование** - настройте shared cache для уменьшения размера образов
