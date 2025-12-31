"""
Модуль для запроса текущей погоды по городу.

Использует парсинг Gismeteo для получения актуальных данных о погоде.
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup
from api.detect.localize import geocode
from api.logger import root_logger

log = root_logger.debug
logger = logging.getLogger(__name__)


async def get_weather(city: str, time_reference: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Получает текущую погоду для указанного города через парсинг Gismeteo.

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
    if time_reference:
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
            return None

    try:
        # Ищем город на Gismeteo через поиск
        import urllib.parse

        encoded_city = urllib.parse.quote(city)
        search_url = f"https://www.gismeteo.ru/search/{encoded_city}/"

        async with aiohttp.ClientSession() as session:
            # Устанавливаем User-Agent для избежания блокировок
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    log(f"Gismeteo поиск недоступен: статус {response.status}")
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # Ищем ссылку на страницу погоды города
                # Gismeteo использует ссылки вида /weather-city-{id}/
                city_link = None
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    link_text = link.get_text().strip().lower()
                    # Ищем ссылки на погоду и проверяем, что текст ссылки содержит название города
                    if "/weather-" in href and city.lower() in link_text:
                        city_link = href
                        break

                # Если не нашли по тексту, пробуем первую ссылку на погоду
                if not city_link:
                    for link in soup.find_all("a", href=True):
                        href = link.get("href", "")
                        if "/weather-" in href:
                            city_link = href
                            break

                if not city_link:
                    log(f"Не найдена ссылка на погоду для {city}")
                    return None

                # Если ссылка относительная, делаем её абсолютной
                if city_link.startswith("/"):
                    city_link = f"https://www.gismeteo.ru{city_link}"

                log(f"Найдена ссылка на погоду: {city_link}")

                # Получаем страницу с погодой
                async with session.get(
                    city_link, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as weather_response:
                    if weather_response.status != 200:
                        log(f"Страница погоды недоступна: статус {weather_response.status}")
                        return None

                    weather_html = await weather_response.text()
                    weather_soup = BeautifulSoup(weather_html, "html.parser")

                    # Парсим данные о погоде
                    temperature = "N/A"
                    condition = "N/A"
                    humidity = "N/A"
                    wind_speed = "N/A"
                    wind_direction = "N/A"
                    pressure = "N/A"
                    visibility = "N/A"

                    # Температура - ищем в различных местах
                    temp_elem = (
                        weather_soup.find(class_=re.compile("temp|value|temperature", re.I))
                        or weather_soup.find(attrs={"data-value": True})
                        or weather_soup.find("span", class_=re.compile("unit", re.I))
                        or weather_soup.find("div", class_=re.compile("now.*temp", re.I))
                    )

                    if temp_elem:
                        temp_text = temp_elem.get_text().strip()
                        # Извлекаем число из текста (может быть со знаком минус)
                        temp_match = re.search(r"-?\d+", temp_text)
                        if temp_match:
                            temperature = int(temp_match.group())

                    # Условия (солнечно, пасмурно и т.д.)
                    condition_elem = (
                        weather_soup.find(class_=re.compile("condition|weather|description", re.I))
                        or weather_soup.find(attrs={"title": re.compile("погода|weather", re.I)})
                        or weather_soup.find("div", class_=re.compile("text|desc", re.I))
                        or weather_soup.find("span", class_=re.compile("tooltip", re.I))
                    )
                    if condition_elem:
                        condition = condition_elem.get_text().strip()
                        # Очищаем от лишних символов
                        condition = re.sub(r"\s+", " ", condition)
                        if len(condition) > 50:  # Если слишком длинное, обрезаем
                            condition = condition[:50] + "..."

                    # Влажность
                    humidity_elem = weather_soup.find(string=re.compile("влажность|humidity", re.I))
                    if humidity_elem:
                        parent = humidity_elem.find_parent()
                        if parent:
                            value_elem = parent.find(class_=re.compile("value|number", re.I))
                            if value_elem:
                                humidity_text = value_elem.get_text().strip()
                                humidity_match = re.search(r"\d+", humidity_text)
                                if humidity_match:
                                    humidity = int(humidity_match.group())

                    # Скорость ветра
                    wind_elem = weather_soup.find(string=re.compile("ветер|wind", re.I))
                    if wind_elem:
                        parent = wind_elem.find_parent()
                        if parent:
                            # Ищем скорость ветра
                            speed_elem = parent.find(class_=re.compile("value|speed|number", re.I))
                            if speed_elem:
                                speed_text = speed_elem.get_text().strip()
                                # Может быть в м/с или км/ч
                                speed_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:м/с|км/ч|мс|кмч)", speed_text, re.I)
                                if speed_match:
                                    wind_speed = speed_match.group(1).replace(",", ".")
                                    # Если в км/ч, конвертируем в м/с
                                    if "км" in speed_text.lower():
                                        wind_speed = f"{float(wind_speed) / 3.6:.1f} м/с"
                                    else:
                                        wind_speed = f"{wind_speed} м/с"

                            # Ищем направление ветра
                            dir_elem = parent.find(class_=re.compile("direction|dir", re.I))
                            if dir_elem:
                                wind_direction = dir_elem.get_text().strip()

                    # Давление
                    pressure_elem = weather_soup.find(string=re.compile("давление|pressure", re.I))
                    if pressure_elem:
                        parent = pressure_elem.find_parent()
                        if parent:
                            value_elem = parent.find(class_=re.compile("value|number", re.I))
                            if value_elem:
                                pressure_text = value_elem.get_text().strip()
                                pressure_match = re.search(r"(\d+(?:[.,]\d+)?)", pressure_text)
                                if pressure_match:
                                    pressure = pressure_match.group(1).replace(",", ".")

                    weather_data = {
                        "temperature": temperature,
                        "condition": condition,
                        "humidity": humidity,
                        "wind_speed": wind_speed,
                        "wind_direction": wind_direction,
                        "pressure": pressure,
                        "visibility": visibility,
                        "city": city,
                        "timestamp": datetime.now().isoformat(),
                    }

                    log(f"✅ Получена погода через Gismeteo для {city}: {temperature}°C, {condition}")
                    return weather_data

    except Exception as e:
        log(f"Ошибка при получении погоды через Gismeteo: {e}")
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
