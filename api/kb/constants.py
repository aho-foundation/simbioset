"""Constants for Knowledge Base API.

This module defines all constants used across the Knowledge Base API,
including tree limits, category colors, source types, sentiment types,
and sender types as specified in conversation_tree_framework.md.
"""

MAX_TREE_DEPTH = 100  # Maximum depth to prevent cycles and stack overflow
MAX_CHILDREN_PER_NODE = 50  # Performance limit for UI rendering
MAX_TOTAL_NODES = 10000  # Memory limit to prevent application slowdown

# Category colors (not explicitly documented but used for visualization)
CATEGORY_COLORS = {
    "threat": "#ff4444",
    "protection": "#44ff44",
    "conservation": "#4444ff",
    "neutral": "#888888",
}

SOURCE_TYPE_CONFIRM = "confirm"
SOURCE_TYPE_DOUBT = "doubt"

SENTIMENT_POSITIVE = "positive"
SENTIMENT_NEGATIVE = "negative"
SENTIMENT_NEUTRAL = "neutral"

SENDER_USER = "user"
SENDER_BOT = "bot"
