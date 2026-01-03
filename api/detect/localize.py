"""
этот модуль предоставляет функции геокодинга
"""

from typing import Optional, Dict, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import re


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Преобразует координаты в адрес с помощью Nominatim (OpenStreetMap).

    Args:
        lat: Широта
        lon: Долгота

    Returns:
        Адрес в виде строки или None при ошибке
    """
    try:
        geolocator = Nominatim(user_agent="simbioset")
        location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
        return location.address if location else None
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None


async def reverse_geocode_location(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Преобразует координаты в подробную информацию о местоположении.

    Args:
        lat: Широта
        lon: Долгота

    Returns:
        Словарь с информацией о местоположении или None при ошибке
    """
    try:
        geolocator = Nominatim(user_agent="simbioset")
        location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
        if location:
            return {
                "display_name": location.address,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "raw": location.raw,
            }
        return None
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None


def geocode(caption: str) -> Optional[tuple[float, float]]:
    """
    Преобразует адрес в координаты с помощью Nominatim (OpenStreetMap).

    Args:
        caption: Адрес в виде строки

    Returns:
        Кортеж (широта, долгота) или None при ошибке
    """
    try:
        geolocator = Nominatim(user_agent="simbioset")
        location = geolocator.geocode(caption, exactly_one=True, timeout=10)
        if location:
            return (location.latitude, location.longitude)
        return None
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None


def extract_location_and_time(text: str) -> Dict[str, Any]:
    """
    Извлекает информацию о местоположении и времени из текста.

    Args:
        text: Текст для анализа

    Returns:
        Словарь с извлеченной информацией о местоположении и времени
    """
    # Явно указываем тип словаря, чтобы mypy не ограничивал значения только None.
    result: Dict[str, Any] = {"location": None, "time_reference": None}

    # Ищем возможные названия местоположений (города, регионы и т.д.)
    location_patterns = [
        r"\b(?:в|на|около|возле|рядом с)\s+([А-ЯЁ][а-яё]*\s*[А-ЯЁ]*[а-яё]*)",
        r"\b([А-ЯЁ][а-яё]*\s*[А-ЯЁ]*[а-яё]*)\s+(?:область|край|республика|район|город|село|деревня|поселок|станция|озеро|река|лес)\b",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["location"] = match.group(1).strip()
            break

    # Ищем возможные временные ссылки
    time_patterns = [
        r"\b(\d{4})\s*(?:год|года|году|годом)\b",  # год
        r"\b(январ[ья]|феврал[ья]|март[а]|апрел[ья]|ма[ья]|июн[ья]|июл[ья]|август[а]|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])\b",  # месяц
        r"\b(летом|весной|осенью|зимой|в(?:\s+|)(?:этом|прошлом|следующем)\s+(?:летом|весной|осенью|зимой))\b",  # время года
        r"\b(сегодня|вчера|завтра|нынче|сейчас|давно|давеча|раньше|позже)\b",  # относительное время
    ]

    for pattern in time_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result["time_reference"] = ", ".join(matches)
            break

    return result
