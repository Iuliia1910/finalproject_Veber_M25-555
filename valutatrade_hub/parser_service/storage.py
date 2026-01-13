import json
from pathlib import Path
import tempfile

class RatesStorage:
    def __init__(self, file_path="data/exchange_rates.json"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]")

    def save_rates(self, rates):
        existing = self.load_all()

        new_records = []
        existing_ids = {r["id"] for r in existing}
        for r in rates:
            iso_ts = r["timestamp"]
            record_id = f"{r['from_currency'].upper()}{r['to_currency'].upper()}_{iso_ts}"
            if record_id not in existing_ids:
                record = r.copy()
                record["id"] = record_id
                record["meta"] = {
                    "raw_id": r.get("meta", {}).get("raw_id", r.get("from_currency")),
                    "status_code": r.get("meta", {}).get("status_code", 200),
                    "request_ms": r.get("meta", {}).get("request_ms", 0),
                    "etag": r.get("meta", {}).get("etag", "")
                }
                new_records.append(record)

        all_records = existing + new_records

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp_file:
            json.dump(all_records, tmp_file, indent=2, ensure_ascii=False)
            tmp_name = tmp_file.name

        Path(tmp_name).replace(self.file_path)

    def load_all(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)