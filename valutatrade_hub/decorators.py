"""
Декораторы для логирования действий в ValutaTrade Hub.
"""

import functools
from datetime import datetime
from typing import Callable, Any, Dict

# Абсолютные импорты
try:
    from valutatrade_hub.core.exceptions import ValutaTradeError
    from valutatrade_hub.logging_config import actions_logger
except ImportError:
    # Запасной вариант для прямого запуска
    from .core.exceptions import ValutaTradeError
    from .logging_config import actions_logger


def log_action(action_name: str, verbose: bool = False, log_result: bool = True):
    """
    Декоратор для логирования действий пользователя.

    Args:
        action_name: Название действия (BUY, SELL, REGISTER, LOGIN и т.д.)
        verbose: Подробное логирование (дополнительный контекст)
        log_result: Логировать результат действия

    Returns:
        Декорированная функция
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Получаем информацию о пользователе и параметрах
            user_info = _extract_user_info(func, args, kwargs)
            action_params = _extract_action_params(func, args, kwargs)

            # Логируем начало действия
            _log_action_start(action_name, user_info, action_params)

            result = None
            error_info = None

            try:
                # Выполняем функцию
                result = func(*args, **kwargs)

                # Логируем успешное завершение
                if log_result:
                    _log_action_success(
                        action_name,
                        user_info,
                        action_params,
                        result,
                        verbose
                    )

                return result

            except ValutaTradeError as e:
                # Логируем бизнес-ошибки
                error_info = {
                    "type": type(e).__name__,
                    "message": e.user_message,
                }
                _log_action_error(
                    action_name,
                    user_info,
                    action_params,
                    error_info,
                    verbose
                )
                raise  # Пробрасываем исключение дальше

            except Exception as e:
                # Логируем неожиданные ошибки
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                }
                _log_action_error(
                    action_name,
                    user_info,
                    action_params,
                    error_info,
                    verbose
                )
                raise  # Пробрасываем исключение дальше

        return wrapper

    return decorator


def _extract_user_info(func: Callable, args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Извлекает информацию о пользователе из аргументов функции."""
    user_info = {}

    # Для методов классов, которые первым аргументом принимают self
    if args and hasattr(args[0], 'auth_manager'):
        try:
            auth_manager = args[0].auth_manager
            if auth_manager and auth_manager.is_logged_in():
                user = auth_manager.get_current_user()
                if user:
                    user_info["username"] = user.username
                    user_info["user_id"] = user.user_id
        except:
            pass

    # Ищем username и user_id в аргументах
    func_params = func.__code__.co_varnames[:func.__code__.co_argcount]

    # Проверяем позиционные аргументы
    for i, param_name in enumerate(func_params):
        if i < len(args):
            if param_name == 'username':
                user_info["username"] = args[i]
            elif param_name == 'user_id':
                user_info["user_id"] = args[i]

    # Проверяем именованные аргументы
    if 'username' in kwargs:
        user_info["username"] = kwargs['username']
    if 'user_id' in kwargs:
        user_info["user_id"] = kwargs['user_id']

    return user_info


def _extract_action_params(func: Callable, args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Извлекает параметры действия из аргументов функции."""
    params = {}

    # Получаем названия параметров функции
    func_params = func.__code__.co_varnames[:func.__code__.co_argcount]

    # Обрабатываем позиционные аргументы
    for i, param_name in enumerate(func_params):
        if i < len(args):
            if param_name in ['currency', 'currency_code', 'from_currency', 'to_currency']:
                params[param_name] = args[i]
            elif param_name == 'amount':
                params['amount'] = args[i]
            elif param_name == 'rate':
                params['rate'] = args[i]
            elif param_name == 'base_currency':
                params['base_currency'] = args[i]

    # Обрабатываем именованные аргументы
    for param_name in ['currency', 'currency_code', 'from_currency', 'to_currency',
                       'amount', 'rate', 'base_currency']:
        if param_name in kwargs:
            params[param_name] = kwargs[param_name]

    return params


def _log_action_start(action_name: str, user_info: Dict, params: Dict):
    """Логирует начало действия."""
    log_data = {
        "action": f"{action_name}_START",
        "timestamp": datetime.now().isoformat(),
        **user_info,
        **params,
    }

    actions_logger.debug(
        f"Начало действия {action_name}",
        extra=log_data
    )


def _log_action_success(action_name: str, user_info: Dict, params: Dict,
                        result: Any, verbose: bool):
    """Логирует успешное завершение действия."""
    log_data = {
        "action": action_name,
        "timestamp": datetime.now().isoformat(),
        "result": "OK",
        **user_info,
        **params,
    }

    # Добавляем информацию из результата если есть
    if isinstance(result, dict):
        if 'rate' in result:
            log_data["rate"] = result['rate']
        if 'new_balance' in result:
            log_data["new_balance"] = result['new_balance']
        if 'cost_usd' in result:
            log_data["cost_usd"] = result['cost_usd']
        if 'revenue_usd' in result:
            log_data["revenue_usd"] = result['revenue_usd']

    # Добавляем контекст если включен verbose режим
    if verbose and result:
        log_data["context"] = str(result)

    actions_logger.info(
        f"Действие {action_name} выполнено успешно",
        extra=log_data
    )


def _log_action_error(action_name: str, user_info: Dict, params: Dict,
                      error_info: Dict, verbose: bool):
    """Логирует ошибку при выполнении действия."""
    log_data = {
        "action": action_name,
        "timestamp": datetime.now().isoformat(),
        "result": "ERROR",
        **user_info,
        **params,
        "error_type": error_info["type"],
        "error_message": error_info["message"],
    }

    # Добавляем контекст если включен verbose режим
    if verbose:
        log_data["context"] = f"Ошибка: {error_info['type']} - {error_info['message']}"

    actions_logger.error(
        f"Действие {action_name} завершилось ошибкой",
        extra=log_data
    )


# Специализированные декораторы для конкретных действий
def log_buy(verbose: bool = False):
    """Декоратор для логирования покупки валюты."""
    return log_action("BUY", verbose=verbose, log_result=True)


def log_sell(verbose: bool = False):
    """Декоратор для логирования продажи валюты."""
    return log_action("SELL", verbose=verbose, log_result=True)


def log_register(verbose: bool = False):
    """Декоратор для логирования регистрации."""
    return log_action("REGISTER", verbose=verbose, log_result=True)


def log_login(verbose: bool = False):
    """Декоратор для логирования входа в систему."""
    return log_action("LOGIN", verbose=verbose, log_result=True)


def log_portfolio_view(verbose: bool = False):
    """Декоратор для логирования просмотра портфеля."""
    return log_action("PORTFOLIO_VIEW", verbose=verbose, log_result=False)


def log_rate_request(verbose: bool = False):
    """Декоратор для логирования запроса курса."""
    return log_action("RATE_REQUEST", verbose=verbose, log_result=False)


def log_deposit(verbose: bool = False):
    """Декоратор для логирования пополнения счета."""
    return log_action("DEPOSIT", verbose=verbose, log_result=True)