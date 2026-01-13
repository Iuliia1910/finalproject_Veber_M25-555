# valutatrade_hub/parser_service/api_clients.py

class ApiRequestError(Exception):
    """Выбрасывается при ошибках обращения к внешним API"""
    pass

from abc import ABC, abstractmethod

class BaseApiClient(ABC):
    @abstractmethod
    def fetch_rates(self) -> dict:
        """Возвращает словарь курсов валют в формате {PAIR: rate}"""
        pass
import requests
from .config import ParserConfig

class CoinGeckoClient(BaseApiClient):
    def __init__(self, config: ParserConfig):
        self.config = config

    def fetch_rates(self) -> dict:
        ids = ",".join([self.config.CRYPTO_ID_MAP[t] for t in self.config.CRYPTO_CURRENCIES])
        vs_currency = self.config.BASE_FIAT_CURRENCY.lower()
        url = f"{self.config.COINGECKO_URL}?ids={ids}&vs_currencies={vs_currency}"

        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            rates = {}
            for ticker, cg_id in self.config.CRYPTO_ID_MAP.items():
                if cg_id in data:
                    pair = f"{ticker}_{self.config.BASE_FIAT_CURRENCY}"
                    rates[pair] = data[cg_id][vs_currency]

            return rates

        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Ошибка запроса к CoinGecko: {e}")
        except KeyError as e:
            raise ApiRequestError(f"Ошибка обработки данных CoinGecko: {e}")

class ExchangeRateApiClient(BaseApiClient):
    def __init__(self, config: ParserConfig):
        if not config.EXCHANGERATE_API_KEY:
            raise ValueError("Не указан API-ключ для ExchangeRate-API")
        self.config = config

    def fetch_rates(self) -> dict:
        """
        Получает курсы фиатных валют относительно BASE_CURRENCY.
        Возвращает словарь вида {'EUR_USD': 1.23, ...}.
        """
        url = f"{self.config.EXCHANGERATE_API_URL}/{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_FIAT_CURRENCY}"
        try:
            resp = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            # Проверяем результат API
            if data.get("result") != "success":
                raise ApiRequestError(f"Ошибка ExchangeRate-API: {data.get('error-type', 'Unknown error')}")

            # Новое поле в актуальном API
            rates = data.get("conversion_rates")
            if not rates:
                raise ApiRequestError("Ошибка ExchangeRate-API: отсутствует поле 'conversion_rates'")

            # Фильтруем только нужные валюты из списка FIAT_CURRENCIES
            filtered = {
                f"{curr}_{self.config.BASE_FIAT_CURRENCY}": rate
                for curr, rate in rates.items()
                if curr in self.config.FIAT_CURRENCIES
            }

            return filtered

        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Ошибка сети ExchangeRate-API: {e}")

