# valutatrade_hub/infra/database.py

class DatabaseManager:
    def __init__(self, db_url="sqlite:///data/db.sqlite3"):
        self.db_url = db_url