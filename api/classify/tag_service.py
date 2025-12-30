"""Сервис для управления тегами классификации параграфов.

Автоматически обновляет список тегов через LLM анализ данных.
"""

import json
from typing import List, Optional, Dict, Any

from api.storage.db import DatabaseManagerBase
from api.llm import call_llm_with_retry
from api.logger import root_logger

log = root_logger.debug


class TagService:
    """Сервис для управления тегами классификации."""

    def __init__(self, db_manager: DatabaseManagerBase):
        """Инициализация сервиса.

        Args:
            db_manager: Менеджер базы данных (DatabaseManager или PostgreSQLManager)
        """
        self.db_manager = db_manager
        self._ensure_tables()
        self._initialize_default_tags()

    def _ensure_tables(self) -> None:
        """Создает таблицы если их нет."""
        from pathlib import Path

        # Try multiple possible paths for schema.sql
        possible_paths = [
            Path(__file__).parent / "schema.sql",
            self.db_manager.db_path.parent / "api" / "storage" / "schema.sql",
            Path("api/storage/schema.sql"),
        ]

        for schema_path in possible_paths:
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                if self.db_manager.connection:
                    self.db_manager.connection.executescript(schema_sql)
                    self.db_manager.connection.commit()
                break

    def _initialize_default_tags(self) -> None:
        """Инициализирует теги по умолчанию, если их нет."""
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM tags")
        count = cursor.fetchone()[0]

        if count == 0:
            default_tags = [
                {
                    "id": "ecosystem_vulnerability",
                    "name": "ecosystem_vulnerability",
                    "description": "Уязвимости экосистемы - возможные риски и слабые места",
                    "category": "ecosystem",
                },
                {
                    "id": "ecosystem_risk",
                    "name": "ecosystem_risk",
                    "description": "Риски экосистемы - найденные проблемы, требующие решения",
                    "category": "ecosystem",
                },
                {
                    "id": "suggested_ecosystem_solution",
                    "name": "suggested_ecosystem_solution",
                    "description": "Предлагаемые решения для экосистемы",
                    "category": "solution",
                },
                {
                    "id": "neutral",
                    "name": "neutral",
                    "description": "Нейтральный контент без специфической классификации",
                    "category": "general",
                },
            ]

            for tag_data in default_tags:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO tags (id, name, description, category, usage_count, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (tag_data["id"], tag_data["name"], tag_data["description"], tag_data["category"], 0, True),
                )

            self.db_manager.connection.commit()
            log(f"✅ Инициализировано {len(default_tags)} тегов по умолчанию")

    def get_all_tags(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Получает все теги.

        Args:
            active_only: Возвращать только активные теги

        Returns:
            Список словарей с данными тегов
        """
        cursor = self.db_manager.connection.cursor()
        if active_only:
            cursor.execute("SELECT * FROM tags WHERE is_active = 1 ORDER BY usage_count DESC, name")
        else:
            cursor.execute("SELECT * FROM tags ORDER BY usage_count DESC, name")

        rows = cursor.fetchall()
        result = []
        for row in rows:
            row_dict = dict(row)
            # Парсим examples из JSON
            if row_dict.get("examples"):
                try:
                    row_dict["examples"] = json.loads(row_dict["examples"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["examples"] = []
            else:
                row_dict["examples"] = []
            result.append(row_dict)

        return result

    def get_tag(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """Получает тег по имени.

        Args:
            tag_name: Название тега

        Returns:
            Словарь с данными тега или None
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT * FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()

        if row:
            row_dict = dict(row)
            if row_dict.get("examples"):
                try:
                    row_dict["examples"] = json.loads(row_dict["examples"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["examples"] = []
            else:
                row_dict["examples"] = []
            return row_dict

        return None

    def create_tag(
        self,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        examples: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Создает новый тег.

        Args:
            name: Название тега
            description: Описание тега
            category: Категория тега
            examples: Примеры использования тега

        Returns:
            Словарь с данными созданного тега
        """
        cursor = self.db_manager.connection.cursor()
        tag_id = name  # Используем name как id для простоты

        examples_json = json.dumps(examples) if examples else None

        cursor.execute(
            """
            INSERT INTO tags (id, name, description, category, examples, usage_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tag_id, name, description, category, examples_json, 0, True),
        )

        self.db_manager.connection.commit()
        log(f"✅ Создан тег: {name}")

        return self.get_tag(name) or {}

    def update_tag_usage(self, tag_names: List[str]) -> None:
        """Обновляет счетчик использования тегов.

        Args:
            tag_names: Список названий тегов
        """
        if not tag_names:
            return

        cursor = self.db_manager.connection.cursor()
        for tag_name in tag_names:
            cursor.execute(
                "UPDATE tags SET usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (tag_name,),
            )

        self.db_manager.connection.commit()

    def add_example_to_tag(self, tag_name: str, example: str) -> None:
        """Добавляет пример использования тега.

        Args:
            tag_name: Название тега
            example: Пример параграфа с этим тегом
        """
        tag = self.get_tag(tag_name)
        if not tag:
            return

        examples = tag.get("examples", [])
        if example not in examples:
            examples.append(example)
            # Ограничиваем количество примеров (храним последние 10)
            if len(examples) > 10:
                examples = examples[-10:]

            cursor = self.db_manager.connection.cursor()
            cursor.execute(
                "UPDATE tags SET examples = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (json.dumps(examples), tag_name),
            )
            self.db_manager.connection.commit()

    async def suggest_tags_for_paragraph(
        self, paragraph_content: str, existing_tags: Optional[List[str]] = None
    ) -> List[str]:
        """Предлагает теги для параграфа через LLM.

        Args:
            paragraph_content: Содержимое параграфа
            existing_tags: Уже существующие теги (для контекста)

        Returns:
            Список предложенных тегов
        """
        # Получаем активные теги
        available_tags = self.get_all_tags(active_only=True)

        # Загружаем промпт из файла
        from pathlib import Path

        prompt_path = Path(__file__).parent.parent / "prompts" / "tag_classifier.txt"
        if not prompt_path.exists():
            # Fallback на относительный путь
            prompt_path = Path("api/prompts/tag_classifier.txt")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            log(f"⚠️ Промпт не найден: {prompt_path}, используем упрощенный вариант")
            # Упрощенный fallback
            tags_list = "\n".join([f"- {tag['name']}: {tag.get('description', '')}" for tag in available_tags])
            prompt_template = """Проанализируй параграф и предложи теги из списка.

Доступные теги:
{tags_list}

Параграф:
{paragraph_content}

Уже назначенные теги: {existing_tags}

Верни JSON массив: ["tag1", "tag2"]"""

        # Формируем список тегов для промпта
        tags_list = "\n".join([f"- {tag['name']}: {tag.get('description', '')}" for tag in available_tags])

        # Ограничиваем длину параграфа для экономии токенов
        paragraph_limited = paragraph_content[:1000]

        # Формируем строку существующих тегов
        existing_tags_str = ", ".join(existing_tags) if existing_tags else "нет"

        # Подставляем значения в шаблон
        prompt = prompt_template.format(
            tags_list=tags_list, paragraph_content=paragraph_limited, existing_tags=existing_tags_str
        )

        try:
            response = await call_llm_with_retry(prompt)
            # Парсим JSON ответ
            # LLM может вернуть ответ с пояснениями, нужно извлечь JSON
            import re

            json_match = re.search(r"\[.*?\]", response, re.DOTALL)
            if json_match:
                tags = json.loads(json_match.group())
                # Валидируем теги - проверяем, что они существуют
                valid_tags = [tag for tag in tags if any(t["name"] == tag for t in available_tags)]
                return valid_tags
            else:
                log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response}")
                return []
        except Exception as e:
            log(f"⚠️ Ошибка при предложении тегов через LLM: {e}")
            return []

    async def call_llm_for_tags(self, prompt: str) -> Optional[List[str]]:
        """Вызывает LLM для классификации с произвольным промптом.

        Args:
            prompt: Произвольный промпт для LLM

        Returns:
            Список тегов или None при ошибке
        """
        try:
            response = await call_llm_with_retry(
                llm_context=prompt, origin="hybrid_classification", context_size_hint="normal"
            )

            # Парсим ответ как JSON или список через запятую
            response = response.strip()

            # Пробуем распарсить как JSON
            try:
                result = json.loads(response)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

            # Пробуем распарсить как список через запятую
            if "," in response:
                tags = [tag.strip().strip('"').strip("'") for tag in response.split(",")]
                return [tag for tag in tags if tag]

            # Если ничего не получилось, возвращаем пустой список
            log(f"⚠️ Не удалось распарсить ответ LLM: {response}")
            return []

        except Exception as e:
            log(f"⚠️ Ошибка при вызове LLM для классификации: {e}")
            return None

    async def analyze_and_update_tags(self, sample_size: int = 100) -> Dict[str, Any]:
        """Анализирует параграфы и обновляет список тегов через LLM.

        Args:
            sample_size: Количество параграфов для анализа

        Returns:
            Словарь с результатами анализа
        """
        cursor = self.db_manager.connection.cursor()

        # Получаем выборку параграфов с тегами
        cursor.execute(
            """
            SELECT content, tags, COUNT(*) as count
            FROM paragraphs
            WHERE tags IS NOT NULL AND tags != '[]'
            GROUP BY tags
            ORDER BY count DESC
            LIMIT ?
            """,
            (sample_size,),
        )

        rows = cursor.fetchall()
        if not rows:
            return {"analyzed": 0, "new_tags": [], "updated_tags": []}

        # Анализируем паттерны тегов: ключ - имя тега, значение - список примеров текстов
        tag_patterns: Dict[str, List[str]] = {}
        for row in rows:
            tags_json = row["tags"]
            try:
                tags = json.loads(tags_json)
                for tag in tags:
                    if tag not in tag_patterns:
                        tag_patterns[tag] = []
                    tag_patterns[tag].append(row["content"][:200])  # Первые 200 символов как пример
            except (json.JSONDecodeError, TypeError):
                continue

        # Формируем промпт для LLM для анализа и предложения новых тегов
        current_tags_info = "\n".join(
            [
                f"- {tag['name']}: {tag.get('description', '')} (использований: {tag.get('usage_count', 0)})"
                for tag in self.get_all_tags()
            ]
        )

        prompt = f"""Проанализируй текущие теги и предложи улучшения.

Текущие теги:
{current_tags_info}

Примеры использования тегов:
{json.dumps(tag_patterns, ensure_ascii=False, indent=2)[:2000]}

Задачи:
1. Предложи новые теги, которые могут улучшить классификацию (если нужно)
2. Предложи улучшения описаний существующих тегов
3. Предложи теги для деактивации (если они не используются или не нужны)

Верни JSON в формате:
{{
  "new_tags": [
    {{"name": "tag_name", "description": "описание", "category": "категория"}}
  ],
  "updated_tags": [
    {{"name": "tag_name", "description": "новое описание"}}
  ],
  "deactivate_tags": ["tag_name1", "tag_name2"]
}}

Ответ:"""

        try:
            response = await call_llm_with_retry(prompt)
            # Парсим JSON ответ
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                analysis_result = json.loads(json_match.group())

                new_tags = []
                for tag_data in analysis_result.get("new_tags", []):
                    created = self.create_tag(
                        name=tag_data["name"],
                        description=tag_data.get("description"),
                        category=tag_data.get("category"),
                    )
                    new_tags.append(created)

                updated_tags = []
                for tag_data in analysis_result.get("updated_tags", []):
                    cursor.execute(
                        "UPDATE tags SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                        (tag_data.get("description"), tag_data["name"]),
                    )
                    updated_tags.append(tag_data["name"])

                deactivated_tags = []
                for tag_name in analysis_result.get("deactivate_tags", []):
                    cursor.execute(
                        "UPDATE tags SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE name = ?", (tag_name,)
                    )
                    deactivated_tags.append(tag_name)

                self.db_manager.connection.commit()

                return {
                    "analyzed": len(rows),
                    "new_tags": new_tags,
                    "updated_tags": updated_tags,
                    "deactivated_tags": deactivated_tags,
                }
            else:
                log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response}")
                return {"analyzed": len(rows), "new_tags": [], "updated_tags": [], "deactivated_tags": []}
        except Exception as e:
            log(f"⚠️ Ошибка при анализе тегов через LLM: {e}")
            return {"analyzed": len(rows), "new_tags": [], "updated_tags": [], "deactivated_tags": []}

    def get_tags_for_classification(self) -> List[Dict[str, Any]]:
        """Получает теги для использования в классификации.

        Возвращает только активные теги с их описаниями для LLM.

        Returns:
            Список тегов с описаниями
        """
        return self.get_all_tags(active_only=True)
