"""
API routes для детекторов.

Предоставляет endpoints для вызова детекторов напрямую или на основе intent detection.
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional, List, Awaitable
from pydantic import BaseModel
import json

from api.detect.organism_detector import detect_organisms
from api.detect.ecosystem_scaler import detect_ecosystems
from api.detect.environment_quality import detect_environment
from api.detect.localize import extract_location_and_time
from api.detect.factcheck import check_factuality
from api.llm import call_llm
from api.logger import root_logger
from pathlib import Path
import re
import json
from api.prompts.conversation_summary import SUMMARY_PROMPT

router = APIRouter(prefix="/api/detect", tags=["Detectors"])

log = root_logger.debug


class DetectRequest(BaseModel):
    """Запрос на детекцию."""

    text: str
    location_data: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class IntentRequest(BaseModel):
    """Запрос на определение намерения."""

    query: str
    context: Optional[str] = None


@router.post("/intent")
async def detect_intent(request: IntentRequest) -> Dict[str, Any]:
    """
    Определяет намерение пользователя и рекомендует детекторы.

    Returns:
        {
            "mode": "PLANNING" | "DIRECT",
            "goal": "основная цель",
            "requirements": ["требование1", "требование2"],
            "complexity": "НИЗКАЯ" | "СРЕДНЯЯ" | "ВЫСОКАЯ",
            "location": "местоположение или не указано",
            "time": "время или не указано",
            "confidence": 0.0-1.0,
            "reason": "причина выбора режима",
            "recommended_detectors": ["organisms", "ecosystems", "environment"]
        }
    """
    # Загружаем промпт
    prompt_path = Path(__file__).parent.parent / "prompts" / "intent_detector.txt"
    if not prompt_path.exists():
        prompt_path = Path("api/prompts/intent_detector.txt")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Intent detector prompt not found")

    # Форматируем промпт
    prompt = prompt_template.replace("{query}", request.query).replace("{context}", request.context or "")

    try:
        response = await call_llm(prompt, origin="intent_detector")

        # Парсим ответ
        result = _parse_intent_response(response)

        # Определяем рекомендуемые детекторы на основе намерения
        result["recommended_detectors"] = _recommend_detectors(result, request.query)

        return result
    except Exception as e:
        log(f"⚠️ Ошибка при определении намерения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/organisms")
async def detect_organisms_endpoint(request: DetectRequest) -> Dict[str, Any]:
    """
    Обнаруживает организмы в тексте.

    Returns:
        {
            "organisms": [...],
            "count": 0
        }
    """
    try:
        organisms = await detect_organisms(request.text)
        return {"organisms": organisms, "count": len(organisms)}
    except Exception as e:
        log(f"⚠️ Ошибка при обнаружении организмов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ecosystems")
async def detect_ecosystems_endpoint(request: DetectRequest) -> Dict[str, Any]:
    """
    Обнаруживает экосистемы в тексте.

    Returns:
        {
            "ecosystems": [...],
            "count": 0
        }
    """
    try:
        # Извлекаем локализацию, если не предоставлена
        location_data = request.location_data
        if not location_data:
            location_data = extract_location_and_time(request.text)

        ecosystems = await detect_ecosystems(request.text, location_data=location_data)
        return {"ecosystems": ecosystems, "count": len(ecosystems)}
    except Exception as e:
        log(f"⚠️ Ошибка при обнаружении экосистем: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/environment")
async def detect_environment_endpoint(request: DetectRequest) -> Dict[str, Any]:
    """
    Извлекает данные о состоянии окружающей среды.

    Returns:
        {
            "environment": {...},
            "confidence": 0.0-1.0
        }
    """
    try:
        # Извлекаем локализацию, если не предоставлена
        location_data = request.location_data
        if not location_data:
            location_data = extract_location_and_time(request.text)

        environment_data = await detect_environment(request.text, location_data=location_data)
        return {"environment": environment_data, "confidence": environment_data.get("confidence", 0.0)}
    except Exception as e:
        log(f"⚠️ Ошибка при извлечении данных об окружающей среде: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/all")
async def detect_all(request: DetectRequest) -> Dict[str, Any]:
    """
    Вызывает все детекторы параллельно.

    Returns:
        {
            "organisms": {...},
            "ecosystems": {...},
            "environment": {...},
            "location": {...}
        }
    """
    try:
        # Извлекаем локализацию один раз
        location_data = request.location_data
        if not location_data:
            location_data = extract_location_and_time(request.text)

        # Вызываем все детекторы параллельно
        import asyncio

        organisms_task = detect_organisms(request.text)
        ecosystems_task = detect_ecosystems(request.text, location_data=location_data)
        environment_task = detect_environment(request.text, location_data=location_data)

        organisms_result, ecosystems_result, environment_result = await asyncio.gather(
            organisms_task, ecosystems_task, environment_task, return_exceptions=True
        )

        # Обрабатываем исключения
        if isinstance(organisms_result, Exception):
            log(f"⚠️ Ошибка при обнаружении организмов: {organisms_result}")
            organisms_result = {"organisms": [], "count": 0}
        else:
            organisms_result = {"organisms": organisms_result, "count": len(organisms_result)}

        if isinstance(ecosystems_result, Exception):
            log(f"⚠️ Ошибка при обнаружении экосистем: {ecosystems_result}")
            ecosystems_result = {"ecosystems": [], "count": 0}
        else:
            ecosystems_result = {"ecosystems": ecosystems_result, "count": len(ecosystems_result)}

        if isinstance(environment_result, Exception):
            log(f"⚠️ Ошибка при извлечении данных об окружающей среде: {environment_result}")
            environment_result = {"environment": {}, "confidence": 0.0}
        else:
            environment_result = {
                "environment": environment_result,
                "confidence": environment_result.get("confidence", 0.0),
            }

        return {
            "organisms": organisms_result,
            "ecosystems": ecosystems_result,
            "environment": environment_result,
            "location": location_data,
        }
    except Exception as e:
        log(f"⚠️ Ошибка при вызове всех детекторов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smart")
async def detect_smart(request: DetectRequest) -> Dict[str, Any]:
    """
    Умный вызов детекторов на основе intent detection.

    Сначала определяет намерение, затем вызывает только нужные детекторы.
    """
    try:
        # Определяем намерение
        intent_request = IntentRequest(
            query=request.text, context=request.context.get("context") if request.context else None
        )
        intent_result = await detect_intent(intent_request)

        # Вызываем только рекомендуемые детекторы
        recommended = intent_result.get("recommended_detectors", [])
        results = {"intent": intent_result}

        # Извлекаем локализацию один раз
        location_data = request.location_data
        if not location_data:
            location_data = extract_location_and_time(request.text)

        # Вызываем детекторы параллельно
        import asyncio

        tasks: Dict[str, Awaitable[Any]] = {}
        if "organisms" in recommended:
            tasks["organisms"] = detect_organisms(request.text)
        if "ecosystems" in recommended:
            tasks["ecosystems"] = detect_ecosystems(request.text, location_data=location_data)
        if "environment" in recommended:
            tasks["environment"] = detect_environment(request.text, location_data=location_data)

        if tasks:
            task_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for i, (key, _task) in enumerate(tasks.items()):
                result = task_results[i]
                if isinstance(result, Exception):
                    log(f"⚠️ Ошибка при вызове {key}: {result}")
                    results[key] = {"error": str(result)}
                else:
                    if key == "organisms" and isinstance(result, list):
                        results[key] = {"organisms": result, "count": len(result)}
                    elif key == "ecosystems" and isinstance(result, list):
                        results[key] = {"ecosystems": result, "count": len(result)}
                    elif key == "environment" and isinstance(result, dict):
                        results[key] = {
                            "environment": result,
                            "confidence": float(result.get("confidence", 0.0)),
                        }

        results["location"] = location_data
        return results
    except Exception as e:
        log(f"⚠️ Ошибка при умном вызове детекторов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_intent_response(response: str) -> Dict[str, Any]:
    """Парсит ответ intent detector."""
    result = {
        "mode": "DIRECT",
        "goal": "",
        "requirements": [],
        "complexity": "НИЗКАЯ",
        "location": "не указано",
        "time": "не указано",
        "confidence": 0.5,
        "reason": "",
    }

    # Парсим поля
    mode_match = re.search(r"РЕЖИМ:\s*(PLANNING|DIRECT)", response, re.IGNORECASE)
    if mode_match:
        result["mode"] = mode_match.group(1).upper()

    goal_match = re.search(r"ЦЕЛЬ:\s*(.+)", response, re.IGNORECASE)
    if goal_match:
        result["goal"] = goal_match.group(1).strip()

    complexity_match = re.search(r"СЛОЖНОСТЬ:\s*(НИЗКАЯ|СРЕДНЯЯ|ВЫСОКАЯ)", response, re.IGNORECASE)
    if complexity_match:
        result["complexity"] = complexity_match.group(1).upper()

    location_match = re.search(r"МЕСТОПОЛОЖЕНИЕ:\s*(.+)", response, re.IGNORECASE)
    if location_match:
        result["location"] = location_match.group(1).strip()

    time_match = re.search(r"ВРЕМЯ:\s*(.+)", response, re.IGNORECASE)
    if time_match:
        result["time"] = time_match.group(1).strip()

    confidence_match = re.search(r"УВЕРЕННОСТЬ:\s*([0-9.]+)", response)
    if confidence_match:
        result["confidence"] = float(confidence_match.group(1))

    reason_match = re.search(r"ПРИЧИНА:\s*(.+)", response, re.IGNORECASE)
    if reason_match:
        result["reason"] = reason_match.group(1).strip()

    return result


def _recommend_detectors(intent_result: Dict[str, Any], query: str) -> List[str]:
    """Рекомендует детекторы на основе намерения и запроса."""
    recommended = []
    query_lower = query.lower()

    # Всегда проверяем на организмы, если есть биологические термины
    bio_keywords = [
        "организм",
        "растение",
        "животное",
        "птица",
        "насекомое",
        "бактерия",
        "гриб",
        "вид",
        "species",
        "organism",
    ]
    if any(keyword in query_lower for keyword in bio_keywords):
        recommended.append("organisms")

    # Экосистемы
    eco_keywords = [
        "экосистема",
        "лес",
        "озеро",
        "биосфера",
        "среда",
        "ecosystem",
        "biome",
        "habitat",
    ]
    if any(keyword in query_lower for keyword in eco_keywords):
        recommended.append("ecosystems")

    # Окружающая среда
    env_keywords = [
        "климат",
        "погода",
        "температура",
        "влажность",
        "окружающая среда",
        "загрязнение",
        "качество",
        "climate",
        "environment",
        "pollution",
    ]
    if any(keyword in query_lower for keyword in env_keywords):
        recommended.append("environment")

    # Если режим PLANNING, добавляем все детекторы для полноты контекста
    if intent_result.get("mode") == "PLANNING" and not recommended:
        recommended = ["organisms", "ecosystems", "environment"]

    return recommended


@router.post("/summary")
async def summary_endpoint(request: DetectRequest) -> Dict[str, Any]:
    """
    Генерирует саммари диалога.

    Returns:
        {
            "summary": "краткое содержание диалога",
            "key_points": ["ключевой момент 1", "ключевой момент 2"],
            "topics": ["тема 1", "тема 2"],
            "sentiment": "positive/negative/neutral",
            "entities": ["сущность 1", "сущность 2"]
        }
    """
    try:
        # Форматируем промпт
        prompt = SUMMARY_PROMPT.replace("{conversation}", request.text)

        # Вызываем LLM
        response = await call_llm(prompt, origin="conversation_summary")

        # Парсим JSON ответ
        try:
            result = json.loads(response.strip())
            # Валидируем структуру
            validated_result = {
                "summary": result.get("summary", "Не удалось сгенерировать сводку"),
                "key_points": result.get("key_points", []),
                "topics": result.get("topics", []),
                "sentiment": result.get("sentiment", "neutral"),
                "entities": result.get("entities", []),
            }
            return validated_result
        except json.JSONDecodeError as json_error:
            log(f"⚠️ Не удалось распарсить JSON ответ: {response}")
            # Возвращаем fallback структуру
            return {
                "summary": f"Сводка диалога: {response[:200]}...",
                "key_points": [],
                "topics": [],
                "sentiment": "unknown",
                "entities": [],
            }

    except Exception as e:
        log(f"⚠️ Ошибка при генерации саммари: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/factcheck")
async def factcheck_endpoint(request: DetectRequest) -> Dict[str, Any]:
    """
    Проверяет достоверность утверждений в тексте.

    Returns:
        {
            "status": "true" | "false" | "partial" | "unverifiable" | "unknown",
            "details": {
                "confidence": 0.0-1.0,
                ...
            }
        }
    """
    try:
        result = check_factuality(request.text)
        return result
    except Exception as e:
        log(f"⚠️ Ошибка при проверке достоверности: {e}")
        raise HTTPException(status_code=500, detail=str(e))
