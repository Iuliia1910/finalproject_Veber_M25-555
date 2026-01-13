class InsufficientFundsError(Exception):
#Недостаточно средств для снятия
    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        message = f"Недостаточно средств: доступно {available:.4f} {code}, требуется {required:.4f} {code}"
        super().__init__(message)

class CurrencyNotFoundError(Exception):
#если валюта неизвестна
    def __init__(self, code: str):
        self.code = code
        message = f"Неизвестная валюта '{code}'"
        super().__init__(message)

class ApiRequestError(Exception):
#при сбое внешнего API
    def __init__(self, reason: str):
        message = f"Ошибка при обращении к внешнему API: {reason}"
        super().__init__(message)
        self.reason = reason