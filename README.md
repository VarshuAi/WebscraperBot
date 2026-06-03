# 🕷️ WebscraperBot

> **Simple, powerful and versatile** web scraping tool for Telegram. Extract any data from any website through a clean, menu-driven interface — no coding required.

![Version](https://img.shields.io/badge/Version-2.0-6366f1?style=for-the-badge)
![Patch](https://img.shields.io/badge/New%20Patch-Web%20Crawling-10b981?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-3b82f6?style=for-the-badge)

---

## 🛠️ Scraping Options

| # | Option | Method | Description |
|---|--------|--------|-------------|
| 1 | 📄 **Full Content** | Static | All visible text from the page |
| 2 | 🗂️ **HTML Data** | Static | Raw HTML source code |
| 3 | 🔗 **All Links** | Static | Every hyperlink found (absolute URLs) |
| 4 | 📝 **All Paragraphs** | Static | Every `<p>` tag text |
| 5 | 🖼️ **All Images** | Static | All image URLs (`img`, `og:image`, regex) |
| 6 | 🎵 **All Audio** | Static | Audio files (mp3, ogg, wav, aac, etc.) |
| 7 | 🎬 **All Video** | Static | Video files + YouTube embeds |
| 8 | 📑 **All PDFs** | Static | All PDF links |
| 9 | 🍪 **Cookies** | Playwright ✨ | All cookies after page load |
| 10 | 💾 **LocalStorage** | Playwright ✨ | JS localStorage key-value pairs |
| 11 | 🔎 **Metadata** | Static | Title, meta tags, OG tags, HTTP headers |
| 12 | 📸 **Screenshot** | Playwright ✨ | Full-page PNG screenshot |
| 13 | 🎥 **Web Recording** | Playwright ✨ | 15-second scroll session video |
| 14 | 🕸️ **Web Crawl** | Static | BFS crawler — entire site map |

> ✨ = requires headless browser (Playwright), takes 20–40s

---

## 🚀 Setup & Installation

### 1. Clone the repo
```bash
git clone https://github.com/VarshuAi/WebscraperBot.git
cd WebscraperBot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers
```bash
playwright install chromium
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env and set your BOT_TOKEN
```

### 5. Run the bot
```bash
python bot.py
```

---

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome menu |
| `/help` | Show help |
| `/url <url>` | Set URL via command |
| `/crawl <url> [depth] [max_pages]` | Quick crawl |
| `/visits` | Show your request count |

---

## 💬 Usage Flow

1. **Send a URL** → `https://example.com`
2. Bot shows the **14-option inline menu**
3. Tap an option → bot scrapes and returns results
4. Large results are auto-sent as **file downloads** (.txt / .json)
5. Send another URL anytime to change target

---

## 🕸️ Web Crawl Details

- **Algorithm**: BFS (Breadth-First Search)
- **Default**: Max 50 pages, depth 3
- **Scope**: Same-domain only (won't follow external links)
- **Output**: 
  - Live progress updates every 5 pages
  - Summary with stats
  - Full JSON report with all pages, links, and images

Custom crawl:
```
/crawl https://example.com 2 20
# depth=2, max_pages=20
```

---

## 📁 Project Structure

```
webscraper-bot/
├── bot.py           # Main bot (menus, session, dispatchers)
├── scraper.py       # All scraping logic (BS4 + Playwright + Crawler)
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Tech Stack

- **[pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)** — Telegram bot framework
- **[Requests](https://requests.readthedocs.io/)** — HTTP client
- **[BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)** + **lxml** — HTML parsing
- **[Playwright](https://playwright.dev/python/)** — Headless browser (Chromium)

---

## 📄 License

MIT — free to use, fork, and deploy.

---

Made with ❤️ by **[VarshuAi](https://github.com/VarshuAi)**
