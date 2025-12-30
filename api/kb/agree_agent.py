"""
Агентная система для дополнения графа знаний новыми сущностями и связями.

Реализует подход AgREE (Agentic Reasoning for Knowledge Graph Completion on Emerging Entities):
- Итеративный поиск информации о новых организмах
- Multi-step reasoning для построения триплетов
- Автоматическое дополнение графа знаний
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from api.llm import call_llm_with_retry
from api.detect.web_search import WebSearchService
from api.classify.organism_classifier import classify_organism_role
from api.storage.symbiotic_service import SymbioticService
from api.storage.organism_service import OrganismService
from api.storage.ecosystem_service import EcosystemService
from api.logger import root_logger

log = root_logger.debug


class AgREEAgent:
    """Агент для дополнения графа знаний новыми сущностями и связями."""

    def __init__(
        self,
        symbiotic_service: SymbioticService,
        organism_service: OrganismService,
        ecosystem_service: EcosystemService,
        web_search_service: Optional[WebSearchService] = None,
        max_iterations: int = 5,
    ):
        """Инициализация агента.

        Args:
            symbiotic_service: Сервис для работы с симбиотическими связями
            organism_service: Сервис для работы с организмами
            ecosystem_service: Сервис для работы с экосистемами
            web_search_service: Сервис для веб-поиска (опционально)
            max_iterations: Максимальное количество итераций поиска
        """
        self.symbiotic_service = symbiotic_service
        self.organism_service = organism_service
        self.ecosystem_service = ecosystem_service
        self.web_search_service = web_search_service or WebSearchService()
        self.max_iterations = max_iterations

        # Загружаем промпт
        prompt_path = Path(__file__).parent.parent / "prompts" / "agree_agent.txt"
        if not prompt_path.exists():
            prompt_path = Path("api/prompts/agree_agent.txt")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
        except FileNotFoundError:
            log("⚠️ Промпт agree_agent.txt не найден, используем упрощенный вариант")
            self.prompt_template = """Ты агент для дополнения графа знаний. Найди информацию об организме и создай триплеты.
