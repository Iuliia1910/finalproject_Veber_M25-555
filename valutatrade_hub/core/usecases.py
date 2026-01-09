import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from .models import User, Portfolio, Wallet


class AuthManager:
    """Менеджер аутентификации и регистрации."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.users_file = os.path.join(data_dir, "users.json")
        self.current_user: Optional[User] = None

    def register(self, username: str, password: str) -> User:
        """Регистрация нового пользователя по ТЗ."""
        users = self._load_users()

        # 1. Проверить уникальность username в users.json
        for user_data in users:
            if user_data["username"] == username:
                raise ValueError(f"Имя пользователя '{username}' уже занято")

        # 2. Создать пользователя (генерация user_id будет внутри)
        user = User.create(username, password)

        # 2. Сгенерировать user_id (автоинкремент)
        if users:
            user_id = max(u["user_id"] for u in users) + 1
        else:
            user_id = 1

        # Установка ID
        user._user_id = user_id

        # 4. Сохранить пользователя в users.json
        users.append(user.to_dict())
        self._save_users(users)

        # 5. Создать пустой портфель
        portfolio_mgr = PortfolioManager(self.data_dir)
        portfolio_mgr.create_portfolio(user_id)

        return user

    def login(self, username: str, password: str) -> User:
        """Вход пользователя в систему."""
        users = self._load_users()

        # 1. Найти пользователя по username
        user_found = False
        user_data = None

        for u in users:
            if u["username"] == username:
                user_found = True
                user_data = u
                break

        if not user_found:
            raise ValueError(f"Пользователь '{username}' не найден")

        # 2. Сравнить хеш пароля
        user = User.from_dict(user_data)
        if not user.verify_password(password):
            raise ValueError("Неверный пароль")

        self.current_user = user
        return user

    def logout(self):
        """Выход пользователя из системы."""
        self.current_user = None

    def is_logged_in(self) -> bool:
        """Проверка, авторизован ли пользователь."""
        return self.current_user is not None

    def get_current_user(self) -> Optional[User]:
        """Получение текущего пользователя."""
        return self.current_user

    def _load_users(self) -> List[Dict]:
        """Загрузка пользователей из JSON."""
        if not os.path.exists(self.users_file):
            return []

        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_users(self, users: List[Dict]):
        """Сохранение пользователей в JSON."""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)


class PortfolioManager:
    """Менеджер портфелей и операций."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.portfolios_file = os.path.join(data_dir, "portfolios.json")

    def create_portfolio(self, user_id: int):
        """Создание пустого портфеля для пользователя."""
        portfolios = self._load_portfolios()

        if str(user_id) not in portfolios:
            portfolios[str(user_id)] = {"user_id": user_id, "wallets": {}}
            self._save_portfolios(portfolios)

    def get_portfolio(self, user_id: int) -> Portfolio:
        """Получение портфеля пользователя."""
        portfolios = self._load_portfolios()

        if str(user_id) not in portfolios:
            self.create_portfolio(user_id)
            portfolios = self._load_portfolios()

        return Portfolio.from_dict(portfolios[str(user_id)])

    def save_portfolio(self, portfolio: Portfolio):
        """Сохранение портфеля пользователя."""
        portfolios = self._load_portfolios()
        portfolios[str(portfolio.user_id)] = portfolio.to_dict()
        self._save_portfolios(portfolios)

    def buy_currency(self, user_id: int, currency: str, amount: float) -> Dict:
        """Покупка валюты по ТЗ."""
        portfolio = self.get_portfolio(user_id)
        currency = currency.upper()

        # Валидация
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")

        # Проверяем наличие USD кошелька (для покупки нужен USD)
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet:
            raise ValueError("Для покупки валюты необходим USD кошелёк. Пополните USD.")

        # Получаем курс
        rate_mgr = RateManager(self.data_dir)
        try:
            rate = rate_mgr.get_rate(currency, "USD")
        except Exception:
            raise ValueError(f"Не удалось получить курс для {currency}→USD")

        # Рассчитываем стоимость в USD
        cost_usd = amount * rate

        # Проверяем достаточно ли USD
        if usd_wallet.balance < cost_usd:
            raise ValueError(f"Недостаточно USD. Требуется: {cost_usd:.2f}, доступно: {usd_wallet.balance:.2f}")

        # Снимаем USD
        usd_wallet.withdraw(cost_usd)

        # Добавляем купленную валюту (автоматически создаем кошелек если его нет)
        target_wallet = portfolio.get_wallet(currency)
        if not target_wallet:
            target_wallet = portfolio.add_currency(currency)

        target_wallet.deposit(amount)

        # Сохраняем изменения
        self.save_portfolio(portfolio)

        return {
            "currency": currency,
            "amount": amount,
            "rate": rate,
            "cost_usd": cost_usd,
            "new_balance": target_wallet.balance,
            "remaining_usd": usd_wallet.balance
        }

    def sell_currency(self, user_id: int, currency: str, amount: float) -> Dict:
        """Продажа валюты по ТЗ."""
        portfolio = self.get_portfolio(user_id)
        currency = currency.upper()

        # Валидация
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")

        # Проверяем наличие кошелька с валютой
        wallet = portfolio.get_wallet(currency)
        if not wallet:
            raise ValueError(
                f"У вас нет кошелька '{currency}'. Добавьте валюту: она создаётся автоматически при первой покупке.")

        # Проверяем достаточно ли средств
        if wallet.balance < amount:
            raise ValueError(f"Недостаточно средств: доступно {wallet.balance:.4f} {currency}, требуется {amount:.4f}")

        # Получаем курс
        rate_mgr = RateManager(self.data_dir)
        try:
            rate = rate_mgr.get_rate(currency, "USD")
        except Exception:
            raise ValueError(f"Не удалось получить курс для {currency}→USD")

        # Рассчитываем выручку в USD
        revenue_usd = amount * rate

        # Снимаем валюту
        wallet.withdraw(amount)

        # Добавляем USD (создаем кошелек если его нет)
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet:
            usd_wallet = portfolio.add_currency("USD")

        usd_wallet.deposit(revenue_usd)

        # Сохраняем изменения
        self.save_portfolio(portfolio)

        return {
            "currency": currency,
            "amount": amount,
            "rate": rate,
            "revenue_usd": revenue_usd,
            "new_balance": wallet.balance,
            "new_usd_balance": usd_wallet.balance
        }

    def _load_portfolios(self) -> Dict:
        """Загрузка портфелей из JSON."""
        if not os.path.exists(self.portfolios_file):
            return {}

        try:
            with open(self.portfolios_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_portfolios(self, portfolios: Dict):
        """Сохранение портфелей в JSON."""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.portfolios_file, 'w', encoding='utf-8') as f:
            json.dump(portfolios, f, ensure_ascii=False, indent=2)


