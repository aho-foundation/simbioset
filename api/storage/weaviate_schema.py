"""Заглушка для совместимости - теперь используется встроенная AutoSchema Weaviate

⚠️  ВНИМАНИЕ: Этот файл оставлен только для совместимости импортов.
Теперь используется встроенная AutoSchema Weaviate, которая автоматически
создает и адаптирует схему на основе добавляемых данных.

Настройки AutoSchema (два уровня):

1. Уровень Weaviate сервера (в переменных окружения Weaviate):
   - AUTOSCHEMA_ENABLED=true (включить AutoSchema в Weaviate)
   - AUTOSCHEMA_DEFAULT_NUMBER=number
   - AUTOSCHEMA_DEFAULT_DATE=date

2. Уровень приложения (в переменных окружения приложения):
   - WEAVIATE_USE_BUILTIN_AUTOSCHEMA=true (по умолчанию: true)
   - WEAVIATE_AUTOSCHEMA_DEFAULT_NUMBER=number (опционально)
   - WEAVIATE_AUTOSCHEMA_DEFAULT_DATE=date (опционально)

См. документацию:
- docs/infra/WEAVIATE_AUTOSCHEMA_SETUP.md - настройка AutoSchema
- docs/infra/WEAVIATE_DEPLOY_AUTOSCHEMA.md - развертывание с AutoSchema
"""


def update_schema_if_needed(client) -> bool:
    """Заглушка - схема управляется Weaviate автоматически через AutoSchema"""
    return False


def create_schema_if_not_exists(client) -> None:
    """Заглушка - схема создается Weaviate автоматически при добавлении данных"""
    pass
