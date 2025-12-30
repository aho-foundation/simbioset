#!/bin/bash
# Скрипт для исправления проблем с портами Weaviate
set -e

echo "🔧 Исправление проблем с портами Weaviate..."

# Проверить контейнеры Weaviate
echo "🔍 Проверяем контейнеры Weaviate..."
if docker ps | grep -q weaviate; then
    echo "📋 Текущие контейнеры Weaviate:"
    docker ps | grep weaviate
    echo ""
    echo "🛑 Останавливаем старые контейнеры..."
    docker stop $(docker ps -q --filter "name=weaviate") 2>/dev/null || true
    docker rm $(docker ps -a -q --filter "name=weaviate") 2>/dev/null || true
    echo "✅ Старые контейнеры остановлены"
fi

# Проверить Dokku контейнеры
echo "🔍 Проверяем Dokku контейнеры..."
if docker ps | grep -q "weaviate.web"; then
    echo "📋 Dokku контейнеры Weaviate:"
    docker ps | grep "weaviate.web"
    echo ""
    echo "🛑 Останавливаем Dokku контейнеры..."
    docker stop $(docker ps -q --filter "name=weaviate.web") 2>/dev/null || true
    docker rm $(docker ps -a -q --filter "name=weaviate.web") 2>/dev/null || true
    echo "✅ Dokku контейнеры остановлены"
fi

# Проверить, что порт 8080 занят
echo "🔍 Проверяем порт 8080..."
if netstat -tulpn 2>/dev/null | grep -q ":8080 "; then
    echo "⚠️  Порт 8080 все еще занят:"
    netstat -tulpn | grep ":8080 "
    echo ""
    echo "🔍 Ищем процесс, использующий порт..."
    PORT_PROCESS=$(netstat -tulpn 2>/dev/null | grep ":8080 " | awk '{print $7}' | cut -d'/' -f1)
    if [ -n "$PORT_PROCESS" ] && [ "$PORT_PROCESS" != "-" ]; then
        echo "📊 Процесс $PORT_PROCESS использует порт 8080"
        ps aux | grep "$PORT_PROCESS" | grep -v grep || echo "Процесс не найден в ps"
    fi
    echo ""
    echo "💡 Рекомендации:"
    echo "1. Проверьте: docker ps | grep 8080"
    echo "2. Или измените порт Weaviate"
else
    echo "✅ Порт 8080 свободен"
fi

# Попытаться перезапустить Weaviate
echo ""
echo "🔄 Пытаемся перезапустить Weaviate..."
if dokku ps:start weaviate 2>/dev/null; then
    echo "✅ Weaviate запущен"
    sleep 3
    if dokku ps:report weaviate | grep -q "running"; then
        echo "🎉 Weaviate работает!"
    else
        echo "❌ Weaviate не запустился"
    fi
else
    echo "❌ Не удалось запустить Weaviate"
    echo "Возможно нужно изменить порт или проверить конфигурацию"
fi

# Проверить статус Weaviate
echo ""
echo "📊 Финальный статус Weaviate:"
if dokku ps:report weaviate 2>/dev/null | grep -q "running"; then
    echo "✅ Weaviate запущен"
    echo "🌐 Должен быть доступен на http://weaviate:8080"
else
    echo "❌ Weaviate не запущен"
    echo "Попробуйте: dokku ps:start weaviate"
fi