"""
messages got classified by type:
    1 ecosystem vulnerability (possible risks)
    2 ecosystem risk (found problem to solve)
    3 suggested ecosystem solution
"""

from enum import Enum
from typing import Optional, Dict, Any


class MessageClassification(Enum):
    """Классификация сообщений"""

    ECOSYSTEM_VULNERABILITY = "ecosystem_vulnerability"  # уязвимости экосистемы
    ECOSYSTEM_RISK = "ecosystem_risk"  # риски экосистемы
    ECOSYSTEM_SOLUTION = "ecosystem_solution"  # решения экосистемы
    NEUTRAL = "neutral"


def classify_message_type(text: str) -> str:
    """
    Классифицирует сообщение по типу.

    Args:
        text: Текст сообщения для классификации

    Returns:
        Строка с типом классификации
    """
    # Заглушка для тестирования - всегда возвращает ecosystem_risk
    return "ecosystem_risk"
