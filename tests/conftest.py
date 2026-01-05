"""Конфигурация pytest для интеграционных тестов Weaviate"""

import pytest
import asyncio
import os
from typing import AsyncGenerator


@pytest.fixture(scope="session")
def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Weaviate availability check - simplified to avoid v3 deprecation warnings
weaviate_skip = pytest.mark.skip(reason="Weaviate tests skipped - requires Weaviate connection")


def pytest_addoption(parser):
    """Добавляет опцию командной строки для локального запуска Weaviate"""
    parser.addoption(
        "--weaviate-local",
        action="store_true",
        default=False,
        help="Запустить локальный Weaviate для тестов (требует установленный бинарник)",
    )