class RateManager:
    """Менеджер курсов валют."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.rates_file = os.path.join(data_dir, "rates.json")
        self._rates_cache = None
        self._last_update = None

        # Инициализация курсов если файла нет
        if not os.path.exists(self.rates_file):
            self.update_rates()

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Получение курса валюты по ТЗ."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1.0

        rates = self._load_rates()

        # Пробуем прямой курс
        rate_key = f"{from_currency}_{to_currency}"
        if rate_key in rates:
            rate_data = rates[rate_key]
            # Проверяем свежесть курса (менее 5 минут)
            if self._is_rate_fresh(rate_data):
                return rate_data["rate"]
            else:
                # Обновляем устаревший курс
                return self._update_and_get_rate(from_currency, to_currency)

        # Пробуем обратный курс
        reverse_key = f"{to_currency}_{from_currency}"
        if reverse_key in rates:
            rate_data = rates[reverse_key]
            if self._is_rate_fresh(rate_data):
                return 1.0 / rate_data["rate"]
            else:
                return self._update_and_get_rate(from_currency, to_currency)

        # Если курса нет, создаем новый
        return self._update_and_get_rate(from_currency, to_currency)

    def _update_and_get_rate(self, from_currency: str, to_currency: str) -> float:
        """Обновляет и возвращает курс."""
        rates = self._load_rates()
        rate_key = f"{from_currency}_{to_currency}"

        # Используем заглушку для курса
        rate = self._get_stub_rate(from_currency, to_currency)

        # Обновляем кеш
        rates[rate_key] = {
            "rate": rate,
            "updated_at": datetime.now().isoformat()
        }

        # Обновляем время последнего обновления
        rates["last_refresh"] = datetime.now().isoformat()

        # Сохраняем
        self._save_rates(rates)

        return rate

    def _is_rate_fresh(self, rate_data: Dict) -> bool:
        """Проверяет свежесть курса (менее 5 минут)."""
        try:
            updated_at = datetime.fromisoformat(rate_data["updated_at"].replace('Z', '+00:00'))
            now = datetime.now()
            return (now - updated_at) < timedelta(minutes=5)
        except:
            return False

    def update_rates(self):
        """Обновление всех курсов валют (заглушка)."""
        # Фиксированные курсы как в ТЗ
        rates = {
            "last_refresh": datetime.now().isoformat(),
            "source": "ParserService"
        }

        # Основные курсы из ТЗ
        stub_rates = {
            "EUR_USD": 1.0786,
            "BTC_USD": 59337.21,
            "RUB_USD": 0.01016,
            "ETH_USD": 3720.00,
            "USD_EUR": 0.9271,
            "USD_BTC": 0.00001685,
            "USD_ETH": 0.0002688,
            "USD_RUB": 98.42,
            "CNY_USD": 0.138,
            "USD_CNY": 7.25,
            "GBP_USD": 1.26,
            "USD_GBP": 0.7937,
        }

        for key, rate in stub_rates.items():
            rates[key] = {
                "rate": rate,
                "updated_at": datetime.now().isoformat()
            }

        self._save_rates(rates)
        self._rates_cache = rates
        self._last_update = datetime.now()

    def _get_stub_rate(self, from_currency: str, to_currency: str) -> float:
        """Заглушка для курсов валют."""
        # Базовые курсы (к USD)
        base_rates = {
            "USD": 1.0,
            "EUR": 1.0786,
            "BTC": 59337.21,
            "ETH": 3720.00,
            "RUB": 0.01016,
            "CNY": 0.138,
            "GBP": 1.26,
        }

        from_rate = base_rates.get(from_currency.upper(), 1.0)
        to_rate = base_rates.get(to_currency.upper(), 1.0)

        return from_rate / to_rate

    def _load_rates(self) -> Dict:
        """Загрузка курсов из JSON."""
        if self._rates_cache is not None:
            return self._rates_cache

        if not os.path.exists(self.rates_file):
            # Создаём начальные курсы
            rates = self.update_rates()
            return rates

        try:
            with open(self.rates_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    rates = self.update_rates()
                    return rates
                data = json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            data = self.update_rates()

        self._rates_cache = data
        return data

    def _save_rates(self, rates: Dict):
        """Сохранение курсов в JSON."""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.rates_file, 'w', encoding='utf-8') as f:
            json.dump(rates, f, ensure_ascii=False, indent=2)