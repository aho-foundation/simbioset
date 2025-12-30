## Документация проекта

### Хранилище и миграция
- `vector_db_comparison.md` — сравнение векторных БД (FAISS, Qdrant, Milvus, Weaviate)
- `weaviate_classification.md` — автоматическая классификация и NER в Weaviate
- `infra/storage_analysis.md` — обзор хранилища и дублирования данных

### Инфраструктура Weaviate
- `infra/WEAVIATE_DOKKU_SETUP.md` — развертывание Weaviate в Dokku
- `infra/WEAVIATE_APP_LINKING.md` — подключение приложений Dokku к Weaviate
- `infra/WEAVIATE_AUTHENTICATION.md` — настройка аутентификации Weaviate (API Key)
- `infra/WEAVIATE_LOCAL_SETUP.md` — локальный запуск Weaviate без Docker для разработки и тестирования
- `infra/WEAVIATE_GRAPHQL_TYPES.md` — GraphQL Schema-First для генерации типов фронтенда
- `infra/WEAVIATE_SOLIDJS.md` — использование Weaviate в SolidJS с runtime валидацией
- `infra/WEAVIATE_SCHEMA_WORKFLOW.md` — workflow работы со схемой и синхронизация типов
- `infra/WEAVIATE_SCHEMA_FIRST.md` — schema-first подход для данных
- `infra/WEAVIATE_CLASSIFICATION_EXAMPLES.md` — примеры для классификации тегов в Weaviate

### Кеширование и оптимизация
- `infra/dockerfile_cache_setup.md` — настройка кешей менеджеров пакетов

### Агенты и архитектура
- `agent/detectors_architecture.md` — архитектура детекторов и их API.
- `agent/llm.md` и `agent/holistic_model.md` — описание LLM-архитектуры, ретраев только на бэкенде и общей модели.
- `agent/conversation_tree_framework.md` — фреймворк дерева диалога.
- `agent/agree_agent.md` — агентная система AgREE для дополнения графа знаний новыми сущностями.
- `agent/rag_and_memory_best_practices.md` — лучшие практики для RAG и долгосрочной памяти с двумя графами.


