import logging
from typing import Any

logger = logging.getLogger(__name__)

class TelegramBotController:
    def __init__(self, enable: bool = False, bot_token: str = "", cloner_instance: Any = None):
        self.enable = enable
        self.bot_token = bot_token
        self.cloner = cloner_instance

    async def start_bot(self):
        if not self.enable or not self.bot_token:
            return

        try:
            from telethon import TelegramClient, events
            bot = TelegramClient("data/control_bot_session", 37604254, "a3e5e613247c608bb81a3000c9bb9785")
            await bot.start(bot_token=self.bot_token)

            @bot.on(events.NewMessage(pattern=r"^/status"))
            async def status_handler(event):
                is_paused = getattr(self.cloner, "is_paused", False) if self.cloner else False
                await event.respond(f"🤖 **Cloner Status**: {'⏸️ Paused' if is_paused else '▶️ Running'}")

            @bot.on(events.NewMessage(pattern=r"^/pause"))
            async def pause_handler(event):
                if self.cloner:
                    self.cloner.is_paused = True
                await event.respond("⏸️ Cloner has been **PAUSED**.")

            @bot.on(events.NewMessage(pattern=r"^/resume"))
            async def resume_handler(event):
                if self.cloner:
                    self.cloner.is_paused = False
                await event.respond("▶️ Cloner has been **RESUMED**.")

            logger.info("🤖 [Bot Control] Telegram Controller Bot active for commands (/status, /pause, /resume)")
        except Exception as e:
            logger.warning(f"⚠️ [Bot Controller Note]: {e}")
