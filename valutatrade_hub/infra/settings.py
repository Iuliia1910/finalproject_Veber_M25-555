import toml
from typing import Any

class SettingsLoader:

    #Singleton для конфигурации проекта.
    #Загружает секцию [tool.valutatrade] из pyproject.toml и кэширует.
    _instance = None
    _settings: dict = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_settings()
        return cls._instance

    def _load_settings(self):
        try:
            with open("pyproject.toml", "r", encoding="utf-8") as f:
                data = toml.load(f)
            self._settings = data.get("tool", {}).get("valutatrade", {})
        except FileNotFoundError:
            self._settings = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def reload(self):
        self._load_settings()