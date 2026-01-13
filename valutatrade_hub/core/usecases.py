import os
import json
import hashlib
from datetime import datetime
from typing import Any
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import InsufficientFundsError, CurrencyNotFoundError
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader
from pathlib import Path


# ================= SETTINGS SINGLETON =================
settings = SettingsLoader()
portfolios_file = Path(settings.get("PORTFOLIOS_FILE", "data/portfolios.json"))
rates_file = Path(settings.get("RATES_FILE", "data/rates.json"))
users_file = Path(settings.get("USERS_FILE", 'data/users.json'))
default_base_currency = settings.get("DEFAULT_BASE_CURRENCY", "USD")
DEFAULT_BASE_CURRENCY = "USD"

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def write_portfolio(user_id: int, wallets: dict):
    """Обновляет кошельки пользователя"""
    portfolios = load_json(portfolios_file)
    portfolio = next((p for p in portfolios if p["user_id"] == user_id), None)
    if not portfolio:
        portfolio = {"user_id": user_id, "wallets": wallets}
        portfolios.append(portfolio)
    else:
        portfolio["wallets"] = wallets
    save_json(portfolios_file, portfolios)

def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def generate_salt(length=8) -> str:
    return os.urandom(length).hex()

def hash_password(password: str, salt: str) -> str:
    """Хэшируем пароль с солью"""
    return hashlib.sha256((password + salt).encode()).hexdigest()

def now_iso() -> str:
    return datetime.utcnow().isoformat()

def read_portfolio(user_id: int) -> dict:
    """Возвращает словарь кошельков пользователя"""
    if not portfolios_file.exists():
        return {}
    with portfolios_file.open("r", encoding="utf-8") as f:
        portfolios = json.load(f)

    portfolio = next((p for p in portfolios if p["user_id"] == user_id), None)
    return portfolio["wallets"] if portfolio else {}


# ================= USECASES =================
@log_action("REGISTER")
def register(username: str, password: str):
    username = username.strip()
    if not username:
        raise ValueError("Имя пользователя не может быть пустым")
    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    users = load_json(users_file)
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max([u["user_id"] for u in users] + [0]) + 1
    salt = generate_salt()
    hashed_password = hash_password(password, salt)
    registration_date = datetime.utcnow().isoformat()

    users.append({
        "user_id": user_id,
        "username": username,
        "hashed_password": hashed_password,
        "salt": salt,
        "registration_date": registration_date
    })
    save_json(users_file, users)

    return {
        "user_id": user_id,
        "username": username,
        "result": "OK"
    }


@log_action("LOGIN")
def login(username: str, password: str):
    username = username.strip()
    password = password.strip()
    user = get_user_by_username(username)
    if not user:
        raise ValueError(f"Пользователь '{username}' не найден")

    hashed_input = hash_password(password, user["salt"])
    if hashed_input != user["hashed_password"]:
        raise ValueError("Неверный пароль")

    return {
        "user_id": user["user_id"],
        "username": username,
        "result": "OK"
    }

def get_user_by_username(username: str):
    users = load_json(users_file)
    for u in users:
        if u["username"] == username:
            return u
    return None


def get_user_portfolio(user_id: int) -> dict:
    portfolios = load_json(portfolios_file)
    portfolio = next((p for p in portfolios if p["user_id"] == user_id), None)
    if portfolio:
        return portfolio.get("wallets", {})
    return {}


@log_action("DEPOSIT")
def deposit(user_id: int, currency: str, amount: float):
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    portfolios = load_json(portfolios_file)
    portfolio = next((p for p in portfolios if p["user_id"] == user_id), None)
    if portfolio is None:
        portfolio = {"user_id": user_id, "wallets": {}}
        portfolios.append(portfolio)

    wallets = portfolio["wallets"]
    wallets[currency] = wallets.get(currency, {"balance": 0.0})
    old_balance = wallets[currency]["balance"]

    wallets[currency]["balance"] += amount
    new_balance = wallets[currency]["balance"]

    save_json(portfolios_file, portfolios)

    return {
        "old_balance": old_balance,
        "new_balance": new_balance,
        "amount": amount,
        "currency": currency
    }

