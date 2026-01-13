import json
import logging
from pathlib import Path
from valutatrade_hub.core.usecases import register, login, deposit, buy, sell, get_rate_usecase
from valutatrade_hub.core.exceptions import InsufficientFundsError, CurrencyNotFoundError, ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.core.utils import RatesCache
from valutatrade_hub.infra.settings import SettingsLoader
logger = logging.getLogger(__name__)

current_user = None
SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "BTC", "ETH"]
ttl_seconds = SettingsLoader().get("RATES_CACHE_TTL", 3600)
PORTFOLIO_FILE = Path("data/portfolios.json")
cache = RatesCache(ttl_seconds=ttl_seconds)

def get_user_portfolio(user_id: int):
    if not PORTFOLIO_FILE.exists():
        return {"user_id": user_id, "wallets": {}}

    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for user in data:
        if user["user_id"] == user_id:
            return user

    return {"user_id": user_id, "wallets": {}}

def show_portfolio(base_currency: str = "USD"):
    global current_user
    if not current_user:
        print("Сначала выполните login")
        return

    user_id = current_user["user_id"]
    user_portfolio = get_user_portfolio(user_id)
    wallets = user_portfolio.get("wallets", {})

    print(f"\nПортфель пользователя '{current_user['username']}' (база: {base_currency}):")
    total = 0.0

    for code, wallet in wallets.items():
        amount = wallet.get("balance", 0.0)
        converted = amount
        try:
            if code != base_currency:
                pair = cache.get_pair(code, base_currency)
                if not pair:
                    raise CurrencyNotFoundError(f"Курс {code}->{base_currency} не найден или устарел")
                converted = amount * pair["rate"]
            print(f"- {code}: {amount:.4f}  → {converted:.2f} {base_currency}")
            total += converted
        except CurrencyNotFoundError:
            print(f"- {code}: {amount:.4f}  → ??? {base_currency} (курс отсутствует)")

    print(f"ИТОГО: {total:.2f} {base_currency}\n")

