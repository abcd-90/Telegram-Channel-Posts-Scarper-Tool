import os
import logging
from telethon import TelegramClient
from src.config import AppConfig

logger = logging.getLogger(__name__)

class TelegramClientManager:
    def __init__(self, config: AppConfig, session_dir: str = "data"):
        self.config = config
        self.session_dir = session_dir
        os.makedirs(self.session_dir, exist_ok=True)

        proxy_type = os.getenv("PROXY_TYPE", "").lower()
        proxy = None
        if proxy_type in ["socks5", "socks4", "http"]:
            import python_socks
            p_kind = python_socks.ProxyType.SOCKS5 if proxy_type == "socks5" else (
                python_socks.ProxyType.SOCKS4 if proxy_type == "socks4" else python_socks.ProxyType.HTTP
            )
            proxy = (
                p_kind,
                os.getenv("PROXY_HOST", "127.0.0.1"),
                int(os.getenv("PROXY_PORT", 1080)),
                True,
                os.getenv("PROXY_USER") or None,
                os.getenv("PROXY_PASS") or None
            )
            logger.info(f"🌐 [Proxy Configured] Routing MTProto connection through {proxy_type.upper()} {os.getenv('PROXY_HOST')}:{os.getenv('PROXY_PORT')}")

        user_session_path = os.path.join(self.session_dir, "user_session")
        self.user_client = TelegramClient(
            user_session_path,
            config.telegram.api_id,
            config.telegram.api_hash,
            proxy=proxy,
            flood_sleep_threshold=config.settings.flood_sleep_threshold,
            connection_retries=5,
            retry_delay=1,
            auto_reconnect=True,
            request_retries=5
        )

        self.bot_client = None
        if config.bot_token:
            bot_session_path = os.path.join(self.session_dir, "bot_session")
            self.bot_client = TelegramClient(
                bot_session_path,
                config.telegram.api_id,
                config.telegram.api_hash,
                flood_sleep_threshold=config.settings.flood_sleep_threshold,
                connection_retries=5,
                retry_delay=1,
                auto_reconnect=True,
                request_retries=5
            )

    async def start(self):
        """Starts Telegram user client (and admin bot client if token provided)."""
        logger.info("Starting Telegram User Client...")
        if self.config.telegram.phone_number:
            await self.user_client.start(phone=self.config.telegram.phone_number)
        else:
            await self.user_client.start()

        user_me = await self.user_client.get_me()
        logger.info(f"User Client logged in as: {user_me.first_name} (ID: {user_me.id})")

        if self.bot_client and self.config.bot_token:
            logger.info("Starting Telegram Admin Bot Client...")
            await self.bot_client.start(bot_token=self.config.bot_token)
            bot_me = await self.bot_client.get_me()
            logger.info(f"Admin Bot logged in as @{bot_me.username} (ID: {bot_me.id})")

    async def stop(self):
        """Disconnects clients safely."""
        logger.info("Disconnecting Telegram clients...")
        if self.user_client and self.user_client.is_connected():
            await self.user_client.disconnect()
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
        logger.info("Clients disconnected successfully.")

