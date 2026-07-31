import os
import sys
import asyncio
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telegram.ext import ApplicationBuilder

from src.config import load_config
from src.database import Database
from src.bot_cloner import BotChannelCloner

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main")

async def main():
    logger.info("Initializing Telegram Bot Channel Cloner...")
    config = load_config()

    if not config.bot_token:
        logger.error("BOT_TOKEN is not set in environment or config.yaml!")
        return

    db = Database()
    await db.init_db()

    app = ApplicationBuilder().token(config.bot_token).build()
    bot_cloner = BotChannelCloner(app.bot, db, config)
    bot_cloner.register_handlers(app)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("Bot is running and listening for new messages. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping Bot...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
