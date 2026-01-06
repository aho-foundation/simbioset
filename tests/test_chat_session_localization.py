"""
Unit тесты для функциональности локализации в ChatSessionService.

Тестирует привязку локализации к сессиям чата.
Использует локальный Redis для тестирования.
"""

from unittest.mock import AsyncMock, patch
import pytest
import redis.asyncio as redis
import time

from api.chat.service import ChatSessionService
from api.chat.models import ChatSessionCreate


@pytest.fixture(scope="session")
async def redis_available():
    """Проверяет доступность Redis."""
    try:
        # Создаем тестовый Redis клиент
        test_redis = redis.from_url("redis://localhost:6379", decode_responses=True)
        await test_redis.ping()
        await test_redis.close()
        return True
    except Exception:
        return False


class TestChatSessionLocalization:
    """Тесты для функциональности локализации в чат-сессиях."""

    @pytest.fixture
    def session_service(self):
        """Фикстура с ChatSessionService."""
        return ChatSessionService()

    @pytest.fixture
    def test_session_data(self):
        """Фикстура с тестовыми данными сессии."""
        return ChatSessionCreate(topic="Тестовая сессия для локализации", conceptTreeId=None)

    @pytest.fixture(autouse=True)
    def mock_session_manager(self):
        """Автоматически мокаем session_manager для всех тестов."""
        with patch("api.chat.service.session_manager") as mock_manager:
            # Настраиваем моки для всех методов
            mock_manager.create_session = AsyncMock()
            mock_manager.get_session = AsyncMock(return_value=None)
            mock_manager.update_session = AsyncMock()

            # Для тестов get_session возвращаем данные сессии когда нужно
            def mock_get_session_side_effect(session_id):
                # Имитируем возврат данных сессии из кеша сервиса
                return None  # По умолчанию None, переопределяем в тестах при необходимости

            mock_manager.get_session.side_effect = mock_get_session_side_effect
            yield mock_manager

    @pytest.mark.asyncio
    async def test_create_session_initial_location_none(self, session_service, test_session_data):
        """Тест, что при создании сессии локализация изначально отсутствует."""
        # Act
        session = await session_service.create_session(test_session_data)

        # Assert
        assert session.location is None
        assert session.id is not None
        assert session.topic == test_session_data.topic

    @pytest.mark.asyncio
    async def test_update_session_location_success(self, session_service, test_session_data):
        """Тест успешного обновления локализации сессии."""
        # Arrange
        session = await session_service.create_session(test_session_data)
        original_updated_at = session.updated_at

        test_location_data = {
            "location": "Москва",
            "ecosystems": [
                {"name": "городской парк", "scale": "habitat"},
                {"name": "микробиом почвы", "scale": "organ"},
            ],
            "coordinates": {"latitude": 55.7558, "longitude": 37.6176},
            "source": "test",
        }

        # Даем небольшую задержку, чтобы updated_at изменился
        time.sleep(0.001)

        # Act
        updated_session = await session_service.update_session_location(session.id, test_location_data)

        # Assert
        assert updated_session is not None
        assert updated_session.id == session.id
        assert updated_session.location == test_location_data
        assert updated_session.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_update_session_location_clear(self, session_service, test_session_data):
        """Тест сброса локализации сессии."""
        # Arrange
        session = await session_service.create_session(test_session_data)
        test_location_data = {
            "location": "Москва",
            "ecosystems": [{"name": "парк", "scale": "habitat"}],
            "coordinates": {"latitude": 55.7558, "longitude": 37.6176},
        }

        # Устанавливаем локализацию
        await session_service.update_session_location(session.id, test_location_data)
        # Нужно заново получить сессию, чтобы проверить location
        updated_session = await session_service.get_session(session.id)
        assert updated_session.location == test_location_data

        # Act - Сбрасываем локализацию
        cleared_session = await session_service.update_session_location(session.id, None)

        # Assert
        assert cleared_session is not None
        assert cleared_session.location is None
        assert cleared_session.id == session.id

    @pytest.mark.asyncio
    async def test_update_session_location_not_found(self, session_service):
        """Тест обновления локализации для несуществующей сессии."""
        # Act
        result = await session_service.update_session_location("nonexistent-id", {"location": "test"})

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_with_location(self, session_service, test_session_data):
        """Тест получения сессии с установленной локализацией."""
        # Arrange
        session = await session_service.create_session(test_session_data)
        test_location_data = {
            "location": "Санкт-Петербург",
            "ecosystems": [{"name": "река Нева", "scale": "habitat"}],
            "coordinates": {"latitude": 59.9343, "longitude": 30.3351},
            "source": "manual",
        }
        await session_service.update_session_location(session.id, test_location_data)

        # Act
        retrieved_session = await session_service.get_session(session.id)

        # Assert
        assert retrieved_session is not None
        assert retrieved_session.location == test_location_data
        assert retrieved_session.id == session.id

    @pytest.mark.asyncio
    async def test_location_data_structure_preservation(self, session_service, test_session_data):
        """Тест сохранения структуры данных локализации."""
        # Arrange
        session = await session_service.create_session(test_session_data)

        complex_location_data = {
            "location": "Лесной массив",
            "ecosystems": [
                {
                    "name": "Смешанный лес",
                    "scale": "habitat",
                    "description": "Лес с преобданием сосны и березы",
                    "confidence": 0.85,
                    "biome": "temperate_forest",
                    "threat_level": "medium",
                },
                {
                    "name": "Почвенный микробиом",
                    "scale": "organ",
                    "description": "Комплекс почвенных микроорганизмов",
                    "confidence": 0.92,
                    "biome": "soil_microbiome",
                },
            ],
            "coordinates": {"latitude": 56.2345, "longitude": 38.1234, "accuracy": 10.5},
            "weather": {"temperature": 18.5, "humidity": 65, "pressure": 750, "wind_speed": 3.2},
            "source": "integrated_analysis",
            "timestamp": int(time.time() * 1000),
        }

        # Act
        updated_session = await session_service.update_session_location(session.id, complex_location_data)

        # Assert
        assert updated_session is not None
        assert updated_session.location == complex_location_data

        # Проверяем, что все вложенные структуры сохранены
        location = updated_session.location
        assert location["location"] == "Лесной массив"
        assert len(location["ecosystems"]) == 2
        assert location["ecosystems"][0]["name"] == "Смешанный лес"
        assert location["ecosystems"][1]["scale"] == "organ"
        assert location["coordinates"]["accuracy"] == 10.5
        assert location["weather"]["temperature"] == 18.5
        assert location["source"] == "integrated_analysis"
        assert "timestamp" in location

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent_location(self, session_service):
        """Тест независимости локализации разных сессий."""
        # Arrange
        session1 = await session_service.create_session(ChatSessionCreate(topic="Сессия 1", conceptTreeId=None))
        session2 = await session_service.create_session(ChatSessionCreate(topic="Сессия 2", conceptTreeId=None))

        location1 = {
            "location": "Москва",
            "ecosystems": [{"name": "парк", "scale": "habitat"}],
        }
        location2 = {
            "location": "Петербург",
            "ecosystems": [{"name": "река", "scale": "habitat"}],
        }

        # Act
        await session_service.update_session_location(session1.id, location1)
        await session_service.update_session_location(session2.id, location2)

        # Assert
        updated_session1 = await session_service.get_session(session1.id)
        updated_session2 = await session_service.get_session(session2.id)

        assert updated_session1.location == location1
        assert updated_session2.location == location2
        assert updated_session1.location != updated_session2.location

    @pytest.mark.asyncio
    async def test_location_update_timestamp(self, session_service, test_session_data):
        """Тест обновления timestamp при изменении локализации."""
        # Arrange
        session = await session_service.create_session(test_session_data)
        initial_timestamp = session.updated_at

        time.sleep(0.01)  # Увеличенная задержка для надежности

        # Act - Первое обновление
        await session_service.update_session_location(session.id, {"location": "test1"})

        # Assert
        first_update = await session_service.get_session(session.id)
        assert first_update.updated_at > initial_timestamp
        first_timestamp = first_update.updated_at

        time.sleep(1.0)  # Увеличенная задержка для надежности

        # Act - Второе обновление
        await session_service.update_session_location(session.id, {"location": "test2"})

        # Assert
        second_update = await session_service.get_session(session.id)
        second_timestamp = second_update.updated_at
        assert second_timestamp > first_timestamp

    @pytest.mark.asyncio
    async def test_location_none_handling(self, session_service, test_session_data):
        """Тест корректной обработки None значений в локализации."""
        # Arrange
        session = await session_service.create_session(test_session_data)

        # Act & Assert - Установка None
        result = await session_service.update_session_location(session.id, None)
        assert result is not None
        assert result.location is None

        # Act & Assert - Повторная установка None
        result2 = await session_service.update_session_location(session.id, None)
        assert result2 is not None
        assert result2.location is None

        # Act & Assert - Установка данных после None
        test_data = {"location": "test"}
        result3 = await session_service.update_session_location(session.id, test_data)
        assert result3 is not None
        assert result3.location == test_data
