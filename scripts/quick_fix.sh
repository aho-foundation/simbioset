#!/bin/bash
# Скрипт быстрого восстановления приложения
set -e

APP_NAME="${1:-simbioset-website}"

echo "🚀 Быстрое восстановление $APP_NAME..."

# 1. Принудительно включить FAISS
echo "🔧 Включаем FAISS для быстрого старта..."
dokku config:set "$APP_NAME" FORCE_FAISS=true

# 2. Остановить приложение
echo "🛑 Останавливаем приложение..."
dokku ps:stop "$APP_NAME"

# 3. Очистить кеш если нужно
echo "🧹 Очищаем кеш..."
dokku repo:gc "$APP_NAME" 2>/dev/null || true

# 4. Перезапустить
echo "🔄 Перезапускаем приложение..."
dokku ps:rebuild "$APP_NAME"

# 5. Проверить статус
echo ""
echo "📊 Проверяем статус..."
sleep 5

if dokku ps:report "$APP_NAME" | grep -q "running"; then
    echo "✅ Приложение запущено!"

    # Проверить health check
    echo "🏥 Проверяем health check..."
    if curl -f -s "https://simbioset.ru/health" > /dev/null 2>&1; then
        echo "✅ Health check прошел"
    else
        echo "⚠️  Health check не прошел, проверяем логи..."
        dokku logs "$APP_NAME" --tail 10
    fi
else
    echo "❌ Приложение не запустилось"
    echo "Логи: dokku logs $APP_NAME --tail 50"
fi

echo ""
echo "💡 Следующие шаги:"
echo "- Если все OK: можете отключить FORCE_FAISS через dokku config:set $APP_NAME FORCE_FAISS=false"
echo "- Для диагностики: ./scripts/diagnose.sh $APP_NAME"