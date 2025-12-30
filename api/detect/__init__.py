# детекторы просто расширяют контекст промпта для анализа

from . import (
    ecosystem_scaler,
    environment_quality,
    factcheck,
    image_processor,
    localize,
    organism_detector,
    relevance,
    rolestate,
    web_search,
)

__all__ = [
    "ecosystem_scaler",
    "environment_quality",
    "factcheck",
    "image_processor",
    "localize",
    "organism_detector",
    "relevance",
    "rolestate",
    "web_search",
]
