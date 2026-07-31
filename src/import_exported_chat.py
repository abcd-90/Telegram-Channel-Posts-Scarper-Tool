import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from telegram import Bot
from telegram.error import RetryAfter, TelegramError

# Add project root directory to python path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config import load_config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s]: %(message)s")
logger = logging.getLogger("Importer")

async def import_exported_history(json_path: str, target_channel_id: str):
    config = load_config()
    if not config.bot_token:
        logger.error("BOT_TOKEN is missing in config/config.yaml or .env!")
        return

    bot = Bot(token=config.bot_token)
    logger.info("Connecting Bot to Telegram...")
    bot_info = await bot.get_me()
    logger.info(f"Bot connected: @{bot_info.username}")

    if not os.path.exists(json_path):
        logger.error(f"Export file '{json_path}' not found!")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    logger.info(f"Loaded {len(messages)} messages from '{json_path}'")

    export_dir = os.path.dirname(os.path.abspath(json_path))
    success_count = 0

    for idx, msg in enumerate(messages, 1):
        msg_type = msg.get("type")
        if msg_type != "message":
            continue

        text_content = msg.get("text")
        text_str = ""
        if isinstance(text_content, str):
            text_str = text_content
        elif isinstance(text_content, list):
            for part in text_content:
                if isinstance(part, str):
                    text_str += part
                elif isinstance(part, dict) and "text" in part:
                    text_str += part["text"]

        media_file = None
        if "file" in msg and msg["file"]:
            media_file = os.path.join(export_dir, msg["file"])
        elif "photo" in msg and msg["photo"]:
            media_file = os.path.join(export_dir, msg["photo"])

        try:
            if media_file and os.path.exists(media_file):
                logger.info(f"[{idx}/{len(messages)}] Uploading media file: {os.path.basename(media_file)}")
                with open(media_file, "rb") as f:
                    if media_file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        await bot.send_photo(chat_id=target_channel_id, photo=f, caption=text_str[:1024] if text_str else None)
                    elif media_file.lower().endswith((".mp4", ".mkv", ".mov", ".avi")):
                        await bot.send_video(chat_id=target_channel_id, video=f, caption=text_str[:1024] if text_str else None)
                    else:
                        await bot.send_document(chat_id=target_channel_id, document=f, caption=text_str[:1024] if text_str else None)
            elif text_str.strip():
                logger.info(f"[{idx}/{len(messages)}] Sending text message...")
                await bot.send_message(chat_id=target_channel_id, text=text_str)

            success_count += 1
            await asyncio.sleep(1.5)  # Safe delay to prevent rate limits

        except RetryAfter as e:
            logger.warning(f"Rate limited. Waiting {e.retry_after} seconds...")
            await asyncio.sleep(e.retry_after)
        except TelegramError as e:
            logger.error(f"Failed to send message #{msg.get('id')}: {e}")

    logger.info(f"🎉 SUCCESS! Imported {success_count} messages into channel {target_channel_id}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\nUsage: py src/import_exported_chat.py <path_to_result.json> <target_channel_id>")
        print("Example: py src/import_exported_chat.py result.json @my_target_channel\n")
    else:
        json_file = sys.argv[1]
        target = sys.argv[2]
        asyncio.run(import_exported_history(json_file, target))
