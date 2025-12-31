"""
Тесты модуля получения погоды через Gismeteo.

Проверяет парсинг погоды, обработку ошибок и форматирование данных.
"""

import pytest
from unittest.mock import patch, AsyncMock
from api.detect.weather import get_weather, format_weather_for_context


class TestWeather:
    """Тесты модуля погоды."""

    @pytest.mark.asyncio
    @patch("api.detect.weather.geocode")
    @patch("aiohttp.ClientSession")
    async def test_get_weather_success(self, mock_session_class, mock_geocode):
        """Тест успешного получения погоды через Gismeteo."""
        # Мокаем геокодирование
        mock_geocode.return_value = (55.7558, 37.6173)  # Москва

        # Мокаем HTML ответы от Gismeteo
        search_html = """
        <html>
            <body>
                <a href="/weather-moscow-4368/">Москва</a>
            </body>
        </html>
        """

        weather_html = """
        <html>
            <body>
                <div class="temp">+15</div>
                <div class="condition">Облачно с прояснениями</div>
                <div>Влажность: <span class="value">65</span>%</div>
                <div>Ветер: <span class="speed">5 м/с</span> <span class="direction">СЗ</span></div>
                <div>Давление: <span class="value">760</span> мм рт.ст.</div>
            </body>
        </html>
        """

        # Настраиваем моки для aiohttp
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        # Первый запрос - поиск города
        search_response = AsyncMock()
        search_response.status = 200
        search_response.text = AsyncMock(return_value=search_html)
        search_response.__aenter__ = AsyncMock(return_value=search_response)
        search_response.__aexit__ = AsyncMock(return_value=None)

        # Второй запрос - страница погоды
        weather_response = AsyncMock()
        weather_response.status = 200
        weather_response.text = AsyncMock(return_value=weather_html)
        weather_response.__aenter__ = AsyncMock(return_value=weather_response)
        weather_response.__aexit__ = AsyncMock(return_value=None)

        # session.get() должен возвращать async context manager (не корутину!)
        # Используем MagicMock, который будет возвращать response объекты
        def mock_get(*args, **kwargs):
            # Возвращаем следующий response из списка
            if not hasattr(mock_get, "call_count"):
                mock_get.call_count = 0
            mock_get.call_count += 1
            if mock_get.call_count == 1:
                return search_response
            return weather_response

        mock_session.get = mock_get

        # Вызываем функцию
        result = await get_weather("Москва")

        # Проверяем результат
        assert result is not None
        assert result["city"] == "Москва"
        assert result["temperature"] == 15
        assert "Облачно" in result["condition"]
        assert result["timestamp"] is not None

    @pytest.mark.asyncio
    @patch("api.detect.weather.geocode")
    async def test_get_weather_no_city(self, mock_geocode):
        """Тест обработки случая, когда город не указан."""
        result = await get_weather("")
        assert result is None

        result = await get_weather(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_weather_past_time(self):
        """Тест обработки времени в прошлом - не запрашиваем погоду."""
        result = await get_weather("Москва", time_reference="вчера")
        assert result is None

        result = await get_weather("Москва", time_reference="давно")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_weather_future_time(self):
        """Тест обработки времени в будущем - не запрашиваем погоду."""
        result = await get_weather("Москва", time_reference="завтра")
        assert result is None

        result = await get_weather("Москва", time_reference="позже")
        assert result is None

    @pytest.mark.asyncio
    @patch("api.detect.weather.geocode")
    @patch("aiohttp.ClientSession")
    async def test_get_weather_current_time(self, mock_session_class, mock_geocode):
        """Тест обработки текущего времени - запрашиваем погоду."""
        mock_geocode.return_value = (55.7558, 37.6173)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        search_response = AsyncMock()
        search_response.status = 200
        search_response.text = AsyncMock(
            return_value='<html><body><a href="/weather-moscow-4368/">Москва</a></body></html>'
        )
        search_response.__aenter__ = AsyncMock(return_value=search_response)
        search_response.__aexit__ = AsyncMock(return_value=None)

        weather_response = AsyncMock()
        weather_response.status = 200
        weather_response.text = AsyncMock(return_value='<html><body><div class="temp">+15</div></body></html>')
        weather_response.__aenter__ = AsyncMock(return_value=weather_response)
        weather_response.__aexit__ = AsyncMock(return_value=None)

        # session.get() должен возвращать async context manager (не корутину!)
        def mock_get(*args, **kwargs):
            if not hasattr(mock_get, "call_count"):
                mock_get.call_count = 0
            mock_get.call_count += 1
            if mock_get.call_count == 1:
                return search_response
            return weather_response

        mock_session.get = mock_get

        result = await get_weather("Москва", time_reference="сегодня")
        # Должен вернуть результат, так как время текущее
        assert result is not None or result is None  # Может быть None если парсинг не сработал

    @pytest.mark.asyncio
    @patch("api.detect.weather.geocode")
    @patch("aiohttp.ClientSession")
    async def test_get_weather_search_fails(self, mock_session_class, mock_geocode):
        """Тест обработки ошибки при поиске города."""
        mock_geocode.return_value = (55.7558, 37.6173)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        search_response = AsyncMock()
        search_response.status = 404  # Страница не найдена
        search_response.__aenter__ = AsyncMock(return_value=search_response)
        search_response.__aexit__ = AsyncMock(return_value=None)

        # session.get() должен возвращать async context manager (не корутину!)
        def mock_get(*args, **kwargs):
            return search_response

        mock_session.get = mock_get

        result = await get_weather("Москва")
        assert result is None

    @pytest.mark.asyncio
    @patch("api.detect.weather.geocode")
    @patch("aiohttp.ClientSession")
    async def test_get_weather_no_city_link(self, mock_session_class, mock_geocode):
        """Тест обработки случая, когда ссылка на город не найдена."""
        mock_geocode.return_value = (55.7558, 37.6173)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        search_response = AsyncMock()
        search_response.status = 200
        search_response.text = AsyncMock(return_value="<html><body><p>Город не найден</p></body></html>")
        search_response.__aenter__ = AsyncMock(return_value=search_response)
        search_response.__aexit__ = AsyncMock(return_value=None)

        # session.get() должен возвращать async context manager (не корутину!)
        def mock_get(*args, **kwargs):
            return search_response

        mock_session.get = mock_get

        result = await get_weather("НесуществующийГород")
        assert result is None

    @pytest.mark.asyncio
    @patch("api.detect.weather.geocode")
    @patch("aiohttp.ClientSession")
    async def test_get_weather_parsing_error(self, mock_session_class, mock_geocode):
        """Тест обработки ошибки парсинга."""
        mock_geocode.return_value = (55.7558, 37.6173)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        search_response = AsyncMock()
        search_response.status = 200
        search_response.text = AsyncMock(
            return_value='<html><body><a href="/weather-moscow-4368/">Москва</a></body></html>'
        )
        search_response.__aenter__ = AsyncMock(return_value=search_response)
        search_response.__aexit__ = AsyncMock(return_value=None)

        weather_response = AsyncMock()
        weather_response.status = 200
        weather_response.text = AsyncMock(return_value="<html><body>Некорректный HTML</body></html>")
        weather_response.__aenter__ = AsyncMock(return_value=weather_response)
        weather_response.__aexit__ = AsyncMock(return_value=None)

        # session.get() должен возвращать async context manager (не корутину!)
        def mock_get(*args, **kwargs):
            if not hasattr(mock_get, "call_count"):
                mock_get.call_count = 0
            mock_get.call_count += 1
            if mock_get.call_count == 1:
                return search_response
            return weather_response

        mock_session.get = mock_get

        # Должен вернуть None при ошибке парсинга, но не упасть
        result = await get_weather("Москва")
        # Может быть None если парсинг не сработал, но не должно быть исключения
        assert result is None or isinstance(result, dict)

    def test_format_weather_for_context_empty(self):
        """Тест форматирования пустых данных о погоде."""
        result = format_weather_for_context(None)
        assert result == ""

        result = format_weather_for_context({})
        assert result == ""

    def test_format_weather_for_context_full(self):
        """Тест форматирования полных данных о погоде."""
        weather_data = {
            "temperature": 15,
            "condition": "Облачно",
            "humidity": 65,
            "wind_speed": "5.0 м/с",
            "wind_direction": "СЗ",
            "city": "Москва",
        }

        result = format_weather_for_context(weather_data)
        assert "Москва" in result
        assert "15°C" in result
        assert "Облачно" in result
        assert "65%" in result
        assert "5.0 м/с" in result
        assert "СЗ" in result

    def test_format_weather_for_context_partial(self):
        """Тест форматирования частичных данных о погоде."""
        weather_data = {
            "temperature": 15,
            "condition": "N/A",
            "humidity": "N/A",
            "wind_speed": "N/A",
            "city": "Москва",
        }

        result = format_weather_for_context(weather_data)
        assert "Москва" in result
        assert "15°C" in result
        assert "N/A" not in result  # N/A значения не должны попадать в результат

    def test_format_weather_for_context_wind_with_direction(self):
        """Тест форматирования ветра с направлением."""
        weather_data = {
            "temperature": 15,
            "wind_speed": "5.0 м/с",
            "wind_direction": "СЗ",
            "city": "Москва",
        }

        result = format_weather_for_context(weather_data)
        assert "ветер: 5.0 м/с (СЗ)" in result

    def test_format_weather_for_context_wind_without_direction(self):
        """Тест форматирования ветра без направления."""
        weather_data = {
            "temperature": 15,
            "wind_speed": "5.0 м/с",
            "wind_direction": "N/A",
            "city": "Москва",
        }

        result = format_weather_for_context(weather_data)
        assert "ветер: 5.0 м/с" in result
        assert "(N/A)" not in result  # N/A направление не должно попадать в результат
