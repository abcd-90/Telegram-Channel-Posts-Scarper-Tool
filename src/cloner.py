import os
import io
import time
import psutil
import asyncio
import logging
from typing import Dict, List, Optional, Set, Union
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageMediaPoll,
    InputMediaPoll,
    Poll,
    PollAnswer,
    InputMediaDocument,
    InputDocument,
    InputMediaPhoto,
    InputPhoto
)
from telethon.errors import ChatForwardsRestrictedError

from src.config import AppConfig, ChannelPair
from src.database import Database
from src.utils import retry_with_backoff, MediaManager

logger = logging.getLogger(__name__)

def normalize_chat_id(chat_id_val) -> int:
    """Helper to convert any Telethon Entity/Peer/str/int chat_id to standard integer format (-100xxxx)."""
    if isinstance(chat_id_val, int):
        return chat_id_val
    if hasattr(chat_id_val, 'channel_id'):
        return int(f"-100{chat_id_val.channel_id}")
    if hasattr(chat_id_val, 'chat_id'):
        return int(f"-100{chat_id_val.chat_id}")
    if hasattr(chat_id_val, 'id'):
        raw_id = chat_id_val.id
        raw_str = str(raw_id)
        if raw_str.startswith("-100"):
            return int(raw_str)
        return int(f"-100{raw_id}")
    
    val_str = str(chat_id_val).strip()
    if val_str.startswith("-100"):
        return int(val_str)
    elif val_str.replace("-", "").isdigit():
        if val_str.startswith("-"):
            return int(val_str)
        return int(f"-100{val_str}")
    return int(val_str)

class PerformanceMonitor:
    """Real-time performance profiling & metric logger."""
    def __init__(self):
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())
        self.download_bytes = 0
        self.upload_bytes = 0
        self.download_time = 0.0
        self.upload_time = 0.0
        self.api_wait_time = 0.0
        self.messages_processed = 0

    def add_download(self, bytes_len: int, duration: float):
        self.download_bytes += bytes_len
        self.download_time += duration

    def add_upload(self, bytes_len: int, duration: float):
        self.upload_bytes += bytes_len
        self.upload_time += duration

    def add_api_wait(self, duration: float):
        self.api_wait_time += duration

    def get_report(self) -> str:
        elapsed = max(time.time() - self.start_time, 0.001)
        mem_info = self.process.memory_info()
        cpu_usage = self.process.cpu_percent(interval=None)

        down_mb = self.download_bytes / (1024 * 1024)
        up_mb = self.upload_bytes / (1024 * 1024)

        down_tp = down_mb / self.download_time if self.download_time > 0 else 0.0
        up_tp = up_mb / self.upload_time if self.upload_time > 0 else 0.0

        return (
            f"\n📊 === TELEGRAM CLONER PERFORMANCE REPORT ===\n"
            f"⏱️ Total Execution Time: {round(elapsed, 2)}s\n"
            f"✉️ Messages Synced: {self.messages_processed}\n"
            f"⚡ Avg Download Speed: {round(down_tp, 2)} MB/s ({round(down_mb, 1)} MB Total)\n"
            f"🚀 Avg Upload Speed: {round(up_tp, 2)} MB/s ({round(up_mb, 1)} MB Total)\n"
            f"⏳ Total API Wait Time: {round(self.api_wait_time, 2)}s\n"
            f"💻 CPU Usage: {cpu_usage}%\n"
            f"🧠 RAM Usage: {round(mem_info.rss / (1024 * 1024), 2)} MB\n"
            f"=================================================\n"
        )

