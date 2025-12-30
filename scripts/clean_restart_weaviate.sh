#!/bin/bash
# Полная очистка и перезапуск Weaviate
set -e

echo "🧹 Полная очистка Weaviate..."

# 1. Остановить Dokku приложение
echo "🛑 Останавливаем Dokku приложение..."
dokku ps:stop weaviate 2>/dev/null || true

# 2. Очистить все контейнеры связанные с Weaviate
echo "🗑️  Очищаем контейнеры..."
docker stop $(docker ps -q --filter "name=weaviate") 2>/dev/null || true
docker rm $(docker ps -a -q --filter "name=weaviate") 2>/dev/null || true

# 3. Очистить образы (опционально)
read -p "Очистить Docker образы Weaviate? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Очищаем образы..."
    docker rmi $(docker images -q "dokku/weaviate") 2>/dev/null || true
fi

# 4. Проверить порт
echo "🔍 Проверяем порт 8080..."
if netstat -tulpn 2>/dev/null | grep -q ":8080 "; then
    echo "⚠️  Порт 8080 все еще занят:"
    netstat -tulpn | grep ":8080 "
    echo "💡 Попробуйте остановить процесс вручную"
else
    echo "✅ Порт 8080 свободен"
fi

# 5. Перезапустить Weaviate
echo "🔄 Перезапускаем Weaviate..."
if dokku ps:rebuild weaviate; then
    echo "✅ Weaviate перезапущен!"
    sleep 5

    # Проверить статус
    if dokku ps:report weaviate | grep -q "running"; then
        echo "🎉 Weaviate работает!"
        echo "🌐 Проверьте: curl http://localhost:8080/v1/meta"
    else
        echo "❌ Weaviate не запустился"
        echo "Логи: dokku logs weaviate --tail 50"
    fi
else
    echo "❌ Ошибка перезапуска Weaviate"
    echo "Логи: dokku logs weaviate --tail 50"
fi