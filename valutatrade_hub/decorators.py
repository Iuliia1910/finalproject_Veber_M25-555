import logging
from functools import wraps

logger = logging.getLogger("actions_logger")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)
file_handler = logging.FileHandler("logs/actions.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def log_action(action: str, verbose: bool = True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            username = kwargs.get("username") or "unknown"
            currency = kwargs.get("currency") or ""
            amount = kwargs.get("amount") or 0.0
            base = kwargs.get("base_currency") or ""
            old_balance = kwargs.get("old_balance")
            new_balance = kwargs.get("new_balance")

            try:
                result = func(*args, **kwargs)
                log_msg = (
                    f"{action} user='{username}' currency='{currency}' "
                    f"amount={amount} rate={kwargs.get('rate', 0)} base='{base}' "
                    f"result=OK"
                )
                if verbose and old_balance is not None and new_balance is not None:
                    log_msg += f" ({old_balance:.4f} → {new_balance:.4f})"

                logger.info(log_msg)
                return result
            except Exception as e:
                log_msg = (
                    f"{action} user='{username}' currency='{currency}' "
                    f"amount={amount} rate={kwargs.get('rate', 0)} base='{base}' "
                    f"result=ERROR error_type={type(e).__name__} "
                    f"error_message='{str(e)}'"
                )
                if verbose and old_balance is not None and new_balance is not None:
                    log_msg += f" ({old_balance:.4f} → ???)"
                logger.error(log_msg)
                raise

        return wrapper
    return decorator
