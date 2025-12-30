"""
Тесты новой схемы базы данных для хранения узлов знаний и параграфов.

Проверяет работу с таблицами:
- knowledge_nodes (узлы знаний)
- paragraphs (параграфы документов и диалогов)
- vectors (векторные представления для FAISS)
- node_children (связи parent-child)
- ecosystems (экосистемы)
- organisms (организмы)
- organism_ecosystems (связи организм-экосистема)
- symbiotic_relationships (симбиотические связи)
"""

import pytest
import sqlite3
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

from api.storage.db import DatabaseManager


class TestStorageSchema:
    """Тесты новой схемы базы данных для хранения узлов знаний и параграфов."""

    def setup_method(self):
        """Настройка тестов - создаем временную БД и инициализируем схему."""
        # Создаем временный файл БД
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Инициализируем DatabaseManager
        self.db_manager = DatabaseManager(db_path=self.db_path)
        self.db_manager.connect()

        # Включаем поддержку внешних ключей в SQLite (требуется для CASCADE DELETE)
        self.db_manager.connection.execute("PRAGMA foreign_keys = ON")

        # Загружаем и выполняем схему
        schema_path = Path(__file__).parent.parent / "api" / "storage" / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # Выполняем схему
        self.db_manager.connection.executescript(schema_sql)
        self.db_manager.connection.commit()

    def teardown_method(self):
        """Очистка после тестов."""
        if self.db_manager.connection:
            self.db_manager.disconnect()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_schema_tables_exist(self):
        """Тест: проверяем, что все таблицы созданы."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "knowledge_nodes",
            "paragraphs",
            "documents",
            "vectors",
            "metadata",
            "node_children",
        ]

        for table in expected_tables:
            assert table in tables, f"Таблица {table} не найдена"

    def test_knowledge_nodes_create(self):
        """Тест: создание узла знания."""
        node_id = "test_node_1"
        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO knowledge_nodes 
            (id, content, type, category, timestamp, role, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                "Тестовый узел знания",
                "message",
                "neutral",
                timestamp,
                "user",
                "session_1",
            ),
        )
        self.db_manager.connection.commit()

        # Проверяем, что узел создан
        cursor.execute("SELECT * FROM knowledge_nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["content"] == "Тестовый узел знания"
        assert row["type"] == "message"
        assert row["category"] == "neutral"
        assert row["role"] == "user"
        assert row["session_id"] == "session_1"

    def test_knowledge_nodes_parent_child(self):
        """Тест: создание иерархии узлов (parent-child)."""
        parent_id = "parent_node"
        child_id = "child_node"
        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()

        # Создаем родительский узел
        cursor.execute(
            """
            INSERT INTO knowledge_nodes 
            (id, content, type, category, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (parent_id, "Родительский узел", "message", "neutral", timestamp),
        )

        # Создаем дочерний узел
        cursor.execute(
            """
            INSERT INTO knowledge_nodes 
            (id, parent_id, content, type, category, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                child_id,
                parent_id,
                "Дочерний узел",
                "message",
                "neutral",
                timestamp,
            ),
        )

        # Добавляем связь в node_children
        cursor.execute(
            """
            INSERT INTO node_children (parent_id, child_id, child_order)
            VALUES (?, ?, ?)
            """,
            (parent_id, child_id, 0),
        )

        self.db_manager.connection.commit()

        # Проверяем parent_id
        cursor.execute("SELECT parent_id FROM knowledge_nodes WHERE id = ?", (child_id,))
        row = cursor.fetchone()
        assert row["parent_id"] == parent_id

        # Проверяем node_children
        cursor.execute("SELECT child_id FROM node_children WHERE parent_id = ?", (parent_id,))
        children = [row[0] for row in cursor.fetchall()]
        assert child_id in children

    def test_paragraphs_create_from_node(self):
        """Тест: создание параграфа из узла знания."""
        node_id = "test_node_2"
        paragraph_id = "para_1"
        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()

        # Создаем узел
        cursor.execute(
            """
            INSERT INTO knowledge_nodes 
            (id, content, type, category, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (node_id, "Узел с параграфом", "message", "neutral", timestamp),
        )

        # Создаем параграф из узла
        cursor.execute(
            """
            INSERT INTO paragraphs 
            (id, content, node_id, document_type, paragraph_index, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                paragraph_id,
                "Содержимое параграфа из узла",
                node_id,
                "knowledge",
                0,
                timestamp,
            ),
        )

        self.db_manager.connection.commit()

        # Проверяем параграф
        cursor.execute("SELECT * FROM paragraphs WHERE id = ?", (paragraph_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["node_id"] == node_id
        assert row["document_type"] == "knowledge"
        assert row["paragraph_index"] == 0

    def test_paragraphs_create_from_document(self):
        """Тест: создание параграфов из документа."""
        document_id = "doc_1"
        paragraph_id_1 = "para_doc_1"
        paragraph_id_2 = "para_doc_2"
        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()

        # Создаем документ
        cursor.execute(
            """
            INSERT INTO documents (id, title, content, source_url)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, "Тестовый документ", "Полное содержимое документа", "https://example.com"),
        )

        # Создаем параграфы из документа
        for i, para_id in enumerate([paragraph_id_1, paragraph_id_2]):
            cursor.execute(
                """
                INSERT INTO paragraphs 
                (id, content, document_id, document_type, paragraph_index, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    para_id,
                    f"Параграф {i + 1} документа",
                    document_id,
                    "document",
                    i,
                    timestamp,
                ),
            )

        self.db_manager.connection.commit()

        # Проверяем параграфы
        cursor.execute(
            "SELECT * FROM paragraphs WHERE document_id = ? ORDER BY paragraph_index",
            (document_id,),
        )
        paragraphs = cursor.fetchall()
        assert len(paragraphs) == 2
        assert paragraphs[0]["paragraph_index"] == 0
        assert paragraphs[1]["paragraph_index"] == 1

    def test_paragraphs_classification(self):
        """Тест: классификация и fact-checking параграфов."""
        paragraph_id = "para_classified"
        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()

        # Используем tags (JSON массив) вместо несуществующей колонки classification
        tags_json = json.dumps(["ecosystem_risk"])

        cursor.execute(
            """
            INSERT INTO paragraphs 
            (id, content, document_type, tags, fact_check_result, 
             fact_check_details, location, time_reference, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paragraph_id,
                "Экосистема находится под угрозой",
                "knowledge",
                tags_json,
                "true",
                json.dumps({"source": "expert_analysis"}),
                "Москва",
                "2024",
                timestamp,
            ),
        )

        self.db_manager.connection.commit()

        # Проверяем классификацию
        cursor.execute("SELECT * FROM paragraphs WHERE id = ?", (paragraph_id,))
        row = cursor.fetchone()
        # Проверяем, что тег присутствует в JSON массиве
        tags = json.loads(row["tags"]) if row["tags"] else []
        assert "ecosystem_risk" in tags
        assert row["fact_check_result"] == "true"
        assert row["location"] == "Москва"
        assert row["time_reference"] == "2024"

    def test_vectors_create(self):
        """Тест: создание вектора для параграфа."""
        paragraph_id = "para_vector"
        vector_id = "vec_1"
        timestamp = int(datetime.now().timestamp() * 1000)
        embedding_dim = 384

        # Создаем тестовый вектор (384 измерения для multilingual-MiniLM)
        import numpy as np

        embedding = np.random.rand(embedding_dim).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)  # Нормализуем

        cursor = self.db_manager.connection.cursor()

        # Создаем параграф
        cursor.execute(
            """
            INSERT INTO paragraphs 
            (id, content, document_type, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (paragraph_id, "Параграф с вектором", "knowledge", timestamp),
        )

        # Создаем вектор
        cursor.execute(
            """
            INSERT INTO vectors 
            (id, paragraph_id, embedding, embedding_dimension, faiss_index_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (vector_id, paragraph_id, embedding.tobytes(), embedding_dim, 0),
        )

        self.db_manager.connection.commit()

        # Проверяем вектор
        cursor.execute("SELECT * FROM vectors WHERE id = ?", (vector_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["paragraph_id"] == paragraph_id
        assert row["embedding_dimension"] == embedding_dim

        # Проверяем, что вектор можно восстановить
        restored_embedding = np.frombuffer(row["embedding"], dtype=np.float32)
        assert len(restored_embedding) == embedding_dim
        assert np.allclose(restored_embedding, embedding)

    def test_cascade_delete(self):
        """Тест: каскадное удаление (при удалении узла удаляются параграфы и векторы)."""
        node_id = "node_cascade"
        paragraph_id = "para_cascade"
        vector_id = "vec_cascade"
        timestamp = int(datetime.now().timestamp() * 1000)

        import numpy as np

        cursor = self.db_manager.connection.cursor()

        # Создаем узел
        cursor.execute(
            """
            INSERT INTO knowledge_nodes 
            (id, content, type, category, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (node_id, "Узел для каскада", "message", "neutral", timestamp),
        )

        # Создаем параграф
        cursor.execute(
            """
            INSERT INTO paragraphs 
            (id, content, node_id, document_type, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (paragraph_id, "Параграф для каскада", node_id, "knowledge", timestamp),
        )

        # Создаем вектор
        embedding = np.random.rand(384).astype(np.float32)
        cursor.execute(
            """
            INSERT INTO vectors 
            (id, paragraph_id, embedding, embedding_dimension)
            VALUES (?, ?, ?, ?)
            """,
            (vector_id, paragraph_id, embedding.tobytes(), 384),
        )

        self.db_manager.connection.commit()

        # Удаляем узел (должны удалиться параграф и вектор)
        cursor.execute("DELETE FROM knowledge_nodes WHERE id = ?", (node_id,))
        self.db_manager.connection.commit()

        # Проверяем, что параграф удален
        cursor.execute("SELECT * FROM paragraphs WHERE id = ?", (paragraph_id,))
        assert cursor.fetchone() is None

        # Проверяем, что вектор удален
        cursor.execute("SELECT * FROM vectors WHERE id = ?", (vector_id,))
        assert cursor.fetchone() is None

    def test_indexes_exist(self):
        """Тест: проверяем наличие индексов для производительности."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = [row[0] for row in cursor.fetchall()]

        # Проверяем ключевые индексы
        important_indexes = [
            "idx_nodes_parent_id",
            "idx_nodes_type",
            "idx_nodes_session_id",
            "idx_paragraphs_node_id",
            "idx_paragraphs_document_id",
            "idx_vectors_paragraph_id",
            "idx_ecosystems_name",
            "idx_ecosystems_scale",
            "idx_organisms_name",
            "idx_organisms_trophic_level",
            "idx_organisms_internal_ecosystem_id",
            "idx_organism_ecosystems_organism_id",
            "idx_symbiotic_relationships_organism1",
        ]

        for idx in important_indexes:
            assert idx in indexes, f"Индекс {idx} не найден"

    def test_search_by_session(self):
        """Тест: поиск узлов по сессии."""
        session_id = "test_session"
        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()

        # Создаем несколько узлов в одной сессии
        for i in range(3):
            cursor.execute(
                """
                INSERT INTO knowledge_nodes 
                (id, content, type, category, session_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"node_session_{i}",
                    f"Узел {i} сессии",
                    "message",
                    "neutral",
                    session_id,
                    timestamp,
                ),
            )

        self.db_manager.connection.commit()

        # Ищем узлы по сессии
        cursor.execute("SELECT * FROM knowledge_nodes WHERE session_id = ?", (session_id,))
        nodes = cursor.fetchall()
        assert len(nodes) == 3

    def test_search_paragraphs_by_classification(self):
        """Тест: поиск параграфов по классификации."""
        import json

        timestamp = int(datetime.now().timestamp() * 1000)

        cursor = self.db_manager.connection.cursor()

        # Создаем параграфы с разной классификацией (используем tags JSON массив)
        classifications = ["ecosystem_risk", "ecosystem_vulnerability", "neutral"]
        for i, classification in enumerate(classifications):
            tags_json = json.dumps([classification])
            cursor.execute(
                """
                INSERT INTO paragraphs 
                (id, content, document_type, tags, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"para_class_{i}",
                    f"Параграф {i}",
                    "knowledge",
                    tags_json,
                    timestamp,
                ),
            )

        self.db_manager.connection.commit()

        # Ищем параграфы с ecosystem_risk используя JSON функции SQLite
        cursor.execute(
            """
            SELECT * FROM paragraphs 
            WHERE json_extract(tags, '$[0]') = ? 
            OR json_extract(tags, '$') LIKE ?
            """,
            ("ecosystem_risk", "%ecosystem_risk%"),
        )
        risk_paragraphs = cursor.fetchall()
        assert len(risk_paragraphs) == 1
        # Проверяем, что тег присутствует в JSON массиве
        tags = json.loads(risk_paragraphs[0]["tags"]) if risk_paragraphs[0]["tags"] else []
        assert "ecosystem_risk" in tags

    def test_ecosystems_table_exists(self):
        """Тест существования таблицы ecosystems."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ecosystems'")
        assert cursor.fetchone() is not None

    def test_organisms_table_exists(self):
        """Тест существования таблицы organisms."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organisms'")
        assert cursor.fetchone() is not None

    def test_organism_ecosystems_table_exists(self):
        """Тест существования таблицы organism_ecosystems."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organism_ecosystems'")
        assert cursor.fetchone() is not None

    def test_symbiotic_relationships_table_exists(self):
        """Тест существования таблицы symbiotic_relationships."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='symbiotic_relationships'")
        assert cursor.fetchone() is not None

    def test_create_ecosystem(self):
        """Тест создания экосистемы."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO ecosystems (id, name, description, location, scale)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("eco_test", "Лес", "Смешанный лес", "Московская область", "habitat"),
        )
        self.db_manager.connection.commit()

        cursor.execute("SELECT * FROM ecosystems WHERE id = ?", ("eco_test",))
        row = cursor.fetchone()
        assert row is not None
        assert dict(row)["name"] == "Лес"
        assert dict(row)["scale"] == "habitat"

    def test_create_organism_with_internal_ecosystem(self):
        """Тест создания организма с внутренней экосистемой."""
        # Создаем экосистему микробиома
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO ecosystems (id, name, scale)
            VALUES (?, ?, ?)
            """,
            ("eco_microbiome", "Микробиом кишечника", "organ"),
        )

        # Создаем организм с ссылкой на внутреннюю экосистему
        cursor.execute(
            """
            INSERT INTO organisms (id, name, type, internal_ecosystem_id)
            VALUES (?, ?, ?, ?)
            """,
            ("org_human", "человек", "животное", "eco_microbiome"),
        )
        self.db_manager.connection.commit()

        cursor.execute("SELECT internal_ecosystem_id FROM organisms WHERE id = ?", ("org_human",))
        row = cursor.fetchone()
        assert row[0] == "eco_microbiome"

    def test_link_organism_to_ecosystem(self):
        """Тест связывания организма с экосистемой."""
        cursor = self.db_manager.connection.cursor()

        # Создаем экосистему и организм
        cursor.execute(
            "INSERT INTO ecosystems (id, name, scale) VALUES (?, ?, ?)",
            ("eco_forest", "Лес", "habitat"),
        )
        cursor.execute(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            ("org_oak", "дуб", "растение"),
        )

        # Связываем
        cursor.execute(
            """
            INSERT INTO organism_ecosystems (organism_id, ecosystem_id, role_in_ecosystem, interaction_type)
            VALUES (?, ?, ?, ?)
            """,
            ("org_oak", "eco_forest", "продуцент", "symbiotic"),
        )
        self.db_manager.connection.commit()

        # Проверяем связь
        cursor.execute(
            "SELECT * FROM organism_ecosystems WHERE organism_id = ? AND ecosystem_id = ?",
            ("org_oak", "eco_forest"),
        )
        row = cursor.fetchone()
        assert row is not None
        assert dict(row)["role_in_ecosystem"] == "продуцент"

    def test_create_symbiotic_relationship(self):
        """Тест создания симбиотической связи."""
        cursor = self.db_manager.connection.cursor()

        # Создаем организмы и экосистему
        cursor.executemany(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            [("org_bee", "пчела", "животное"), ("org_flower", "цветок", "растение")],
        )
        cursor.execute(
            "INSERT INTO ecosystems (id, name, scale) VALUES (?, ?, ?)",
            ("eco_meadow", "Луг", "habitat"),
        )

        # Создаем симбиотическую связь
        cursor.execute(
            """
            INSERT INTO symbiotic_relationships 
            (id, organism1_id, organism2_id, relationship_type, level, ecosystem_id, strength)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("symb_1", "org_bee", "org_flower", "mutualism", "inter_organism", "eco_meadow", 0.9),
        )
        self.db_manager.connection.commit()

        # Проверяем связь
        cursor.execute("SELECT * FROM symbiotic_relationships WHERE id = ?", ("symb_1",))
        row = cursor.fetchone()
        assert row is not None
        assert dict(row)["relationship_type"] == "mutualism"
        assert dict(row)["level"] == "inter_organism"

    def test_ecosystem_cascade_delete(self):
        """Тест каскадного удаления экосистемы."""
        cursor = self.db_manager.connection.cursor()

        # Создаем экосистему и организм с внутренней экосистемой
        cursor.execute(
            "INSERT INTO ecosystems (id, name, scale) VALUES (?, ?, ?)",
            ("eco_parent", "Родительская", "habitat"),
        )
        cursor.execute(
            "INSERT INTO ecosystems (id, name, scale, parent_ecosystem_id) VALUES (?, ?, ?, ?)",
            ("eco_child", "Дочерняя", "micro_habitat", "eco_parent"),
        )
        cursor.execute(
            "INSERT INTO organisms (id, name, type, internal_ecosystem_id) VALUES (?, ?, ?, ?)",
            ("org_test", "организм", "животное", "eco_child"),
        )
        self.db_manager.connection.commit()

        # Удаляем дочернюю экосистему
        cursor.execute("DELETE FROM ecosystems WHERE id = ?", ("eco_child",))
        self.db_manager.connection.commit()

        # Проверяем, что организм остался, но internal_ecosystem_id стал NULL
        cursor.execute("SELECT internal_ecosystem_id FROM organisms WHERE id = ?", ("org_test",))
        row = cursor.fetchone()
        assert row[0] is None  # SET NULL при удалении

    def test_organism_ecosystem_cascade_delete(self):
        """Тест каскадного удаления связей организм-экосистема."""
        cursor = self.db_manager.connection.cursor()

        # Создаем экосистему и организм
        cursor.execute(
            "INSERT INTO ecosystems (id, name, scale) VALUES (?, ?, ?)",
            ("eco_test", "Лес", "habitat"),
        )
        cursor.execute(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            ("org_test", "дуб", "растение"),
        )
        cursor.execute(
            "INSERT INTO organism_ecosystems (organism_id, ecosystem_id) VALUES (?, ?)",
            ("org_test", "eco_test"),
        )
        self.db_manager.connection.commit()

        # Удаляем организм
        cursor.execute("DELETE FROM organisms WHERE id = ?", ("org_test",))
        self.db_manager.connection.commit()

        # Проверяем, что связь удалена
        cursor.execute("SELECT * FROM organism_ecosystems WHERE organism_id = ?", ("org_test",))
        assert cursor.fetchone() is None

    def test_ecosystem_scale_constraint(self):
        """Тест ограничения на масштаб экосистемы."""
        cursor = self.db_manager.connection.cursor()

        # Попытка создать экосистему с невалидным масштабом
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO ecosystems (id, name, scale) VALUES (?, ?, ?)",
                ("eco_invalid", "Тест", "invalid_scale"),
            )
            self.db_manager.connection.commit()

    def test_organism_type_constraint(self):
        """Тест ограничения на тип организма."""
        cursor = self.db_manager.connection.cursor()

        # Попытка создать организм с невалидным типом
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
                ("org_invalid", "Тест", "invalid_type"),
            )
            self.db_manager.connection.commit()

    def test_symbiotic_relationship_level_constraint(self):
        """Тест ограничения на уровень симбиотической связи."""
        cursor = self.db_manager.connection.cursor()

        cursor.executemany(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            [("org1", "организм1", "животное"), ("org2", "организм2", "растение")],
        )

        # Попытка создать связь с невалидным уровнем
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO symbiotic_relationships 
                (id, organism1_id, organism2_id, relationship_type, level)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("symb_invalid", "org1", "org2", "mutualism", "invalid_level"),
            )
            self.db_manager.connection.commit()

    def test_symbiotic_relationship_self_reference_check(self):
        """Тест проверки, что организм не может быть связан сам с собой."""
        cursor = self.db_manager.connection.cursor()

        cursor.execute(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            ("org_self", "организм", "животное"),
        )

        # Попытка создать связь организма с самим собой
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO symbiotic_relationships 
                (id, organism1_id, organism2_id, relationship_type, level)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("symb_self", "org_self", "org_self", "mutualism", "inter_organism"),
            )
            self.db_manager.connection.commit()
