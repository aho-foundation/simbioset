"""Настройки приложения"""

import os
from pathlib import Path
from dotenv import load_dotenv
from api.logger import root_logger as logger

load_dotenv()

WEBHOOK_URL = "https://simbioset.ru/bot"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
default_models = [
    "deepseek-r1",
    "deepseek-v3",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gpt-oss-120b",
    "llama-4-maverick",
    "llama-4-scout",
    "qwen-3-0.6b",
    "qwen-3-1.7b",
    "qwen-3-14b",
    "qwen-3-235b",
    "qwen-3-30b",
    "qwen-3-32b",
    "qwen-3-4b",
    "command-a",
    "command-r",
    "command-r7b",
    "o4-mini",
]

MODELS_LIST = os.getenv("MODELS_LIST", default_models)

# Корневая директория проекта
ROOT_DIR = Path(__file__).parent.absolute()
DEV_SERVER_PID_FILE_NAME = "dev-server.pid"
PORT = os.getenv("PORT") or 5000

# DB
DB_URL = (
    os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or os.getenv("DB_URL", "").replace("postgres://", "postgresql://")
    or "sqlite:///simbioset.db"
)
DATABASE_URL = DB_URL
DATABASE_PATH = os.getenv("DATABASE_PATH") or "simbioset.db"

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


# 💾 Настройка локального кеша для HuggingFace моделей
def get_index_dump_dir() -> str:
    """Определяет лучшую папку для индекса векторного поиска"""
    # Используем ту же логику, что и для моделей
    return get_models_cache_dir()


def get_models_cache_dir() -> str:
    """Определяет лучшую папку для кеша моделей"""
    # Приоритетные пути для кеша моделей (от лучшего к худшему)
    cache_paths = [
        "/app/.cache",  # Shared cache storage (Dokku mount)
        "/app/models",  # Models storage (Dokku mount)
        "./models",  # Local fallback
    ]

    for cache_path in cache_paths:
        path = Path(cache_path)
        logger.info(
            f"🔍 Checking {cache_path} - exists: {path.exists()}, writable: {os.access(str(path), os.W_OK) if path.exists() else 'N/A'}"
        )

        if path.exists() and os.access(str(path), os.W_OK):
            logger.info(f"✅ Using cache directory: {path}")
            return str(path)

    # Если ничего не подошло, создаем локальную директорию
    cache_dir = Path("./models")
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Using local fallback: {cache_dir}")
    return str(cache_dir)


MODELS_CACHE_DIR = get_models_cache_dir()
HF_HOME = MODELS_CACHE_DIR
# Сохраняем БД в директории моделей
DATABASE_PATH = os.path.join(MODELS_CACHE_DIR, "simbioset.db")
os.environ.setdefault("HF_HOME", MODELS_CACHE_DIR)
MODEL_PATH = MODELS_CACHE_DIR

# Search service configuration
SEARCH_MAX_BATCH_SIZE = int(os.getenv("SEARCH_MAX_BATCH_SIZE", "25"))
SEARCH_CACHE_ENABLED = bool(os.getenv("SEARCH_CACHE_ENABLED", "true").lower() in ["true", "1", "yes"])
SEARCH_CACHE_TTL_SECONDS = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "300"))
SEARCH_PREFETCH_SIZE = int(os.getenv("SEARCH_PREFETCH_SIZE", "200"))
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Управление автоматическими детекторами при сохранении параграфов
# По умолчанию выключено, чтобы не ломать UX быстрого чата.
ENABLE_AUTOMATIC_DETECTORS = bool(os.getenv("ENABLE_AUTOMATIC_DETECTORS", "false").lower() in ["true", "1", "yes"])

# LLM Proxy Service
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "https://llm.simbioset.ru")
LLM_PROXY_TOKEN = os.getenv("LLM_PROXY_TOKEN", "")

# Weaviate Vector Database
# HTTP URL для REST API операций (схема, управление)
WEAVIATE_URL = os.getenv("WEAVIATE_URL")  # Если не задан, будет вычислен из gRPC URL
# gRPC URL для векторных операций (поиск, вставка) - основной протокол
WEAVIATE_GRPC_URL = os.getenv("WEAVIATE_GRPC_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", None)  # Optional, если используется аутентификация
# Имя класса в Weaviate для хранения параграфов (можно переопределить через env для тестирования/миграций)
WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME", "Paragraph")
