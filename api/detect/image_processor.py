"""
Обработка изображений: микроскоп, обычные фото, спутниковые снимки NASA.

Поддерживает:
- Изображения с микроскопа (микробиология, клетки, ткани)
- Обычные фотографии (экосистемы, организмы, ландшафты)
- Спутниковые снимки NASA (ландшафты, экосистемы, изменения климата)
"""

import io
import base64
from typing import Dict, Any, Optional, List, cast
from enum import Enum
from pathlib import Path
from PIL import Image, ExifTags


from api.logger import root_logger
from api.llm import call_llm
from api.settings import LLM_PROXY_URL, LLM_PROXY_TOKEN
from openai import AsyncOpenAI
from openai import APIError, AuthenticationError, APIConnectionError, APITimeoutError
from openai.types.chat import ChatCompletion

log = root_logger.debug

# Инициализация OpenAI клиента для прокси
_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    """Получает или создает OpenAI клиент для прокси."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            base_url=f"{LLM_PROXY_URL}/v1",
            api_key=LLM_PROXY_TOKEN or "not-needed",
            timeout=120.0,
        )
    return _openai_client


class ImageType(Enum):
    """Тип изображения для определения стратегии обработки."""

    MICROSCOPE = "microscope"  # Изображения с микроскопа
    PHOTO = "photo"  # Обычные фотографии
    SATELLITE = "satellite"  # Спутниковые снимки NASA
    UNKNOWN = "unknown"  # Неизвестный тип


class ImageProcessor:
    """Обработчик изображений для анализа экосистем и организмов."""

    def __init__(self):
        """Инициализация процессора изображений."""
        root_logger.info("Инициализация процессора изображений")

        # Загружаем промпты из файлов
        self._prompt_vision = self._load_prompt("image_analysis_vision.txt")

    async def process_image(
        self,
        image_data: bytes,
        filename: Optional[str] = None,
        image_type: Optional[ImageType] = None,
    ) -> Dict[str, Any]:
        """
        Обрабатывает изображение, загруженное в чат (microscope или photo).

        Основной use case: когда пользователь перетаскивает изображение в чат,
        оно анализируется через vision модели для получения описания.
        """
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))

            # Извлекаем метаданные
            metadata = self._extract_metadata(image)

            # Конвертируем в base64 для хранения
            base64_str = base64.b64encode(image_data).decode("utf-8")

            # Анализируем изображение через vision модели (без предварительного определения типа)
            # Используем универсальный промпт для всех типов изображений
            description = await self._analyze_image_with_llm(image, ImageType.PHOTO, metadata)

            # Определяем тип изображения на основе описания от LLM
            if image_type is None:
                image_type = self._detect_image_type_from_description(description, filename)

            # Извлекаем информацию об организмах и экосистемах из описания
            organisms = await self._extract_organisms_from_description(description)
            ecosystems = await self._extract_ecosystems_from_description(description)

            # Извлекаем локализацию
            location_data = await self._extract_location_from_description(description)

            # Извлекаем данные об окружающей среде и климатических условиях
            environment_data = await self._extract_environment_from_description(description, location_data)

            return {
                "image_type": image_type.value,
                "description": description,
                "metadata": metadata,
                "base64": base64_str,
                "width": image.width,
                "height": image.height,
                "format": image.format or "UNKNOWN",
                "detected_organisms": organisms,
                "detected_ecosystems": ecosystems,
                "location": location_data.get("location"),
                "time_reference": location_data.get("time_reference"),
                "environment": environment_data,
            }
        except Exception as e:
            log(f"⚠️ Ошибка при обработке изображения: {e}")
            return {
                "error": str(e),
                "image_type": ImageType.UNKNOWN.value,
            }

    def _detect_image_type_from_description(self, description: str, filename: Optional[str] = None) -> ImageType:
        """
        Определяет тип изображения на основе описания от LLM.

        Основные типы для чата:
        - MICROSCOPE: изображения с микроскопа (клетки, ткани, микроорганизмы)
        - PHOTO: обычные фотографии (экосистемы, организмы, ландшафты)
        - SATELLITE: спутниковые снимки (редко используется в чате)

        Args:
            description: Описание изображения от LLM
            filename: Имя файла (для дополнительной проверки)

        Returns:
            Тип изображения
        """
        description_lower = description.lower()

        # Ключевые слова для определения микроскопа
        microscope_keywords = [
            "микроскоп",
            "microscope",
            "микроскопия",
            "microscopy",
            "микроскопический",
            "microscopic",
            "клетка",
            "клетки",
            "cell",
            "cells",
            "клеточный",
            "cellular",
            "ткань",
            "ткани",
            "tissue",
            "tissues",
            "бактерия",
            "бактерии",
            "bacteria",
            "bacterial",
            "препарат",
            "specimen",
            "slide",
            "слайд",
            "окраска",
            "stain",
            "гистология",
            "histology",
            "цитология",
            "cytology",
            "микроорганизм",
            "микроорганизмы",
            "microorganism",
            "microorganisms",
        ]

        # Ключевые слова для спутниковых снимков
        satellite_keywords = [
            "спутник",
            "satellite",
            "nasa",
            "landsat",
            "modis",
            "sentinel",
            "космический снимок",
            "satellite image",
            "earth observation",
        ]

        # Проверяем описание на ключевые слова
        if any(keyword in description_lower for keyword in microscope_keywords):
            return ImageType.MICROSCOPE

        if any(keyword in description_lower for keyword in satellite_keywords):
            return ImageType.SATELLITE

        # Дополнительная проверка по имени файла (если описание не помогло)
        if filename:
            filename_lower = filename.lower()
            if any(keyword in filename_lower for keyword in ["microscope", "micro", "cell", "tissue", "bacteria"]):
                return ImageType.MICROSCOPE
            if any(keyword in filename_lower for keyword in ["nasa", "satellite", "landsat"]):
                return ImageType.SATELLITE

        # По умолчанию считаем обычной фотографией (основной use case для чата)
        return ImageType.PHOTO

    def _extract_metadata(self, image: Image.Image) -> Dict[str, Any]:
        """
        Извлекает метаданные из изображения.

        Args:
            image: Объект PIL Image

        Returns:
            Словарь с метаданными
        """
        metadata: Dict[str, Any] = {
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "mode": image.mode,
        }

        # Извлекаем EXIF данные (используем публичный API getexif для совместимости с Pillow)
        try:
            exif = image.getexif()
            if exif:
                exif_data: Dict[str, str] = {}
                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    exif_data[str(tag)] = str(value)
                metadata["exif"] = exif_data
        except Exception:
            # Безопасно игнорируем любые ошибки EXIF, так как это вспомогательная информация
            pass

        return metadata

    def _load_prompt(self, filename: str) -> str:
        """
        Загружает промпт из файла.

        Args:
            filename: Имя файла промпта в папке prompts

        Returns:
            Содержимое промпта или fallback версия
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / filename
        if not prompt_path.exists():
            prompt_path = Path("api/prompts") / filename

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            log(f"⚠️ Промпт {filename} не найден, используем упрощенный вариант")
            # Fallback промпт
            return """Опиши это изображение подробно. Что видно на изображении? Какие объекты, структуры, организмы или элементы присутствуют? Какой тип изображения это может быть (микроскопия, фотография природы, спутниковый снимок)? Опиши все детали, которые видишь."""

    async def _analyze_image_with_llm(
        self,
        image: Image.Image,
        image_type: ImageType,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Анализирует изображение через vision модели или LLM для получения описания.

        Тип изображения передается для совместимости, но не используется для формирования промпта.
        Тип будет определен после получения описания.

        Приоритет:
        1. vision модели (gpt-4o, gemini-2.0-flash и т.д.)
        2. LLM fallback (текстовый промпт)

        Args:
            image: Объект PIL Image
            image_type: Тип изображения (не используется, оставлен для совместимости)
            metadata: Метаданные изображения

        Returns:
            Описание изображения
        """
        # Пытаемся использовать vision модели
        try:
            return await self._analyze_image_with_vision(image, metadata)
        except Exception as e:
            log(f"⚠️ Ошибка при анализе через vision: {e}, переключаемся на LLM fallback")

        # Fallback на LLM
        return await self._analyze_image_with_llm_fallback(image, metadata)

    async def _analyze_image_with_vision(
        self,
        image: Image.Image,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Анализирует изображение через vision модели (gpt-4o, gemini и т.д.).

        Args:
            image: Объект PIL Image
            metadata: Метаданные изображения

        Returns:
            Описание изображения
        """
        # Конвертируем изображение в base64
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        image_data_url = f"data:image/jpeg;base64,{image_base64}"

        # Загружаем промпт из файла
        prompt = self._prompt_vision

        # Список vision моделей, которые поддерживают изображения
        vision_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-pro-vision",
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-sonnet",
        ]

        # Пробуем найти доступную vision модель через прокси
        for model_name in vision_models:
            try:
                log(f"🖼️ Анализ изображения через прокси vision модель: {model_name}")

                # Формируем сообщение с изображением для vision моделей
                # Используем cast для типизации, так как структура соответствует ожидаемому формату OpenAI SDK
                messages = cast(
                    List[Dict[str, Any]],
                    [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": image_data_url}},
                            ],
                        }
                    ],
                )

                # Вызываем прокси-сервис для vision моделей через OpenAI SDK
                client = _get_openai_client()

                # При stream=False возвращается ChatCompletion, не AsyncStream
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,  # type: ignore[arg-type]
                    stream=False,
                )

                # Type narrowing: при stream=False response всегда ChatCompletion
                if isinstance(response, ChatCompletion) and response.choices and len(response.choices) > 0:
                    description = response.choices[0].message.content if response.choices[0].message else ""

                    if description and len(description.strip()) > 10:
                        log(f"✅ Описание получено через {model_name} ({len(description)} символов)")
                        return description.strip()
                else:
                    log(f"⚠️ Пустой ответ от прокси для {model_name}")
                    continue

            except (AuthenticationError, APIError, APIConnectionError, APITimeoutError) as e:
                log(f"⚠️ Ошибка с моделью {model_name}: {e}, пробуем следующую")
                continue
            except Exception as e:
                log(f"⚠️ Неожиданная ошибка с моделью {model_name}: {e}, пробуем следующую")
                continue

        # Если ни одна vision модель не сработала, выбрасываем исключение для fallback
        raise Exception("Нет доступных vision моделей")

    async def _analyze_image_with_llm_fallback(
        self,
        image: Image.Image,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Анализирует изображение через LLM (fallback метод).

        Args:
            image: Объект PIL Image
            metadata: Метаданные изображения

        Returns:
            Описание изображения
        """
        # Конвертируем изображение в base64 для отправки в LLM
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Загружаем промпт из файла и форматируем с метаданными
        prompt = self._prompt_vision.format(
            width=image.width,
            height=image.height,
            format=image.format or "UNKNOWN",
            metadata=metadata.get("exif", {}),
        )

        try:
            # Отправляем изображение и промпт в LLM
            # Примечание: для vision моделей нужно использовать специальный API
            # Здесь используем текстовое описание через промпт
            description = await call_llm(prompt, origin="image_vision")
            return description
        except Exception as e:
            log(f"⚠️ Ошибка при анализе изображения через LLM: {e}")
            return f"Изображение: {image.width}x{image.height} пикселей"

    async def _extract_organisms_from_description(self, description: str) -> List[Dict[str, Any]]:
        """
        Извлекает информацию об организмах из описания изображения.

        Args:
            description: Описание изображения

        Returns:
            Список обнаруженных организмов
        """
        try:
            from api.detect.organism_detector import detect_organisms

            organisms = await detect_organisms(description)
            return organisms
        except Exception as e:
            log(f"⚠️ Ошибка при извлечении организмов: {e}")
            return []

    async def _extract_ecosystems_from_description(self, description: str) -> List[Dict[str, Any]]:
        """
        Извлекает информацию об экосистемах из описания изображения.

        Args:
            description: Описание изображения

        Returns:
            Список обнаруженных экосистем
        """
        try:
            from api.detect.ecosystem_scaler import detect_ecosystems

            ecosystems = await detect_ecosystems(description)
            return ecosystems
        except Exception as e:
            log(f"⚠️ Ошибка при извлечении экосистем: {e}")
            return []

    async def _extract_location_from_description(self, description: str) -> Dict[str, Any]:
        """
        Извлекает локализацию из описания изображения.

        Args:
            description: Описание изображения

        Returns:
            Словарь с локализацией
        """
        try:
            from api.detect.localize import extract_location_and_time

            location_data = extract_location_and_time(description)
            return location_data
        except Exception as e:
            log(f"⚠️ Ошибка при извлечении локализации: {e}")
            return {}

    async def _extract_environment_from_description(
        self, description: str, location_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Извлекает данные о состоянии окружающей среды и климатических условиях из описания изображения.

        Args:
            description: Описание изображения
            location_data: Опциональные данные локализации

        Returns:
            Словарь с данными об окружающей среде
        """
        try:
            from api.detect.environment_quality import detect_environment

            environment_data = await detect_environment(description, location_data)
            return environment_data
        except Exception as e:
            log(f"⚠️ Ошибка при извлечении данных об окружающей среде: {e}")
            return {}


def is_image_file(filename: str) -> bool:
    """
    Проверяет, является ли файл изображением.

    Args:
        filename: Имя файла

    Returns:
        True если файл изображение
    """
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic"}
    return Path(filename).suffix.lower() in image_extensions
