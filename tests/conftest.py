"""Конфигурация pytest для интеграционных тестов Weaviate"""

import pytest


def pytest_addoption(parser):
    """Добавляет опцию командной строки для локального запуска Weaviate"""
    parser.addoption(
        "--weaviate-local",
        action="store_true",
        default=False,
        help="Запустить локальный Weaviate для тестов (требует установленный бинарник)",
    )
