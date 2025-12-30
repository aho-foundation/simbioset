#!/bin/bash
# Полное восстановление приложения после проблем
set -e

APP_NAME="${1:-simbioset-website}"

echo "🚀 Полное восстановление $APP_NAME..."
echo "====================================="

# Шаг 1: Диагностика
echo ""
echo "1️⃣ Диагностика текущего состояния..."
./scripts/diagnose.sh "$APP_NAME"

# Шаг 2: Настройка storage
echo ""
echo "2️⃣ Настройка storage..."
./scripts/setup_storage.sh "$APP_NAME"

# Шаг 3: Остановка проблемных сервисов
echo ""
echo "3️⃣ Очистка проблемных контейнеров..."
docker stop $(docker ps -q --filter "name=weaviate") 2>/dev/null || true
docker rm $(docker ps -a -q --filter "name=weaviate") 2>/dev/null || true

# Шаг 4: Перезапуск Weaviate
echo ""
echo "4️⃣ Перезапуск Weaviate..."
if dokku ps:report weaviate 2>/dev/null | grep -q "running"; then
    echo "✅ Weaviate уже запущен"
else
    dokku ps:start weaviate 2>/dev/null || echo "⚠️  Weaviate не удалось запустить"
fi

# Шаг 5: Настройка приложения
echo ""
echo "5️⃣ Настройка приложения..."
# Включаем FAISS для надежного старта
dokku config:set "$APP_NAME" FORCE_FAISS=true

# Шаг 6: Перезапуск приложения
echo ""
echo "6️⃣ Перезапуск приложения..."
dokku ps:rebuild "$APP_NAME"

# Шаг 7: Финальная проверка
echo ""
echo "7️⃣ Финальная проверка..."
sleep 10
./scripts/diagnose.sh "$APP_NAME"

echo ""
echo "🎉 Восстановление завершено!"
echo ""
echo "💡 Следующие шаги:"
echo "- Если все работает: dokku config:set $APP_NAME FORCE_FAISS=false"
echo "- Для подключения к Weaviate: dokku config:set $APP_NAME WEAVIATE_URL=http://weaviate:8080"
echo "- Перезапустите: dokku ps:restart $APP_NAME"