import os
import json
import logging
import asyncio
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class BackupRestoreManager:
    def __init__(self, enable: bool = False, interval_hours: int = 24, backup_path: str = "./backups/"):
        self.enable = enable
        self.interval_hours = interval_hours
        self.backup_path = backup_path
        os.makedirs(self.backup_path, exist_ok=True)

    async def backup_messages(self, messages_data: List[Dict[str, Any]], channel_id: str):
        if not self.enable:
            return

        file_path = os.path.join(self.backup_path, f"backup_{channel_id}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(messages_data, f, indent=2, ensure_ascii=False)
            logger.info(f"📦 [Backup Created] Saved {len(messages_data)} messages -> {file_path}")
        except Exception as e:
            logger.error(f"⚠️ [Backup Failed]: {e}")
