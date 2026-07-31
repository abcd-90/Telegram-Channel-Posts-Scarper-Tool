import os
import sys
import asyncio
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telethon import TelegramClient

from src.config import load_config
from src.database import Database
from src.cloner import ChannelCloner

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("UserbotScraper")

async def main():
    config = load_config()

    if not config.telegram.api_id or not config.telegram.api_hash:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured in .env or config/config.yaml!")
        return

    os.makedirs("data", exist_ok=True)
    db = Database("data/clone_history.db")
    await db.init_db()

    import python_socks
    proxy_host = os.getenv("PROXY_HOST")
    proxy_port = os.getenv("PROXY_PORT")
    proxy = None
    if proxy_host and proxy_port:
        proxy = (python_socks.ProxyType.SOCKS5, proxy_host, int(proxy_port))

    session_path = "data/user_session"
    client = TelegramClient(
        session_path,
        config.telegram.api_id,
        config.telegram.api_hash,
        proxy=proxy,
        sequential_updates=True,
        connection_retries=10,
        retry_delay=2
    )

    logger.info(f"Connecting Telegram Userbot with API ID {config.telegram.api_id}...")
    phone = config.telegram.phone_number or None
    await client.start(phone=phone)

    me = await client.get_me()
    logger.info(f"Logged in as Telegram User: {me.first_name} (@{me.username}) - Phone: {me.phone}")

    # Fetch initial dialogs to cache all private channels into Telethon's memory
    logger.info("Caching private channels entity database...")
    try:
        await client.get_dialogs(limit=200)
    except Exception as e:
        logger.warning(f"Dialog caching note: {e}")

    cloner = ChannelCloner(client, db, config)
    await cloner.register_handlers()

    # Feature 10: Analytics Tracker DB Init
    await cloner.analytics.init_db()

    # Feature 6: FastAPI Web Dashboard Server
    from src.web.server import WebDashboardServer
    web_server = WebDashboardServer(enable=True, port=8080, cloner_instance=cloner)
    await web_server.start_server()

    # Feature 9: Telegram Bot Controller
    if config.bot_token:
        from src.bot_controller import TelegramBotController
        bot_ctrl = TelegramBotController(enable=True, bot_token=config.bot_token, cloner_instance=cloner)
        await bot_ctrl.start_bot()

    # Feature 3: Scheduled Mirroring
    from src.scheduler import ScheduledMirror
    scheduler = ScheduledMirror(enable=False, cron_expr="0 2 * * *")
    scheduler.start(cloner.backfill_all_pairs)

    logger.info("Starting past history clone...")
    await cloner.backfill_all_pairs()

    logger.info("Historical clone complete! Bot is now listening for new live posts in real-time. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
