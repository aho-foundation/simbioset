#!/bin/bash
# Скрипт для исправления проблем с портами Weaviate
set -e

echo "🔧 Исправление проблем с портами Weaviate..."

# Проверить, что порт 8080 занят
echo "🔍 Проверяем порт 8080..."
if netstat -tulpn 2>/dev/null | grep -q ":8080 "; then
    echo "⚠️  Порт 8080 занят:"
    netstat -tulpn | grep ":8080 "
    echo ""
    echo "Возможные решения:"
    echo "1. Остановить процесс, использующий порт 8080"
    echo "2. Изменить порт Weaviate на 8081"
    echo ""
    read -p "Изменить порт Weaviate на 8081? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 Меняем порт Weaviate на 8081..."

        # Остановить Weaviate
        dokku ps:stop weaviate

        # Изменить docker-options
        dokku docker-options:remove weaviate deploy,run "--publish=8080:8080"
        dokku docker-options:add weaviate deploy,run "--publish=8081:8080"

        # Обновить приложение
        dokku config:set simbioset-website WEAVIATE_URL=http://weaviate:8081

        # Перезапустить Weaviate
        dokku ps:rebuild weaviate

        echo "✅ Порт изменен на 8081"
        echo "🔄 Обновите WEAVIATE_URL в приложении если нужно"
    fi
else
    echo "✅ Порт 8080 свободен"
fi

# Проверить статус Weaviate
echo ""
echo "📊 Статус Weaviate:"
if dokku ps:report weaviate 2>/dev/null | grep -q "running"; then
    echo "✅ Weaviate запущен"
else
    echo "❌ Weaviate не запущен"
    echo "Запуск: dokku ps:start weaviate"
fi