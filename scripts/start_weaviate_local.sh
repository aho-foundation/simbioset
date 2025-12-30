#!/bin/bash
# Скрипт для локального запуска Weaviate без Docker

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Запуск Weaviate локально (без Docker)${NC}"

# Проверяем, установлен ли Weaviate
WEAVIATE_BINARY="${WEAVIATE_BINARY:-weaviate}"

if ! command -v "$WEAVIATE_BINARY" &> /dev/null; then
    echo -e "${RED}❌ Weaviate не найден. Установите Weaviate:${NC}"
    echo ""
    echo "Способ 1: Скачать бинарник с GitHub Releases:"
    echo "  wget https://github.com/weaviate/weaviate/releases/latest/download/weaviate-<OS>-<ARCH> -O weaviate"
    echo "  chmod +x weaviate"
    echo "  sudo mv weaviate /usr/local/bin/"
    echo ""
    echo "Способ 2: Использовать Docker (если доступен):"
    echo "  docker run -d -p 8080:8080 -p 50051:50051 semitechnologies/weaviate:latest"
    echo ""
    echo "Способ 3: Установить через Homebrew (macOS):"
    echo "  brew install weaviate"
    echo ""
    exit 1
fi

# Создаем директорию для данных
DATA_DIR="${WEAVIATE_DATA_DIR:-./.weaviate-data}"
mkdir -p "$DATA_DIR"

echo -e "${YELLOW}📁 Директория данных: $DATA_DIR${NC}"

# Проверяем, не запущен ли уже Weaviate
if curl -s http://localhost:8080/v1/meta > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Weaviate уже запущен на http://localhost:8080${NC}"
    echo "Используйте существующий экземпляр или остановите его:"
    echo "  pkill weaviate"
    exit 0
fi

# Запускаем Weaviate
echo -e "${GREEN}🔄 Запуск Weaviate...${NC}"

# Запускаем Weaviate с переменными окружения (новый API)
PERSISTENCE_DATA_PATH="$DATA_DIR" \
DEFAULT_VECTORIZER_MODULE=none \
ENABLE_MODULES="" \
"$WEAVIATE_BINARY" \
    --host 0.0.0.0 \
    --port 8080 \
    &

WEAVIATE_PID=$!

# Ждем запуска
echo -e "${YELLOW}⏳ Ожидание запуска Weaviate...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8080/v1/meta > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Weaviate запущен успешно!${NC}"
        echo ""
        echo "URL: http://localhost:8080"
        echo "GraphQL: http://localhost:8080/v1/graphql"
        echo "PID: $WEAVIATE_PID"
        echo ""
        echo "Для остановки: kill $WEAVIATE_PID"
        echo "Или используйте: pkill weaviate"
        echo ""
        echo "Переменные окружения для приложения:"
        echo "  export WEAVIATE_URL=http://localhost:8080"
        echo "  export WEAVIATE_GRPC_URL=localhost:50051"
        echo ""
        
        # Сохраняем PID в файл для удобной остановки
        echo "$WEAVIATE_PID" > .weaviate.pid
        echo "PID сохранен в .weaviate.pid"
        
        # Ждем завершения процесса
        wait $WEAVIATE_PID
        exit 0
    fi
    sleep 1
done

# Если не запустился
echo -e "${RED}❌ Weaviate не запустился за 30 секунд${NC}"
kill $WEAVIATE_PID 2>/dev/null || true
exit 1
