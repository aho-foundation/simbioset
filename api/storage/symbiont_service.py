"""
Сервис для работы с симбионтами и патогенами в Weaviate.

Предоставляет методы для создания, поиска и управления симбионтами и патогенами
с иерархической структурой и связями с организмами и экосистемами.
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

from api.storage.weaviate_storage import WeaviateStorage
from api.logger import root_logger

log = root_logger.debug


class SymbiontPathogen:
    """Модель симбионта или патогена.

    Note: organism_ecological_role описывает роль конкретного организма в экосистеме.
    Общий ecological impact экосистемы должен вычисляться отдельно на основе
    состава видов и связей в ней, а не быть статичным полем.
    """

    def __init__(
        self,
        id: str,
        name: str,
        scientific_name: Optional[str] = None,
        type: str = "symbiont",  # symbiont, pathogen, commensal, parasite
        category: Optional[str] = None,
        host_organism_id: Optional[str] = None,
        parent_symbiont_id: Optional[str] = None,
        interaction_type: str = "mutualistic",
        biochemical_role: Optional[str] = None,
        transmission_method: Optional[str] = None,
        virulence_factors: Optional[List[str]] = None,
        symbiotic_benefits: Optional[List[str]] = None,
        organism_ecological_role: Optional[
            str
        ] = None,  # Роль организма в экосистеме (не общий ecological impact экосистемы)
        geographic_distribution: Optional[str] = None,
        prevalence: float = 0.0,
        risk_level: str = "low",
        detection_confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.name = name
        self.scientific_name = scientific_name
        self.type = type
        self.category = category
        self.host_organism_id = host_organism_id
        self.parent_symbiont_id = parent_symbiont_id
        self.interaction_type = interaction_type
        self.biochemical_role = biochemical_role
        self.transmission_method = transmission_method
        self.virulence_factors = virulence_factors or []
        self.symbiotic_benefits = symbiotic_benefits or []
        self.organism_ecological_role = organism_ecological_role
        self.geographic_distribution = geographic_distribution
        self.prevalence = prevalence
        self.risk_level = risk_level
        self.detection_confidence = detection_confidence
        self.metadata = metadata or {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbiontPathogen":
        """Создает объект из словаря."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            scientific_name=data.get("scientific_name"),
            type=data.get("type", "symbiont"),
            category=data.get("category"),
            host_organism_id=data.get("host_organism_id"),
            parent_symbiont_id=data.get("parent_symbiont_id"),
            interaction_type=data.get("interaction_type", "mutualistic"),
            biochemical_role=data.get("biochemical_role"),
            transmission_method=data.get("transmission_method"),
            virulence_factors=data.get("virulence_factors", []),
            symbiotic_benefits=data.get("symbiotic_benefits", []),
            organism_ecological_role=data.get("organism_ecological_role"),
            geographic_distribution=data.get("geographic_distribution"),
            prevalence=data.get("prevalence", 0.0),
            risk_level=data.get("risk_level", "low"),
            detection_confidence=data.get("detection_confidence", 0.0),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь для Weaviate."""
        return {
            "id": self.id,
            "name": self.name,
            "scientific_name": self.scientific_name,
            "type": self.type,
            "category": self.category,
            "host_organism_id": self.host_organism_id,
            "parent_symbiont_id": self.parent_symbiont_id,
            "interaction_type": self.interaction_type,
            "biochemical_role": self.biochemical_role,
            "transmission_method": self.transmission_method,
            "virulence_factors": self.virulence_factors,
            "symbiotic_benefits": self.symbiotic_benefits,
            "organism_ecological_role": self.organism_ecological_role,
            "geographic_distribution": self.geographic_distribution,
            "prevalence": self.prevalence,
            "risk_level": self.risk_level,
            "detection_confidence": self.detection_confidence,
            "metadata": self.metadata,
        }


class SymbiontService:
    """Сервис для управления симбионтами и патогенами."""

    def __init__(self, weaviate_storage: WeaviateStorage):
        self.weaviate = weaviate_storage
        self.class_name = "SymbiontPathogen"

    async def create_symbiont(self, symbiont: SymbiontPathogen) -> str:
        """
        Создает нового симбионта/патогена в Weaviate.

        Args:
            symbiont: Объект симбионта/патогена

        Returns:
            ID созданного объекта
        """
        try:
            # Преобразуем объект в данные для Weaviate
            data = symbiont.to_dict()

            # Генерируем эмбеддинг для названия
            embedding_text = f"{symbiont.name} {symbiont.scientific_name or ''} {symbiont.biochemical_role or ''}"
            embedding = self.weaviate._create_embedding(embedding_text)

            # Добавляем объект в Weaviate как документ
            # Convert to paragraph format for compatibility
            paragraph_data = {
                "text": f"{symbiont.name} {symbiont.scientific_name or ''}",
                "document_id": f"symbiont_{symbiont.id}",
                "document_type": "symbiont",
                "metadata": data,
            }
            self.weaviate.add_documents([paragraph_data], f"symbiont_{symbiont.id}")

            log(f"✅ Создан симбионт/патоген: {symbiont.name} (ID: {symbiont.id})")
            return symbiont.id

        except Exception as e:
            log(f"❌ Ошибка создания симбионта/патогена {symbiont.name}: {e}")
            raise

    async def get_symbiont(self, symbiont_id: str) -> Optional[SymbiontPathogen]:
        """
        Получает симбионта/патогена по ID.

        Args:
            symbiont_id: ID симбионта/патогена

        Returns:
            Объект симбионта/патогена или None
        """
        try:
            # Get paragraph by ID and extract symbiont data from metadata
            paragraph = self.weaviate.get_paragraph_by_id(f"symbiont_{symbiont_id}", symbiont_id)
            if paragraph and paragraph.metadata:
                return SymbiontPathogen.from_dict(paragraph.metadata)
            return None

        except Exception as e:
            log(f"❌ Ошибка получения симбионта/патогена {symbiont_id}: {e}")
            return None

    async def search_symbionts(
        self,
        query: str,
        type_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        host_organism_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[SymbiontPathogen]:
        """
        Ищет симбионтов/патогенов по текстовому запросу с фильтрами.

        Args:
            query: Текстовый запрос для поиска
            type_filter: Фильтр по типу (symbiont, pathogen, etc.)
            category_filter: Фильтр по категории
            host_organism_id: Фильтр по организму-хозяину
            limit: Максимальное количество результатов

        Returns:
            Список найденных симбионтов/патогенов
        """
        try:
            # Создаем фильтры
            filters = []
            if type_filter:
                filters.append({"path": ["type"], "operator": "Equal", "valueString": type_filter})
            if category_filter:
                filters.append({"path": ["category"], "operator": "Equal", "valueString": category_filter})
            if host_organism_id:
                filters.append({"path": ["host_organism_id"], "operator": "Equal", "valueString": host_organism_id})

            # Выполняем поиск среди документов symbiont типа
            paragraphs = await self.weaviate.search_similar_paragraphs(
                query=query,
                document_id="symbiont_documents",  # This might need adjustment
                top_k=limit,
            )

            # Преобразуем результаты
            symbionts = []
            for paragraph in paragraphs:
                if paragraph.metadata:
                    try:
                        symbiont = SymbiontPathogen.from_dict(paragraph.metadata)
                        symbionts.append(symbiont)
                    except Exception:
                        continue

            return symbionts

        except Exception as e:
            log(f"❌ Ошибка поиска симбионтов/патогенов: {e}")
            return []

    async def get_symbionts_by_host(self, host_organism_id: str) -> List[SymbiontPathogen]:
        """
        Получает всех симбионтов/патогенов для заданного организма-хозяина.

        Args:
            host_organism_id: ID организма-хозяина

        Returns:
            Список симбионтов/патогенов
        """
        try:
            # Получаем все документы symbiont типа и фильтруем вручную
            all_docs = self.weaviate.get_all_documents()
            symbiont_docs = [doc for doc in all_docs if doc.startswith("symbiont_")]

            symbionts = []
            for doc_id in symbiont_docs[:100]:  # Ограничиваем для производительности
                paragraphs = self.weaviate.get_document_paragraphs(doc_id)
                for paragraph in paragraphs:
                    if paragraph.metadata and paragraph.metadata.get("host_organism_id") == host_organism_id:
                        try:
                            symbiont = SymbiontPathogen.from_dict(paragraph.metadata)
                            symbionts.append(symbiont)
                        except Exception:
                            continue

            return symbionts

        except Exception as e:
            log(f"❌ Ошибка получения симбионтов для хозяина {host_organism_id}: {e}")
            return []

    async def get_child_symbionts(self, parent_symbiont_id: str) -> List[SymbiontPathogen]:
        """
        Получает дочерние симбионты/патогены для иерархической структуры.

        Args:
            parent_symbiont_id: ID родительского симбионта

        Returns:
            Список дочерних симбионтов/патогенов
        """
        try:
            # Получаем все документы symbiont типа и фильтруем вручную
            all_docs = self.weaviate.get_all_documents()
            symbiont_docs = [doc for doc in all_docs if doc.startswith("symbiont_")]

            symbionts = []
            for doc_id in symbiont_docs[:50]:  # Ограничиваем для производительности
                paragraphs = self.weaviate.get_document_paragraphs(doc_id)
                for paragraph in paragraphs:
                    if paragraph.metadata and paragraph.metadata.get("parent_symbiont_id") == parent_symbiont_id:
                        try:
                            symbiont = SymbiontPathogen.from_dict(paragraph.metadata)
                            symbionts.append(symbiont)
                        except Exception:
                            continue

            return symbionts

        except Exception as e:
            log(f"❌ Ошибка получения дочерних симбионтов для {parent_symbiont_id}: {e}")
            return []

    async def update_symbiont(self, symbiont_id: str, updates: Dict[str, Any]) -> bool:
        """
        Обновляет данные симбионта/патогена.

        Args:
            symbiont_id: ID симбионта для обновления
            updates: Поля для обновления

        Returns:
            True если обновление успешно
        """
        try:
            # Get current paragraph, update metadata, and save back
            paragraph = self.weaviate.get_paragraph_by_id(f"symbiont_{symbiont_id}", symbiont_id)
            if paragraph and paragraph.metadata:
                paragraph.metadata.update(updates)
                success = self.weaviate.update_paragraph(f"symbiont_{symbiont_id}", paragraph)
                if success:
                    log(f"✅ Обновлен симбионт/патоген {symbiont_id}")
                    return True
            return False

        except Exception as e:
            log(f"❌ Ошибка обновления симбионта/патогена {symbiont_id}: {e}")
            return False

    async def delete_symbiont(self, symbiont_id: str) -> bool:
        """
        Удаляет симбионта/патогена.

        Args:
            symbiont_id: ID симбионта для удаления

        Returns:
            True если удаление успешно
        """
        try:
            success = self.weaviate.delete_paragraph(f"symbiont_{symbiont_id}", symbiont_id)
            if success:
                log(f"✅ Удален симбионт/патоген {symbiont_id}")
                return True
            return False

        except Exception as e:
            log(f"❌ Ошибка удаления симбионта/патогена {symbiont_id}: {e}")
            return False
