import logging
from typing import List, Set, Optional, Any

logger = logging.getLogger(__name__)

class DuplicateDetector:
    def __init__(self, enable: bool = True, similarity_threshold: int = 85):
        self.enable = enable
        self.similarity_threshold = similarity_threshold
        self.seen_texts: List[str] = []

    def is_duplicate(self, text: str, msg_id: int, media_obj: Optional[Any] = None) -> bool:
        if not self.enable:
            return False

        # Media duplicate tracking by document/photo unique ID or size
        if media_obj:
            doc = getattr(media_obj, 'document', None)
            photo = getattr(media_obj, 'photo', None)
            media_key = None
            if doc:
                media_key = f"doc_{doc.id}_{getattr(doc, 'size', 0)}"
            elif photo:
                media_key = f"photo_{photo.id}"

            if media_key:
                if media_key in self.seen_texts:
                    logger.info(f"⏭️ [Duplicate Media] Skipped identical media asset for msg_{msg_id}")
                    return True
                self.seen_texts.append(media_key)

        lowered = (text or "").strip().lower()
        if not lowered or len(lowered) < 5:
            return False

        # Exact duplicate match
        if lowered in self.seen_texts:
            logger.info(f"⏭️ [Duplicate Text] Skipped exact duplicate message: msg_{msg_id}")
            return True

        # Fuzzy similarity check
        try:
            from difflib import SequenceMatcher
            for seen in self.seen_texts[-500:]:
                if isinstance(seen, str) and not seen.startswith("doc_") and not seen.startswith("photo_"):
                    ratio = SequenceMatcher(None, lowered, seen).ratio() * 100
                    if ratio >= self.similarity_threshold:
                        logger.info(f"⏭️ [Duplicate] Skipped similar message ({round(ratio,1)}% match): msg_{msg_id}")
                        return True
        except Exception:
            pass

        self.seen_texts.append(lowered)
        if len(self.seen_texts) > 2000:
            self.seen_texts.pop(0)

        return False
