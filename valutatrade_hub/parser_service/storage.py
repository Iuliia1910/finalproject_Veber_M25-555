import json
import os
import tempfile
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class RateEntry:
    id: str
    from_currency: str
    to_currency: str
    rate: float
    timestamp: str
    source: str
    meta: Dict[str, Any]


class RatesStorage:
    def __init__(self, config):
        self.config = config
        self.config.ensure_directories()
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        if not self.config.RATES_FILE_PATH.exists():
            self._atomic_write(self.config.RATES_FILE_PATH, {
                "pairs": {},
                "last_refresh": None,
                "metadata": {}
            })

        if not self.config.HISTORY_FILE_PATH.exists():
            self._atomic_write(self.config.HISTORY_FILE_PATH, [])

    def _atomic_write(self, path, data):
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            os.unlink(tmp)
            raise

    # -------- current rates --------

    def save_current_rates(self, rates: Dict[str, float], source: str):
        now = datetime.now(timezone.utc).isoformat()

        with open(self.config.RATES_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for pair, rate in rates.items():
            base, quote = pair.split("_", 1)
            data["pairs"][pair] = {  # <--- должен быть словарь, а не list
                "rate": rate,
                "from_currency": base,
                "to_currency": quote,
                "source": source,
                "updated_at": now,
            }

        data["last_refresh"] = now
        self._atomic_write(self.config.RATES_FILE_PATH, data)

    def load_rates(self) -> Dict[str, Any]:
        """
        Загружает текущие курсы из exchange_rates.json
        """
        if not self.config.RATES_FILE_PATH.exists():
            return {
                "pairs": {},
                "last_refresh": None,
                "metadata": {},
            }

        try:
            with open(self.config.RATES_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.warning("Rates file is not a dict, resetting")
                return {
                    "pairs": {},
                    "last_refresh": None,
                    "metadata": {},
                }

            return data

        except json.JSONDecodeError:
            logger.warning("Rates file is corrupted, resetting")
            return {
                "pairs": {},
                "last_refresh": None,
                "metadata": {},
            }

    def load_current_rates(self):
        """
        Совместимость с updater / cli.
        Если курсы уже есть — просто ничего не делаем.
        """
        return self.load_rates()

    # -------- history --------

    def save_to_history(self, rates: Dict[str, float], source: str):
        """Сохраняет курсы в историю (rates.json)."""

        history: list = []

        # 1. Безопасно загружаем историю
        if (
                getattr(self.config, "HISTORY_FILE_PATH", None)
                and os.path.exists(self.config.HISTORY_FILE_PATH)
        ):
            try:
                with open(self.config.HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        history = loaded
                    else:
                        logger.warning(
                            "History file is not a list, resetting history"
                        )
            except json.JSONDecodeError:
                logger.warning("History file is corrupted, resetting history")

        # 2. Добавляем новые записи
        now = datetime.now(timezone.utc)
        ts = now.isoformat()

        for pair, rate in rates.items():
            if "_" not in pair:
                continue

            base, quote = pair.split("_", 1)

            entry = RateEntry(
                id=f"{pair}_{now.strftime('%Y%m%d_%H%M%S')}",
                from_currency=base,
                to_currency=quote,
                rate=rate,
                timestamp=ts,
                source=source,
                meta={"pair": pair},
            )

            history.append(asdict(entry))

        # 3. Ограничиваем размер истории
        max_entries = getattr(self, "MAX_HISTORY_ENTRIES", 1000)
        if len(history) > max_entries:
            history = history[-max_entries:]

        # 4. Сохраняем обратно
        self._atomic_write(self.config.HISTORY_FILE_PATH, history)

