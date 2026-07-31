import asyncio
import time
from telethon import TelegramClient
from src.config import load_config

async def test():
    config = load_config()
    client = TelegramClient("data/user_session", config.telegram.api_id, config.telegram.api_hash)
    await client.start()
    
    source_entity = await client.get_entity(-1002883085073)
    async for msg in client.iter_messages(source_entity, limit=200, reverse=True):
        if msg.id == 120:
            print(f"Found message 120! Media size: {getattr(msg.media.document, 'size', 0) / (1024*1024):.1f} MB")
            start_t = time.time()
            path = await client.download_media(msg, file="data/temp_test.mp4")
            elapsed = time.time() - start_t
            print(f"Download finished in {elapsed:.1f}s! Speed: {(568.2 / elapsed):.2f} MB/s")
            break
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
