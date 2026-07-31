import logging
from telethon import TelegramClient, events
from src.cloner import ChannelCloner
from src.database import Database
from src.config import parse_channel_id

logger = logging.getLogger(__name__)

class AdminBot:
    def __init__(self, client: TelegramClient, cloner: ChannelCloner, db: Database):
        self.client = client
        self.cloner = cloner
        self.db = db

    async def register_commands(self):
        """Register Telegram Bot command handlers."""
        
        @self.client.on(events.NewMessage(pattern=r"^/start$"))
        async def handle_start(event: events.NewMessage.Event):
            welcome_msg = (
                "🤖 **Telegram Channel Cloner & Mirroring Bot**\n\n"
                "Available Commands:\n"
                "• `/status` - View current syncing status & statistics\n"
                "• `/pause` - Temporarily pause real-time syncing\n"
                "• `/resume` - Resume real-time syncing\n"
                "• `/addpair <source_id> <target_id>` - Add new channel sync pair\n"
                "• `/removepair <source_id>` - Remove channel pair\n"
            )
            await event.respond(welcome_msg)

        @self.client.on(events.NewMessage(pattern=r"^/status$"))
        async def handle_status(event: events.NewMessage.Event):
            stats = await self.db.get_stats()
            pairs = await self.db.get_all_pairs()
            
            status_str = "⏸️ **Paused**" if self.cloner.is_paused else "▶️ **Active & Syncing**"
            
            msg = f"📊 **System Status:** {status_str}\n"
            msg += f"📦 **Total Synced Messages:** {stats['total_synced_messages']}\n"
            msg += f"🔗 **Active Channel Pairs:** {stats['active_pairs_count']}\n\n"
            
            if pairs:
                msg += "**Configured Pairs:**\n"
                for p in pairs:
                    msg += f"• `{p['source']}` ➔ `{p['target']}` (Edits: {p['mirror_edits']}, Deletions: {p['mirror_deletions']})\n"
            else:
                msg += "_No active channel pairs configured._"

            await event.respond(msg)

        @self.client.on(events.NewMessage(pattern=r"^/pause$"))
        async def handle_pause(event: events.NewMessage.Event):
            self.cloner.is_paused = True
            await event.respond("⏸️ Real-time channel cloning has been **paused**.")

        @self.client.on(events.NewMessage(pattern=r"^/resume$"))
        async def handle_resume(event: events.NewMessage.Event):
            self.cloner.is_paused = False
            await event.respond("▶️ Real-time channel cloning has been **resumed**.")

        @self.client.on(events.NewMessage(pattern=r"^/addpair(?:\s+(\S+)\s+(\S+))?$"))
        async def handle_addpair(event: events.NewMessage.Event):
            args = event.text.split()[1:]
            if len(args) < 2:
                await event.respond("⚠️ **Usage:** `/addpair <source_channel_id> <target_channel_id>`\nExample: `/addpair -1001234567890 -1009876543210`")
                return

            try:
                source_id = parse_channel_id(args[0])
                target_id = parse_channel_id(args[1])
                
                await self.db.add_pair(source_id, target_id)
                await self.cloner.reload_pairs()
                
                await event.respond(f"✅ Successfully added channel pair:\n`{source_id}` ➔ `{target_id}`")
            except Exception as e:
                await event.respond(f"❌ Error adding pair: {e}")

        @self.client.on(events.NewMessage(pattern=r"^/removepair(?:\s+(\S+))?$"))
        async def handle_removepair(event: events.NewMessage.Event):
            args = event.text.split()[1:]
            if len(args) < 1:
                await event.respond("⚠️ **Usage:** `/removepair <source_channel_id>`\nExample: `/removepair -1001234567890`")
                return

            try:
                source_id = parse_channel_id(args[0])
                await self.db.remove_pair(source_id)
                await self.cloner.reload_pairs()
                
                await event.respond(f"🗑️ Successfully removed channel pair for source `{source_id}`.")
            except Exception as e:
                await event.respond(f"❌ Error removing pair: {e}")

        logger.info("Admin bot commands registered successfully.")
