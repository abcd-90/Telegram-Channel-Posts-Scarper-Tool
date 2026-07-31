import os
import aiosqlite
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/clone_history.db"):
        self.db_path = db_path

    async def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")

            # Check if message_mappings has the updated column schema
            has_msg_col = False
            try:
                async with db.execute("PRAGMA table_info(message_mappings)") as cursor:
                    rows = await cursor.fetchall()
                    has_msg_col = any(row[1] == "target_message_id" for row in rows)
            except Exception:
                has_msg_col = False

            if not has_msg_col:
                await db.execute("DROP TABLE IF EXISTS message_mappings")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS message_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_channel_id INTEGER NOT NULL,
                    source_message_id INTEGER NOT NULL,
                    target_channel_id INTEGER NOT NULL,
                    target_message_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_channel_id, source_message_id, target_channel_id)
                )
            """)

            # Check if channel_pairs has the updated column schema
            has_pair_col = False
            try:
                async with db.execute("PRAGMA table_info(channel_pairs)") as cursor:
                    rows = await cursor.fetchall()
                    has_pair_col = any(row[1] == "source" for row in rows)
            except Exception:
                has_pair_col = False

            if not has_pair_col:
                await db.execute("DROP TABLE IF EXISTS channel_pairs")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS channel_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    mirror_edits BOOLEAN DEFAULT 1,
                    mirror_deletions BOOLEAN DEFAULT 1,
                    UNIQUE(source, target)
                )
            """)
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def get_target_message_id(self, source_channel_id: int, source_message_id: int, target_channel_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute(
                """
                SELECT target_message_id FROM message_mappings
                WHERE source_channel_id = ? AND source_message_id = ? AND target_channel_id = ?
                """,
                (source_channel_id, source_message_id, target_channel_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def save_mapping(self, source_channel_id: int, source_message_id: int, target_channel_id: int, target_message_id: int):
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO message_mappings (source_channel_id, source_message_id, target_channel_id, target_message_id)
                VALUES (?, ?, ?, ?)
                """,
                (source_channel_id, source_message_id, target_channel_id, target_message_id)
            )
            await db.commit()

    async def delete_mapping(self, source_channel_id: int, source_message_id: int, target_channel_id: int) -> Optional[int]:
        target_msg_id = await self.get_target_message_id(source_channel_id, source_message_id, target_channel_id)
        if target_msg_id:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute(
                    """
                    DELETE FROM message_mappings
                    WHERE source_channel_id = ? AND source_message_id = ? AND target_channel_id = ?
                    """,
                    (source_channel_id, source_message_id, target_channel_id)
                )
                await db.commit()
        return target_msg_id

    async def add_pair(self, source: str, target: str, mirror_edits: bool = True, mirror_deletions: bool = True):
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO channel_pairs (source, target, mirror_edits, mirror_deletions)
                VALUES (?, ?, ?, ?)
                """,
                (str(source), str(target), mirror_edits, mirror_deletions)
            )
            await db.commit()

    async def get_all_pairs(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM channel_pairs") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
