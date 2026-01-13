# models.py
import hashlib
import os
from datetime import datetime
from copy import deepcopy
from exceptions import InsufficientFundsError

class User:
    def __init__(self, user_id: int, username: str, password: str, registration_date: datetime = None, salt: str = None):
        self._user_id = user_id
        self.username = username
        self._salt = salt or self._generate_salt()
        self._hashed_password = self._hash_password(password)
        self._registration_date = registration_date or datetime.utcnow()

    @property
    def user_id(self):
        return self._user_id

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value: str):
        if not value:
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value

    @property
    def registration_date(self):
        return self._registration_date

    @property
    def hashed_password(self):
        return self._hashed_password

    @property
    def salt(self):
        return self._salt

    def get_user_info(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
            "salt": self._salt
        }

    def change_password(self, new_password: str):
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = self._generate_salt()
        self._hashed_password = self._hash_password(new_password)

    def verify_password(self, password: str) -> bool:
        return self._hashed_password == self._hash_password(password)

    def _generate_salt(self, length: int = 8) -> str:
        return os.urandom(length).hex()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256((password + self._salt).encode()).hexdigest()


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self._balance = 0.0
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self._balance += amount
        return self._balance

    def withdraw(self, amount: float):
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self._balance -= amount
        return self._balance

    def get_balance_info(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance
        }

class Portfolio:
    def __init__(self, user_id: int, wallets: dict[str, Wallet] = None):
        self._user_id = user_id
        self._wallets = wallets or {}

    @property
    def user_id(self):
        return self._user_id

    @property
    def wallets(self) -> dict:
        return deepcopy(self._wallets)

    def add_currency(self, currency_code: str):
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк для {currency_code} уже существует")
        self._wallets[currency_code] = Wallet(currency_code)
        return self._wallets[currency_code]

    def get_wallet(self, currency_code: str) -> Wallet:
        if currency_code not in self._wallets:
            raise KeyError(f"Кошелёк для {currency_code} не найден")
        return self._wallets[currency_code]

    def get_total_value(self, base_currency='USD') -> float:

        exchange_rates = {
            'USD': 1.0,
            'EUR': 1.1,
            'BTC': 30000,
            'ETH': 2000,
        }

        if base_currency not in exchange_rates:
            raise ValueError(f"Базовая валюта {base_currency} не поддерживается")

        total = 0.0
        for code, wallet in self._wallets.items():
            rate = exchange_rates.get(code)
            if rate is None:
                raise ValueError(f"Нет курса для валюты {code}")
            total += wallet.balance * rate / exchange_rates[base_currency]
        return total