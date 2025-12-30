"""
Модуль для запроса текущей погоды по городу.

Использует бесплатный API wttr.in для получения актуальных данных о погоде.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

import aiohttp
from api.detect.localize import geocode
from api.logger import root_logger

log = root_logger.debug
logger = logging.getLogger(__name__)


async def get_weather(city: str, time_reference: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Получает текущую погоду для указанного города.

    Args:
        city: Название города
        time_reference: Временная ссылка (сегодня, сейчас и т.д.)
                       Если не указана или не относится к текущему моменту, возвращает None

    Returns:
        Словарь с данными о погоде или None если:
        - город не указан
        - время не относится к текущему моменту
        - произошла ошибка при запросе
        {
            "temperature": "<температура в градусах Цельсия>",
            "condition": "<описание условий: солнечно/пасмурно/дождь и т.д.>",
            "humidity": "<влажность в процентах>",
            "wind_speed": "<скорость ветра в м/с>",
            "wind_direction": "<направление ветра>",
            "pressure": "<давление в мм рт.ст.>",
            "visibility": "<видимость в км>",
            "city": "<название города>",
            "timestamp": "<время запроса>"
        }
    """
    if not city or not city.strip():
        return None

    # Проверяем, относится ли время к текущему моменту
    # Если время не указано - запрашиваем текущую погоду
    if time_reference:
        import re

        current_time_indicators = ["сегодня", "сейчас", "нынче", "текущий момент"]
        past_time_indicators = ["вчера", "давно", "давеча", "раньше"]
        future_time_indicators = ["завтра", "позже"]

        time_lower = time_reference.lower()

        # Если время относится к прошлому или будущему - не запрашиваем погоду
        if any(indicator in time_lower for indicator in past_time_indicators + future_time_indicators):
            return None

        # Если время не относится к текущему моменту явно - проверяем наличие конкретной даты
        if not any(indicator in time_lower for indicator in current_time_indicators):
            # Проверяем, есть ли конкретная дата (год, месяц) - это не текущий момент
            if re.search(r"\d{4}", time_reference) or re.search(
                r"(январ|феврал|март|апрел|ма[ья]|июн|июл|август|сентябр|октябр|ноябр|декабр)",
                time_reference,
                re.IGNORECASE,
            ):
                return None
            # Если время указано как сезон без года (например, "летом", "зимой") - не запрашиваем
            # так как это может быть не текущий сезон
            return None

    try:
        # Получаем координаты города для более точного запроса
        coordinates = geocode(city)
        if coordinates:
            lat, lon = coordinates
            # Используем координаты для более точного запроса (формат @lat,lon)
            url = f"https://wttr.in/@{lat},{lon}?format=j1&lang=ru"
        else:
            # Используем название города (URL-кодируем для безопасности)
            import urllib.parse

            encoded_city = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded_city}?format=j1&lang=ru"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()

                    # Парсим данные из ответа wttr.in
                    current = data.get("current_condition", [{}])[0]
                    if not current:
                        return None

                    weather_data = {
                        "temperature": current.get("temp_C", "N/A"),
                        "condition": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
                        "humidity": current.get("humidity", "N/A"),
                        "wind_speed": current.get("windspeedKmph", "N/A"),
                        "wind_direction": current.get("winddir16Point", "N/A"),
                        "pressure": current.get("pressure", "N/A"),
                        "visibility": current.get("visibility", "N/A"),
                        "city": city,
                        "timestamp": datetime.now().isoformat(),
                    }

                    # Форматируем скорость ветра в м/с (wttr.in возвращает в км/ч)
                    if isinstance(weather_data["wind_speed"], (int, float)):
                        weather_data["wind_speed"] = f"{weather_data['wind_speed'] / 3.6:.1f} м/с"

                    log(f"✅ Получена погода для {city}: {weather_data['temperature']}°C, {weather_data['condition']}")
                    return weather_data
                else:
                    logger.warning(f"⚠️ Ошибка при запросе погоды: статус {response.status}")
                    return None

    except aiohttp.ClientError as e:
        logger.warning(f"⚠️ Ошибка сети при запросе погоды: {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при получении погоды: {e}")
        return None


def format_weather_for_context(weather_data: Optional[Dict[str, Any]]) -> str:
    """
    Форматирует данные о погоде для включения в контекст LLM.

    Args:
        weather_data: Данные о погоде из get_weather

    Returns:
        Отформатированная строка с информацией о погоде или пустая строка
    """
    if not weather_data:
        return ""

    parts = []
    if weather_data.get("temperature") and weather_data["temperature"] != "N/A":
        parts.append(f"температура: {weather_data['temperature']}°C")
    if weather_data.get("condition") and weather_data["condition"] != "N/A":
        parts.append(f"условия: {weather_data['condition']}")
    if weather_data.get("humidity") and weather_data["humidity"] != "N/A":
        parts.append(f"влажность: {weather_data['humidity']}%")
    if weather_data.get("wind_speed") and weather_data["wind_speed"] != "N/A":
        wind_info = f"ветер: {weather_data['wind_speed']}"
        if weather_data.get("wind_direction") and weather_data["wind_direction"] != "N/A":
            wind_info += f" ({weather_data['wind_direction']})"
        parts.append(wind_info)

    if parts:
        city = weather_data.get("city", "указанном городе")
        return f"Текущая погода в {city}: {', '.join(parts)}."

    return ""
