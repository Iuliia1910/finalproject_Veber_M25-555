"""
Конфигурация логирования для ValutaTrade Hub.
"""

import logging
import logging.config
import json
from datetime import datetime

from valutatrade_hub.infra.settings import settings


class JSONFormatter(logging.Formatter):
    """Форматирование логов в JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Добавляем дополнительные поля если есть
        if hasattr(record, 'action'):
            log_data['action'] = record.action
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'username'):
            log_data['username'] = record.username
        if hasattr(record, 'currency'):
            log_data['currency'] = record.currency

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """Настройка логирования."""

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": settings.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            },
            "json": {
                "()": JSONFormatter
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": settings.get("log_file", "valutatrade.log"),
                "encoding": "utf-8",
                "mode": "a"
            },
            "actions_file": {
                "class": "logging.FileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": "actions.log",
                "encoding": "utf-8",
                "mode": "a"
            }
        },
        "loggers": {
            "valutatrade": {
                "level": settings.get("log_level", "INFO").upper(),
                "handlers": ["console", "file"],
                "propagate": False
            },
            "valutatrade.actions": {
                "level": "INFO",
                "handlers": ["actions_file"],
                "propagate": False
            }
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"]
        }
    }

    try:
        logging.config.dictConfig(log_config)
    except Exception as e:
        # Если не удалось настроить файловое логирование, используем только консоль
        print(f"⚠️  Не удалось настроить файловое логирование: {e}")
        # Простая настройка только консоли
        logging.basicConfig(
            level=getattr(logging, settings.get("log_level", "INFO").upper()),
            format=settings.get("log_format", "%(levelname)s - %(message)s")
        )


# Создаем логгеры
logger = logging.getLogger("valutatrade")
actions_logger = logging.getLogger("valutatrade.actions")

# Инициализируем логирование
setup_logging()