class ChannelCloner:
    def __init__(self, client: TelegramClient, db: Database, config: AppConfig):
        self.client = client
        self.db = db
        self.config = config
        self.media_manager = MediaManager()
        self.is_paused: bool = False
        self.pairs_map: Dict[Union[int, str], List[ChannelPair]] = {}
        self.entity_cache: Dict[int, Any] = {}
        self.semaphore = asyncio.Semaphore(10)
        self.perf = PerformanceMonitor()

        # Modular Features Initializations (Fail-Soft)
        from src.filters.content_filter import ContentFilter
        from src.duplicate_detector import DuplicateDetector
        from src.translator import MessageTranslator
        from src.auto_reply import AutoReplyManager
        from src.analytics import AnalyticsTracker

        self.content_filter = ContentFilter(enable=True)
        self.duplicate_detector = DuplicateDetector(enable=True)
        self.translator = MessageTranslator(enable=False)  # Toggle in config
        self.auto_reply = AutoReplyManager(enable=False)
        self.analytics = AnalyticsTracker()

    async def get_cached_entity(self, chat_id: int):
        if chat_id not in self.entity_cache:
            t0 = time.time()
            self.entity_cache[chat_id] = await self.client.get_entity(chat_id)
            self.perf.add_api_wait(time.time() - t0)
        return self.entity_cache[chat_id]

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

        logger.info(f"[Telethon] Loaded {len(db_pairs)} active channel pairs.")

    async def register_handlers(self):
        """Register Telethon event listeners for incoming new messages, edits, and deletions."""
        await self.reload_pairs()

        @self.client.on(events.NewMessage)
        async def on_new_message(event: events.NewMessage.Event):
            if self.is_paused:
                return

            chat_id = event.chat_id
            matched_pairs = self.pairs_map.get(chat_id, [])

            if not matched_pairs:
                chat = await event.get_chat()
                if hasattr(chat, 'username') and chat.username:
                    uname = f"@{chat.username}"
                    matched_pairs = self.pairs_map.get(uname, [])

            if not matched_pairs:
                return

            for pair in matched_pairs:
                asyncio.create_task(self._safe_clone_message(event.message, pair.source, pair.target))

        @self.client.on(events.MessageEdited)
        async def on_message_edited(event: events.MessageEdited.Event):
            if self.is_paused:
                return
            chat_id = event.chat_id
            matched_pairs = self.pairs_map.get(chat_id, [])

            for pair in matched_pairs:
                if pair.mirror_edits:
                    asyncio.create_task(self._handle_message_edit(event.message, pair))

        @self.client.on(events.MessageDeleted)
        async def on_message_deleted(event: events.MessageDeleted.Event):
            if self.is_paused:
                return
            chat_id = event.chat_id
            matched_pairs = self.pairs_map.get(chat_id, [])

            for pair in matched_pairs:
                if pair.mirror_deletions:
                    asyncio.create_task(self._handle_message_deletion(event, pair))

        logger.info("Telethon event handlers successfully registered.")

    async def _safe_clone_message(self, message, source, target):
        async with self.semaphore:
            try:
                await self._clone_single_message_obj(message, source, target)
                self.perf.messages_processed += 1
            except Exception as e:
                logger.error(f"[Error] Failed to clone message {message.id}: {e}")

    async def _handle_message_deletion(self, event, pair):
        try:
            source_norm = normalize_chat_id(pair.source)
            target_norm = normalize_chat_id(pair.target)
            for deleted_id in event.deleted_ids:
                target_msg_id = await self.db.delete_mapping(source_norm, deleted_id, target_norm)
                if target_msg_id:
                    await retry_with_backoff(self.client.delete_messages, pair.target, [target_msg_id], max_retries=3)
        except Exception as e:
            logger.error(f"[Error] Failed mirroring deletion: {e}")

    async def backfill_all_pairs(self):
        """Clone all past existing messages using Producer-Consumer queue pipeline."""
        for source, pairs in self.pairs_map.items():
            for pair in pairs:
                if getattr(pair, "backfill_history", True):
                    await self.backfill_history(pair.source, pair.target)

    async def backfill_history(self, source, target, limit: Optional[int] = None):
        """Asynchronous Concurrent Producer-Consumer Backfill Pipeline."""
        source_norm = normalize_chat_id(source)
        target_norm = normalize_chat_id(target)

        try:
            source_entity = await self.get_cached_entity(source_norm)
            target_entity = await self.get_cached_entity(target_norm)
        except Exception as e:
            logger.error(f"[Error] Cannot resolve entities ({source_norm} -> {target_norm}): {e}")
            return

        messages = []
        async for msg in self.client.iter_messages(source_entity, limit=limit, reverse=True):
            if msg.action:
                continue
            messages.append(msg)

        logger.info(f"🚀 [Strict Chronological Sequence] Starting backfill of {len(messages)} messages in exact source order...")

        queue = asyncio.Queue(maxsize=50)

        async def worker():
            while True:
                msg = await queue.get()
                if msg is None:
                    queue.task_done()
                    break
                try:
                    await self._safe_clone_message(msg, source_norm, target_entity)
                except Exception as e:
                    logger.error(f"Worker error: {e}")
                finally:
                    queue.task_done()

        # Launch 5 concurrent pipeline consumer workers
        workers = [asyncio.create_task(worker()) for _ in range(5)]

        for idx, msg in enumerate(messages, 1):
            existing = await self.db.get_target_message_id(source_norm, msg.id, target_norm)
            if existing:
                continue
            await queue.put(msg)

        await queue.join()

        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers)

        logger.info(f"Historical backfill complete for {source_norm}.\n{self.perf.get_report()}")

    async def _clone_single_message_obj(self, source_msg, source_id, target_entity):
        """3-Step ultra-fast cloning hierarchy: Forward -> Copy -> In-memory streaming fallback."""
        source_norm = normalize_chat_id(source_id)
        target_norm = normalize_chat_id(target_entity)

        # Deduplication check
        existing = await self.db.get_target_message_id(source_norm, source_msg.id, target_norm)
        if existing:
            return

        text_content = source_msg.text or ""

        # Feature 1: AI Content Filter Hook
        if not self.content_filter.is_allowed(text_content, source_msg.id):
            return

        # Feature 8: Duplicate Detection Hook (Text & Media Hashing)
        if self.duplicate_detector.is_duplicate(text_content, source_msg.id, source_msg.media):
            return

        # Feature 4: Message Translation Hook
        if text_content and self.translator.enable:
            source_msg.text = await self.translator.translate_text(text_content, source_msg.id)

        # Tier 1: Server-side forward (Instantaneous server copy)
        if self.config.settings.forward_enabled:
            try:
                fwd = await retry_with_backoff(self.client.forward_messages, target_entity, source_msg, max_retries=1)
                if fwd:
                    target_msg_id = fwd[0].id if isinstance(fwd, list) else fwd.id
                    await self.db.save_mapping(source_norm, source_msg.id, target_norm, target_msg_id)
                    logger.info(f"⚡ [Instant Copy] Server-side forwarded msg {source_msg.id} -> Target {target_msg_id}")
                    return
            except ChatForwardsRestrictedError:
                pass
            except Exception:
                pass

        # Tier 2: Direct InputMedia Server Copy (Instant clone without downloading)
        if source_msg.media and not isinstance(source_msg.media, MessageMediaPoll):
            try:
                text = source_msg.text or ""
                doc = getattr(source_msg.media, 'document', None)
                photo = getattr(source_msg.media, 'photo', None)

                if doc:
                    from telethon.tl.types import InputMediaDocument, InputDocument
                    input_doc = InputDocument(
                        id=doc.id,
                        access_hash=doc.access_hash,
                        file_reference=doc.file_reference
                    )
                    input_media = InputMediaDocument(id=input_doc)
                    sent_msg = await retry_with_backoff(
                        self.client.send_message,
                        target_entity,
                        message=text,
                        file=input_media,
                        formatting_entities=source_msg.entities,
                        max_retries=1
                    )
                    if sent_msg:
                        await self.db.save_mapping(source_norm, source_msg.id, target_norm, sent_msg.id)
                        logger.info(f"⚡ [INSTANT SERVER COPY] Synced document msg {source_msg.id} -> Target {sent_msg.id}")
                        return
                elif photo:
                    from telethon.tl.types import InputMediaPhoto, InputPhoto
                    input_photo = InputPhoto(
                        id=photo.id,
                        access_hash=photo.access_hash,
                        file_reference=photo.file_reference
                    )
                    input_media = InputMediaPhoto(id=input_photo)
                    sent_msg = await retry_with_backoff(
                        self.client.send_message,
                        target_entity,
                        message=text,
                        file=input_media,
                        formatting_entities=source_msg.entities,
                        max_retries=1
                    )
                    if sent_msg:
                        await self.db.save_mapping(source_norm, source_msg.id, target_norm, sent_msg.id)
                        logger.info(f"⚡ [INSTANT SERVER COPY] Synced photo msg {source_msg.id} -> Target {sent_msg.id}")
                        return
            except Exception as e:
                logger.debug(f"Direct InputMedia copy note: {e}")

        # Tier 3: Re-upload Fallback with adaptive chunk size & real-time MB/s counter
        logger.warning(f"⚠️ [Tier 3 Fallback Triggered] Message {source_msg.id} requires full media re-upload.")
        await self._reupload_message_fast(source_msg, source_norm, target_norm, target_entity)

    async def _reupload_message_fast(self, source_msg, source_norm: int, target_norm: int, target_entity):
        """Re-upload media preserving exact original file attributes, mime types, filenames, and extensions."""
        try:
            text = source_msg.text or ""
            entities = source_msg.entities

            # Handle Polls
            if isinstance(source_msg.media, MessageMediaPoll):
                poll_obj: Poll = source_msg.media.poll
                poll_answers = [PollAnswer(text=ans.text, option=ans.option) for ans in poll_obj.answers]
                input_poll = InputMediaPoll(
                    poll=Poll(
                        id=0,
                        question=poll_obj.question,
                        answers=poll_answers,
                        closed=poll_obj.closed,
                        public_voters=poll_obj.public_voters,
                        multiple_choice=poll_obj.multiple_choice,
                        quiz=poll_obj.quiz
                    )
                )
                sent_msg = await retry_with_backoff(self.client.send_message, target_entity, file=input_poll, max_retries=3)

            # Handle Media (Photo, Video, Document, Audio, Voice, APK, ZIP, etc.)
            elif source_msg.media and self.config.settings.download_media:
                doc = getattr(source_msg.media, 'document', None)
                attributes = getattr(doc, 'attributes', None) if doc else None
                mime_type = getattr(doc, 'mime_type', None) if doc else None

                last_stream_log = [-5]
                t_stream_start = time.time()
                def stream_progress(bytes_processed, total_bytes, action):
                    if total_bytes > 0:
                        percent = int((bytes_processed / total_bytes) * 100)
                        if percent >= last_stream_log[0] + 5 or bytes_processed == total_bytes:
                            last_stream_log[0] = percent
                            mb_done = round(bytes_processed / (1024 * 1024), 2)
                            mb_total = round(total_bytes / (1024 * 1024), 2)
                            elapsed = max(time.time() - t_stream_start, 0.001)
                            speed_mbs = round(mb_done / elapsed, 2)
                            logger.info(f"⚡🚀 [TRUE MTPROTO PIPE STREAM] {action} msg {source_msg.id}: {percent}% ({mb_done}MB / {mb_total}MB) @ {speed_mbs} MB/s")

                from src.fast_telethon import stream_media_direct_pipeline
                try:
                    sent_msg = await stream_media_direct_pipeline(
                        self.client,
                        source_msg,
                        target_entity,
                        caption=text,
                        formatting_entities=entities,
                        attributes=attributes,
                        mime_type=mime_type,
                        progress_callback=stream_progress
                    )
                except Exception as stream_err:
                    logger.warning(f"Direct stream pipeline note ({stream_err}), executing robust fallback...")
                    # Fallback to local file caching if stream pipeline fails
                    temp_file_name = f"msg_{source_msg.id}"
                    original_filename = None
                    if doc and hasattr(doc, 'attributes'):
                        for attr in doc.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                original_filename = attr.file_name
                                break

                    temp_file_path = os.path.join(self.media_manager.temp_dir, original_filename or temp_file_name)
                    downloaded_path = await retry_with_backoff(
                        self.client.download_media,
                        source_msg,
                        file=temp_file_path,
                        max_retries=3
                    )
                    if downloaded_path and os.path.exists(downloaded_path):
                        sent_msg = await retry_with_backoff(
                            self.client.send_file,
                            target_entity,
                            file=downloaded_path,
                            caption=text,
                            formatting_entities=entities,
                            attributes=attributes,
                            mime_type=mime_type,
                            force_document=bool(doc),
                            max_retries=3
                        )
                        self.media_manager.cleanup_file(downloaded_path)
                    else:
                        raise ValueError(f"Media download returned empty path for msg {source_msg.id}")

            # Text-only Message
            else:
                raw_txt = getattr(source_msg, 'raw_text', None) or text
                sent_msg = await retry_with_backoff(
                    self.client.send_message,
                    target_entity,
                    message=raw_txt,
                    formatting_entities=entities,
                    parse_mode=None,
                    max_retries=3
                )

            if sent_msg:
                await self.db.save_mapping(source_norm, source_msg.id, target_norm, sent_msg.id)

        except Exception as e:
            logger.error(f"[Error] Failed to reupload message {source_msg.id}: {e}")

    async def _handle_message_edit(self, source_msg, pair: ChannelPair):
        """Mirror edits with exponential backoff retry."""
        source_norm = normalize_chat_id(pair.source)
        target_norm = normalize_chat_id(pair.target)

        target_msg_id = await self.db.get_target_message_id(source_norm, source_msg.id, target_norm)
        if not target_msg_id:
            return

        text = source_msg.text or ""
        try:
            await retry_with_backoff(
                self.client.edit_message,
                pair.target,
                target_msg_id,
                text=text,
                formatting_entities=source_msg.entities,
                max_retries=3
            )
        except Exception as e:
            logger.error(f"[Error] Failed editing target msg {pair.target}:{target_msg_id}: {e}")

