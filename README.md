# Simbioset Website

Веб-приложение для анализа экосистем и симбиотических связей организмов с использованием ИИ.

## 🚀 Быстрый старт

### Frontend (SolidJS)
```bash
npm install
npm run dev
# Откройте http://localhost:3000 для просмотра приложения
```

**Новый компонент поиска параграфов:**
- Используйте `ParagraphSearch` компонент для поиска в Weaviate
- Пример: `<ParagraphSearch documentId="chat_123" limit={20} />`

### Backend (Python/FastAPI)
```bash
# Активировать виртуальное окружение
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Запустить сервер
python -m api.main
```

### Weaviate (локально для разработки)
```bash
# Запустить Weaviate локально
./scripts/start_weaviate_local.sh

# В другом терминале запустить тесты
source .venv/bin/activate
pytest tests/test_weaviate_integration.py --weaviate-local
```

## 🏗️ Архитектура

- **Frontend**: SolidJS + TypeScript
- **Backend**: Python FastAPI + PostgreSQL
- **Vector Store**: Weaviate (мигрировано с FAISS)
- **AI**: OpenAI GPT + локальные модели
- **Deployment**: Dokku

## 📚 Документация

- [Обзор архитектуры](docs/README.md)
- [Миграция на Weaviate](docs/weaviate_classification.md)
- [Сравнение векторных БД](docs/vector_db_comparison.md)
- [Развертывание Weaviate](docs/infra/WEAVIATE_DOKKU_SETUP.md)

## 🧪 Тестирование

```bash
# Backend тесты
pytest tests/

# Frontend тесты
npm test

# E2E тесты
npx playwright test
```

## 🚀 Деплой

### Dokku
```bash
# Быстрое восстановление (если приложение не работает)
./scripts/quick_fix.sh simbioset-website

# Исправление проблем с Weaviate портами
./scripts/fix_weaviate_ports.sh

# Диагностика проблем
./scripts/diagnose.sh simbioset-website

# Полная настройка Weaviate (см. docs/infra/WEAVIATE_DOKKU_SETUP.md)
dokku apps:create weaviate
./scripts/setup_dokku_cache.sh weaviate

# Подключить приложение к Weaviate
dokku config:set simbioset-website \
  WEAVIATE_URL=http://weaviate:8080 \
  WEAVIATE_GRPC_URL=weaviate:50051 \
  FORCE_FAISS=false  # Отключить принудительный FAISS

# Развернуть приложение
git push dokku main
```

### Troubleshooting

#### Health Checks
```bash
# Проверить здоровье приложения
curl https://simbioset.ru/health

# Проверить логи приложения
dokku logs simbioset-website --tail 50
```

#### Weaviate Issues
Приложение автоматически проверяет доступность Weaviate при старте и логирует статус:

```
🔍 Проверяем доступность Weaviate на http://weaviate:8080
✅ Weaviate доступен: версия 1.35.1, модули: ['text2vec-transformers']
🎯 Weaviate доступен, инициализируем WeaviateStorage...
✅ WeaviateStorage инициализирован успешно
```

Если Weaviate недоступен, приложение переключается на FAISS:

```
⚠️ Weaviate недоступен (DNS resolution failed), используем FAISSStorage
✅ FAISSStorage инициализирован (fallback)
```

**Принудительное отключение Weaviate:**
```bash
dokku config:set simbioset-website FORCE_FAISS=true
dokku ps:restart simbioset-website
```

#### Диагностика проблем:

```bash
# Быстрая диагностика
./scripts/diagnose.sh simbioset-website

# Быстрое восстановление (включает FAISS)
./scripts/quick_fix.sh simbioset-website

# Исправление проблем с портами Weaviate
./scripts/fix_weaviate_ports.sh

# Ручная диагностика:
# Проверить статус приложений
dokku ps:report simbioset-website
dokku ps:report weaviate

# Проверить переменные окружения
dokku config:show simbioset-website | grep -E "(WEAVIATE|FORCE_FAISS)"

# Проверить логи
dokku logs simbioset-website --tail 50
dokku logs weaviate --tail 50

# Проверить API Weaviate
curl http://localhost:8080/v1/meta
```

## 📊 Мониторинг

- **Health check endpoint**: `/health` - проверка готовности приложения
- **Docker health checks**: встроены в Dockerfile для автоматического перезапуска
- Логи через `dokku logs <app>`
- Метрики через `/metrics` endpoint (если настроено)

## 🔧 Разработка

### Переменные окружения
```bash
# Копировать шаблон
cp .env.example .env

# Настроить значения
WEAVIATE_URL=http://localhost:8080
OPENAI_API_KEY=your_key_here
DATABASE_URL=postgresql://...
```

### Код качества
```bash
# Backend
ruff check . --fix
mypy .

# Frontend
npm run typecheck
npm run format
```

## 📝 Контрибьютинг

1. Создать feature branch
2. Написать тесты
3. Обновить документацию
4. Создать PR

## 📄 Лицензия

MIT
