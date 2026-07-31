import asyncio
import logging
import os
import shutil
import tempfile
from typing import Any, Callable, Optional
from telethon.errors import ChatForwardsRestrictedError, MediaCaptionTooLongError

logger = logging.getLogger(__name__)

async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs
) -> Any:
    """Execute async function with exponential backoff retry logic."""
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (ChatForwardsRestrictedError, MediaCaptionTooLongError, asyncio.CancelledError):
            # Instant non-retryable exception - raise immediately for instant fallback
            raise
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                raise e
            logger.warning(f"Telegram RPCError on attempt {attempt}/{max_retries}: {e}")
            await asyncio.sleep(delay)
            delay *= backoff_factor

class MediaManager:
    def __init__(self, temp_dir: Optional[str] = None):
        if temp_dir:
            self.temp_dir = temp_dir
        else:
            self.temp_dir = os.path.join(tempfile.gettempdir(), "telegram_cloner_media")
        os.makedirs(self.temp_dir, exist_ok=True)

    def cleanup_file(self, file_path: str):
        """Safely remove temporary downloaded file."""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {file_path}: {e}")

    def cleanup_all(self):
        """Clear the entire temporary directory."""
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir, exist_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clear temp directory {self.temp_dir}: {e}")