def update_rates_cli(source: str = None):
    config = ParserConfig()
    storage = RatesStorage(config.HISTORY_FILE_PATH)
    cache = RatesCache(file_path=config.RATES_FILE_PATH, ttl_seconds=3600)

    clients = []
    if source is None:
        clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
    elif source.lower() == "coingecko":
        clients = [CoinGeckoClient(config)]
    elif source.lower() in ("exchangerate", "exchangerate-api"):
        clients = [ExchangeRateApiClient(config)]
    else:
        print(f"Unknown source '{source}'. Valid options: coingecko, exchangerate")
        return

    updater = RatesUpdater(clients=clients, storage=storage, cache=cache)

    print("INFO: Starting rates update...")
    try:
        updater.run_update()
        total_rates = len(cache.all_pairs())
        last_refresh = cache.data.get("last_refresh", "N/A")
        print(f"Update successful. Total rates updated: {total_rates}. Last refresh: {last_refresh}")
    except ApiRequestError as e:
        print(f"ERROR: {e}")
        print("Update completed with errors. Check logs/parser.log for details.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        print("Update failed. Check logs/parser.log for details.")

MENU_OPTIONS = {
    "1": "register",
    "2": "login",
    "3": "show-portfolio",
    "4": "deposit",
    "5": "buy",
    "6": "sell",
    "7": "get-rate",
    "8": "logout",
    "9": "update-rates",
    "0": "exit"
}


def interactive_cli():
    global current_user
    print("ValutaTrade")

    config = ParserConfig()
    storage = RatesStorage(config.HISTORY_FILE_PATH)
    cache = RatesCache(file_path=config.RATES_FILE_PATH, ttl_seconds=3600)
    clients_map = {
        "coingecko": CoinGeckoClient(config),
        "exchangerate": ExchangeRateApiClient(config)
    }

    while True:
        print("\nДоступные команды:")
        for key, cmd in MENU_OPTIONS.items():
            print(f"{key}. {cmd}")

        choice = input("Введите команду или номер: ").strip().lower()
        cmd = MENU_OPTIONS.get(choice, choice)

        if cmd == "exit":
            print("Выход...")
            break

        elif cmd == "register":
            username = input("Username: ")
            password = input("Password: ")
            try:
                result = register(username, password)
                print(f"Пользователь '{result['username']}' зарегистрирован (id={result['user_id']})")
            except ValueError as e:
                print(e)

        elif cmd == "login":
            username = input("Username: ")
            password = input("Password: ")
            try:
                result = login(username, password)
                current_user = {"user_id": result["user_id"], "username": result["username"]}
                print(f"Вы вошли как '{current_user['username']}'")
            except ValueError as e:
                print(e)

        elif cmd == "logout":
            if current_user:
                print(f"Пользователь '{current_user['username']}' вышел из системы")
                current_user = None
            else:
                print("Вы не вошли в систему")

        elif cmd == "show-portfolio":
            base = input("Базовая валюта (по умолчанию USD): ").strip() or "USD"
            show_portfolio(base)

        elif cmd == "deposit":
            if not current_user:
                print("Сначала выполните login")
                continue
            currency = input("Валюта для депозита: ").strip().upper()
            try:
                amount = float(input("Сумма: "))
                result = deposit(current_user["user_id"], currency, amount)
                print(f"Депозит выполнен: {result['amount']:.4f} {currency}")
            except ValueError as e:
                print(e)

        elif cmd == "buy":
            if not current_user:
                print("Сначала выполните login")
                continue

            currency = input("Валюта для покупки: ").strip().upper()
            try:
                amount = float(input("Сумма покупки: "))
            except ValueError:
                print("Сумма должна быть числом больше 0")
                continue

            base = input("Базовая валюта (по умолчанию USD): ").strip().upper() or "USD"

            try:
                result = buy(current_user["user_id"], currency, amount, base)
                print(f"Покупка выполнена: {result['amount']:.4f} {currency} "
                      f"(курс: {result['rate']:.4f} {result['base_currency']}, "
                      f"потрачено: {result['cost_in_base']:.2f} {result['base_currency']})")
            except InsufficientFundsError as e:
                print(f"Ошибка: {e}")
            except ValueError as e:
                print(f"Ошибка: {e}")
            except Exception as e:
                print(f"Неожиданная ошибка: {e}")


        elif cmd == "sell":
            if not current_user:
                print("Сначала выполните login")
                continue

            currency = input("Валюта для продажи: ").strip().upper()
            try:
                amount = float(input("Сумма продажи: "))
            except ValueError:
                print("Сумма должна быть числом больше 0")
                continue

            base = input("Базовая валюта (по умолчанию USD): ").strip().upper() or "USD"

            try:
                result = sell(current_user["user_id"], currency, amount, base)
                print(f"Продажа выполнена: {result['amount']:.4f} {currency} "
                      f"(курс: {result['rate']:.4f} {result['base_currency']}, "
                      f"получено: {result['revenue_in_base']:.2f} {result['base_currency']})")
            except InsufficientFundsError as e:
                print(f"Ошибка: {e}")
            except ValueError as e:
                print(f"Ошибка: {e}")
            except Exception as e:
                print(f"Неожиданная ошибка: {e}")


        elif cmd == "get-rate":
            from_curr = input("Откуда: ").strip().upper()
            to_curr = input("Куда: ").strip().upper()
            try:
                data = get_rate_usecase(from_curr, to_curr)
                rate = data["rate"]
                updated_at = data["updated_at"]
                print(f"Курс {from_curr}→{to_curr}: {rate:.8f} (обновлено: {updated_at})")
            except CurrencyNotFoundError as e:
                print(e)
            except ApiRequestError as e:
                print(f"Ошибка API: {e}. Повторите позже / проверьте сеть")

        elif cmd == "update-rates":
            source_input = input("Источник (coingecko / exchangerate / all): ").strip().lower()
            if source_input in ("all", ""):
                selected_clients = list(clients_map.values())
            elif source_input in clients_map:
                selected_clients = [clients_map[source_input]]
            else:
                print(f"Неизвестный источник '{source_input}'. Доступные: coingecko, exchangerate, all")
                continue

            updater = RatesUpdater(clients=selected_clients, storage=storage, cache=cache)
            print("INFO: Starting rates update...")
            try:
                updater.run_update()
                total_rates = len(cache.all_pairs())
                last_refresh = cache.data.get("last_refresh", "N/A")
                print(f"Update successful. Total rates updated: {total_rates}. Last refresh: {last_refresh}")
            except ApiRequestError as e:
                print(f"Ошибка API: {e}. Проверьте сеть / попробуйте позже.")
            except Exception as e:
                print(f"Неожиданная ошибка: {e}. См. logs/parser.log")

        else:
            print("Неизвестная команда. Попробуйте снова.")

def main():
    interactive_cli()


if __name__ == "__main__":
    main()