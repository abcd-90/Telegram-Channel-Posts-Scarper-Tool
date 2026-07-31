import os
import aiosqlite
import logging
import time

logger = logging.getLogger(__name__)

class AnalyticsTracker:
    def __init__(self, db_path: str = "./data/analytics.db"):
        self.db_path = db_path
        self.start_time = time.time()

    async def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_cloned INTEGER DEFAULT 0,
                    total_size_bytes INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                INSERT OR IGNORE INTO stats (id, total_cloned, total_size_bytes, errors_count)
                VALUES (1, 0, 0, 0)
            """)
            await db.commit()

    async def record_clone(self, size_bytes: int = 0):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE stats SET 
                        total_cloned = total_cloned + 1,
                        total_size_bytes = total_size_bytes + ?
                    WHERE id = 1
                """, (size_bytes,))
                await db.commit()
        except Exception as e:
            logger.warning(f"Analytics note: {e}")

    async def get_stats(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT total_cloned, total_size_bytes, errors_count FROM stats WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if row:
                        uptime = round(time.time() - self.start_time, 2)
                        mb = round(row[1] / (1024 * 1024), 2)
                        return {
                            "total_cloned": row[0],
                            "total_size_mb": mb,
                            "errors_count": row[2],
                            "uptime_seconds": uptime
                        }
        except Exception:
            pass
        return {"total_cloned": 0, "total_size_mb": 0, "errors_count": 0, "uptime_seconds": 0}
