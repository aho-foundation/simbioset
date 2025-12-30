#!/bin/bash
# Скрипт быстрой диагностики проблем с приложением
set -e

APP_NAME="${1:-simbioset-website}"

echo "🔍 Диагностика приложения $APP_NAME..."
echo "========================================"

# Проверяем статус приложения
echo ""
echo "📊 Статус приложения:"
dokku ps:report "$APP_NAME" 2>/dev/null || echo "❌ Приложение не найдено"

# Проверяем health check
echo ""
echo "🏥 Health check:"
if curl -f -s "https://simbioset.ru/health" > /dev/null 2>&1; then
    echo "✅ Health check прошел"
else
    echo "❌ Health check не прошел"
fi

# Проверяем переменные окружения
echo ""
echo "🔧 Переменные окружения:"
dokku config:show "$APP_NAME" 2>/dev/null | grep -E "(WEAVIATE|FORCE_FAISS|DATABASE)" | head -10

# Проверяем последние логи
echo ""
echo "📝 Последние логи (ошибки):"
dokku logs "$APP_NAME" --tail 20 2>/dev/null | grep -E "(ERROR|❌|💥|Connection refused)" | tail -5 || echo "Нет ошибок в последних логах"

# Проверяем Weaviate если настроен
echo ""
echo "🔍 Статус Weaviate:"
WEAVIATE_CONFIG=$(dokku config:show "$APP_NAME" 2>/dev/null | grep WEAVIATE_URL || echo "")
FORCE_FAISS=$(dokku config:show "$APP_NAME" 2>/dev/null | grep FORCE_FAISS || echo "")

if [ -n "$WEAVIATE_CONFIG" ]; then
    echo "✅ WEAVIATE_URL настроен"
    if dokku ps:report weaviate 2>/dev/null | grep -q "running"; then
        echo "✅ Weaviate запущен"
        # Тестируем подключение
        if curl -f -s --max-time 5 "http://weaviate:8080/v1/meta" > /dev/null 2>&1; then
            echo "✅ Weaviate API доступен"
        else
            echo "❌ Weaviate API недоступен"
        fi
    else
        echo "❌ Weaviate не запущен"
    fi
else
    echo "ℹ️  WEAVIATE_URL не настроен"
fi

if [ -n "$FORCE_FAISS" ]; then
    echo "ℹ️  FORCE_FAISS: $FORCE_FAISS"
else
    echo "ℹ️  FORCE_FAISS не установлен (по умолчанию false)"
fi

# Подробная проверка подключения к Weaviate
if [ -n "$WEAVIATE_CONFIG" ] && dokku ps:report weaviate 2>/dev/null | grep -q "running"; then
    echo ""
    echo "🔗 Подробная проверка подключения к Weaviate:"
    ./scripts/test_weaviate_from_app.sh "$APP_NAME" 2>/dev/null || echo "❌ Не удалось выполнить тест"
fi

echo ""
echo "💡 Рекомендации:"
echo "- Если приложение не запускается: проверь логи 'dokku logs $APP_NAME --tail 100'"
echo "- Если Weaviate проблемы: 'dokku config:set $APP_NAME FORCE_FAISS=true'"
echo "- Для перезапуска: 'dokku ps:restart $APP_NAME'"