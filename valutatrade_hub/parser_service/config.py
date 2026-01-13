import os
from dataclasses import dataclass, field
from typing import Tuple, Dict

@dataclass(frozen=True)
class ParserConfig:
    """
    Конфигурация Parser Service:
    - API-ключи из переменных окружения
    - Эндпоинты для запросов
    - Списки валют
    - Пути к файлам
    - Таймауты запросов
    """

    # ⚠️ Секретные ключи через переменные окружения
    EXCHANGERATE_API_KEY: str = field(default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", ""))

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Базовая валюта для всех запросов
    BASE_FIAT_CURRENCY: str = "USD"

    # Списки валют
    FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "SOL")

    # Сопоставление тикеров и CoinGecko ID
    CRYPTO_ID_MAP: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    })

    # Пути к файлам
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10  # секунд
