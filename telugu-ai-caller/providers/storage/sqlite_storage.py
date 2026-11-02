"""
SQLite Storage Provider Implementation (Default active storage).
"""

import time
from typing import Dict, Any
from providers.storage.base import BaseStorageProvider
from database import get_connection, init_db
from config import DATABASE_PATH


class SQLiteStorageProvider(BaseStorageProvider):
    def __init__(self):
        super().__init__(provider_name="sqlite")
        self.db_path = str(DATABASE_PATH)

    def is_configured(self) -> bool:
        return bool(self.db_path)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "engine": "sqlite3",
            "database_path": self.db_path
        }

    def get_connection(self):
        return get_connection()

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            _ = cursor.fetchone()
            conn.close()
            latency = round((time.time() - start) * 1000, 1)
            return {
                "success": True,
                "latency_ms": latency,
                "message": f"SQLite database connected: {self.db_path} ({latency}ms).",
                "details": {"path": self.db_path}
            }
        except Exception as e:
            latency = round((time.time() - start) * 1000, 1)
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"SQLite connection failed: {str(e)}",
                "details": {"error": str(e)}
            }

