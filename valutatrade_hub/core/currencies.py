from abc import ABC, abstractmethod

# ================= ОШИБКА ДЛЯ НЕИЗВЕСТНОЙ ВАЛЮТЫ =================
class CurrencyNotFoundError(Exception):
    pass

# ================= АБСТРАКТНЫЙ КЛАСС =================
class Currency(ABC):
    def __init__(self, name: str, code: str):
        name = name.strip()
        code = code.strip().upper()

        if not name:
            raise ValueError("Currency name не может быть пустым")
        if not (2 <= len(code) <= 5) or " " in code:
            raise ValueError("Currency code должен быть 2–5 символов, без пробелов")

        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строку для UI/логов"""
        pass

# ================= FIAT ВАЛЮТА =================
class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        issuing_country = issuing_country.strip()
        if not issuing_country:
            raise ValueError("issuing_country не может быть пустым")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"

# ================= КРИПТОВАЛЮТА =================
class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        algorithm = algorithm.strip()
        if not algorithm:
            raise ValueError("algorithm не может быть пустым")
        if market_cap < 0:
            raise ValueError("market_cap должен быть >= 0")
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        mcap_str = f"{self.market_cap:.2e}"
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap_str})"

# ================= РЕЕСТР / ФАБРИКА ВАЛЮТ =================
_currency_registry = {
    # Fiat
    "USD": lambda: FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": lambda: FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": lambda: FiatCurrency("Russian Ruble", "RUB", "Russia"),
    # Crypto
    "BTC": lambda: CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": lambda: CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
}

def get_currency(code: str) -> Currency:
    code = code.strip().upper()
    factory = _currency_registry.get(code)
    if not factory:
        raise CurrencyNotFoundError(f"Currency '{code}' not found")
    return factory()
