#!/bin/bash
# Тестировать подключение к Weaviate из контейнера приложения

APP_NAME="${1:-simbioset-website}"

echo "🔗 Тестируем подключение к Weaviate из $APP_NAME..."

# Проверяем статус Weaviate
echo "🔍 Статус Weaviate:"
if dokku ps:report weaviate 2>/dev/null | grep -q "running"; then
    echo "✅ Weaviate запущен"
else
    echo "❌ Weaviate не запущен"
    exit 1
fi

# Тестируем подключение через Dokku run
echo ""
echo "🌐 Тестируем подключение через Dokku run..."
dokku run "$APP_NAME" bash -c "
echo '🌐 Тестируем DNS разрешение...'
nslookup weaviate 2>/dev/null || echo '❌ DNS разрешение weaviate не работает'

echo ''
echo '🔍 Переменные окружения:'
echo \"WEAVIATE_URL: \$WEAVIATE_URL\"
echo \"FORCE_FAISS: \$FORCE_FAISS\"

echo ''
echo '🌐 Тестируем HTTP подключение...'
if [ -n \"\$WEAVIATE_URL\" ]; then
    curl -v --max-time 5 \"\$WEAVIATE_URL/v1/meta\" 2>&1 | head -10
else
    echo '⚠️  WEAVIATE_URL не установлен'
fi

echo ''
echo '🐳 Проверяем сеть Dokku...'
ping -c 2 weaviate 2>/dev/null || echo '❌ Ping weaviate не работает'
"

echo ""
echo "✅ Тест завершен"