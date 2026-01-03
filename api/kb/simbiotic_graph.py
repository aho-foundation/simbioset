"""
Graph-Augmented RAG: Дополнение контекста через граф симбиотических связей.

Объединяет векторный поиск параграфов с графом симбиотических связей
для более богатого контекста при генерации ответов LLM.
"""

from typing import List, Dict, Any, Optional, Set
from api.storage.faiss import Paragraph
from api.storage.symbiotic_service import SymbioticService
from api.storage.organism_service import OrganismService
from api.storage.ecosystem_service import EcosystemService
from api.logger import root_logger

log = root_logger.debug


class SimbioticGraphContextBuilder:
    """Строитель контекста с использованием графа симбиотических связей."""

    def __init__(
        self,
        symbiotic_service: SymbioticService,
        organism_service: OrganismService,
        ecosystem_service: EcosystemService,
    ):
        """Инициализация строителя контекста.

        Args:
            symbiotic_service: Сервис для работы с симбиотическими связями
            organism_service: Сервис для работы с организмами
            ecosystem_service: Сервис для работы с экосистемами
        """
        self.symbiotic_service = symbiotic_service
        self.organism_service = organism_service
        self.ecosystem_service = ecosystem_service

    def extract_organism_ids_from_paragraphs(self, paragraphs: List[Paragraph]) -> List[str]:
        """Извлекает ID организмов из параграфов.

        Ищет organism_ids в metadata параграфов или находит организмы
        по paragraph_id в БД.

        Args:
            paragraphs: Список параграфов

        Returns:
            Список ID организмов
        """
        organism_ids: Set[str] = set()

        for para in paragraphs:
            # Пытаемся извлечь из metadata
            if para.metadata and "organism_ids" in para.metadata:
                ids = para.metadata["organism_ids"]
                if isinstance(ids, list):
                    organism_ids.update(ids)

            # Если нет в metadata, ищем в БД по paragraph_id
            if para.id:
                cursor = self.organism_service.db_manager.connection.cursor()
                cursor.execute("SELECT id FROM organisms WHERE paragraph_id = ?", (para.id,))
                rows = cursor.fetchall()
                for row in rows:
                    organism_ids.add(row[0])

        return list(organism_ids)

    def get_organism_name(self, organism_id: str) -> str:
        """Получает название организма по ID.

        Args:
            organism_id: ID организма

        Returns:
            Название организма или ID, если не найден
        """
        cursor = self.organism_service.db_manager.connection.cursor()
        cursor.execute("SELECT name FROM organisms WHERE id = ?", (organism_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return organism_id

    def expand_via_graph(
        self,
        organism_ids: List[str],
        max_depth: int = 2,
        max_relationships: int = 10,
    ) -> Dict[str, Any]:
        """Расширяет контекст через граф симбиотических связей.

        Args:
            organism_ids: Список ID организмов для расширения
            max_depth: Максимальная глубина обхода графа
            max_relationships: Максимальное количество связей для возврата

        Returns:
            Словарь с расширенным контекстом:
            {
                "related_organisms": [...],
                "relationships": [...],
                "ecosystems": [...]
            }
        """
        if not organism_ids:
            return {"related_organisms": [], "relationships": [], "ecosystems": []}

        visited_organisms: Set[str] = set(organism_ids)
        relationships: List[Dict[str, Any]] = []
        related_organism_ids: Set[str] = set()

        def traverse(organism_id: str, depth: int):
            """Рекурсивно обходит граф симбиотических связей."""
            if depth > max_depth or organism_id in visited_organisms:
                return

            visited_organisms.add(organism_id)

            # Получаем связи для организма
            org_relationships = self.symbiotic_service.get_relationships_for_organism(organism_id)

            for rel in org_relationships[:max_relationships]:
                # Определяем связанный организм
                other_org_id = rel["organism2_id"] if rel["organism1_id"] == organism_id else rel["organism1_id"]

                # Добавляем связь
                relationships.append(rel)
                related_organism_ids.add(other_org_id)

                # Продолжаем обход, если не достигли максимальной глубины
                if depth < max_depth:
                    traverse(other_org_id, depth + 1)

        # Начинаем обход с каждого организма
        for org_id in organism_ids:
            traverse(org_id, 0)

        # Получаем информацию об экосистемах
        ecosystems: List[Dict[str, Any]] = []
        ecosystem_ids: Set[str] = set()

        for rel in relationships:
            if rel.get("ecosystem_id"):
                ecosystem_ids.add(rel["ecosystem_id"])

        for eco_id in ecosystem_ids:
            ecosystem = self.ecosystem_service.get_ecosystem(eco_id)
            if ecosystem:
                ecosystems.append(ecosystem)

        return {
            "related_organisms": list(related_organism_ids),
            "relationships": relationships[:max_relationships],
            "ecosystems": ecosystems,
        }

    def format_graph_context(
        self,
        graph_context: Dict[str, Any],
        max_relationships: int = 10,
    ) -> str:
        """
        Форматирует графовый контекст для включения в промпт LLM.

        Использует структурированный формат в стиле Weaviate метрик:
        - Четкие категории и метки
        - Структурированная информация
        - Типы данных и статусы
        - Иерархическая организация

        Args:
            graph_context: Результат expand_via_graph
            max_relationships: Максимальное количество связей для форматирования

        Returns:
            Структурированная строка с графовым контекстом
        """
        context_parts = []

        # === СИМБИОТИЧЕСКИЕ СВЯЗИ ===
        relationships = graph_context.get("relationships", [])[:max_relationships]
        if relationships:
            context_parts.append("=== SYMBIOTIC RELATIONSHIPS ===")

            for i, rel in enumerate(relationships, 1):
                org1_id = rel.get("organism1_id", "")
                org2_id = rel.get("organism2_id", "")
                rel_type = rel.get("relationship_type", "unknown")
                level = rel.get("level", "inter_organism")
                description = rel.get("description", "")
                strength = rel.get("strength", 0.5)

                org1_name = self.get_organism_name(org1_id)
                org2_name = self.get_organism_name(org2_id)

                # Форматируем как Weaviate-style метрику
                context_parts.append(f"🔗 Relationship_{i}: {org1_name} → {org2_name}")
                context_parts.append(f"   ├── Type: {rel_type} | Level: {level}")
                context_parts.append(f"   ├── Status: active | Strength: {strength:.2f}")

                if description:
                    # Разбиваем длинное описание на строки
                    desc_lines = [description[i : i + 60] for i in range(0, len(description), 60)]
                    for j, desc_line in enumerate(desc_lines):
                        prefix = "   ├── Description:" if j == 0 else "   │   "
                        context_parts.append(f"{prefix} {desc_line}")

                # Добавляем метаданные если есть
                metadata = []
                if rel.get("biochemical_exchange"):
                    metadata.append("biochemical_exchange=yes")
                if rel.get("ecosystem_id"):
                    metadata.append("ecosystem_linked=yes")

                if metadata:
                    context_parts.append(f"   └── Metadata: {', '.join(metadata)}")
                else:
                    context_parts.append("   └── Metadata: none")
                context_parts.append("")  # Пустая строка между связями

        # === ЭКОСИСТЕМНЫЕ СУЩНОСТИ ===
        ecosystems = graph_context.get("ecosystems", [])
        if ecosystems:
            context_parts.append("=== ECOSYSTEM ENTITIES ===")

            for i, eco in enumerate(ecosystems[:5], 1):
                name = eco.get("name", "")
                description = eco.get("description", "")
                scale = eco.get("scale", "")
                location = eco.get("location", "")

                # Форматируем как Weaviate-style метрику
                context_parts.append(f"🌍 Entity_{i}: {name}")
                context_parts.append(f"   ├── Scale: {scale} | Type: ecosystem")
                context_parts.append(f"   ├── Status: active | Location: {location or 'unspecified'}")

                if description:
                    # Разбиваем длинное описание на строки
                    desc_lines = [description[i : i + 60] for i in range(0, len(description), 60)]
                    for j, desc_line in enumerate(desc_lines):
                        prefix = "   ├── Description:" if j == 0 else "   │   "
                        context_parts.append(f"{prefix} {desc_line}")

                # Добавляем метаданные если есть
                metadata = []
                if eco.get("parent_ecosystem_id"):
                    metadata.append("has_parent=yes")
                if eco.get("metabolic_characteristics"):
                    metadata.append("has_metabolism=yes")

                if metadata:
                    context_parts.append(f"   └── Metadata: {', '.join(metadata)}")
                else:
                    context_parts.append("   └── Metadata: none")
                context_parts.append("")  # Пустая строка между сущностями

        # === СИСТЕМНЫЕ МЕТРИКИ ===
        if relationships or ecosystems:
            context_parts.append("=== GRAPH METRICS ===")
            context_parts.append(f"📊 Total Relationships: {len(relationships)}")
            context_parts.append(f"📊 Total Ecosystems: {len(ecosystems)}")

            # Распределение типов связей
            if relationships:
                rel_types = [rel.get("relationship_type", "unknown") for rel in relationships]
                type_counts: dict[str, int] = {}
                for rel_type in rel_types:
                    type_counts[rel_type] = type_counts.get(rel_type, 0) + 1
                type_summary = ", ".join([f"{t}: {c}" for t, c in type_counts.items()])
                context_parts.append(f"📊 Relationship Types: {type_summary}")

            # Распределение масштабов экосистем
            if ecosystems:
                scales = [eco.get("scale", "unspecified") for eco in ecosystems]
                scale_counts: dict[str, int] = {}
                for scale in scales:
                    scale_counts[scale] = scale_counts.get(scale, 0) + 1
                scale_summary = ", ".join([f"{s}: {c}" for s, c in scale_counts.items()])
                context_parts.append(f"📊 Ecosystem Scales: {scale_summary}")

            context_parts.append("📊 Status: active | Type: ecological_graph")
            context_parts.append("⏱️ Timestamp: real-time | Source: knowledge_graph")

        # Если контекст пустой, возвращаем специальное сообщение
        if not context_parts:
            return "=== GRAPH CONTEXT ===\n📊 Status: inactive | Message: No graph relationships found"

        return "\n".join(context_parts)

    async def build_graph_augmented_context(
        self,
        paragraphs: List[Paragraph],
        max_depth: int = 2,
        max_relationships: int = 10,
    ) -> str:
        """Строит контекст, объединяя векторный поиск и граф симбиотических связей.

        Args:
            paragraphs: Найденные параграфы из векторного поиска
            max_depth: Максимальная глубина обхода графа
            max_relationships: Максимальное количество связей

        Returns:
            Объединенный контекст для LLM
        """
        if not paragraphs:
            return ""

        # Извлекаем организмы из параграфов
        organism_ids = self.extract_organism_ids_from_paragraphs(paragraphs)

        if not organism_ids:
            log("ℹ️ Не найдено организмов в параграфах для расширения через граф")
            return ""

        log(f"🔍 Найдено {len(organism_ids)} организмов в параграфах, расширяю через граф...")

        # Расширяем через граф
        graph_context = self.expand_via_graph(organism_ids, max_depth=max_depth, max_relationships=max_relationships)

        if not graph_context.get("relationships"):
            log("ℹ️ Не найдено симбиотических связей для расширения контекста")
            return ""

        # Форматируем графовый контекст
        formatted = self.format_graph_context(graph_context, max_relationships=max_relationships)

        log(f"✅ Расширен контекст через граф: {len(graph_context.get('relationships', []))} связей")

        return formatted

    def find_paragraphs_by_organisms(
        self,
        organism_ids: List[str],
        document_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Находит параграфы, связанные с организмами.

        Args:
            organism_ids: Список ID организмов
            document_id: ID документа для фильтрации (опционально)
            limit: Максимальное количество результатов

        Returns:
            Список словарей с информацией о параграфах
        """
        if not organism_ids:
            return []

        cursor = self.organism_service.db_manager.connection.cursor()

        # Строим запрос для поиска параграфов
        placeholders = ",".join(["?"] * len(organism_ids))
        query = f"""
            SELECT DISTINCT p.id, p.content, p.node_id, p.document_id, p.timestamp
            FROM paragraphs p
            INNER JOIN organisms o ON o.paragraph_id = p.id
            WHERE o.id IN ({placeholders})
        """

        params = list(organism_ids)

        if document_id:
            query += " AND p.document_id = ?"
            params.append(document_id)

        query += " ORDER BY p.timestamp DESC LIMIT ?"
        params.append(str(limit))

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append(
                {
                    "id": row[0],
                    "content": row[1][:500],  # Ограничиваем длину
                    "node_id": row[2],
                    "document_id": row[3],
                    "timestamp": row[4],
                }
            )

        return results
