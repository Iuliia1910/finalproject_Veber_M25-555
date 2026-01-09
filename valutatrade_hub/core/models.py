# valutatrade_hub/core/models.py
import hashlib
import secrets
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional


class User:

    def __init__(self, user_id: int, username: str, hashed_password: str,
                 salt: str, registration_date: datetime):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # Геттеры
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    # Сеттеры с проверками
    @username.setter
    def username(self, value: str):
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    # Методы
    def get_user_info(self) -> Dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat()
        }

    def change_password(self, new_password: str):
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        # Создаём новую соль
        new_salt = secrets.token_hex(8)
        # Хешируем пароль
        hash_obj = hashlib.sha256((new_password + new_salt).encode())
        self._hashed_password = hash_obj.hexdigest()
        self._salt = new_salt

    def verify_password(self, password: str) -> bool:
        hash_obj = hashlib.sha256((password + self._salt).encode())
        return hash_obj.hexdigest() == self._hashed_password

    @staticmethod
    def create(username: str, password: str) -> 'User':
        if not username or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        salt = secrets.token_hex(8)
        hash_obj = hashlib.sha256((password + salt).encode())

        return User(
            user_id=0,  # Будет установлен при сохранении
            username=username.strip(),
            hashed_password=hash_obj.hexdigest(),
            salt=salt,
            registration_date=datetime.now()
        )

    def to_dict(self) -> Dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"])
        )


class Wallet:

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code.upper()
        self._balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self.balance = self._balance + amount

    def withdraw(self, amount: float):
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        if amount > self._balance:
            raise ValueError(f"Недостаточно средств. Доступно: {self._balance}")
        self.balance = self._balance - amount

    def get_balance_info(self) -> Dict:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance
        }

    def to_dict(self) -> Dict:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Wallet':
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"]
        )


class Portfolio:

    def __init__(self, user_id: int, wallets: Optional[Dict[str, Wallet]] = None):
        self._user_id = user_id
        self._wallets = wallets or {}

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        currency_code = currency_code.upper()

        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк с валютой {currency_code} уже существует")

        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        currency_code = currency_code.upper()
        return self._wallets.get(currency_code)

    def get_total_value(self, exchange_rates: Dict[str, float],
                        base_currency: str = 'USD') -> float:
        total = 0.0
        base_currency = base_currency.upper()

        for currency, wallet in self._wallets.items():
            if currency == base_currency:
                total += wallet.balance
            else:
                rate_key = f"{currency}_{base_currency}"
                reverse_key = f"{base_currency}_{currency}"

                if rate_key in exchange_rates:
                    rate = exchange_rates[rate_key]
                    total += wallet.balance * rate
                elif reverse_key in exchange_rates:
                    rate = exchange_rates[reverse_key]
                    total += wallet.balance / rate

        return total

    def to_dict(self) -> Dict:
        return {
            "user_id": self._user_id,
            "wallets": {
                currency: wallet.to_dict()
                for currency, wallet in self._wallets.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Portfolio':
        wallets = {}
        for currency, wallet_data in data.get("wallets", {}).items():
            wallets[currency] = Wallet.from_dict(wallet_data)

        return cls(
            user_id=data["user_id"],
            wallets=wallets
        )