
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from .currencies import get_currency, CurrencyNotFoundError

from valutatrade_hub.core.models import User, Portfolio
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError,
    UserNotFoundError,
    InvalidPasswordError,
    UsernameTakenError,
    InvalidAmountError,
    WalletNotFoundError,
    RateUnavailableError
)
from valutatrade_hub.core.currencies import get_currency, FiatCurrency
from valutatrade_hub.infra.settings import settings
from valutatrade_hub.decorators import (
    log_buy,
    log_sell,
    log_register,
    log_login,
    log_portfolio_view,
    log_rate_request,
    log_deposit
)
from valutatrade_hub.logging_config import logger

class AuthManager:

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.data_dir
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.current_user: Optional[User] = None

    @log_register(verbose=True)
    def register(self, username: str, password: str) -> User:
        """Регистрация нового пользователя по ТЗ."""
        if len(password) < settings.password_min_length:
            raise ValueError(f"Пароль должен быть не короче {settings.password_min_length} символов")

        # Безопасная операция: чтение→модификация→запись
        users = self._safe_load_users()

        # 1. Проверить уникальность username в users.json
        for user_data in users:
            if user_data["username"] == username:
                raise UsernameTakenError(username)

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
        self._safe_save_users(users)

        # 5. Создать пустой портфель
        portfolio_mgr = PortfolioManager(self.data_dir)
        portfolio_mgr.create_portfolio(user_id)

        logger.info(f"Пользователь {username} зарегистрирован с ID {user_id}")
        return user

    @log_login(verbose=True)
    def login(self, username: str, password: str) -> User:
        """Вход пользователя в систему."""
        users = self._safe_load_users()

        # 1. Найти пользователя по username
        user_found = False
        user_data = None

        for u in users:
            if u["username"] == username:
                user_found = True
                user_data = u
                break

        if not user_found:
            raise UserNotFoundError(username)

        # 2. Сравнить хеш пароля
        user = User.from_dict(user_data)
        if not user.verify_password(password):
            raise InvalidPasswordError()

        self.current_user = user
        logger.info(f"Пользователь {username} вошел в систему")
        return user

    def logout(self):
        """Выход пользователя из системы."""
        if self.current_user:
            logger.info(f"Пользователь {self.current_user.username} вышел из системы")
        self.current_user = None

    def is_logged_in(self) -> bool:
        """Проверка, авторизован ли пользователь."""
        return self.current_user is not None

    def get_current_user(self) -> Optional[User]:
        """Получение текущего пользователя."""
        return self.current_user

    def _safe_load_users(self) -> List[Dict]:
        """Безопасная загрузка пользователей из JSON."""
        if not os.path.exists(self.users_file):
            return []

        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            # В случае ошибки возвращаем пустой список
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке пользователей: {e}")
            raise ApiRequestError(f"Ошибка чтения данных пользователей: {str(e)}")

    def _safe_save_users(self, users: List[Dict]):
        """Безопасное сохранение пользователей в JSON."""
        try:
            # Создаем директорию если нужно
            os.makedirs(self.data_dir, exist_ok=True)

            # Создаем временный файл для безопасной записи
            temp_file = self.users_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)

            # Атомарная замена файла
            os.replace(temp_file, self.users_file)

        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")
            raise ApiRequestError(f"Ошибка записи данных пользователей: {str(e)}")


