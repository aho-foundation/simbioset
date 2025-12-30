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
# Развернуть Weaviate
dokku apps:create weaviate
./scripts/setup_dokku_cache.sh weaviate
# ... см. docs/infra/WEAVIATE_DOKKU_SETUP.md

# Развернуть приложение
git push dokku main
```

## 📊 Мониторинг

- Health checks встроены в Dockerfile
- Логи через `dokku logs <app>`
- Метрики через `/metrics` endpoint

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
