import logging
import warnings
from pathlib import Path
from typing import Any

import colorlog

_lib_path = Path(__file__).parents[1]
_leng_path = len(_lib_path.as_posix())


def basic_filter(record: logging.LogRecord) -> bool:
    """🔍 Базовый фильтр для всех логов - только добавляет метаданные"""
    # Define `package` attribute with the relative path.
    record.package = record.pathname[_leng_path + 1 :].replace(".py", "")
    record.emoji = (
        ""
        if record.levelno == logging.INFO
        else "👷‍♂️"
        if record.levelno == logging.WARNING
        else "❌"
        if record.levelno == logging.ERROR
        else "🧨"
        if record.levelno == logging.CRITICAL
        else ""
    )
    return True


# Define the color scheme
color_scheme = {
    "DEBUG": "light_black",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}

# Define secondary log colors
secondary_colors = {
    "log_name": {"DEBUG": "blue"},
    "asctime": {"DEBUG": "cyan"},
    "process": {"DEBUG": "purple"},
    "module": {"DEBUG": "light_black,bg_blue"},
    "funcName": {"DEBUG": "light_white,bg_blue"},  # Add this line
}

# Define the log format string
fmt_string = "%(emoji)s%(log_color)s%(package)s.%(funcName)s%(reset)s %(white)s%(message)s"

# Define formatting configuration
fmt_config = {
    "log_colors": color_scheme,
    "secondary_log_colors": secondary_colors,
    "style": "%",
    "reset": True,
}


class MultilineColoredFormatter(colorlog.ColoredFormatter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.log_colors = kwargs.pop("log_colors", {})
        self.secondary_log_colors = kwargs.pop("secondary_log_colors", {})

    def format(self, record: logging.LogRecord) -> str:
        # Add default emoji if not present
        if not hasattr(record, "emoji"):
            record.emoji = "📝"

        # Add default package if not present
        if not hasattr(record, "package"):
            record.package = getattr(record, "name", "unknown")

        # Format the first line normally
        formatted_first_line = super().format(record)

        # Check if the message has multiple lines
        lines = formatted_first_line.split("\n")
        if len(lines) > 1:
            # For multiple lines, only apply colors to the first line
            # Keep subsequent lines without color formatting
            formatted_lines = [formatted_first_line]
            formatted_lines.extend(lines[1:])
            return "\n".join(formatted_lines)
        return super().format(record)


# Create a MultilineColoredFormatter object for colorized logging
formatter = MultilineColoredFormatter(fmt_string, **fmt_config)


def get_colorful_logger(name: str = "main") -> logging.Logger:
    # Create and configure the logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create a stream handler with the formatter
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addFilter(basic_filter)  # 🔍 Базовый фильтр без подавления

    return logger


# Set up the root logger with the same formatting
root_logger = get_colorful_logger()

# Suppress verbose warnings from external libraries
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")
warnings.filterwarnings("ignore", category=DeprecationWarning)
