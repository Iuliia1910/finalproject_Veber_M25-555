import json
import os
from typing import Any, Dict, Optional


class SettingsLoader:
    _instance = None
    _initialized = False

    class _SingletonMeta(type):

        def __call__(cls, *args, **kwargs):
            if cls._instance is None:
                cls._instance = super().__call__(*args, **kwargs)
            return cls._instance

    __metaclass__ = _SingletonMeta

    def __init__(self):
        if self._initialized:
            return

        self._config: Dict[str, Any] = {}
        self._config_file = self._find_config_file()
        self._load_config()

        self._set_defaults()

        self._initialized = True

    def _find_config_file(self) -> Optional[str]:
        possible_paths = [
            "pyproject.toml",
            "config.json",
            "valutatrade_config.json",
            os.path.join("config", "valutatrade.json"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def _load_config(self):
        if not self._config_file:
            return

        try:
            if self._config_file.endswith('.json'):
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            elif self._config_file.endswith('.toml'):
                import toml
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    data = toml.load(f)
                    self._config = data.get('tool', {}).get('valutatrade', {})
        except (json.JSONDecodeError, FileNotFoundError, ImportError) as e:
            print(f"Не удалось загрузить конфигурацию: {e}")
            self._config = {}

    def _set_defaults(self):
        defaults = {
            "data_dir": "data",
            "users_file": "data/users.json",
            "portfolios_file": "data/portfolios.json",
            "rates_file": "data/rates.json",

            "rates_ttl_seconds": 300,
            "default_base_currency": "USD",
            "rates_source": "stub",

            "log_level": "INFO",
            "log_file": "valutatrade.log",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",

            "password_min_length": 4,
            "session_timeout_minutes": 60,

            "default_commission": 0.001,
            "min_trade_amount": 0.0001,
            "supported_currencies": ["USD", "EUR", "BTC", "ETH", "RUB", "CNY", "GBP"],

            "api_timeout_seconds": 10,
            "api_max_retries": 3,
            "api_base_url": "https://api.valutatrade.example.com",

            "cli_prompt": "valutatrade> ",
            "show_currency_info": True,
            "enable_color_output": True,
        }

        for key, value in defaults.items():
            if key not in self._config:
                self._config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def reload(self):
        old_config = self._config.copy()

        try:
            self._load_config()
            self._set_defaults()
            print("Конфигурация перезагружена")
        except Exception as e:
            print(f"Ошибка перезагрузки конфигурации: {e}")
            self._config = old_config

    def set(self, key: str, value: Any):
        self._config[key] = value

    def save(self):
        if not self._config_file or not self._config_file.endswith('.json'):
            print("Сохранение конфигурации доступно только для JSON файлов")
            return

        try:
            os.makedirs(os.path.dirname(self._config_file) or '.', exist_ok=True)

            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)

            print(f"Конфигурация сохранена в {self._config_file}")
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")

    def get_all(self) -> Dict[str, Any]:
        return self._config.copy()

    def print_config(self, prefix: str = ""):
        print("КОНФИГУРАЦИЯ VALUTATRADE HUB")

        for key, value in sorted(self._config.items()):
            if prefix and not key.startswith(prefix):
                continue

            if isinstance(value, (list, tuple)):
                value_str = ', '.join(str(v) for v in value)
            elif isinstance(value, dict):
                value_str = "{...}"
            else:
                value_str = str(value)

            print(f"{key:30} : {value_str}")

        print(f"{'=' * 60}\n")

    @property
    def data_dir(self) -> str:
        return self.get("data_dir")

    @property
    def rates_ttl(self) -> int:
        return self.get("rates_ttl_seconds")

    @property
    def default_base_currency(self) -> str:
        return self.get("default_base_currency")

    @property
    def supported_currencies(self) -> list:
        return self.get("supported_currencies")

    @property
    def log_level(self) -> str:
        return self.get("log_level")

    @property
    def password_min_length(self) -> int:
        return self.get("password_min_length")

    @property
    def log_format(self) -> str:
        return self.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    @property
    def log_file(self) -> str:
        return self.get("log_file", "valutatrade.log")

settings = SettingsLoader()