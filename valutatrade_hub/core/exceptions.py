class ValutaTradeError(Exception):
    """Базовое исключение для всех ошибок ValutaTrade Hub."""

    def __init__(self, message: str, user_message: str = None):
        super().__init__(message)
        self.user_message = user_message or message
        self.internal_message = message


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств для операции."""

    def __init__(self, currency_code: str, available: float, required: float):
        message = (
            f"Insufficient funds: available {available} {currency_code}, "
            f"required {required} {currency_code}"
        )
        user_message = (
            f"Недостаточно средств: доступно {available:.4f} {currency_code}, "
            f"требуется {required:.4f} {currency_code}"
        )
        super().__init__(message, user_message)

        self.currency_code = currency_code
        self.available = available
        self.required = required


class CurrencyNotFoundError(ValutaTradeError):
    """Неизвестная валюта."""

    def __init__(self, currency_code: str):
        message = f"Currency not found: '{currency_code}'"
        user_message = f"Неизвестная валюта '{currency_code}'"
        super().__init__(message, user_message)

        self.currency_code = currency_code


class ApiRequestError(ValutaTradeError):
    """Ошибка при обращении к внешнему API."""

    def __init__(self, reason: str, status_code: int = None):
        message = f"API request failed: {reason}"
        user_message = f"Ошибка при обращении к внешнему API: {reason}"
        super().__init__(message, user_message)

        self.reason = reason
        self.status_code = status_code


class UserNotFoundError(ValutaTradeError):
    """Пользователь не найден."""

    def __init__(self, username: str):
        message = f"User not found: '{username}'"
        user_message = f"Пользователь '{username}' не найден"
        super().__init__(message, user_message)

        self.username = username


class InvalidPasswordError(ValutaTradeError):
    """Неверный пароль."""

    def __init__(self):
        message = "Invalid password"
        user_message = "Неверный пароль"
        super().__init__(message, user_message)


class UsernameTakenError(ValutaTradeError):
    """Имя пользователя уже занято."""

    def __init__(self, username: str):
        message = f"Username already taken: '{username}'"
        user_message = f"Имя пользователя '{username}' уже занято"
        super().__init__(message, user_message)

        self.username = username


class InvalidAmountError(ValutaTradeError):
    """Некорректная сумма."""

    def __init__(self, amount: float):
        message = f"Invalid amount: {amount}"
        user_message = "'amount' должен быть положительным числом"
        super().__init__(message, user_message)

        self.amount = amount


class InvalidCurrencyCodeError(ValutaTradeError):
    """Некорректный код валюты."""

    def __init__(self, currency_code: str):
        message = f"Invalid currency code: '{currency_code}'"
        user_message = f"Код валюты '{currency_code}' некорректен или пуст"
        super().__init__(message, user_message)

        self.currency_code = currency_code


class NotLoggedInError(ValutaTradeError):
    """Пользователь не авторизован."""

    def __init__(self):
        message = "User not logged in"
        user_message = "Сначала выполните login"
        super().__init__(message, user_message)


class WalletNotFoundError(ValutaTradeError):
    """Кошелек не найден."""

    def __init__(self, currency_code: str):
        message = f"Wallet not found for currency: '{currency_code}'"
        user_message = (
            f"У вас нет кошелька '{currency_code}'. "
            f"Добавьте валюту: она создаётся автоматически при первой покупке."
        )
        super().__init__(message, user_message)

        self.currency_code = currency_code


class RateUnavailableError(ValutaTradeError):
    """Курс недоступен."""

    def __init__(self, from_currency: str, to_currency: str):
        message = f"Rate unavailable: {from_currency}→{to_currency}"
        user_message = (
            f"Курс {from_currency}→{to_currency} недоступен. "
            f"Повторите попытку позже."
        )
        super().__init__(message, user_message)

        self.from_currency = from_currency
        self.to_currency = to_currency


def handle_exception(exception: Exception) -> str:
    """
    Обрабатывает исключение и возвращает сообщение для пользователя.

    Args:
        exception: Исключение для обработки

    Returns:
        Сообщение для пользователя
    """
    if isinstance(exception, ValutaTradeError):
        return exception.user_message
    elif isinstance(exception, ValueError):
        # Обработка стандартных ValueError
        if "недостаточно средств" in str(exception).lower():
            return str(exception)
        elif "нет кошелька" in str(exception).lower():
            return str(exception)
        elif "amount" in str(exception).lower() and "положительным" in str(exception).lower():
            return str(exception)
        else:
            return f"Ошибка: {exception}"
    else:
        return f"Внутренняя ошибка системы: {type(exception).__name__}"