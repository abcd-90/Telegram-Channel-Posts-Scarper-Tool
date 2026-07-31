import os
import sys
import asyncio
import logging
from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telethon import TelegramClient
from src.config import load_config, parse_channel_id
from src.database import Database
from src.cloner import normalize_chat_id

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s]: %(message)s")
logger = logging.getLogger("Deduplicator")

async def clean_target_duplicates():
    config = load_config()
    db = Database("data/clone_history.db")
    await db.init_db()

    client = TelegramClient("data/user_session", config.telegram.api_id, config.telegram.api_hash)
    await client.start()

    if not config.channels:
        logger.error("No channel pairs found in config.yaml")
        return

    target_channel = config.channels[0].target
    target_entity = await client.get_entity(parse_channel_id(target_channel) if 'parse_channel_id' in globals() else target_channel)

    logger.info(f"🔍 Scanning target channel {target_channel} for duplicate posts...")

    seen_signatures = {}
    to_delete_msg_ids = []

    async for msg in client.iter_messages(target_entity, limit=500):
        if not msg or msg.action:
            continue

        text = (msg.text or "").strip().lower()
        doc = getattr(msg.media, 'document', None)
        photo = getattr(msg.media, 'photo', None)

        media_id = doc.id if doc else (photo.id if photo else None)
        sig = (text, media_id)

        if sig in seen_signatures and sig != ("", None):
            logger.info(f"🗑️ Found Duplicate Target Message ID {msg.id} (Matches Msg {seen_signatures[sig]}) -> Marking for Delete")
            to_delete_msg_ids.append(msg.id)
        else:
            seen_signatures[sig] = msg.id

    if to_delete_msg_ids:
        logger.info(f"🧹 Deleting {len(to_delete_msg_ids)} duplicate messages from target channel...")
        # Delete in chunks of 100
        for i in range(0, len(to_delete_msg_ids), 100):
            chunk = to_delete_msg_ids[i:i+100]
            await client.delete_messages(target_entity, chunk)
            await asyncio.sleep(1)
        logger.info("✅ Target Channel Cleaned Successfully!")
    else:
        logger.info("✨ No duplicate messages found in Target Channel.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(clean_target_duplicates())
