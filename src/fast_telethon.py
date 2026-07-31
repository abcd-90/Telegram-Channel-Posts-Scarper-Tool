import os
import math
import asyncio
import logging
from typing import Optional, Callable
from telethon import TelegramClient
from telethon.tl.types import InputFileLocation, TypeInputFile
from telethon.tl.functions.upload import GetFileRequest, SaveBigFilePartRequest, SaveFilePartRequest

logger = logging.getLogger(__name__)

# Supercharged 100-Socket Concurrent MTProto Transfer Engine
CHUNK_SIZE = 1024 * 1024  # 1 MB per chunk for maximum TCP throughput
WORKERS = 100             # 100 Parallel MTProto TCP Sockets

async def download_file_parallel(
    client: TelegramClient,
    location: InputFileLocation,
    out_file_path: str,
    file_size: int,
    dc_id: int = 4,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """Download Telegram media using 16 parallel socket workers for extreme speed."""
    if file_size <= 0:
        return await client.download_media(location, file=out_file_path)

    part_count = math.ceil(file_size / CHUNK_SIZE)
    os.makedirs(os.path.dirname(out_file_path), exist_ok=True)

    with open(out_file_path, "wb") as f:
        f.seek(file_size - 1)
        f.write(b"\0")

    downloaded_bytes = 0
    lock = asyncio.Lock()

    workers = min(16, part_count)
    senders = []
    for _ in range(workers):
        try:
            sender = await client._borrow_sender(dc_id)
            senders.append(sender)
        except Exception:
            pass

    if not senders:
        senders = [client]

    queue = asyncio.Queue()
    for i in range(part_count):
        queue.put_nowait(i)

    async def worker_loop(sender):
        nonlocal downloaded_bytes
        while not queue.empty():
            part_index = await queue.get()
            offset = part_index * CHUNK_SIZE
            limit = min(CHUNK_SIZE, file_size - offset)

            for attempt in range(3):
                try:
                    req = GetFileRequest(
                        location=location,
                        offset=offset,
                        limit=limit
                    )
                    try:
                        result = await sender(req)
                    except Exception:
                        result = await client(req)

                    data = result.bytes
                    with open(out_file_path, "r+b") as f:
                        f.seek(offset)
                        f.write(data)

                    async with lock:
                        downloaded_bytes += len(data)
                        if progress_callback:
                            progress_callback(downloaded_bytes, file_size)
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.warning(f"Chunk {part_index} retry note: {e}")
                    await asyncio.sleep(0.2)
            queue.task_done()

    worker_tasks = [asyncio.create_task(worker_loop(s)) for s in senders]
    await asyncio.gather(*worker_tasks)

    for sender in senders:
        if sender != client:
            try:
                await client._return_sender(sender)
            except Exception:
                pass

    return out_file_path


async def upload_file_parallel(
    client: TelegramClient,
    file_path: str,
    dc_id: int = 4,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> TypeInputFile:
    """Upload media using 100 independent TCP socket connections for maximum speed."""
    file_size = os.path.getsize(file_path)
    file_id = client._get_input_file_id()
    is_big = file_size > 10 * 1024 * 1024

    part_count = math.ceil(file_size / CHUNK_SIZE)
    uploaded_bytes = 0
    lock = asyncio.Lock()

    senders = []
    for _ in range(WORKERS):
        try:
            sender = await client._borrow_sender(dc_id)
            senders.append(sender)
        except Exception:
            pass

    if not senders:
        senders = [client]

    queue = asyncio.Queue()
    for i in range(part_count):
        queue.put_nowait(i)

    async def worker_loop(sender):
        nonlocal uploaded_bytes
        while not queue.empty():
            part_index = await queue.get()
            offset = part_index * CHUNK_SIZE
            limit = min(CHUNK_SIZE, file_size - offset)

            with open(file_path, "rb") as f:
                f.seek(offset)
                data = f.read(limit)

            for attempt in range(5):
                try:
                    if is_big:
                        req = SaveBigFilePartRequest(
                            file_id=file_id,
                            file_part=part_index,
                            file_total_parts=part_count,
                            bytes=data
                        )
                    else:
                        req = SaveFilePartRequest(
                            file_id=file_id,
                            file_part=part_index,
                            bytes=data
                        )

                    if hasattr(sender, 'send') or hasattr(sender, '__call__'):
                        await sender(req)
                    else:
                        await client(req)

                    async with lock:
                        uploaded_bytes += len(data)
                        if progress_callback:
                            progress_callback(uploaded_bytes, file_size)
                    break
                except Exception as e:
                    if attempt == 4:
                        logger.warning(f"Upload chunk {part_index} error: {e}")
                    await asyncio.sleep(0.1)
            queue.task_done()

async def stream_media_direct_pipeline(
    client: TelegramClient,
    source_msg,
    target_entity,
    caption: str = "",
    formatting_entities = None,
    attributes = None,
    mime_type: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Optional[Any]:
    """True MTProto Producer-Consumer Pipe: Streams download chunks directly into upload parts without full file waiting."""
    doc = getattr(source_msg.media, 'document', None)
    file_size = getattr(doc, 'size', 0) if doc else 0

    if file_size <= 0:
        return None

    file_id = client._get_input_file_id()
    part_count = math.ceil(file_size / CHUNK_SIZE)
    is_big = file_size > 10 * 1024 * 1024

    # Bounded Asyncio Queue for Producer (Download) -> Consumer (Upload) stream
    chunk_queue = asyncio.Queue(maxsize=8)
    
    download_bytes = 0
    upload_bytes = 0

    # Producer Task: Download MTProto GetFileRequest Chunks
    async def producer_download():
        nonlocal download_bytes
        part_index = 0
        async for chunk in client.iter_download(source_msg.media, chunk_size=CHUNK_SIZE):
            await chunk_queue.put((part_index, chunk))
            download_bytes += len(chunk)
            if progress_callback:
                progress_callback(download_bytes, file_size, "Download")
            part_index += 1
        await chunk_queue.put((None, None))  # Sentinel EOF signal

    # Consumer Task: Upload MTProto SaveBigFilePartRequest Chunks immediately
    async def consumer_upload():
        nonlocal upload_bytes
        while True:
            part_index, data = await chunk_queue.get()
            if part_index is None:
                chunk_queue.task_done()
                break

            if is_big:
                req = SaveBigFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    file_total_parts=part_count,
                    bytes=data
                )
            else:
                req = SaveFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    bytes=data
                )

            await client(req)
            upload_bytes += len(data)
            if progress_callback:
                progress_callback(upload_bytes, file_size, "Upload")
            chunk_queue.task_done()

    # Run Producer and Consumer in Parallel
    await asyncio.gather(producer_download(), consumer_upload())

    # Finalize Telegram InputFile construction
    file_name = f"media_{source_msg.id}"
    if attributes:
        for attr in attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                file_name = attr.file_name
                break

    if is_big:
        from telethon.tl.types import InputFileBig
        input_file = InputFileBig(id=file_id, parts=part_count, name=file_name)
    else:
        from telethon.tl.types import InputFile
        input_file = InputFile(id=file_id, parts=part_count, name=file_name, md5_checksum="")

    # Preserving exact video streaming UI (force_document=False for videos/photos so Telegram renders inline player)
    is_video_or_photo = False
    if attributes:
        from telethon.tl.types import DocumentAttributeVideo, MessageMediaPhoto
        for attr in attributes:
            if isinstance(attr, DocumentAttributeVideo):
                is_video_or_photo = True
                break
    if isinstance(getattr(source_msg, 'media', None), MessageMediaPhoto):
        is_video_or_photo = True

    force_doc = False if is_video_or_photo else bool(doc)

    # Prevent link truncation by splitting long captions (> 1024 chars)
    short_caption = caption if len(caption) <= 1024 else ""

    sent_msg = await client.send_file(
        target_entity,
        file=input_file,
        caption=short_caption,
        formatting_entities=formatting_entities if short_caption else None,
        parse_mode='md' if not formatting_entities else None,
        attributes=attributes,
        mime_type=mime_type,
        force_document=force_doc
    )

    if len(caption) > 1024:
        text_msg = await client.send_message(
            target_entity,
            message=caption,
            formatting_entities=formatting_entities,
            parse_mode='md' if not formatting_entities else None
        )
        sent_msg = text_msg or sent_msg

    return sent_msg
