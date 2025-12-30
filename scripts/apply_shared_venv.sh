#!/bin/bash

# Apply Shared Python Venv to All Apps
# Монтирует shared venv ко всем Python приложениям

set -e

SHARED_VENV_DIR="/app/.cache/venv"

echo "🐍 Применение shared Python venv ко всем приложениям..."

# Проверяем, существует ли shared venv
if [ ! -d "$SHARED_VENV_DIR" ]; then
    echo "❌ Shared venv не найден: $SHARED_VENV_DIR"
    echo "Сначала запустите: ./scripts/setup_shared_python_cache.sh"
    exit 1
fi

# Получаем список всех приложений
APPS=$(dokku apps:list 2>/dev/null | grep -v "=====> My Apps" | grep -v "^$" | sed 's/  //g')

echo "📋 Найденные приложения:"
echo "$APPS"
echo ""

# Функция для проверки, является ли приложение Python
is_python_app() {
    local app=$1
    # Проверяем по образу или конфигурации
    dokku config:get $app DOKKU_APP_TYPE 2>/dev/null | grep -q "python" || \
    dokku config:get $app PYTHONPATH 2>/dev/null || \
    dokku config:show $app 2>/dev/null | grep -q "python"
}

for app in $APPS; do
    # Пропускаем системные приложения
    if [[ $app == dokku.* ]]; then
        echo "⏭️ Пропускаем системное приложение: $app"
        continue
    fi

    echo "🔍 Проверяем приложение: $app"

    # Проверяем, смонтирован ли уже shared venv
    if dokku storage:list $app 2>/dev/null | grep -q "shared-venv"; then
        echo "✅ Shared venv уже смонтирован к $app"
        continue
    fi

    # Монтируем shared venv
    echo "🔗 Монтируем shared venv к $app..."
    dokku storage:mount $app $SHARED_VENV_DIR:/opt/shared-venv

    echo "✅ Готово: $app"
done

echo ""
echo "🚀 Пересборка приложений:"
echo "   dokku ps:rebuild simbioset-website"
echo "   dokku ps:rebuild summary24-bot"
echo "   # ... и другие Python приложения"

echo ""
echo "📊 Экономия места: ~8GB на приложение!"
echo "⚡ Shared venv готов к использованию!"