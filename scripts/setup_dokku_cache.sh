#!/bin/bash

# Dokku Persistent Storage Cache Setup
# Настраивает кеширование Python/Node.js пакетов для ускорения сборки

set -e

APP_NAME="simbioset-website"

echo "🔧 Настройка Dokku persistent storage для кеширования..."

# Проверяем, что приложение существует
if ! dokku apps:exists $APP_NAME > /dev/null 2>&1; then
    echo "❌ Приложение $APP_NAME не найдено!"
    echo "Создайте приложение командой: dokku apps:create $APP_NAME"
    exit 1
fi

# Создаем директории для кешей
echo "📁 Создание директорий для кешей..."
sudo mkdir -p /var/lib/dokku/data/storage/shared/{pip,npm,ms-playwright,uv,cargo}
sudo mkdir -p /var/lib/dokku/data/storage/shared/venv/{bin,lib,include}

# Монтируем весь /app/.cache как единый persistent storage
echo "📦 Монтирование общего кеша..."
dokku storage:mount $APP_NAME /var/lib/dokku/data/storage/shared:/app/.cache

# Создаем необходимые директории в persistent storage
echo "📁 Создание директорий кеша..."
sudo mkdir -p /var/lib/dokku/data/storage/shared/{uv,pip,npm,ms-playwright,venv}
sudo mkdir -p /var/lib/dokku/data/storage/shared/venv/{bin,lib,include}

# Устанавливаем права доступа (UID 1000 - стандартный для Dokku приложений)
echo "🔐 Установка прав доступа..."
sudo chown -R 1000:1000 /var/lib/dokku/data/storage/shared
sudo chmod -R 755 /var/lib/dokku/data/storage/shared

# Persistent storage монтируется в /app/.cache

echo "✅ Dokku persistent storage настроен!"
echo ""
echo "💡 Для проверки: dokku storage:list $APP_NAME"
echo "💡 Для пересборки: dokku ps:rebuild $APP_NAME"