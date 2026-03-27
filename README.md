<h1 align="center">
  <img src="https://files.catbox.moe/58gf6k.jpg" alt="LeechxTool Logo" width="200"><br>
  <b>LeechxTool</b>
</h1>

<p align="center">
  <b>A highly advanced, feature-rich Telegram Bot to Mirror & Leech files from Torrents, Direct Links, Google Drive, Rclone, YouTube, and Mega.</b><br>
  <i>Built with headless Cloudflare Bypassing, Vercel Streaming, and Native FFMPEG Merging.</i>
</p>

---

## 🌟 Key Features

### 🚀 Core Downloading & Uploading
*   **Leech & Mirror:** Download from virtually anywhere (Direct Links, Torrents, Magnets, Mega.nz, YouTube) and upload natively to Telegram (`/leech`), Google Drive (`/mirror`), or any `Rclone` supported cloud storage provider.
*   **Yt-Dlp Integration:** Native support for downloading playlists, channels, or videos from thousands of supported websites with full quality selection.
*   **qBittorrent & Aria2c:** Highly optimized multi-threaded downloading for maximum speed, backed by built-in Torrent Searching.
*   **MEGAcmd Integration:** Native, ultra-fast `mega.nz` folder and file downloading using official MEGAcmd binaries, avoiding the slow, broken python API wrappers.

### 🎭 Custom Bypass & Scraping
*   **Headless Selenium Bypasser:** Built-in Chrome WebDriver integration perfectly configured to intercept and bypass **Cloudflare-protected anime sites** (e.g., `rareanimes.app`, `codedew.com`, `swift.multiquality.click`). Send a link, and the bot will autonomously resolve the iframe and download the streams concurrently.
*   **Direct Link Generators:** Automatic bypass support for dozens of URL shorteners and ad-walls.

### 🎬 Interactive Video Tools (`-vt`)
*   **Multi-File Merging:** Send the `-vt` flag to interactively add multiple files. Combine multiple `Video + Audio` tracks or Hardsub `Video + Subtitles` (.srt/.ass) directly inside Telegram.
*   **Editing:** Extract Audio, Trim specific durations, Compress videos, Sync Subtitles, and Watermark media seamlessly via `ffmpeg`.
*   **Custom Thumbnails:** Upload any photo with `-s thumb` or via `/uset` to set a persistent custom thumbnail for all your Telegram uploads.

### 🌐 Vercel Web Stream Player (`vid_stream`)
*   **Native Vercel Integration:** Toggle `Vid_Stream` to ON in your video tools menu. The bot will automatically encrypt your file URLs into a secure Base64 JSON payload, ping your custom Vercel REST API (`VERCEL_URL`), and generate beautiful **Stream** and **Download** web player links embedded perfectly in the final Telegram upload message.

### 👑 Premium User & Group Chat Management
*   **Premium Groups:** Grant premium access to entire groups using `/premiumgc` and revoke it with `/offpremiumgc`. All members in a premium chat automatically bypass the bot's size and daily download limits.
*   **User Controls:** Grant individual premium status, ban users, and authorize specific chats dynamically without restarting the bot.

---

## 🛠️ Deployment

### 🐳 Docker (Highly Recommended)

The bot utilizes a custom base image (`mysterysd/wzmlx:v3`) which comes pre-installed with crucial binaries like `mega-get`, `ffmpeg`, `aria2c`, and Chrome for headless Selenium.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YourUsername/LeechxTool.git
   cd LeechxTool
   ```
2. **Fill in the Configuration:**
   Rename `Config.env` (if sample) or edit the existing one with your API credentials.
3. **Deploy via Docker Compose:**
   ```bash
   docker-compose up -d
   ```

### ☁️ VPS / Heroku (Manual Installation)

1. **Install System Dependencies:**
   - Python 3.10+
   - FFmpeg, Aria2, qBittorrent-nox
   - Google Chrome (Stable) & ChromeDriver
2. **Install Python Packages:**
   ```bash
   pip3 install -r requirements.txt
   ```
3. **Run the Bot:**
   ```bash
   bash start.sh
   ```
   *(Note: The `start.sh` file includes dynamic pulling from the UPSTREAM_REPO to ensure your code is always up to date.)*

---

## ⚙️ Essential Configuration (`Config.env`)

| Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Your Telegram Bot Token from [@BotFather](https://t.me/BotFather). |
| `OWNER_ID` | Your Telegram User ID. |
| `TELEGRAM_API` | Your Telegram API ID from `my.telegram.org`. |
| `TELEGRAM_HASH` | Your Telegram API Hash from `my.telegram.org`. |
| `DATABASE_URL` | MongoDB Connection String (Required for saving settings/users). |
| `VERCEL_URL` | Your Vercel Web Streaming Player URL (e.g., `https://vercel-steam-mod.vercel.app`). |
| `VERCEL_API` | Your secret Vercel Bearer token. |
| `MEGA_LIMIT` | Limit in GBs for downloading from Mega.nz. |
| `NONPREMIUM_LIMIT`| Default GB limit for standard users (Premium users bypass this). |
| `UPSTREAM_REPO` | Git URL for automatic bot updates on reboot. |

*(All variables can be securely viewed and edited live in Telegram via the `/botset` command by the Owner).*

---

## 📜 Command Reference

| Command | Alias | Description |
| :--- | :--- | :--- |
| `/leech` | `/l` | Leech file/link natively to Telegram. |
| `/mirror` | `/m` | Mirror file/link to Google Drive / Rclone. |
| `/ytdl` | `/y` | Download via Yt-Dlp to Cloud. |
| `/ytdlleech` | `/yl` | Download via Yt-Dlp to Telegram. |
| `/clone` | | Clone Google Drive/Rclone files. |
| `/bypass` | | Bypass Cloudflare or Ad-links & start download immediately. |
| `/status` | | Show live ASCII status of active downloads. |
| `/cancel` | | Cancel a specific running task. |
| `/usersettings` | `/uset`, `/us` | User specific settings (Thumbnail, Prefix, Daily limits). |
| `/botsettings` | `/bset`, `/bs` | Owner settings to change `Config.env` variables dynamically. |
| `/premiumgc` | `/primiumgc` | Grant a group chat premium limits bypass. |
| `/offpremiumgc` | `/offprimiumgc` | Revoke a group chat's premium status. |
| `/stats` | | Show Server CPU, RAM, Disk, and Bot uptime statistics. |
| `/restart` | | Restart the bot and apply UPSTREAM updates. |

*(To use video tools, simply reply to a message or attach the link with the `-vt` argument: e.g., `/l <link> -vt`)*

---

<p align="center">
  <b>‣ ᴘᴏᴡᴇʀᴇᴅ ʙʏ: Sᴇᴄʀᴇᴄᴛ 𝐁ᴏᴛ 𝐔ᴘᴅᴀᴛᴇs</b>
</p>
