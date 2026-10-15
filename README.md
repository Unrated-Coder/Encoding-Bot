<div align="center">
  <img src="https://prod.assets.earlygamecdn.com/images/Chisa.jpg?transform=Banner+Webp" alt="VideoEncoder Bot" width="100%">

  # 🎬 All-in-One Advanced Video Processing Engine

  <p>
    <b>An all-in-one Telegram bot for encoding, renaming, stream mapping, metadata injection, and thumbnail embedding in a single FFmpeg pass.</b><br>
    <i>Built with Python (Pyrofork), FFmpeg, Asyncio, and MongoDB (Motor).</i>
  </p>

  <p>
    <a href="https://t.me/Unrated_Coder"><img src="https://img.shields.io/badge/Channel-Unrated Coder-blue?style=for-the-badge&logo=telegram"></a>
    <a href="https://t.me/Og_Luffytaro"><img src="https://img.shields.io/badge/Developer-Luffytaro-blue?style=for-the-badge&logo=telegram"></a>
    <a href="https://github.com/Unrated-Coder/Encoding-Bot"><img src="https://img.shields.io/badge/Language-Python-green?style=for-the-badge&logo=python"></a>
  </p>
</div>

---

## ✨ Features

### 🚀 Unified Processing Dashboard
* **Interactive Control Panel:** Configure Encoding, Renaming, Custom Metadata, Thumbnails, and Audio/Sub Streams interactively before launching execution.
* **Single-Pass FFmpeg Pass:** Combines video encoding, scale filtering, stream mapping, metadata injection (`-metadata`, `-map_metadata -1`), and container thumbnail embedding into ONE FFmpeg pass for maximum speed and minimum CPU overhead.

### 🎥 Video Encoding Settings
* **Codecs:** Choose between **H.264 (x264)** and **H.265 (HEVC)**.
* **Quality & Presets:** Custom **CRF** (14 to 32) and Presets (`ultrafast` to `slow`).
* **Resolution Scaling:** Scale to 1080p, 720p, 576p, 480p, or maintain original scale (`OG`).
* **Audio Codecs:** Re-encode to AAC, AC3, OPUS, ALAC, Vorbis, or Copy.

### ✏️ Custom File Renamer
* **Placeholder Support:** `{filename}`, `{resolution}`, `{codec}`, `{quality}`, `{ext}`.
* **OS Sanitization:** Auto-cleans invalid characters for Linux/Windows file systems.

### 🏷 Custom Metadata Injection
* **Container Metadata:** Custom Video Title, Author, Copyright, and Audio Stream Titles.
* **Clear Metadata:** Option to strip original metadata (`-map_metadata -1`).

### 🖼 Personal Custom Thumbnails
* **Mongo-backed Thumbnails:** Permanent custom thumbnail storage per user via MongoDB Motor.
* **Task Modes:** Toggle between `CUSTOM`, `FRAME`, `DEFAULT`, or `NONE` per task.

---

## 🤖 Commands List

| Command | Description |
| :--- | :--- |
| `/start` | Check bot status. |
| `/help` | Display help menu. |
| `/dl` | Process Telegram file (reply or attached video). |
| `/ddl [url]` | Download & process direct link. |
| `/setthumb` | Set custom thumbnail (reply to photo or attach photo). |
| `/viewthumb` or `/thumb` | View current custom thumbnail. |
| `/delthumb` | Delete custom thumbnail. |
| `/settings` | Manage user default encoding settings. |
| `/status` | View server statistics and task queues. |

---

## ⚙️ Configuration

Configure via environment variables or a `config.env` file:

* `API_ID` & `API_HASH` — Telegram API credentials (my.telegram.org)
* `BOT_TOKEN` — Bot token from @BotFather
* `MONGO_URI` — MongoDB Connection String (Default: `mongodb://localhost:27017/VideoEncoder`)
* `OWNER_ID` — Telegram User ID of owner
* `SUDO_USERS` — Admin User IDs
* `LOG_CHANNEL` — Channel ID for logs
* `DOWNLOAD_DIR` — Downloads folder (Default: `downloads`)
* `ENCODE_DIR` — Output folder (Default: `encode`)

---

## 🐳 Docker Compose Deployment

1. Install Docker Engine and the Docker Compose plugin on your server.
2. Copy the example environment file and add your Telegram credentials:

   ```bash
   cp .env.example .env
   nano .env
   ```

   Set `API_ID`, `API_HASH`, `BOT_TOKEN`, and `OWNER_ID`. Keep `.env` private and never commit it.
3. Build and start the bot and MongoDB:

   ```bash
   docker compose up -d --build
   ```
4. View logs or stop the stack:

   ```bash
   docker compose logs -f bot
   docker compose down
   ```

MongoDB data, downloaded files, encoded output, and bot session files are stored in named Docker volumes and survive container recreation. `docker compose down -v` deletes these volumes and their data.

The Compose setup uses the included MongoDB service. If using MongoDB Atlas or an external server, set `MONGO_URI` in `.env` to its connection string; ensure the database is reachable from the Docker host/container. The bot container waits for MongoDB's health check before starting.

## 🚀 Execution Options

Run the bot easily using any entry point:

```bash
# Option 1: Module execution
python3 -m VideoEncoder

# Option 2: Direct script entry points
python3 main.py
python3 bot.py
python3 app.py
```
### Base Repo ~ https://github.com/abhinai2244/Encoding-Bot.git