@log_action("BUY")
def buy(user_id: int, currency_code: str, amount: float, base_currency: str = None):
    base_currency = (base_currency or DEFAULT_BASE_CURRENCY).upper()
    currency_code = currency_code.upper()

    if amount <= 0:
        raise ValueError("'amount' должен быть > 0")

    # проверка валют
    get_currency(currency_code)
    get_currency(base_currency)

    wallets = read_portfolio(user_id)
    wallets[currency_code] = wallets.get(currency_code, {"balance": 0.0})

    # Получаем курсы из rates.json
    if not rates_file.exists():
        raise CurrencyNotFoundError("Нет данных по курсам")
    with rates_file.open("r", encoding="utf-8") as f:
        rates_data = json.load(f)
    rates = rates_data.get("pairs", {})

    pair_key = f"{currency_code}_{base_currency}"
    reverse_key = f"{base_currency}_{currency_code}"

    if pair_key in rates:
        rate = rates[pair_key]["rate"]
    elif reverse_key in rates:
        rate = 1 / rates[reverse_key]["rate"]
    else:
        raise CurrencyNotFoundError(f"Курс {currency_code}->{base_currency} не найден")

    cost_in_base = amount * rate
    wallets[base_currency] = wallets.get(base_currency, {"balance": 0.0})
    if cost_in_base > wallets[base_currency]["balance"]:
        raise InsufficientFundsError(wallets[base_currency]["balance"], cost_in_base, base_currency)

    # обновляем кошельки
    wallets[base_currency]["balance"] -= cost_in_base
    wallets[currency_code]["balance"] += amount

    write_portfolio(user_id, wallets)

    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "base_currency": base_currency,
        "cost_in_base": cost_in_base,
        "new_balance": wallets[currency_code]["balance"]
    }

@log_action("SELL")
def sell(user_id: int, currency_code: str, amount: float, base_currency: str = None):
    base_currency = (base_currency or DEFAULT_BASE_CURRENCY).upper()
    currency_code = currency_code.upper()

    if amount <= 0:
        raise ValueError("'amount' должен быть > 0")

    get_currency(currency_code)
    get_currency(base_currency)

    wallets = read_portfolio(user_id)
    if currency_code not in wallets:
        raise CurrencyNotFoundError(currency_code)

    if amount > wallets[currency_code]["balance"]:
        raise InsufficientFundsError(wallets[currency_code]["balance"], amount, currency_code)

    # Получаем курсы
    if not rates_file.exists():
        raise CurrencyNotFoundError("Нет данных по курсам")
    with rates_file.open("r", encoding="utf-8") as f:
        rates_data = json.load(f)
    rates = rates_data.get("pairs", {})

    pair_key = f"{currency_code}_{base_currency}"
    reverse_key = f"{base_currency}_{currency_code}"

    if pair_key in rates:
        rate = rates[pair_key]["rate"]
    elif reverse_key in rates:
        rate = 1 / rates[reverse_key]["rate"]
    else:
        raise CurrencyNotFoundError(f"Курс {currency_code}->{base_currency} не найден")

    revenue_in_base = amount * rate

    wallets[currency_code]["balance"] -= amount
    wallets[base_currency] = wallets.get(base_currency, {"balance": 0.0})
    wallets[base_currency]["balance"] += revenue_in_base

    write_portfolio(user_id, wallets)

    return {
        "currency": currency_code,
        "amount": amount,
        "rate": rate,
        "base_currency": base_currency,
        "revenue_in_base": revenue_in_base,
        "new_balance": wallets[currency_code]["balance"]
    }

def get_rate_usecase(from_code: str, to_code: str):
    from_code = from_code.upper()
    to_code = to_code.upper()

    # проверка валют через иерархию
    try:
        get_currency(from_code)
        get_currency(to_code)
    except CurrencyNotFoundError as e:
        raise e

    rates = load_json(rates_file)  # вместо db.load("rates")
    pairs = rates.get("pairs", {})

    pair_key = f"{from_code}_{to_code}"
    reverse_key = f"{to_code}_{from_code}"

    if pair_key in pairs:
        rate_data = pairs[pair_key]
    elif reverse_key in pairs:
        rate_data = pairs[reverse_key]
        rate_data = {"rate": 1 / rate_data["rate"], "updated_at": rate_data["updated_at"], "source": rate_data.get("source")}
    else:
        raise CurrencyNotFoundError(f"{from_code}→{to_code}")

    return rate_data

