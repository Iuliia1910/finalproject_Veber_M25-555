import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import tempfile

class RatesCache:
    def __init__(self, file_path="data/rates.json", ttl_seconds=3600):
        self.file_path = Path(file_path)
        self.ttl = timedelta(seconds=ttl_seconds)
        self.data = self._load_file()

    def _load_file(self):
        if not self.file_path.exists():
            return {"pairs": {}, "last_refresh": None}
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_pair(self, from_currency, to_currency):
        key = f"{from_currency.upper()}_{to_currency.upper()}"
        pair = self.data.get("pairs", {}).get(key)
        if not pair:
            return None

        updated_at = datetime.fromisoformat(pair["updated_at"])
        if datetime.now(timezone.utc) - updated_at > self.ttl:
            return None
        return pair

    def update_pair(self, from_currency, to_currency, rate, source, updated_at=None):
        updated_at = updated_at or datetime.now(timezone.utc).isoformat()
        key = f"{from_currency.upper()}_{to_currency.upper()}"
        current = self.data.get("pairs", {}).get(key)

        if not current or datetime.fromisoformat(updated_at) > datetime.fromisoformat(current["updated_at"]):
            self.data.setdefault("pairs", {})[key] = {
                "rate": rate,
                "updated_at": updated_at,
                "source": source
            }
            self.data["last_refresh"] = datetime.now(timezone.utc).isoformat()
            self._save_file()

    def _save_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp_file:
            json.dump(self.data, tmp_file, indent=2, ensure_ascii=False)
            tmp_name = tmp_file.name
        Path(tmp_name).replace(self.file_path)

    def all_pairs(self):
        return self.data.get("pairs", {})
