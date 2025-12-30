"""FastAPI application for Simbioset API."""

from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.kb.routes import router as routerKb
from api.chat.routes import router as routerChat
from api.chat.file_upload import router as routerFileUpload, init_file_upload_services
from api.projects.routes import router as routerProjects
from api.bot.routes import router as routerBot
from api.storage.routes import router as routerStorage
from api.classify.tag_routes import router as routerTags
from api.detect.routes import router as routerDetect


# Import session manager
from api.sessions import session_manager

# Import storage services
from api.storage.db_factory import create_database_manager
from api.storage.faiss import FAISSStorage
from api.storage.weaviate_storage import WeaviateStorage
from typing import Union
from api.storage.paragraph_service import ParagraphService
from api.classify.tag_service import TagService
from api.storage.nodes_repository import DatabaseNodeRepository
from api.kb.service import KBService
from api.settings import MODELS_CACHE_DIR, DATABASE_URL, DATABASE_PATH, WEAVIATE_URL
from api.logger import root_logger

log = root_logger.debug


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    log("🚀 Starting Simbioset API...")

    # Initialize storage services
    # Используем фабрику для автоматического выбора SQLite или PostgreSQL
    db_manager = create_database_manager(database_url=DATABASE_URL, db_path=DATABASE_PATH or "data/storage.db")
    db_manager.connect()

    # Выбираем хранилище: Weaviate если доступен и не отключен, иначе FAISS
    storage: Union[FAISSStorage, WeaviateStorage]

    # Если WEAVIATE_URL не задан - используем FAISS
    if not WEAVIATE_URL:
        log("🔄 WEAVIATE_URL не задан, инициализация FAISSStorage...")
        storage = FAISSStorage(cache_folder=MODELS_CACHE_DIR)
        log("✅ FAISSStorage инициализирован")
    # Если fallback отключен - пробуем Weaviate без fallback
    else:
        log("🔄 Fallback отключен, попытка инициализации WeaviateStorage...")
        storage = WeaviateStorage(cache_folder=MODELS_CACHE_DIR)
        log("✅ WeaviateStorage инициализирован")

    # Create database repository and KB service
    node_repo = DatabaseNodeRepository(db_manager)
    kb_service = KBService(node_repo)

    # Initialize tag service
    tag_service = TagService(db_manager)

    # Initialize file upload services (with tag_service)
    # Передаем storage (может быть FAISS или Weaviate)
    init_file_upload_services(db_manager, storage, kb_service, tag_service)

    # Store services in app state for access in routes
    app.state.db_manager = db_manager
    app.state.storage = storage  # Универсальное хранилище
    # Для обратной совместимости сохраняем как faiss_storage (если это FAISS)
    if isinstance(storage, FAISSStorage):
        app.state.faiss_storage = storage
    app.state.tag_service = tag_service

    # Связываем tag_service с storage для использования в классификации
    storage._tag_service = tag_service

    # ParagraphService принимает db_manager и storage (может быть FAISS или Weaviate)
    paragraph_service = ParagraphService(db_manager, storage)
    app.state.paragraph_service = paragraph_service
    app.state.kb_service = kb_service

    # Initialize user metrics service with kb_service
    from api.kb.user_metrics import init_user_metrics_service

    init_user_metrics_service(kb_service)

    # Загрузка параграфов из БД в хранилище (только для FAISS, для Weaviate не нужно)
    if isinstance(storage, FAISSStorage):
        try:
            log("🔄 Загрузка параграфов из БД в FAISS индекс...")
            loaded = paragraph_service.load_paragraphs_from_db()
            log(f"✅ Загружено {len(loaded)} параграфов в FAISS индекс")
        except Exception as e:
            log(f"⚠️ Ошибка при загрузке параграфов: {e}")
    else:
        log("ℹ️ WeaviateStorage: загрузка параграфов при старте не требуется (персистентное хранилище)")

    # Start the Telegram bot
    from api.bot.main import start_bot
    import asyncio

    # Run the bot in the background with kb_service
    asyncio.create_task(start_bot(kb_service=kb_service))

    log("✅ Simbioset API started successfully")

    yield

    # Shutdown
    log("🛑 Shutting down Simbioset API...")

    # Close LLM clients
    from api.llm import close_llm_clients

    await close_llm_clients()

    # Close Redis connection
    await session_manager.close()

    # Close database connection
    if hasattr(app.state, "db_manager") and app.state.db_manager.connection:
        app.state.db_manager.disconnect()

    log("✅ Simbioset API shut down successfully")


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware для загрузки сессий из Redis (async для оптимизации)."""

    async def dispatch(self, request: Request, call_next):
        """Загружает сессию из cookie и добавляет в request.state (async)."""
        session_id = request.cookies.get("session_id")
        if session_id:
            session_data = await session_manager.get_session(session_id)
            request.state.session = session_data
        else:
            request.state.session = None

        response = await call_next(request)
        return response


app = FastAPI(
    title="Simbioset API",
    version="1.0.0",
    description="Simbioset API for managing concept nodes",
    lifespan=lifespan,
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://simbioset.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware
app.add_middleware(SessionMiddleware)

# Include routes
app.include_router(routerKb)
app.include_router(routerFileUpload)
app.include_router(routerChat)
app.include_router(routerStorage)
app.include_router(routerTags)
app.include_router(routerProjects)
app.include_router(routerBot)
app.include_router(routerDetect)

# Монтируем статические файлы в /static, а не в корень
app.mount("/static", StaticFiles(directory=Path("dist")), name="static")


# Добавляем маршрут для корня, который будет обслуживать index.html для клиентского роутинга
@app.get("/")
async def read_root():
    from fastapi.responses import FileResponse

    return FileResponse(Path("dist") / "index.html")


# Добавляем маршрут для robots.txt
@app.get("/robots.txt")
async def robots_txt():
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse("User-agent: *\nDisallow: /\n", media_type="text/plain")


# Добавляем маршрут для обслуживания index.html для всех клиентских маршрутов
@app.get("/{full_path:path}")
async def serve_app(full_path: str):
    from fastapi.responses import FileResponse
    import os

    # Проверяем, существует ли файл на диске
    file_path = Path("dist") / full_path
    if file_path.is_file() and os.path.splitext(str(file_path))[1] in [
        ".js",
        ".css",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".json",
        ".txt",
        ".map",
    ]:
        # Если это файл ресурса, обслуживаем его напрямую
        return FileResponse(file_path)
    else:
        # Иначе обслуживаем index.html для клиентского роутинга
        return FileResponse(Path("dist") / "index.html")
