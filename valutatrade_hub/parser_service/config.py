from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class ParserConfig:
    # --- базовые настройки ---
    BASE_CURRENCY: str = "USD"
    REQUEST_TIMEOUT: int = 10
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: float = 1.0

    # --- валюты ---
    FIAT_CURRENCIES: List[str] = field(default_factory=lambda: [
        "EUR", "GBP", "JPY", "RUB", "CNY", "AED"
    ])

    CRYPTO_CURRENCIES: List[str] = field(default_factory=lambda: [
        "BTC", "ETH", "SOL"
    ])

    CRYPTO_ID_MAP: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    })

    # --- API ---
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    EXCHANGERATE_API_KEY: str = "a748faeb2d9bb48fc113bd89"

    # --- cache ---
    CACHE_TTL_MINUTES: int = 10
    MAX_HISTORY_ENTRIES: int = 1000

    # --- пути ---
    BASE_DIR: Path = field(init=False)
    DATA_DIR: Path = field(init=False)
    RATES_FILE_PATH: Path = field(init=False)
    HISTORY_FILE_PATH: Path = field(init=False)

    def __post_init__(self):
        self.BASE_DIR = Path(__file__).resolve().parents[2]
        self.DATA_DIR = self.BASE_DIR / "data"

        self.RATES_FILE_PATH = self.DATA_DIR / "exchange_rates.json"
        self.HISTORY_FILE_PATH = self.DATA_DIR / "rates.json"

    def ensure_directories(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
