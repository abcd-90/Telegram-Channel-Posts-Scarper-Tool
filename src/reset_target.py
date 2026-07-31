import os
import sys
import asyncio
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telethon import TelegramClient
from src.config import load_config, parse_channel_id
from src.database import Database

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s]: %(message)s")
logger = logging.getLogger("FullReset")

async def reset_and_clean():
    config = load_config()
    db_path = "data/clone_history.db"

    client = TelegramClient("data/user_session", config.telegram.api_id, config.telegram.api_hash)
    await client.start()

    if not config.channels:
        logger.error("No channel pairs found in config.yaml")
        return

    target_channel = config.channels[0].target
    target_entity = await client.get_entity(parse_channel_id(target_channel))

    logger.info(f"🧹 [FULL RESET] Clearing target channel {target_channel} for clean re-sync...")

    messages_to_delete = []
    async for msg in client.iter_messages(target_entity, limit=500):
        if msg and not msg.action:
            messages_to_delete.append(msg.id)

    if messages_to_delete:
        logger.info(f"🗑️ Deleting {len(messages_to_delete)} messages from target channel...")
        for i in range(0, len(messages_to_delete), 100):
            chunk = messages_to_delete[i:i+100]
            await client.delete_messages(target_entity, chunk)
            await asyncio.sleep(1)
        logger.info("✨ Target Channel completely wiped clean!")
    else:
        logger.info("Target channel is already empty.")

    await client.disconnect()

    # Clear SQLite database to start fresh clean cloning
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info("🗑️ Local mapping database reset complete!")

if __name__ == "__main__":
    asyncio.run(reset_and_clean())
