import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class ContentFilter:
    def __init__(self, enable: bool = True, blocked_keywords: Optional[List[str]] = None, nsfw_detection: bool = True, min_length: int = 0):
        self.enable = enable
        self.blocked_keywords = blocked_keywords or ["spam", "adult", "casino", "gambling", "crypto_scam"]
        self.nsfw_detection = nsfw_detection
        self.min_length = min_length
        self.nsfw_keywords = ["nsfw", "18+", "porn", "xxx", "hentai", "sex", "adult"]

    def is_allowed(self, text: str, msg_id: int) -> bool:
        if not self.enable:
            return True

        content = (text or "").strip()

        if self.min_length > 0 and len(content) < self.min_length and not content:
            logger.info(f"⛔ [Filtered] Message {msg_id} skipped: Text length ({len(content)}) below min_length ({self.min_length})")
            return False

        lowered = content.lower()

        # Blocked keywords check
        for kw in self.blocked_keywords:
            if kw and re.search(r'\b' + re.escape(kw.lower()) + r'\b', lowered):
                logger.info(f"⛔ [Filtered] Blocked keyword '{kw}' detected in msg {msg_id}")
                return False

        # NSFW detection check
        if self.nsfw_detection:
            for nsfw in self.nsfw_keywords:
                if re.search(r'\b' + re.escape(nsfw) + r'\b', lowered):
                    logger.info(f"⛔ [Filtered] NSFW content skipped: msg {msg_id}")
                    return False

        return True
