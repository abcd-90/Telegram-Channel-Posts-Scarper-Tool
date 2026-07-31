import os
import logging
import yaml
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ChannelPair:
    source: str | int
    target: str | int
    mirror_edits: bool = True
    mirror_deletions: bool = True
    backfill_history: bool = True

@dataclass
class TelegramConfig:
    api_id: int = 37604254
    api_hash: str = "a3e5e613247c608bb81a3000c9bb9785"
    phone_number: Optional[str] = None

@dataclass
class SettingsConfig:
    forward_enabled: bool = False
    download_media: bool = True
    max_file_size_mb: int = 500  # Max file size limit in MB (Set 0 for unlimited)
    retry_attempts: int = 5
    retry_delay: int = 5
    flood_sleep_threshold: int = 60
    log_level: str = "INFO"

@dataclass
class AppConfig:
    telegram: TelegramConfig
    channels: List[ChannelPair] = field(default_factory=list)
    bot_token: Optional[str] = None
    settings: SettingsConfig = field(default_factory=SettingsConfig)

def parse_channel_id(val: str | int) -> str | int:
    """Format channel ID or username."""
    if isinstance(val, int):
        return val
    val_str = str(val).strip()
    if val_str.startswith("@") or not val_str.replace("-", "").isdigit():
        return val_str
    if val_str.startswith("-100"):
        return int(val_str)
    elif val_str.isdigit():
        return int(f"-100{val_str}")
    return int(val_str)

def load_config(config_path: Optional[str] = None) -> AppConfig:
    if not config_path:
        config_path = os.getenv("CONFIG_PATH", "config/config.yaml")

    yaml_data = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}

    tg_data = yaml_data.get("telegram", {})
    api_id_env = os.getenv("TELEGRAM_API_ID") or tg_data.get("api_id") or 37604254
    api_hash_env = os.getenv("TELEGRAM_API_HASH") or tg_data.get("api_hash") or "a3e5e613247c608bb81a3000c9bb9785"
    phone_number = os.getenv("TELEGRAM_PHONE_NUMBER") or tg_data.get("phone_number")
    bot_token = os.getenv("BOT_TOKEN") or yaml_data.get("bot_token")

    telegram_cfg = TelegramConfig(
        api_id=int(api_id_env),
        api_hash=str(api_hash_env),
        phone_number=str(phone_number or "")
    )

    channels_list: List[ChannelPair] = []
    for item in yaml_data.get("channels", []):
        try:
            source = parse_channel_id(item["source"])
            target = parse_channel_id(item["target"])
            mirror_edits = item.get("mirror_edits", True)
            mirror_deletions = item.get("mirror_deletions", True)
            backfill = item.get("backfill_history", True)
            channels_list.append(ChannelPair(
                source=source,
                target=target,
                mirror_edits=mirror_edits,
                mirror_deletions=mirror_deletions,
                backfill_history=backfill
            ))
        except Exception as e:
            logging.warning(f"Error parsing channel pair {item}: {e}")

    settings_data = yaml_data.get("settings", {})
    settings_cfg = SettingsConfig(
        forward_enabled=settings_data.get("forward_enabled", False),
        download_media=settings_data.get("download_media", True),
        max_file_size_mb=settings_data.get("max_file_size_mb", 500),
        retry_attempts=settings_data.get("retry_attempts", 5),
        retry_delay=settings_data.get("retry_delay", 5),
        flood_sleep_threshold=settings_data.get("flood_sleep_threshold", 60),
        log_level=settings_data.get("log_level", "INFO")
    )

    return AppConfig(
        telegram=telegram_cfg,
        channels=channels_list,
        bot_token=bot_token if bot_token and bot_token != "YOUR_BOT_TOKEN" else None,
        settings=settings_cfg
    )
