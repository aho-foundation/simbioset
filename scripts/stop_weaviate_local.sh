#!/bin/bash
# Скрипт для остановки локального Weaviate

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🛑 Остановка локального Weaviate${NC}"

# Пытаемся остановить по PID из файла
if [ -f .weaviate.pid ]; then
    PID=$(cat .weaviate.pid)
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}Остановка процесса $PID...${NC}"
        kill "$PID" 2>/dev/null || true
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Принудительная остановка...${NC}"
            kill -9 "$PID" 2>/dev/null || true
        fi
        rm .weaviate.pid
        echo -e "${GREEN}✅ Weaviate остановлен${NC}"
    else
        echo -e "${YELLOW}⚠️  Процесс $PID не найден${NC}"
        rm .weaviate.pid
    fi
fi

# Также пытаемся остановить все процессы weaviate
if pgrep -x "weaviate" > /dev/null; then
    echo -e "${YELLOW}Остановка всех процессов weaviate...${NC}"
    pkill weaviate || true
    sleep 1
    if pgrep -x "weaviate" > /dev/null; then
        pkill -9 weaviate || true
    fi
    echo -e "${GREEN}✅ Все процессы Weaviate остановлены${NC}"
else
    echo -e "${YELLOW}⚠️  Процессы Weaviate не найдены${NC}"
fi
