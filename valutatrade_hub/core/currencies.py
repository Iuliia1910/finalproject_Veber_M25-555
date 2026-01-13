from abc import ABC, abstractmethod
from typing import Dict

# Абсолютный импорт
from valutatrade_hub.core.exceptions import CurrencyNotFoundError

class Currency(ABC):
    """Абстрактный базовый класс валюты."""

    def __init__(self, name: str, code: str):
        # Валидация кода
        if not code or not isinstance(code, str):
            raise ValueError("Код валюты не может быть пустым")
        if len(code) < 2 or len(code) > 5:
            raise ValueError("Код валюты должен содержать от 2 до 5 символов")
        if ' ' in code:
            raise ValueError("Код валюты не может содержать пробелы")

        # Валидация имени
        if not name or not isinstance(name, str):
            raise ValueError("Имя валюты не может быть пустым")

        self._name = name.strip()
        self._code = code.upper()

    @property
    def name(self) -> str:
        """Человекочитаемое имя валюты."""
        return self._name

    @property
    def code(self) -> str:
        """ISO-код или тикер валюты."""
        return self._code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление для UI/логов."""
        pass

    def __str__(self) -> str:
        return self.get_display_info()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}', code='{self._code}')"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Currency):
            return False
        return self._code == other.code

    def __hash__(self) -> int:
        return hash(self._code)


class FiatCurrency(Currency):
    """Фиатная валюта (традиционные государственные валюты)."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)

        if not issuing_country or not isinstance(issuing_country, str):
            raise ValueError("Страна эмитент не может быть пустой")

        self._issuing_country = issuing_country.strip()

    @property
    def issuing_country(self) -> str:
        """Страна или зона эмиссии валюты."""
        return self._issuing_country

    def get_display_info(self) -> str:
        """Возвращает строковое представление фиатной валюты."""
        return f"[FIAT] {self._code} — {self._name} (Issuing: {self._issuing_country})"

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name='{self._name}', "
                f"code='{self._code}', issuing_country='{self._issuing_country}')")


class CryptoCurrency(Currency):
    """Криптовалюта."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float = 0.0):
        super().__init__(name, code)

        if not algorithm or not isinstance(algorithm, str):
            raise ValueError("Алгоритм не может быть пустым")
        if market_cap < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной")

        self._algorithm = algorithm.strip()
        self._market_cap = market_cap

    @property
    def algorithm(self) -> str:
        """Алгоритм консенсуса/хэширования."""
        return self._algorithm

    @property
    def market_cap(self) -> float:
        """Рыночная капитализация в USD."""
        return self._market_cap

    @market_cap.setter
    def market_cap(self, value: float):
        """Установка рыночной капитализации."""
        if value < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной")
        self._market_cap = value

    def get_display_info(self) -> str:
        """Возвращает строковое представление криптовалюты."""
        # Форматируем капитализацию
        if self._market_cap >= 1e12:
            mcap_str = f"{self._market_cap/1e12:.2f}T"
        elif self._market_cap >= 1e9:
            mcap_str = f"{self._market_cap/1e9:.2f}B"
        elif self._market_cap >= 1e6:
            mcap_str = f"{self._market_cap/1e6:.2f}M"
        else:
            mcap_str = f"{self._market_cap:,.2f}"

        return f"[CRYPTO] {self._code} — {self._name} (Algo: {self._algorithm}, MCAP: ${mcap_str})"

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name='{self._name}', code='{self._code}', "
                f"algorithm='{self._algorithm}', market_cap={self._market_cap})")


# Реестр валют
_CURRENCY_REGISTRY: Dict[str, Currency] = {}


def _initialize_currency_registry():
    """Инициализация реестра валют."""
    global _CURRENCY_REGISTRY

    # Фиатные валюты
    fiats = [
        FiatCurrency("US Dollar", "USD", "United States"),
        FiatCurrency("Euro", "EUR", "Eurozone"),
        FiatCurrency("British Pound", "GBP", "United Kingdom"),
        FiatCurrency("Japanese Yen", "JPY", "Japan"),
        FiatCurrency("Chinese Yuan", "CNY", "China"),
        FiatCurrency("Russian Ruble", "RUB", "Russia"),
        FiatCurrency("Swiss Franc", "CHF", "Switzerland"),
        FiatCurrency("Canadian Dollar", "CAD", "Canada"),
        FiatCurrency("Australian Dollar", "AUD", "Australia"),
    ]

    # Криптовалюты (примерные данные)
    cryptos = [
        CryptoCurrency("Bitcoin", "BTC", "SHA-256", market_cap=1.12e12),
        CryptoCurrency("Ethereum", "ETH", "Ethash", market_cap=372e9),
        CryptoCurrency("Binance Coin", "BNB", "BEP-2/BEP-20", market_cap=85e9),
        CryptoCurrency("Cardano", "ADA", "Ouroboros", market_cap=45e9),
        CryptoCurrency("Solana", "SOL", "Proof of History", market_cap=38e9),
        CryptoCurrency("Ripple", "XRP", "RPCA", market_cap=35e9),
        CryptoCurrency("Polkadot", "DOT", "Nominated Proof-of-Stake", market_cap=25e9),
        CryptoCurrency("Dogecoin", "DOGE", "Scrypt", market_cap=22e9),
        CryptoCurrency("Litecoin", "LTC", "Scrypt", market_cap=6.5e9),
    ]

    # Добавляем все валюты в реестр
    for currency in fiats + cryptos:
        _CURRENCY_REGISTRY[currency.code] = currency


def get_currency(code: str) -> Currency:
    """
    Фабричный метод для получения валюты по коду.

    Args:
        code: Код валюты (например, "USD", "BTC")

    Returns:
        Объект Currency

    Raises:
        CurrencyNotFoundError: Если валюта с таким кодом не найдена
    """
    if not _CURRENCY_REGISTRY:
        _initialize_currency_registry()

    code_upper = code.upper()

    if code_upper not in _CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(code_upper)

    return _CURRENCY_REGISTRY[code_upper]


def get_all_currencies() -> Dict[str, Currency]:
    """Возвращает все зарегистрированные валюты."""
    if not _CURRENCY_REGISTRY:
        _initialize_currency_registry()

    return _CURRENCY_REGISTRY.copy()


def register_currency(currency: Currency):
    """
    Регистрирует новую валюту в реестре.

    Args:
        currency: Объект Currency для регистрации

    Raises:
        ValueError: Если валюта с таким кодом уже существует
    """
    if not _CURRENCY_REGISTRY:
        _initialize_currency_registry()

    if currency.code in _CURRENCY_REGISTRY:
        raise ValueError(f"Валюта с кодом '{currency.code}' уже зарегистрирована")

    _CURRENCY_REGISTRY[currency.code] = currency


def get_currency_type(code: str) -> str:
    """
    Возвращает тип валюты по коду.

    Returns:
        "FIAT", "CRYPTO" или "UNKNOWN"
    """
    try:
        currency = get_currency(code)
        if isinstance(currency, FiatCurrency):
            return "FIAT"
        elif isinstance(currency, CryptoCurrency):
            return "CRYPTO"
    except CurrencyNotFoundError:
        return "UNKNOWN"


# Инициализируем реестр при импорте модуля
_initialize_currency_registry()