Организм: {organism_name}
Верни JSON с полями: sufficient, triplets, gaps, next_search_query."""

    async def complete_knowledge_for_organism(
        self,
        organism_name: str,
        organism_type: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Дополняет граф знаний информацией об организме.

        Args:
            organism_name: Название организма
            organism_type: Тип организма (опционально)
            context: Контекст упоминания (опционально)

        Returns:
            Словарь с результатами:
            {
                "organism_id": "id организма",
                "triplets_created": ["id1", "id2", ...],
                "iterations": 3,
                "final_info": {...}
            }
        """
        log(f"🔍 AgREE: Начинаю дополнение графа знаний для организма '{organism_name}'")

        # Проверяем, есть ли уже организм в БД
        existing_organism = await self._find_existing_organism(organism_name)
        if existing_organism:
            organism_id = existing_organism["id"]
            log(f"✅ Организм '{organism_name}' уже существует в БД: {organism_id}")
        else:
            # Классифицируем организм
            classification = await classify_organism_role(organism_name, organism_type, context)
            organism_id = await self._create_organism(organism_name, organism_type, classification, context)

        # Итеративный поиск и дополнение
        retrieved_info: List[Dict[str, Any]] = []
        triplets_created = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            log(f"🔄 AgREE: Итерация {iteration}/{self.max_iterations}")

            # Получаем известную информацию об организме
            known_info = await self._get_known_info(organism_id)

            # Генерируем поисковый запрос
            if iteration == 1:
                search_query = f"{organism_name} симбиоз экосистема"
            else:
                # Используем LLM для генерации следующего запроса
                search_query = await self._generate_search_query(organism_name, known_info, retrieved_info)

            # Выполняем поиск
            search_results = await self.web_search_service.search_and_extract(search_query, max_results=3)
            retrieved_info.extend(search_results)

            # Анализируем найденную информацию и генерируем триплеты
            analysis = await self._analyze_and_generate_triplets(
                organism_name=organism_name,
                organism_type=organism_type,
                context=context,
                known_info=known_info,
                retrieved_info=retrieved_info,
            )

            # Создаем триплеты
            if analysis.get("triplets"):
                created = await self._create_triplets(organism_id, analysis["triplets"])
                triplets_created.extend(created)

            # Проверяем достаточность информации
            if analysis.get("sufficient", False):
                log(f"✅ AgREE: Информация достаточна после {iteration} итераций")
                break

            # Если не достигли максимума, продолжаем
            if iteration >= self.max_iterations:
                log(f"⚠️ AgREE: Достигнут максимум итераций ({self.max_iterations})")

        return {
            "organism_id": organism_id,
            "triplets_created": triplets_created,
            "iterations": iteration,
            "final_info": {
                "known_info": known_info,
                "retrieved_info_count": len(retrieved_info),
            },
        }

    async def _find_existing_organism(self, organism_name: str) -> Optional[Dict[str, Any]]:
        """Ищет существующий организм в БД по названию.

        Args:
            organism_name: Название организма

        Returns:
            Словарь с информацией об организме или None
        """
        cursor = self.organism_service.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM organisms 
            WHERE name = ? OR scientific_name = ?
            LIMIT 1
            """,
            (organism_name, organism_name),
        )

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def _create_organism(
        self,
        organism_name: str,
        organism_type: Optional[str],
        classification: Dict[str, Any],
        context: Optional[str],
    ) -> str:
        """Создает новый организм в БД.

        Args:
            organism_name: Название организма
            organism_type: Тип организма
            classification: Результат классификации
            context: Контекст упоминания

        Returns:
            ID созданного организма
        """
        import uuid

        organism_id = f"org_{uuid.uuid4()}"
        biochemical_roles_json = json.dumps(classification.get("biochemical_roles", []))
        metabolic_pathways_json = json.dumps(classification.get("metabolic_pathways", []))

        cursor = self.organism_service.db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO organisms 
            (id, name, scientific_name, type, trophic_level, 
             biochemical_roles, metabolic_pathways, context, classification_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organism_id,
                organism_name,
                None,  # scientific_name будет заполнен позже
                organism_type or "другое",
                classification.get("trophic_level", "unknown"),
                biochemical_roles_json,
                metabolic_pathways_json,
                context or "",
                classification.get("confidence", 0.0),
            ),
        )

        self.organism_service.db_manager.connection.commit()
        log(f"✅ Создан организм {organism_id}: {organism_name}")

        return organism_id

    async def _get_known_info(self, organism_id: str) -> Dict[str, Any]:
        """Получает известную информацию об организме из БД.

        Args:
            organism_id: ID организма

        Returns:
            Словарь с известной информацией
        """
        cursor = self.organism_service.db_manager.connection.cursor()
        cursor.execute("SELECT * FROM organisms WHERE id = ?", (organism_id,))
        row = cursor.fetchone()

        if not row:
            return {}

        row_dict = dict(row)
        # Парсим JSON поля
        if row_dict.get("biochemical_roles"):
            try:
                row_dict["biochemical_roles"] = json.loads(row_dict["biochemical_roles"])
            except (json.JSONDecodeError, TypeError):
                row_dict["biochemical_roles"] = []
        else:
            row_dict["biochemical_roles"] = []

        if row_dict.get("metabolic_pathways"):
            try:
                row_dict["metabolic_pathways"] = json.loads(row_dict["metabolic_pathways"])
            except (json.JSONDecodeError, TypeError):
                row_dict["metabolic_pathways"] = []
        else:
            row_dict["metabolic_pathways"] = []

        # Получаем существующие связи
        relationships = self.symbiotic_service.get_relationships_for_organism(organism_id)
        row_dict["relationships"] = relationships

        return row_dict

    async def _generate_search_query(
        self,
        organism_name: str,
        known_info: Dict[str, Any],
        retrieved_info: List[Dict[str, Any]],
    ) -> str:
        """Генерирует поисковый запрос на основе известной информации и пробелов.

        Args:
            organism_name: Название организма
            known_info: Известная информация
            retrieved_info: Уже найденная информация

        Returns:
            Поисковый запрос
        """
        # Простая эвристика: ищем то, чего еще нет
        if not known_info.get("scientific_name"):
            return f"{organism_name} научное название"
        if not known_info.get("relationships"):
            return f"{organism_name} симбиоз взаимодействие"
        if not known_info.get("trophic_level") or known_info.get("trophic_level") == "unknown":
            return f"{organism_name} трофический уровень экосистема"

        return f"{organism_name} экосистема взаимодействие"

    async def _analyze_and_generate_triplets(
        self,
        organism_name: str,
        organism_type: Optional[str],
        context: Optional[str],
        known_info: Dict[str, Any],
        retrieved_info: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Анализирует найденную информацию и генерирует триплеты.

        Args:
            organism_name: Название организма
            organism_type: Тип организма
            context: Контекст упоминания
            known_info: Известная информация
            retrieved_info: Найденная информация

        Returns:
            Словарь с анализом и триплетами
        """
        # Формируем контекст для промпта
        known_info_str = json.dumps(known_info, ensure_ascii=False, indent=2)
        retrieved_info_str = "\n\n".join(
            [
                f"**{r.get('title', 'Без названия')}**\n{r.get('content', '')[:1000]}"
                for r in retrieved_info[-3:]  # Последние 3 результата
            ]
        )

        # Получаем примеры триплетов (если есть)
        example_triplets = []
        if known_info.get("relationships"):
            example_triplets = [
                f"({r.get('organism1_id')}, {r.get('relationship_type')}, {r.get('organism2_id')})"
                for r in known_info["relationships"][:3]
            ]

        # Формируем промпт
        prompt = self.prompt_template.format(
            organism_name=organism_name,
            organism_type=organism_type or "неизвестно",
            context=context or "",
            known_info=known_info_str,
            retrieved_info=retrieved_info_str,
            example_triplets="\n".join(example_triplets) if example_triplets else "Нет примеров",
        )

        try:
            response = await call_llm_with_retry(prompt, origin="agree_agent", context_size_hint="normal")

            # Парсим JSON из ответа
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return analysis
            else:
                log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response}")
                return {
                    "sufficient": False,
                    "triplets": [],
                    "gaps": ["Не удалось распарсить ответ"],
                    "next_search_query": "",
                }
        except Exception as e:
            log(f"⚠️ Ошибка при анализе информации: {e}")
            return {"sufficient": False, "triplets": [], "gaps": [str(e)], "next_search_query": ""}

    async def _create_triplets(
        self,
        organism_id: str,
        triplets: List[Dict[str, Any]],
    ) -> List[str]:
        """Создает триплеты в БД.

        Args:
            organism_id: ID организма (subject)
            triplets: Список триплетов для создания

        Returns:
            Список ID созданных связей
        """
        created_ids = []

        for triplet in triplets:
            try:
                # Находим или создаем объект триплета (другой организм или экосистема)
                object_name = triplet.get("object", "")
                object_id = await self._find_or_create_object(object_name, triplet.get("level", "inter_organism"))

                if not object_id:
                    log(f"⚠️ Не удалось найти/создать объект '{object_name}' для триплета")
                    continue

                # Проверяем, не существует ли уже такая связь
                if triplet.get("level") == "ecosystem":
                    # Для экосистемы создаем связь через organism_ecosystems
                    # Но для симбиотических связей нужны два организма
                    continue

                # Для межорганизменных связей нужен второй организм
                if triplet.get("level") in ["intra_organism", "inter_organism"]:
                    if object_id.startswith("org_"):
                        # Проверяем, не существует ли уже связь
                        if self.symbiotic_service.relationship_exists(organism_id, object_id):
                            log(f"ℹ️ Связь между {organism_id} и {object_id} уже существует")
                            continue

                        # Создаем симбиотическую связь
                        relationship_id = self.symbiotic_service.create_relationship(
                            organism1_id=organism_id,
                            organism2_id=object_id,
                            relationship_type=triplet.get("predicate", "neutral"),
                            description=triplet.get("description"),
                            biochemical_exchange=triplet.get("biochemical_exchange"),
                            ecosystem_id=None,  # Можно добавить позже
                            level=triplet.get("level", "inter_organism"),
                            strength=triplet.get("strength", 0.5),
                        )
                        created_ids.append(relationship_id)
                        log(f"✅ Создан триплет: {organism_id} - {triplet.get('predicate')} - {object_id}")

            except Exception as e:
                log(f"⚠️ Ошибка при создании триплета: {e}")

        return created_ids

    async def _find_or_create_object(self, object_name: str, level: str) -> Optional[str]:
        """Находит или создает объект триплета (организм или экосистема).

        Args:
            object_name: Название объекта
            level: Уровень взаимодействия

        Returns:
            ID объекта или None
        """
        if level == "ecosystem":
            # Ищем экосистему
            cursor = self.ecosystem_service.db_manager.connection.cursor()
            cursor.execute("SELECT id FROM ecosystems WHERE name = ? LIMIT 1", (object_name,))
            row = cursor.fetchone()
            if row:
                return row[0]

            # Создаем экосистему (упрощенно)
            # В реальности нужно больше информации
            return None
        else:
            # Ищем организм
            existing = await self._find_existing_organism(object_name)
            if existing:
                return existing["id"]

            # Создаем организм (упрощенно)
            # В реальности нужно больше информации
            return None