class PortfolioManager:
    """Менеджер портфелей и операций."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.data_dir
        self.portfolios_file = os.path.join(self.data_dir, "portfolios.json")

    def create_portfolio(self, user_id: int):
        """Создание пустого портфеля для пользователя."""
        portfolios = self._safe_load_portfolios()

        if str(user_id) not in portfolios:
            portfolios[str(user_id)] = {"user_id": user_id, "wallets": {}}
            self._safe_save_portfolios(portfolios)
            logger.debug(f"Создан пустой портфель для пользователя {user_id}")

    def get_portfolio(self, user_id: int) -> Portfolio:
        """Получение портфеля пользователя."""
        portfolios = self._safe_load_portfolios()

        if str(user_id) not in portfolios:
            self.create_portfolio(user_id)
            portfolios = self._safe_load_portfolios()

        return Portfolio.from_dict(portfolios[str(user_id)])

    def save_portfolio(self, portfolio: Portfolio):
        """Сохранение портфеля пользователя."""
        portfolios = self._safe_load_portfolios()
        portfolios[str(portfolio.user_id)] = portfolio.to_dict()
        self._safe_save_portfolios(portfolios)

    @log_buy(verbose=True)
    def buy_currency(self, user_id: int, currency_code: str, amount: float) -> Dict[str, Any]:
        """
        Покупка валюты с использованием новой иерархии валют.

        Args:
            user_id: ID пользователя
            currency_code: Код покупаемой валюты
            amount: Количество покупаемой валюты

        Returns:
            Словарь с результатами операции

        Raises:
            InvalidAmountError: Если amount <= 0
            CurrencyNotFoundError: Если валюта не найдена
            RateUnavailableError: Если курс недоступен
            InsufficientFundsError: Если недостаточно средств
            ApiRequestError: При ошибках доступа к данным
        """
        # Валидация amount > 0
        if amount <= 0:
            raise InvalidAmountError(amount)

        # Валидация currency_code через get_currency()
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)

        # Получаем портфель
        portfolio = self.get_portfolio(user_id)

        # Проверяем наличие USD кошелька (для покупки нужен USD)
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet:
            raise WalletNotFoundError("USD")

        # Получаем курс через RateManager
        rate_mgr = RateManager(self.data_dir)
        try:
            rate = rate_mgr.get_rate_with_info(currency_code, "USD")
        except (CurrencyNotFoundError, RateUnavailableError):
            raise RateUnavailableError(currency_code, "USD")
        except Exception as e:
            raise ApiRequestError(f"Ошибка получения курса: {str(e)}")

        # Рассчитываем стоимость в USD
        cost_usd = amount * rate["rate"]

        # Проверяем достаточно ли USD
        if usd_wallet.balance < cost_usd:
            raise InsufficientFundsError("USD", usd_wallet.balance, cost_usd)

        # Снимаем USD
        usd_wallet.withdraw(cost_usd)

        # Автосоздание кошелька при отсутствии валюты
        target_wallet = portfolio.get_wallet(currency_code)
        if not target_wallet:
            target_wallet = portfolio.add_currency(currency_code)

        # Пополняем купленную валюту
        target_wallet.deposit(amount)

        # Сохраняем изменения
        self.save_portfolio(portfolio)

        # Оценочная стоимость покупки
        estimated_cost = amount * rate["rate"]

        return {
            "currency": currency_code,
            "currency_info": currency.get_display_info(),
            "amount": amount,
            "rate": rate["rate"],
            "rate_info": rate["info"],
            "cost_usd": cost_usd,
            "estimated_cost_usd": estimated_cost,
            "new_balance": target_wallet.balance,
            "remaining_usd": usd_wallet.balance,
            "timestamp": datetime.now().isoformat(),
            "result": "SUCCESS",
            "message": f"Куплено {amount:.4f} {currency_code} за {cost_usd:.2f} USD"
        }

    @log_sell(verbose=True)
    def sell_currency(self, user_id: int, currency_code: str, amount: float) -> Dict[str, Any]:
        """
        Продажа валюты с использованием новой иерархии валют.

        Args:
            user_id: ID пользователя
            currency_code: Код продаваемой валюты
            amount: Количество продаваемой валюты

        Returns:
            Словарь с результатами операции

        Raises:
            InvalidAmountError: Если amount <= 0
            CurrencyNotFoundError: Если валюта не найдена
            WalletNotFoundError: Если нет кошелька с валютой
            InsufficientFundsError: Если недостаточно средств
            RateUnavailableError: Если курс недоступен
        """
        # Валидация amount > 0
        if amount <= 0:
            raise InvalidAmountError(amount)

        # Валидация currency_code через get_currency()
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)

        # Получаем портфель
        portfolio = self.get_portfolio(user_id)

        # Проверка кошелька
        wallet = portfolio.get_wallet(currency_code)
        if not wallet:
            raise WalletNotFoundError(currency_code)

        # Проверка средств — иначе InsufficientFundsError
        if wallet.balance < amount:
            raise InsufficientFundsError(currency_code, wallet.balance, amount)

        # Получаем курс
        rate_mgr = RateManager(self.data_dir)
        try:
            rate = rate_mgr.get_rate_with_info(currency_code, "USD")
        except (CurrencyNotFoundError, RateUnavailableError):
            raise RateUnavailableError(currency_code, "USD")
        except Exception as e:
            raise ApiRequestError(f"Ошибка получения курса: {str(e)}")

        # Рассчитываем выручку в USD
        revenue_usd = amount * rate["rate"]

        # Снимаем валюту
        wallet.withdraw(amount)

        # Добавляем USD (создаем кошелек если его нет)
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet:
            usd_wallet = portfolio.add_currency("USD")

        usd_wallet.deposit(revenue_usd)

        # Сохраняем изменения
        self.save_portfolio(portfolio)

        # Оценочная выручка в USD
        estimated_revenue = amount * rate["rate"]

        return {
            "currency": currency_code,
            "currency_info": currency.get_display_info(),
            "amount": amount,
            "rate": rate["rate"],
            "rate_info": rate["info"],
            "revenue_usd": revenue_usd,
            "estimated_revenue_usd": estimated_revenue,
            "new_balance": wallet.balance,
            "new_usd_balance": usd_wallet.balance,
            "timestamp": datetime.now().isoformat(),
            "result": "SUCCESS",
            "message": f"Продано {amount:.4f} {currency_code} за {revenue_usd:.2f} USD"
        }

    @log_deposit(verbose=True)
    def deposit_currency(self, user_id: int, currency_code: str, amount: float) -> Dict[str, Any]:
        """Пополнение валюты."""
        # Валидация
        if amount <= 0:
            raise InvalidAmountError(amount)

        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)

        portfolio = self.get_portfolio(user_id)

        # Получаем или создаем кошелек
        wallet = portfolio.get_wallet(currency_code)
        if not wallet:
            wallet = portfolio.add_currency(currency_code)

        # Пополняем
        wallet.deposit(amount)

        # Сохраняем изменения
        self.save_portfolio(portfolio)

        return {
            "currency": currency_code,
            "currency_info": currency.get_display_info(),
            "amount": amount,
            "new_balance": wallet.balance,
            "timestamp": datetime.now().isoformat(),
            "result": "SUCCESS",
            "message": f"Пополнено {amount:.2f} {currency_code}"
        }

    @log_portfolio_view(verbose=False)
    def get_portfolio_with_info(self, user_id: int, base_currency: str = "USD") -> Dict[str, Any]:
        """Получение портфеля с дополнительной информацией о валютах."""
        portfolio = self.get_portfolio(user_id)
        rate_mgr = RateManager(self.data_dir)

        wallets_info = []
        total_value = 0.0

        for currency_code, wallet in portfolio.wallets.items():
            try:
                currency = get_currency(currency_code)
                currency_info = currency.get_display_info()
                currency_type = "FIAT" if isinstance(currency, FiatCurrency) else "CRYPTO"

                # Расчет стоимости в базовой валюте
                if currency_code == base_currency:
                    value = wallet.balance
                    rate = 1.0
                else:
                    try:
                        rate = rate_mgr.get_rate(currency_code, base_currency)
                        value = wallet.balance * rate
                    except Exception:
                        rate = None
                        value = 0

                total_value += value

                wallets_info.append({
                    "currency_code": currency_code,
                    "currency_info": currency_info,
                    "currency_type": currency_type,
                    "balance": wallet.balance,
                    "rate_to_base": rate,
                    "value_in_base": value,
                    "wallet_info": wallet.get_balance_info(),
                })

            except CurrencyNotFoundError:
                # Пропускаем валюты, которые не найдены в реестре
                continue

        return {
            "user_id": user_id,
            "base_currency": base_currency,
            "wallets": wallets_info,
            "total_value": total_value,
            "wallet_count": len(wallets_info),
            "timestamp": datetime.now().isoformat(),
        }

    def _safe_load_portfolios(self) -> Dict:
        """Безопасная загрузка портфелей из JSON."""
        if not os.path.exists(self.portfolios_file):
            return {}

        try:
            with open(self.portfolios_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Ошибка загрузки портфелей: {e}")
            return {}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке портфелей: {e}")
            raise ApiRequestError(f"Ошибка чтения данных портфелей: {str(e)}")

    def _safe_save_portfolios(self, portfolios: Dict):
        """Безопасное сохранение портфелей в JSON."""
        try:
            # Создаем директорию если нужно
            os.makedirs(self.data_dir, exist_ok=True)

            # Создаем временный файл для безопасной записи
            temp_file = self.portfolios_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(portfolios, f, ensure_ascii=False, indent=2)

            # Атомарная замена файла
            os.replace(temp_file, self.portfolios_file)

        except Exception as e:
            logger.error(f"Ошибка сохранения портфелей: {e}")
            raise ApiRequestError(f"Ошибка записи данных портфелей: {str(e)}")


def _save_rate_pair(self, from_code: str, to_code: str, rate: float):
    """Сохраняет пару курсов (прямой и обратный)."""
    try:
        raw = self._safe_load_rates()
        raw.setdefault("pairs", {})

        # Сохраняем прямой курс
        direct_key = f"{from_code.upper()}_{to_code.upper()}"
        raw["pairs"][direct_key] = {
            "rate": rate,
            "updated_at": datetime.now().isoformat(),
            "source": "api"
        }

        # Сохраняем обратный курс (если rate не 0)
        if rate != 0:
            reverse_key = f"{to_code.upper()}_{from_code.upper()}"
            raw["pairs"][reverse_key] = {
                "rate": 1.0 / rate,
                "updated_at": datetime.now().isoformat(),
                "source": "calculated"
            }

        raw["last_refresh"] = datetime.now().isoformat()
        self._safe_save_rates(raw)

        logger.debug(f"Сохранены курсы: {direct_key}={rate:.6f}, {reverse_key}={1.0 / rate:.6f}")

    except Exception as e:
        logger.error(f"Ошибка сохранения пары курсов: {e}")


class RateManager:
    """Менеджер курсов валют."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.data_dir
        # ФИКС: Используем exchange_rates.json вместо rates.json
        self.rates_file = os.path.join(self.data_dir, "exchange_rates.json")
        self.history_file = os.path.join(self.data_dir, "rates.json")  # для истории
        self._rates_cache = None
        self._last_update = None

        # Используем настройку TTL из Singleton
        self.rates_ttl = timedelta(seconds=settings.rates_ttl)

        # Инициализация курсов если файла нет
        if not os.path.exists(self.rates_file):
            self._update_all_rates()

    def _safe_load_rates(self) -> Dict:
        """Безопасная загрузка курсов из exchange_rates.json."""
        if self._rates_cache is not None:
            return self._rates_cache

        if not os.path.exists(self.rates_file):
            return {"last_refresh": datetime.now().isoformat(), "pairs": {}}

        try:
            with open(self.rates_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {"last_refresh": datetime.now().isoformat(), "pairs": {}}
                data = json.loads(content)

                # Проверяем структуру
                if "pairs" not in data:
                    data["pairs"] = {}

        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Ошибка загрузки курсов: {e}")
            return {"last_refresh": datetime.now().isoformat(), "pairs": {}}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке курсов: {e}")
            raise ApiRequestError(f"Ошибка чтения данных курсов: {str(e)}")

        self._rates_cache = data
        return data

    @log_rate_request(verbose=False)
    class RateManager:
        """Менеджер курсов валют."""

        def __init__(self, data_dir: str = None):
            self.data_dir = data_dir or settings.data_dir
            # ФИКС: Используем exchange_rates.json для текущих курсов
            self.rates_file = os.path.join(self.data_dir, "exchange_rates.json")
            # ФИКС: rates.json используем только для истории
            self.history_file = os.path.join(self.data_dir, "rates.json")
            self._rates_cache = None
            self._last_update = None

            # Используем настройку TTL из Singleton
            self.rates_ttl = timedelta(seconds=settings.rates_ttl)

            # Инициализация курсов если файла нет
            if not os.path.exists(self.rates_file):
                self._update_all_rates()

        def _safe_load_rates(self) -> Dict:
            """Безопасная загрузка курсов из exchange_rates.json."""
            if self._rates_cache is not None:
                return self._rates_cache

            if not os.path.exists(self.rates_file):
                return {"last_refresh": datetime.now().isoformat(), "pairs": {}, "metadata": {}}

            try:
                with open(self.rates_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return {"last_refresh": datetime.now().isoformat(), "pairs": {}, "metadata": {}}
                    data = json.loads(content)

                    # Проверяем структуру
                    if not isinstance(data, dict):
                        logger.warning("Rates file is not a dict, resetting")
                        return {"last_refresh": datetime.now().isoformat(), "pairs": {}, "metadata": {}}

                    if "pairs" not in data:
                        data["pairs"] = {}
                    if "metadata" not in data:
                        data["metadata"] = {}

            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"Ошибка загрузки курсов: {e}")
                return {"last_refresh": datetime.now().isoformat(), "pairs": {}, "metadata": {}}
            except Exception as e:
                logger.error(f"Неожиданная ошибка при загрузке курсов: {e}")
                raise ApiRequestError(f"Ошибка чтения данных курсов: {str(e)}")

            self._rates_cache = data
            return data

        def _safe_save_rates(self, rates: Dict):
            """Безопасное сохранение курсов в exchange_rates.json."""
            try:
                # Убедитесь, что rates - словарь
                if not isinstance(rates, dict):
                    logger.error(f"Ошибка: пытаемся сохранить не словарь: {type(rates)}")
                    rates = {"last_refresh": datetime.now().isoformat(), "pairs": {}, "metadata": {}}

                # Убедитесь, что есть необходимые ключи
                if "pairs" not in rates:
                    rates["pairs"] = {}
                if "metadata" not in rates:
                    rates["metadata"] = {}

                # Создаем директорию если нужно
                os.makedirs(self.data_dir, exist_ok=True)

                # Создаем временный файл для безопасной записи
                temp_file = self.rates_file + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(rates, f, ensure_ascii=False, indent=2)

                # Атомарная замена файла
                os.replace(temp_file, self.rates_file)

                # Обновляем кеш
                self._rates_cache = rates

            except Exception as e:
                logger.error(f"Ошибка сохранения курсов: {e}")
                raise ApiRequestError(f"Ошибка записи данных курсов: {str(e)}")

    def _fetch_rate_from_api(self, base_currency: str, target_currency: str) -> Dict[str, Any]:
        """Получает курс из внешнего API."""
        # Здесь должна быть реализация получения курса из вашего API
        # Временно используем заглушку

        # Имитируем получение курса USD/BASE
        import random

        # Базовые курсы для расчета
        base_rates = {
            "USD": 1.0,
            "EUR": 0.92 + random.random() * 0.1,
            "BTC": 50000 + random.randint(-5000, 5000),
            "ETH": 3000 + random.randint(-300, 300),
            "RUB": 90 + random.randint(-5, 5),
            "CNY": 7.2 + random.random() * 0.2,
            "GBP": 0.78 + random.random() * 0.05,
            "JPY": 157.0 + random.randint(-5, 5),
            "AED": 3.67 + random.random() * 0.1,
            "SOL": 140.0 + random.randint(-10, 10),
        }

        # Для API предполагаем, что base_currency всегда USD
        # Для других случаев нужно будет адаптировать
        if base_currency.upper() != "USD":
            # Для не-USD базовых валют используем обратный курс
            target_rate = base_rates.get(target_currency.upper(), 1.0)
            base_rate = base_rates.get(base_currency.upper(), 1.0)
            rate = target_rate / base_rate
        else:
            rate = base_rates.get(target_currency.upper(), 1.0)

        return {
            "rate": rate,
            "base_currency": base_currency,
            "target_currency": target_currency,
            "timestamp": datetime.now().isoformat()
        }

    def _save_calculated_rate(self, from_code: str, to_code: str, rate: float):
        """Сохраняет вычисленный курс в файл."""
        try:
            raw = self._safe_load_rates()
            raw.setdefault("pairs", {})

            rate_key = f"{from_code.upper()}_{to_code.upper()}"
            raw["pairs"][rate_key] = {
                "rate": rate,
                "updated_at": datetime.now().isoformat(),
                "source": "calculated"
            }

            self._safe_save_rates(raw)
            logger.debug(f"Сохранен вычисленный курс {from_code}→{to_code}: {rate}")

        except Exception as e:
            logger.error(f"Ошибка сохранения вычисленного курса: {e}")

    @log_rate_request(verbose=True)
    def get_rate_with_info(self, from_code: str, to_code: str) -> Dict[str, Any]:
        """
        Получение курса с дополнительной информацией.

        Returns:
            Словарь с курсом и мета-информацией
        """
        try:
            from_currency = get_currency(from_code)
            to_currency = get_currency(to_code)

            rate = self.get_rate(from_code, to_code)
            rates = self._safe_load_rates()

            # Получаем время обновления
            rate_key = f"{from_code.upper()}_{to_code.upper()}"
            updated_at = None

            raw = self._safe_load_rates()
            pairs = raw.get("pairs", {})

            if rate_key in pairs:
                updated_at = pairs[rate_key].get("updated_at")
            else:
                updated_at = raw.get("last_refresh")

            return {
                "from_code": from_code,
                "to_code": to_code,
                "from_info": from_currency.get_display_info(),
                "to_info": to_currency.get_display_info(),
                "rate": rate,
                "inverse_rate": 1.0 / rate if rate != 0 else 0,
                "updated_at": updated_at,
                "timestamp": datetime.now().isoformat(),
                "info": f"Курс {from_code}→{to_code}: {rate:.6f}",
                "result": "SUCCESS"
            }

        except CurrencyNotFoundError as e:
            raise e
        except Exception:
            raise RateUnavailableError(from_code, to_code)

    def _is_rate_fresh(self, rate_data: Dict) -> bool:
        """Проверяет свежесть курса."""
        try:
            updated_at = datetime.fromisoformat(rate_data["updated_at"].replace('Z', '+00:00'))
            now = datetime.now()
            return (now - updated_at) <= self.rates_ttl
        except Exception:
            return False

    def _update_all_rates(self):
        """Инициализация курсов по умолчанию."""
        try:
            # Базовые курсы (заглушка)
            base_rates = {
                "USD": 1.0,
                "EUR": 0.93,
                "RUB": 90.0,
                "BTC": 60000.0,
                "ETH": 3000.0,
                "CNY": 7.3,
                "GBP": 0.78,
            }

            rates = {
                "pairs": {},
                "last_refresh": datetime.now().isoformat(),
                "metadata": {"source": "stub", "version": "1.0"}
            }

            # Создаем все возможные пары USD→X
            for currency, rate in base_rates.items():
                if currency != "USD":
                    pair_key = f"USD_{currency}"
                    rates["pairs"][pair_key] = {
                        "rate": rate,
                        "updated_at": datetime.now().isoformat(),
                        "source": "stub",
                        "from_currency": "USD",
                        "to_currency": currency
                    }

            self._safe_save_rates(rates)
            self._rates_cache = rates

            logger.info("Курсы валют успешно инициализированы")

        except Exception as e:
            logger.error(f"Ошибка инициализации курсов: {e}")
            raise ApiRequestError(f"Ошибка инициализации курсов: {str(e)}")

    def _update_and_get_rate(self, from_code: str, to_code: str) -> float:
        """Обновляет и возвращает курс для пары валют."""
        try:
            # Для простоты - возвращаем через USD
            # В реальном приложении здесь был бы вызов API

            raw = self._safe_load_rates()
            rates = raw.get("pairs", {})

            # Если одна из валют USD
            if from_code.upper() == "USD":
                # Ищем USD→to_code в существующих курсах
                usd_to_key = f"USD_{to_code.upper()}"
                if usd_to_key in rates:
                    rate_data = rates[usd_to_key]
                    # Обновляем время
                    rate_data["updated_at"] = datetime.now().isoformat()
                    rate = self._extract_rate_from_data(rate_data)
                    self._safe_save_rates(raw)
                    return rate

            elif to_code.upper() == "USD":
                # Ищем USD→from_code
                usd_from_key = f"USD_{from_code.upper()}"
                if usd_from_key in rates:
                    rate_data = rates[usd_from_key]
                    rate_data["updated_at"] = datetime.now().isoformat()
                    rate = self._extract_rate_from_data(rate_data)
                    if rate != 0:
                        self._safe_save_rates(raw)
                        return 1.0 / rate

            # Для X→Y через USD
            usd_from_key = f"USD_{from_code.upper()}"
            usd_to_key = f"USD_{to_code.upper()}"

            if usd_from_key in rates and usd_to_key in rates:
                from_rate_data = rates[usd_from_key]
                to_rate_data = rates[usd_to_key]

                # Обновляем время
                from_rate_data["updated_at"] = datetime.now().isoformat()
                to_rate_data["updated_at"] = datetime.now().isoformat()

                usd_to_from = self._extract_rate_from_data(from_rate_data)
                usd_to_to = self._extract_rate_from_data(to_rate_data)

                if usd_to_from != 0:
                    cross_rate = (1.0 / usd_to_from) * usd_to_to

                    # Сохраняем вычисленный курс
                    cross_key = f"{from_code.upper()}_{to_code.upper()}"
                    rates[cross_key] = {
                        "rate": cross_rate,
                        "updated_at": datetime.now().isoformat(),
                        "source": "calculated",
                        "from_currency": from_code.upper(),
                        "to_currency": to_code.upper()
                    }

                    self._safe_save_rates(raw)
                    return cross_rate

            # Если не нашли, используем заглушку
            logger.warning(f"Курс {from_code}→{to_code} не найден, используем заглушку")
            return self._fetch_rate_from_source(from_code, to_code)

        except Exception as e:
            logger.error(f"Ошибка обновления курса {from_code}→{to_code}: {e}")
            raise RateUnavailableError(from_code, to_code)

    def _extract_rate_from_data(self, rate_data):
        """Извлекает значение курса из структуры данных."""
        if isinstance(rate_data, dict):
            if "rate" in rate_data:
                if isinstance(rate_data["rate"], dict):
                    return rate_data["rate"].get("rate", 0)
                else:
                    return rate_data.get("rate", 0)
        return 0

    def _fetch_rate_from_source(self, from_code: str, to_code: str) -> float:
        """Получает курс из внешнего источника (заглушка)."""
        # В реальном приложении здесь был бы вызов API
        # Пока используем случайное значение в разумных пределах

        import random

        # Базовые курсы для расчета
        base_rates = {
            "USD": 1.0,
            "EUR": 0.92 + random.random() * 0.1,
            "BTC": 50000 + random.randint(-5000, 5000),
            "ETH": 3000 + random.randint(-300, 300),
            "RUB": 90 + random.randint(-5, 5),
            "CNY": 7.2 + random.random() * 0.2,
            "GBP": 0.78 + random.random() * 0.05,
        }

        from_rate = base_rates.get(from_code.upper(), 1.0)
        to_rate = base_rates.get(to_code.upper(), 1.0)

        return from_rate / to_rate

    def _safe_save_rates(self, rates: Dict):
        """Безопасное сохранение курсов в exchange_rates.json."""
        try:
            # Убедитесь, что rates - словарь
            if not isinstance(rates, dict):
                logger.error(f"Ошибка: пытаемся сохранить не словарь: {type(rates)}")
                rates = {"last_refresh": datetime.now().isoformat(), "pairs": {}, "metadata": {}}

            # Убедитесь, что есть необходимые ключи
            if "pairs" not in rates:
                rates["pairs"] = {}
            if "metadata" not in rates:
                rates["metadata"] = {}

            # Создаем директорию если нужно
            os.makedirs(self.data_dir, exist_ok=True)

            # Создаем временный файл для безопасной записи
            temp_file = self.rates_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(rates, f, ensure_ascii=False, indent=2)

            # Атомарная замена файла
            os.replace(temp_file, self.rates_file)

            # Обновляем кеш
            self._rates_cache = rates

        except Exception as e:
            logger.error(f"Ошибка сохранения курсов: {e}")
            raise ApiRequestError(f"Ошибка записи данных курсов: {str(e)}")

class EnhancedRateManager(RateManager):
    """Расширенный менеджер курсов с поддержкой типов валют."""

    def get_currency_info(self, currency_code: str) -> str:
        """Получает информацию о валюте."""
        try:
            currency = get_currency(currency_code)
            return currency.get_display_info()
        except CurrencyNotFoundError:
            return f"Неизвестная валюта: {currency_code}"

    def get_rate_with_info(self, from_currency: str, to_currency: str) -> Dict:
        """Получает курс с дополнительной информацией о валютах."""
        try:
            from_curr = get_currency(from_currency)
            to_curr = get_currency(to_currency)

            rate = self.get_rate(from_currency, to_currency)

            return {
                "from": from_curr.get_display_info(),
                "to": to_curr.get_display_info(),
                "rate": rate,
                "from_type": type(from_curr).__name__,
                "to_type": type(to_curr).__name__,
            }
        except CurrencyNotFoundError as e:
            raise ValueError(f"Ошибка получения курса: {e}")




    def info(self, message: str):
        self.logger.info(message)

    def error(self, message: str):
        self.logger.error(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def debug(self, message: str):
        self.logger.debug(message)