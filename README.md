# LeechxTool

A powerful Telegram bot to mirror and leech files from various sources to Telegram, Google Drive, and Rclone supported cloud storages.

## Features

- **Mirroring**: Download from direct links, Torrents, YouTube, Mega, Google Drive, and more to Google Drive or Rclone.
- **Leeching**: Upload downloaded files directly to Telegram.
- **Clone**: Clone files between Google Drive, Rclone, and other supported cloud storages.
- **Yt-Dlp Support**: Download videos from YouTube and supported sites with custom quality selection.
- **JDownloader Support**: Download files using JDownloader.
- **Torrents**: Support for public and private trackers, magnet links, and torrent files.
- **Search**: Built-in torrent search feature.
- **RSS Feed**: Automated downloading via RSS feeds.
- **User Management**: Authorize specific users or chats.
- **Bot Management**: Extensive control over bot settings via commands.

## Deployment

### Docker (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YourUsername/LeechxTool.git
    cd LeechxTool
    ```

2.  **Build the Docker image:**
    ```bash
    docker build -t leechxtool .
    ```

3.  **Run the container:**
    ```bash
    docker run -d \
      -e BOT_TOKEN="your_bot_token" \
      -e OWNER_ID="your_owner_id" \
      -e TELEGRAM_API="your_api_id" \
      -e TELEGRAM_HASH="your_api_hash" \
      -v $(pwd)/config.env:/usr/src/app/config.env \
      -v $(pwd)/accounts:/usr/src/app/accounts \
      leechxtool
    ```

### VPS / Local Machine

1.  **Install Dependencies:**
    -   Python 3.9+
    -   FFmpeg
    -   Aria2
    -   qBittorrent-nox
    -   7-Zip

2.  **Install Python Packages:**
    ```bash
    pip3 install -r requirements.txt
    ```

3.  **Configure:**
    -   Copy `config.env.sample` (if available) to `config.env` and fill in the values.
    -   Or simply create a `config.env` file.

4.  **Run:**
    ```bash
    bash start.sh
    ```

## Configuration (`config.env`)

| Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Your Telegram Bot Token. |
| `OWNER_ID` | Your Telegram User ID. |
| `TELEGRAM_API` | Your Telegram API ID. |
| `TELEGRAM_HASH` | Your Telegram API Hash. |
| `DATABASE_URL` | MongoDB Connection String. |
| `DOWNLOAD_DIR` | Directory for downloads (default: `/usr/src/app/downloads/`). |
| `GDRIVE_ID` | Google Drive Folder ID for uploads. |
| `RCLONE_PATH` | Rclone remote path (e.g., `remote:path`). |
| `DEFAULT_UPLOAD` | `gd` (Google Drive) or `rc` (Rclone). |
| `UPSTREAM_REPO` | Git URL for bot updates. |
| `FSUB_CHANNEL_ID` | Channel ID for forced subscription. |

*See `config.env` for the full list of optional configurations.*

## Commands

| Command | Description |
| :--- | :--- |
| `/start` | Start the bot. |
| `/mirror`, `/m` | Mirror file/link to Cloud. |
| `/leech`, `/l` | Leech file/link to Telegram. |
| `/ytdl`, `/y` | Download via Yt-Dlp to Cloud. |
| `/ytdlleech`, `/yl` | Download via Yt-Dlp to Telegram. |
| `/clone` | Clone Google Drive/Rclone files. |
| `/status` | Show status of current tasks. |
| `/cancel` | Cancel a task. |
| `/list` | Search files in Drive/Rclone. |
| `/search` | Search torrents. |
| `/authorize` | Authorize a chat or user. |
| `/unauthorize` | Revoke authorization. |
| `/users` | List authorized users. |
| `/log` | Get log file. |
| `/stats` | Show system and bot stats. |
| `/restart` | Restart the bot. |
| `/help` | Show help message. |

*Add your `CMD_SUFFIX` (if set) to these commands.*

## Credits

-   Based on various open-source leech bots.
