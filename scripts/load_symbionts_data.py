#!/usr/bin/env python3
"""
Скрипт для загрузки данных о симбионтах и патогенах в Weaviate.

Выкачивает информацию из различных источников и сохраняет в базе знаний
с иерархической структурой симбионтов и патогенов.
"""

import json
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
from datetime import datetime

# Импорты из проекта
import sys

sys.path.append("/Users/tony/code/simbioset-website")

from api.storage.weaviate_storage import WeaviateStorage
from api.storage.symbiont_service import SymbiontService, SymbiontPathogen
from api.logger import root_logger

log = root_logger.debug


class SymbiontsDataLoader:
    """Загрузчик данных о симбионтах и патогенах."""

    def __init__(self):
        self.weaviate_storage = WeaviateStorage()
        self.symbiont_service = SymbiontService(self.weaviate_storage)

    async def load_microbiome_data(self) -> List[Dict[str, Any]]:
        """
        Загружает данные о микробиоме человека из различных источников.

        Returns:
            Список данных о симбионтах микробиома
        """
        log("🔄 Загружаем данные о микробиоме человека...")

        # Примеры симбионтов микробиома человека
        microbiome_symbionts = [
            {
                "name": "Бифидобактерии",
                "scientific_name": "Bifidobacterium",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "ферментация углеводов, синтез витаминов B, защита от патогенов",
                "symbiotic_benefits": [
                    "переваривание грудного молока у младенцев",
                    "защита от кишечных инфекций",
                    "стимуляция иммунитета",
                ],
                "prevalence": 0.95,
                "risk_level": "low",
                "detection_confidence": 0.9,
            },
            {
                "name": "Лактобактерии",
                "scientific_name": "Lactobacillus",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "ферментация лактозы, синтез молочной кислоты, ингибирование патогенов",
                "symbiotic_benefits": [
                    "поддержание кислой среды в кишечнике",
                    "предотвращение роста вредных бактерий",
                    "синтез витаминов",
                ],
                "prevalence": 0.9,
                "risk_level": "low",
                "detection_confidence": 0.85,
            },
            {
                "name": "Бактероиды",
                "scientific_name": "Bacteroides",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "ферментация полисахаридов, синтез короткоцепочечных жирных кислот",
                "symbiotic_benefits": ["расщепление клетчатки", "защита слизистой кишечника", "регуляция иммунитета"],
                "prevalence": 0.8,
                "risk_level": "low",
                "detection_confidence": 0.8,
            },
            {
                "name": "Эшерихия коли (безвредные штаммы)",
                "scientific_name": "Escherichia coli (commensal strains)",
                "type": "commensal",
                "category": "бактерия",
                "interaction_type": "commensal",
                "biochemical_role": "конкуренция с патогенами, синтез витамина K",
                "symbiotic_benefits": [
                    "защита от патогенных бактерий",
                    "синтез витамина K",
                    "регуляция кишечной флоры",
                ],
                "prevalence": 0.7,
                "risk_level": "medium",  # Некоторые штаммы могут быть патогенными
                "detection_confidence": 0.75,
            },
        ]

        return microbiome_symbionts

    async def load_plant_symbionts(self) -> List[Dict[str, Any]]:
        """
        Загружает данные о симбионтах растений.

        Returns:
            Список данных о симбионтах растений
        """
        log("🔄 Загружаем данные о симбионтах растений...")

        plant_symbionts = [
            {
                "name": "Микориза",
                "scientific_name": "Mycorrhiza",
                "type": "symbiont",
                "category": "гриб",
                "interaction_type": "mutualistic",
                "biochemical_role": "усвоение фосфора и азота, защита от патогенов",
                "symbiotic_benefits": [
                    "повышение доступности питательных веществ",
                    "защита корней от патогенов",
                    "улучшение устойчивости к стрессу",
                ],
                "organism_ecological_role": "критично для большинства растений, повышает продуктивность экосистем",
                "prevalence": 0.9,
                "risk_level": "low",
                "detection_confidence": 0.85,
            },
            {
                "name": "Клубеньковые бактерии",
                "scientific_name": "Rhizobium",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "фиксация атмосферного азота",
                "symbiotic_benefits": [
                    "обеспечение растений азотом",
                    "повышение плодородия почвы",
                    "снижение потребности в удобрениях",
                ],
                "organism_ecological_role": "важно для бобовых растений и азотного цикла",
                "prevalence": 0.6,
                "risk_level": "low",
                "detection_confidence": 0.8,
            },
            {
                "name": "Эндосимбионты растений",
                "scientific_name": "Endophytic bacteria",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "защита от насекомых-вредителей, синтез гормонов роста",
                "symbiotic_benefits": ["защита от травоядных", "стимуляция роста", "повышение устойчивости к болезням"],
                "prevalence": 0.7,
                "risk_level": "low",
                "detection_confidence": 0.7,
            },
        ]

        return plant_symbionts

    async def load_pathogens(self) -> List[Dict[str, Any]]:
        """
        Загружает данные о патогенах.

        Returns:
            Список данных о патогенах
        """
        log("🔄 Загружаем данные о патогенах...")

        pathogens = [
            {
                "name": "Золотистый стафилококк",
                "scientific_name": "Staphylococcus aureus",
                "type": "pathogen",
                "category": "бактерия",
                "interaction_type": "pathogenic",
                "biochemical_role": "выработка токсинов, разрушение тканей",
                "transmission_method": "контактный, пищевой, воздушно-капельный",
                "virulence_factors": ["токсин TSST-1", "энтеротоксины", "протеин A"],
                "geographic_distribution": "всемирно",
                "prevalence": 0.3,
                "risk_level": "high",
                "detection_confidence": 0.95,
            },
            {
                "name": "Сальмонелла",
                "scientific_name": "Salmonella",
                "type": "pathogen",
                "category": "бактерия",
                "interaction_type": "pathogenic",
                "biochemical_role": "инвазия клеток кишечника, выработка эндотоксинов",
                "transmission_method": "пищевой, водный, контактный",
                "virulence_factors": ["инвазивность", "эндотоксины", "система секреции III типа"],
                "geographic_distribution": "всемирно",
                "prevalence": 0.15,
                "risk_level": "high",
                "detection_confidence": 0.9,
            },
            {
                "name": "Кандида albicans",
                "scientific_name": "Candida albicans",
                "type": "commensal",  # Может быть как комменсалом, так и патогеном
                "category": "гриб",
                "interaction_type": "commensal",
                "biochemical_role": "конкуренция с патогенами, регуляция иммунитета",
                "transmission_method": "эндогенный (из собственной микрофлоры)",
                "virulence_factors": ["переход в гифальную форму", "адгезия к тканям", "протеазы"],
                "geographic_distribution": "всемирно",
                "prevalence": 0.8,
                "risk_level": "medium",
                "detection_confidence": 0.85,
            },
        ]

        return pathogens

    async def create_symbiont_hierarchy(self) -> None:
        """
        Создает иерархическую структуру симбионтов.

        Организует симбионты в иерархические группы по типам и категориям.
        """
        log("🔄 Создаем иерархическую структуру симбионтов...")

        # Создаем родительские категории
        parent_categories = [
            {
                "name": "Микробиом человека",
                "type": "symbiont",
                "category": "микробиом",
                "biochemical_role": "внутренняя экосистема организма",
                "organism_ecological_role": "регуляция иммунитета, метаболизм, защита",
            },
            {
                "name": "Симбионты растений",
                "type": "symbiont",
                "category": "растения",
                "biochemical_role": "усвоение питательных веществ, защита",
                "organism_ecological_role": "продуктивность растений, почвенное плодородие",
            },
            {
                "name": "Патогены",
                "type": "pathogen",
                "category": "патогены",
                "biochemical_role": "вызывают заболевания",
                "organism_ecological_role": "регуляция популяций, естественный отбор",
            },
        ]

        # Создаем родительские объекты
        parent_ids = {}
        for category in parent_categories:
            parent_symbiont = SymbiontPathogen.from_dict(
                {
                    "id": str(uuid.uuid4()),
                    **category,
                    "detection_confidence": 1.0,
                }
            )
            await self.symbiont_service.create_symbiont(parent_symbiont)
            parent_ids[category["name"]] = parent_symbiont.id

        # Загружаем дочерние объекты
        datasets = [
            (await self.load_microbiome_data(), "Микробиом человека"),
            (await self.load_plant_symbionts(), "Симбионты растений"),
            (await self.load_pathogens(), "Патогены"),
        ]

        for data_list, parent_name in datasets:
            parent_id = parent_ids.get(parent_name)
            if not parent_id:
                continue

            for item in data_list:
                symbiont = SymbiontPathogen.from_dict(
                    {
                        "id": str(uuid.uuid4()),
                        **item,
                        "parent_symbiont_id": parent_id,
                    }
                )
                await self.symbiont_service.create_symbiont(symbiont)

        log("✅ Иерархическая структура симбионтов создана")

    async def load_from_external_sources(self) -> None:
        """
        Загружает данные из внешних источников (API, базы данных).

        Примеры источников:
        - PubMed API
        - NCBI databases
        - научные публикации
        """
        log("🔄 Загружаем данные из внешних источников...")

        # Пример загрузки из PubMed API (нужен API ключ)
        # В реальном проекте здесь будет интеграция с PubMed, NCBI, etc.

        # Пока создаем примеры на основе известных данных
        external_symbionts = [
            {
                "name": "Волчаки (Wolbachia)",
                "scientific_name": "Wolbachia",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "манипуляция репродукцией хозяина, защита от вирусов",
                "symbiotic_benefits": [
                    "защита от вирусов",
                    "контроль популяций насекомых-вредителей",
                    "манипуляция полом потомства",
                ],
                "organism_ecological_role": "регуляция популяций насекомых",
                "prevalence": 0.4,
                "risk_level": "low",
                "detection_confidence": 0.8,
            },
        ]

        for item in external_symbionts:
            symbiont = SymbiontPathogen.from_dict(
                {
                    "id": str(uuid.uuid4()),
                    **item,
                }
            )
            await self.symbiont_service.create_symbiont(symbiont)

        log("✅ Данные из внешних источников загружены")

    async def run(self) -> None:
        """
        Запускает полный процесс загрузки данных о симбионтах и патогенах.
        """
        try:
            log("🚀 Начинаем загрузку данных о симбионтах и патогенах...")

            # Создаем иерархическую структуру
            await self.create_symbiont_hierarchy()

            # Загружаем данные из внешних источников
            await self.load_from_external_sources()

            log("✅ Загрузка данных о симбионтах и патогенах завершена успешно")

        except Exception as e:
            log(f"❌ Ошибка при загрузке данных: {e}")
            raise


async def main():
    """Главная функция скрипта."""
    loader = SymbiontsDataLoader()
    await loader.run()


if __name__ == "__main__":
    asyncio.run(main())
