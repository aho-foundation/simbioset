#!/bin/bash
# Настройка storage для Dokku приложения
set -e

APP_NAME="${1:-simbioset-website}"

echo "💾 Настройка storage для $APP_NAME..."

# Проверить существующие mounts
echo "📋 Текущие mounts:"
dokku storage:list "$APP_NAME" 2>/dev/null || echo "Нет mounts"

# Настроить /app/.cache для shared cache (модели, playwright и т.д.)
echo ""
echo "🔧 Настройка /app/.cache..."
if ! dokku storage:list "$APP_NAME" | grep -q "/app/.cache"; then
    dokku storage:ensure-directory .cache
    dokku storage:mount "$APP_NAME" /var/lib/dokku/data/storage/.cache:/app/.cache
    echo "✅ /app/.cache настроен"
else
    echo "ℹ️  /app/.cache уже настроен"
fi

# Настроить /app/models если нужно (для обратной совместимости)
echo ""
echo "🔧 Настройка /app/models..."
if ! dokku storage:list "$APP_NAME" | grep -q "/app/models"; then
    dokku storage:ensure-directory models
    dokku storage:mount "$APP_NAME" /var/lib/dokku/data/storage/models:/app/models
    echo "✅ /app/models настроен"
else
    echo "ℹ️  /app/models уже настроен"
fi

echo ""
echo "📊 Финальная конфигурация storage:"
dokku storage:list "$APP_NAME"

echo ""
echo "✅ Storage настроен. Приложение будет использовать /app/.cache для моделей."