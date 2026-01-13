import time
import requests
from typing import Dict, Any, Optional


class APIClientBase:

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })

    def _make_request(self, url: str, params: Dict = None, method: str = 'GET') -> Optional[Dict]:
        for attempt in range(self.config.RETRY_ATTEMPTS):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=self.config.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Ошибка запроса: {e}")
                if attempt == self.config.RETRY_ATTEMPTS - 1:
                    print(f"Все попытки неудачны для {url}")
                    return None
                time.sleep(self.config.RETRY_DELAY)
        return None


class CoinGeckoClient(APIClientBase):

    def get_crypto_rates(self) -> Dict[str, float]:
        crypto_ids = list(self.config.CRYPTO_ID_MAP.values())
        crypto_ids_str = ','.join(crypto_ids)

        params = {
            'ids': crypto_ids_str,
            'vs_currencies': self.config.BASE_CURRENCY.lower()
        }

        data = self._make_request(self.config.COINGECKO_URL, params)

        if not data:
            print("Не удалось получить данные от CoinGecko")
            return {}

        rates = {}
        for code, coin_id in self.config.CRYPTO_ID_MAP.items():
            if coin_id in data and self.config.BASE_CURRENCY.lower() in data[coin_id]:
                rate = data[coin_id][self.config.BASE_CURRENCY.lower()]
                rates[f"{self.config.BASE_CURRENCY}_{code}"] = rate
                print(f"{self.config.BASE_CURRENCY}/{code}: {rate}")

        return rates

class ExchangeRateClient(APIClientBase):

    def get_fiat_rates(self) -> Dict[str, float]:

        url = f"{self.config.EXCHANGERATE_API_URL}/{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        data = self._make_request(url)

        if not data:
            print("Не удалось получить данные от ExchangeRate API")
            return {}

        print(f"Статус: {data.get('result', 'N/A')}")

        rates = {}
        if 'conversion_rates' in data:
            for currency in self.config.FIAT_CURRENCIES:
                if currency in data['conversion_rates']:
                    rate = data['conversion_rates'][currency]
                    rates[f"{self.config.BASE_CURRENCY}_{currency}"] = rate
                    print(f"{self.config.BASE_CURRENCY}/{currency}: {rate:.4f}")

        return rates


class RateManager:

    def __init__(self, config):
        self.config = config
        self.coingecko_client = CoinGeckoClient(config)
        self.exchangerate_client = ExchangeRateClient(config)

    def get_all_rates(self) -> Dict[str, Dict[str, Any]]:

        print("\nФИАТНЫЕ ВАЛЮТЫ (ExchangeRate API):")
        fiat_rates = self.exchangerate_client.get_fiat_rates()

        print("\nКРИПТОВАЛЮТЫ (CoinGecko API):")
        crypto_rates = self.coingecko_client.get_crypto_rates()

        all_rates = {}

        for pair, rate in fiat_rates.items():
            all_rates[pair] = {
                'rate': rate,
                'source': 'exchangerate',
                'timestamp': time.time(),
                'type': 'fiat'
            }

        for pair, rate in crypto_rates.items():
            all_rates[pair] = {
                'rate': rate,
                'source': 'coingecko',
                'timestamp': time.time(),
                'type': 'crypto'
            }

        #print("\nДОБАВЛЕНИЕ ОБРАТНЫХ КУРСОВ:")
        #base_pairs = list(all_rates.keys())
        #for pair in base_pairs:
         #   if '_' in pair:
          #      from_curr, to_curr = pair.split('_')
           #     reverse_pair = f"{to_curr}_{from_curr}"

#                if reverse_pair not in all_rates and all_rates[pair]['rate'] > 0:
 #                   reverse_rate = 1 / all_rates[pair]['rate']
  #                  all_rates[reverse_pair] = {
   #                     'rate': reverse_rate,
    #                    'source': all_rates[pair]['source'],
     #                   'timestamp': all_rates[pair]['timestamp'],
      #                  'type': all_rates[pair]['type']
       #             }
        #            print(f"  {reverse_pair}: {reverse_rate:.6f}")

        print(f"\nПОЛУЧЕНО ВСЕГО: {len(all_rates)} курсов")

        return all_rates

    def update_rates_from_dict(self, pairs: dict):
        self.rates = pairs
class ExchangeRateApiClient(ExchangeRateClient):
    pass