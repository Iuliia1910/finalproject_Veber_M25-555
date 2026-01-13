import os
from dataclasses import dataclass, field
from typing import Tuple, Dict

@dataclass(frozen=True)
class ParserConfig:
    # Конфигурация Parser Service:
    #- API-ключи из переменных окружения
    #- Эндпоинты для запросов
    #- Списки валют
    #- Пути к файлам
    #- Таймауты запросов

    EXCHANGERATE_API_KEY: str = field(default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", "a748faeb2d9bb48fc113bd89"))

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_FIAT_CURRENCY: str = "USD"

    FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "SOL")

    CRYPTO_ID_MAP: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    })

    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    REQUEST_TIMEOUT: int = 10
