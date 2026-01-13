import json
from datetime import datetime, timezone
from typing import Dict, Any

from .config import ParserConfig
from .storage import RatesStorage
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.api_clients import RateManager

class RatesUpdater:
    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.rate_manager = RateManager(self.config)
        self.storage = RatesStorage(self.config)

    def update_rates(self, force: bool = False):
        """
        Обновляет курсы валют.
        """
        all_rates = self.rate_manager.get_all_rates()

        if not all_rates:
            raise RuntimeError("Не удалось получить курсы валют")

        self.storage.save_current_rates(all_rates, source="api")
        self.storage.save_to_history(all_rates, source="api")

        return {
            "status": "success",
            "rates_count": len(all_rates),
        }

    def fetch_rates_from_apis(self) -> Dict[str, float]:
        """Возвращает словарь курсов в формате 'USD_BTC': rate"""
        raw_rates = self.rate_manager.get_all_rates()
        rates = {}
        for pair_key, data in raw_rates.items():
            # ожидаем data['rate'] как float
            rates[pair_key] = data.get("rate")
        return rates

    def run_update(self, sources: list = None) -> Dict[str, Any]:
        return self.update_rates(force=True)

    def load_rates(self):
        """Загрузить курсы из RATES_FILE_PATH в RateManager"""
        data = self.storage.load_current_rates()
        self.rate_manager.update_rates_from_dict(data.get("pairs", {}))

    def get_summary(self) -> str:
        try:
            data = self.storage.load_current_rates()
            pairs = data.get("pairs", {})
            last_refresh = data.get("last_refresh")

            summary = ["СВОДКА ПО КУРСАМ ВАЛЮТ"]
            if last_refresh:
                try:
                    dt = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
                    summary.append(f"Обновлено: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception:
                    summary.append(f"Обновлено: {last_refresh}")

            summary.append(f"Всего курсов: {len(pairs)}")

            sources = {}
            for pair_data in pairs.values():
                source = pair_data.get("source", "unknown")
                sources[source] = sources.get(source, 0) + 1

            for source, count in sources.items():
                summary.append(f"  - {source}: {count}")

            return "\n".join(summary)
        except Exception as e:
            return f"Не удалось загрузить сводку: {e}"



