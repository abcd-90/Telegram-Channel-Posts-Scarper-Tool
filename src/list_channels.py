import os
import sys
from pathlib import Path

# Add project root directory to python path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import logging
from telethon import TelegramClient
from src.config import load_config

async def list_joined_channels():
    config = load_config()
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    session_path = os.path.join("data", "user_session")
    
    client = TelegramClient(
        session_path,
        config.telegram.api_id,
        config.telegram.api_hash
    )
    
    print("\n" + "="*60)
    print("TELEGRAM LOGIN SESSION SETUP")
    print("="*60)
    
    phone = config.telegram.phone_number if config.telegram.phone_number else None
    if phone:
        await client.start(phone=phone)
    else:
        await client.start()
    
    print("\n" + "="*60)
    print("YOUR JOINED TELEGRAM CHANNELS & GROUPS:")
    print("="*60 + "\n")

    async for dialog in client.iter_dialogs():
        if dialog.is_channel or dialog.is_group:
            channel_id = dialog.id
            title = dialog.name
            username = f"@{dialog.entity.username}" if hasattr(dialog.entity, 'username') and dialog.entity.username else "No Username (Private Channel)"
            print(f"Name: {title}")
            print(f"ID:   {channel_id}")
            print(f"Link: {username}")
            print("-" * 60)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(list_joined_channels())
