#!/bin/bash
# Очистка старых shared-cache mounts и вывод текущих storage mounts
# Использование: bash cleanup_old_shared_cache.sh [APP_NAME]
# Если APP_NAME не указан - обрабатывает все приложения

set -e

# Функция для обработки одного приложения
process_app() {
    local APP="$1"
    
    if [ -z "$APP" ] || ! dokku apps:exists "$APP" 2>/dev/null; then
        echo "⚠️  Приложение $APP не существует, пропускаем"
        return
    fi
    
    echo "📦 Приложение: $APP"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Получаем все storage mounts
    local STORAGE_REPORT=$(dokku storage:report "$APP" 2>/dev/null || echo "")
    
    if [ -z "$STORAGE_REPORT" ]; then
        echo "  Нет storage mounts"
        echo ""
        return
    fi
    
    # Выводим все mounts
    echo "  Storage mounts:"
    echo "$STORAGE_REPORT" | grep -E "Storage (build|deploy|run) mounts:" | sed 's/^/    /' || true
    
    # Извлекаем все mounts из deploy и run (формат: -v /path:/mount)
    local MOUNTS_LINE=$(echo "$STORAGE_REPORT" | grep -E "Storage (deploy|run) mounts:" | sed 's/.*: *//' || echo "")
    
    if [ -z "$MOUNTS_LINE" ] || [ "$MOUNTS_LINE" = "" ]; then
        echo "  Нет mounts для обработки"
        echo ""
        return
    fi
    
    # Разбиваем строку на отдельные mounts
    local REMOVED=0
    
    # Удаляем старые shared-cache mounts
    echo ""
    echo "  Удаление старых shared-cache mounts..."
    
    # Парсим mounts из строки (формат: -v /path1:/mount1 -v /path2:/mount2 ...)
    for mount in $MOUNTS_LINE; do
        if echo "$mount" | grep -q "shared-cache"; then
            # Извлекаем путь из mount (формат: -v /path:/mount)
            local MOUNT_PATH=$(echo "$mount" | sed 's/-v //')
            echo "    Удаляем: $MOUNT_PATH"
            dokku storage:unmount "$APP" "$MOUNT_PATH" 2>/dev/null && REMOVED=$((REMOVED + 1)) || true
        fi
    done
    
    if [ $REMOVED -eq 0 ]; then
        echo "    Старых shared-cache mounts не найдено"
    else
        echo "    ✅ Удалено $REMOVED старых mounts"
    fi
    
    # Показываем обновленный список
    echo ""
    echo "  Обновленные storage mounts:"
    dokku storage:report "$APP" 2>/dev/null | grep -E "Storage (build|deploy|run) mounts:" | sed 's/^/    /' || true
    
    echo ""
}

# Если указано имя приложения - обрабатываем только его
if [ -n "$1" ]; then
    process_app "$1"
else
    # Иначе обрабатываем все приложения
    echo "🔍 Поиск и очистка старых shared-cache mounts..."
    echo ""
    
    APPS=$(dokku apps:list 2>/dev/null | grep -E '^[a-z0-9][a-z0-9-]*$' | grep -v '^$' || echo "")
    
    if [ -z "$APPS" ]; then
        echo "⚠️  Не найдено Dokku приложений"
        exit 0
    fi
    
    for APP in $APPS; do
        process_app "$APP"
    done
    
    echo "✅ Очистка завершена!"
fi
