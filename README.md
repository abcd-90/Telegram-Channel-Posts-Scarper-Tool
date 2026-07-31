# Telegram Channel Cloning & Mirroring Bot 🚀

A production-ready, real-time Telegram channel cloner and mirror system built in **Python 3.11+** using **Telethon** (official Telegram MTProto API library), **SQLite** (via `aiosqlite`), and **Docker**.

Automatically mirrors text, photos, videos, audio, voice messages, polls, documents, and stickers from one or multiple source Telegram channels to target channels in real-time.

---

## ✨ Features

- **Real-Time Channel Mirroring:** Listens to incoming channel messages, edits, and deletions via Telegram MTProto API.
- **Smart Forwarding Fallback:** Attempts native Telegram forwarding first. If forwarding is restricted by channel admins (`ChatForwardsRestrictedError`), downloads media automatically and re-uploads without "Forwarded from" tags.
- **Deduplication:** Persistent SQLite database tracks `source_msg_id` to `target_msg_id` mappings to prevent duplicate postings.
- **Edit & Deletion Mirroring:** Automatically mirrors text edits and message deletions in real-time.
- **Multi-Channel Support:** Configure multiple `source -> target` channel pairs concurrently.
- **Rate Limit & Error Recovery:** Handles `FloodWaitError` with automatic sleep delays, and retries temporary RPC errors with exponential backoff.
- **Telegram Admin Bot Commands:** Control and monitor the cloner via Telegram commands (`/start`, `/status`, `/pause`, `/resume`, `/addpair`, `/removepair`).
- **Docker Ready:** Complete `Dockerfile` and `docker-compose.yml` for instant deployment.

---

## 📁 Project Structure

```
telegram-cloner-bot/
├── src/
│   ├── __init__.py
│   ├── main.py          # Entry point & event loop runner
│   ├── config.py        # Config parser (YAML + Environment variables)
│   ├── database.py      # SQLite database operations (aiosqlite)
│   ├── client.py        # Telethon client initialization & management
│   ├── cloner.py        # Core cloning logic, edit/deletion handlers
│   ├── admin_bot.py     # Telegram Bot API command handlers
│   └── utils.py         # Retry logic, backoff, and temporary file management
├── config/
│   └── config.yaml      # Channel pairs & settings configuration
├── data/
│   └── clone_history.db # SQLite database & Telethon session files
├── logs/
│   └── app.log          # Application log file
├── Dockerfile           # Python container setup
├── docker-compose.yml   # Docker Compose orchestration
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── README.md            # Documentation
```

---

## 🛠️ Setup Instructions

### Prerequisites
1. **Telegram API Credentials:** Obtain `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org).
2. **Bot Token (Optional):** Obtain a Bot Token from [@BotFather](https://t.me/BotFather) for admin commands.
3. **Channel Admin Access:** Ensure your Telegram account or bot has posting/sending permissions in target channels.

---

### Option 1: Running with Python Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/telegram-cloner-bot.git
   cd telegram-cloner-bot
   ```

2. **Create a virtual environment & install dependencies:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your Telegram API details:
   ```env
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=your_api_hash_here
   TELEGRAM_PHONE_NUMBER=+1234567890
   BOT_TOKEN=your_bot_token_here
   ```

4. **Edit `config/config.yaml`:**
   ```yaml
   telegram:
     api_id: 123456
     api_hash: "your_api_hash_here"
     phone_number: "+1234567890"

   channels:
     - source: -1001234567890
       target: -1009876543210
       mirror_edits: true
       mirror_deletions: true

   bot_token: "your_bot_token_here"

   settings:
     forward_enabled: true
     download_media: true
     retry_attempts: 5
     retry_delay: 5
     flood_sleep_threshold: 60
     log_level: "INFO"
   ```

5. **Start the Bot:**
   ```bash
   python src/main.py
   ```
   *Note: On first launch, Telethon will request your login code (and 2FA password if enabled) sent to your Telegram app.*

---

### Option 2: Running with Docker & Docker Compose

1. **Build and start the container:**
   ```bash
   docker-compose up -d --build
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

---

## 🤖 Admin Bot Commands

If `BOT_TOKEN` is configured, send commands directly to your Bot in Telegram:

- `/start` — Welcome message and command list.
- `/status` — View current syncing state (Active/Paused), number of synced messages, and active pairs.
- `/pause` — Pause message cloning in real-time.
- `/resume` — Resume message cloning.
- `/addpair <source_id> <target_id>` — Dynamically add a new channel pair without restarting the bot.
- `/removepair <source_id>` — Remove a channel pair.

---

## ⚙️ Configuration Parameters (`config.yaml`)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `telegram.api_id` | int | - | Telegram API ID from my.telegram.org |
| `telegram.api_hash` | string | - | Telegram API Hash from my.telegram.org |
| `telegram.phone_number` | string | - | Phone number associated with account |
| `channels` | list | `[]` | List of channel pairs to clone |
| `forward_enabled` | bool | `true` | Try native message forwarding before fallback re-upload |
| `download_media` | bool | `true` | Download and re-upload media if forwarding is restricted |
| `retry_attempts` | int | `5` | Maximum retry attempts for failed requests |
| `retry_delay` | int | `5` | Initial delay (in seconds) for exponential backoff |
| `flood_sleep_threshold` | int | `60` | Auto-sleep threshold for FloodWait errors |

---

## 🔒 Security & Best Practices
- Never commit your `.env` file or `data/*.session` files to public repositories.
- Keep session files stored securely in the `data/` directory.

---

## 📄 License
This project is open-source and available under the MIT License.
