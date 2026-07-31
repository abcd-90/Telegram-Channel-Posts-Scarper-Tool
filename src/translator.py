import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MessageTranslator:
    def __init__(self, enable: bool = False, source_lang: str = "en", target_lang: str = "ur"):
        self.enable = enable
        self.source_lang = source_lang
        self.target_lang = target_lang

    async def translate_text(self, text: str, msg_id: int) -> str:
        if not self.enable or not text or len(text.strip()) == 0:
            return text

        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source=self.source_lang, target=self.target_lang).translate(text)
            if translated:
                logger.info(f"🌐 [Translated] {self.source_lang.upper()} → {self.target_lang.upper()}: msg_{msg_id}")
                return translated
        except Exception as e:
            logger.warning(f"⚠️ [Translator Note] Skipping translation for msg {msg_id}: {e}")

        return text
