"""Схема Weaviate для класса Paragraph (v4 API)"""

import weaviate
from api.settings import WEAVIATE_CLASS_NAME
from api.logger import root_logger

log = root_logger.debug


def create_schema_if_not_exists(client: weaviate.WeaviateClient) -> None:
    """Создает схему класса Paragraph в Weaviate, если она еще не существует.

    Args:
        client: Клиент Weaviate
    """
    try:
        # Проверяем, существует ли класс (v4 API)
        if client.collections.exists(WEAVIATE_CLASS_NAME):
            log(f"ℹ️  Класс {WEAVIATE_CLASS_NAME} уже существует в Weaviate")
            return

        # Создаем класс (v4 API)
        from weaviate.classes.config import Configure, Property, DataType

        # Metadata не включаем в схему Weaviate - он используется только для временных данных
        # (ecosystems, organisms) при обработке, которые затем сохраняются в отдельные поля.
        # В SQLite metadata остается для обратной совместимости.
        properties = [
            Property(name="content", data_type=DataType.TEXT),
            Property(name="document_id", data_type=DataType.TEXT),
            Property(name="node_id", data_type=DataType.TEXT),
            Property(name="document_type", data_type=DataType.TEXT),
            Property(name="session_id", data_type=DataType.TEXT),
            Property(name="organism_ids", data_type=DataType.TEXT_ARRAY),
            Property(name="ecosystem_id", data_type=DataType.TEXT),
            Property(name="location", data_type=DataType.TEXT),
            Property(name="tags", data_type=DataType.TEXT_ARRAY),
            Property(name="timestamp", data_type=DataType.DATE),
            Property(name="author", data_type=DataType.TEXT),
            Property(name="author_id", data_type=DataType.INT),
            Property(name="paragraph_index", data_type=DataType.INT),
        ]

        client.collections.create(
            name=WEAVIATE_CLASS_NAME,
            description="Параграф документа для векторного поиска",
            vectorizer_config=Configure.Vectorizer.none(),
            properties=properties,
        )
        log(f"✅ Схема класса {WEAVIATE_CLASS_NAME} создана в Weaviate")

    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "name already present" in error_msg:
            log(f"ℹ️  Класс {WEAVIATE_CLASS_NAME} уже существует")
        else:
            log(f"❌ Ошибка создания схемы {WEAVIATE_CLASS_NAME}: {e}")
            raise
