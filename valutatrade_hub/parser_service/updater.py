import logging
from datetime import datetime, timezone

from .api_clients import BaseApiClient, ApiRequestError
from .storage import RatesStorage
from valutatrade_hub.core.utils import RatesCache
from .config import ParserConfig

logger = logging.getLogger(__name__)


class RatesUpdater:
    def __init__(self, clients: list[BaseApiClient], storage: RatesStorage, cache: RatesCache):
        self.clients = clients
        self.storage = storage
        self.cache = cache
        self.config = ParserConfig()

    def run_update(self):
        logger.info("START rates update ")
        all_rates = []

        for client in self.clients:
            client_name = client.__class__.__name__
            try:
                logger.info(f"Запрос курсов от {client_name}...")
                rates = client.fetch_rates()
                logger.info(f"Получено {len(rates)} курсов от {client_name}")

                timestamp = datetime.now(timezone.utc).isoformat()

                for pair, rate in rates.items():
                    from_curr, to_curr = pair.split("_")
                    record = {
                        "from_currency": from_curr,
                        "to_currency": to_curr,
                        "rate": rate,
                        "timestamp": timestamp,
                        "source": client_name
                    }
                    all_rates.append(record)

                    self.cache.update_pair(from_curr, to_curr, rate, source=client_name, updated_at=timestamp)

            except ApiRequestError as e:
                logger.error(f"Ошибка клиента {client_name}: {e}")
            except Exception as e:
                logger.exception(f"Неожиданная ошибка при запросе {client_name}: {e}")

        if all_rates:
            self.storage.save_rates(all_rates)
            logger.info(f"Сохранено {len(all_rates)} новых записей в history file")
        else:
            logger.warning("Нет новых курсов для сохранения")

        logger.info("FINISH rates update")