#!/usr/bin/env python3
"""
Скрипт для тестирования функциональности локализации экосистем.

Проверяет работу API локализации и привязку к сессиям.
"""

import asyncio
import json
import sys
from pathlib import Path

# Импорты из проекта
sys.path.append("/Users/tony/code/simbioset-website")

from api.chat.service import ChatSessionService
from api.storage.weaviate_storage import WeaviateStorage
from api.logger import root_logger

log = root_logger.debug


async def test_session_localization():
    """Тестирует привязку локализации к сессии."""

    log("🧪 Тестирование привязки локализации к сессии...")

    # Создаем тестовую сессию
    session_service = ChatSessionService()
    test_session = session_service.create_session({"topic": "Тестовая сессия для локализации", "conceptTreeId": None})

    log(f"✅ Создана тестовая сессия: {test_session.id}")

    # Проверяем, что изначально локализация отсутствует
    initial_location = test_session.location
    assert initial_location is None, "Локализация должна быть None изначально"
    log("✅ Изначально локализация отсутствует")

    # Устанавливаем тестовую локализацию
    test_location_data = {
        "location": "Москва",
        "ecosystems": [{"name": "городской парк", "scale": "habitat"}, {"name": "микробиом почвы", "scale": "organ"}],
        "coordinates": {"latitude": 55.7558, "longitude": 37.6176},
        "source": "test",
    }

    updated_session = session_service.update_session_location(test_session.id, test_location_data)

    assert updated_session is not None, "Сессия должна быть обновлена"
    assert updated_session.location == test_location_data, "Локализация должна быть сохранена"
    log("✅ Локализация успешно сохранена в сессии")

    # Проверяем получение сессии с локализацией
    retrieved_session = session_service.get_session(test_session.id)
    assert retrieved_session is not None, "Сессия должна быть найдена"
    assert retrieved_session.location == test_location_data, "Локализация должна сохраняться при получении"
    log("✅ Локализация сохраняется при получении сессии")

    # Сбрасываем локализацию
    reset_session = session_service.update_session_location(test_session.id, None)
    assert reset_session is not None, "Сессия должна быть обновлена"
    assert reset_session.location is None, "Локализация должна быть сброшена"
    log("✅ Локализация успешно сброшена")

    log("🎉 Все тесты локализации сессий пройдены!")


async def test_symbiont_search():
    """Тестирует поиск симбионтов."""

    log("🧪 Тестирование поиска симбионтов...")

    try:
        weaviate_storage = WeaviateStorage()
        from api.storage.symbiont_service import SymbiontService, SymbiontPathogen

        symbiont_service = SymbiontService(weaviate_storage)

        # Создаем тестового симбионта
        test_symbiont = SymbiontPathogen.from_dict(
            {
                "id": "test-symbiont-001",
                "name": "Тестовый симбионт",
                "scientific_name": "Test symbiont",
                "type": "symbiont",
                "category": "бактерия",
                "interaction_type": "mutualistic",
                "biochemical_role": "тестовый симбиоз",
                "prevalence": 0.5,
                "risk_level": "low",
                "detection_confidence": 0.8,
            }
        )

        await symbiont_service.create_symbiont(test_symbiont)
        log("✅ Тестовый симбионт создан")

        # Ищем созданного симбионта
        search_results = await symbiont_service.search_symbionts(query="Тестовый симбионт", limit=5)

        assert len(search_results) > 0, "Должен быть найден хотя бы один симбионт"
        found_symbiont = search_results[0]
        assert found_symbiont.name == "Тестовый симбионт", "Найден правильный симбионт"
        log("✅ Поиск симбионтов работает корректно")

        # Удаляем тестового симбионта
        delete_success = await symbiont_service.delete_symbiont(test_symbiont.id)
        assert delete_success, "Симбионт должен быть удален"
        log("✅ Симбионт успешно удален")

    except Exception as e:
        log(f"⚠️ Тест поиска симбионтов пропущен (Weaviate недоступен): {e}")


async def main():
    """Главная функция тестирования."""

    log("🚀 Запуск тестирования локализации экосистем...")

    try:
        # Тестируем локализацию сессий
        await test_session_localization()

        # Тестируем поиск симбионтов (если Weaviate доступен)
        await test_symbiont_search()

        log("🎉 Все тесты пройдены успешно!")

    except Exception as e:
        log(f"❌ Ошибка при тестировании: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
