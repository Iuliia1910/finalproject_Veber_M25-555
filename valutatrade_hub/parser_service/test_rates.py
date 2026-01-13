import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

config = ParserConfig()
storage = RatesStorage(config)
print("Storage object:", storage)
updater = RatesUpdater(storage)
updater.update_rates()
print("Update finished")

