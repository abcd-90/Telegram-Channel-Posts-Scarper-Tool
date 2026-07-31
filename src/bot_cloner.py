import logging
from typing import Dict, List, Set
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from telegram.error import RetryAfter, TelegramError

from src.config import AppConfig, ChannelPair, parse_channel_id
from src.database import Database

logger = logging.getLogger(__name__)

class BotApiCloner:
    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self.is_paused: bool = False
        self.pairs_map: Dict[int, List[ChannelPair]] = {}

    async def reload_pairs(self):
        """Reload active pairs from database and config into memory."""
        self.pairs_map.clear()

        for p in self.config.channels:
            await self.db.add_pair(p.source, p.target, p.mirror_edits, p.mirror_deletions)

        db_pairs = await self.db.get_all_pairs()
        for dp in db_pairs:
            source = dp["source"]
            pair_obj = ChannelPair(
                source=source,
                target=dp["target"],
                mirror_edits=dp["mirror_edits"],
                mirror_deletions=dp["mirror_deletions"]
            )
            if source not in self.pairs_map:
                self.pairs_map[source] = []
            self.pairs_map[source].append(pair_obj)

        logger.info(f"[BotAPI] Loaded {len(db_pairs)} active channel pairs across {len(self.pairs_map)} source channels.")

    async def handle_channel_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new channel posts in source channels."""
        if self.is_paused or not update.channel_post:
            return

        post = update.channel_post
        source_id = post.chat_id
        source_msg_id = post.message_id

        if source_id not in self.pairs_map:
            return

        logger.info(f"[BotAPI] New post {source_msg_id} in channel {source_id}")

        for pair in self.pairs_map[source_id]:
            target_id = pair.target
            # Check deduplication
            existing = await self.db.get_target_message_id(source_id, source_msg_id, target_id)
            if existing:
                logger.debug(f"Message {source_msg_id} already cloned to {target_id}. Skipping.")
                continue

            try:
                if self.config.settings.forward_enabled:
                    sent = await context.bot.forward_message(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_id=source_msg_id
                    )
                else:
                    sent = await context.bot.copy_message(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_id=source_msg_id
                    )

                if sent:
                    await self.db.save_mapping(source_id, source_msg_id, target_id, sent.message_id)
                    logger.info(f"[BotAPI Cloned] Source {source_id}:{source_msg_id} -> Target {target_id}:{sent.message_id}")

            except RetryAfter as e:
                logger.warning(f"Rate limited. Retrying after {e.retry_after} seconds.")
                await context.bot.copy_message(chat_id=target_id, from_chat_id=source_id, message_id=source_msg_id)
            except TelegramError as e:
                logger.error(f"Failed to clone post {source_msg_id} to {target_id}: {e}")

    async def handle_edited_channel_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle edited posts in source channels."""
        if self.is_paused or not update.edited_channel_post:
            return

        post = update.edited_channel_post
        source_id = post.chat_id
        source_msg_id = post.message_id

        if source_id not in self.pairs_map:
            return

        for pair in self.pairs_map[source_id]:
            if not pair.mirror_edits:
                continue

            target_msg_id = await self.db.get_target_message_id(source_id, source_msg_id, pair.target)
            if not target_msg_id:
                continue

            try:
                if post.text:
                    await context.bot.edit_message_text(
                        chat_id=pair.target,
                        message_id=target_msg_id,
                        text=post.text,
                        entities=post.entities
                    )
                elif post.caption:
                    await context.bot.edit_message_caption(
                        chat_id=pair.target,
                        message_id=target_msg_id,
                        caption=post.caption,
                        caption_entities=post.caption_entities
                    )
                logger.info(f"[BotAPI Edited] Synced edit for {source_msg_id} -> Target {pair.target}:{target_msg_id}")
            except TelegramError as e:
                logger.error(f"Failed to edit message in target channel {pair.target}:{target_msg_id}: {e}")

    # --- Admin Command Handlers ---

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "🤖 **Telegram Channel Cloner Bot (Bot API Mode)**\n\n"
            "Available Commands:\n"
            "• `/status` - View syncing status & statistics\n"
            "• `/pause` - Temporarily pause real-time syncing\n"
            "• `/resume` - Resume real-time syncing\n"
            "• `/addpair <source_id> <target_id>` - Add channel pair\n"
            "• `/removepair <source_id>` - Remove channel pair\n"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = await self.db.get_stats()
        pairs = await self.db.get_all_pairs()
        status_str = "⏸️ **Paused**" if self.is_paused else "▶️ **Active & Syncing**"
        
        msg = f"📊 **Status:** {status_str}\n"
        msg += f"📦 **Total Synced Messages:** {stats['total_synced_messages']}\n"
        msg += f"🔗 **Active Channel Pairs:** {stats['active_pairs_count']}\n\n"

        if pairs:
            msg += "**Configured Pairs:**\n"
            for p in pairs:
                msg += f"• `{p['source']}` ➔ `{p['target']}`\n"
        else:
            msg += "_No active channel pairs configured._"

        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.is_paused = True
        await update.message.reply_text("⏸️ Real-time channel cloning has been **paused**.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.is_paused = False
        await update.message.reply_text("▶️ Real-time channel cloning has been **resumed**.")

    async def cmd_addpair(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("⚠️ **Usage:** `/addpair <source_id> <target_id>`")
            return
        try:
            source_id = parse_channel_id(args[0])
            target_id = parse_channel_id(args[1])
            await self.db.add_pair(source_id, target_id)
            await self.reload_pairs()
            await update.message.reply_text(f"✅ Added pair: `{source_id}` ➔ `{target_id}`", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding pair: {e}")

    async def cmd_removepair(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("⚠️ **Usage:** `/removepair <source_id>`")
            return
        try:
            source_id = parse_channel_id(args[0])
            await self.db.remove_pair(source_id)
            await self.reload_pairs()
            await update.message.reply_text(f"🗑️ Removed pair for `{source_id}`", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error removing pair: {e}")
