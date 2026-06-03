"""
WebscraperBot — Main bot entry point
A powerful, menu-driven Telegram bot for web scraping.
"""

import os
import io
import json
import time
import asyncio
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile
)
from dotenv import load_dotenv

import scraper

# ─────────────────────────────────────────────────────────
#  Init
# ─────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN not set. Create a .env file with BOT_TOKEN=...')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# Per-user state: { user_id: { 'url': str, 'crawl_depth': int, 'crawl_pages': int } }
USER_STATE: dict[int, dict] = {}

VISITS: dict[int, int] = {}   # visit count per user

# ─────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────

MENU_EMOJI = {
    'full':        '📄',
    'html':        '🗂️',
    'links':       '🔗',
    'paragraphs':  '📝',
    'images':      '🖼️',
    'audio':       '🎵',
    'video':       '🎬',
    'pdfs':        '📑',
    'cookies':     '🍪',
    'localstorage':'💾',
    'metadata':    '🔎',
    'screenshot':  '📸',
    'recording':   '🎥',
    'crawl':       '🕸️',
}

def make_menu_kb(url_set: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    items = [
        ('full',        '📄 Full Content'),
        ('html',        '🗂️ HTML Data'),
        ('links',       '🔗 All Links'),
        ('paragraphs',  '📝 All Paragraphs'),
        ('images',      '🖼️ All Images'),
        ('audio',       '🎵 All Audio'),
        ('video',       '🎬 All Video'),
        ('pdfs',        '📑 All PDFs'),
        ('cookies',     '🍪 Cookies'),
        ('localstorage','💾 LocalStorage'),
        ('metadata',    '🔎 Metadata'),
        ('screenshot',  '📸 Screenshot ✨'),
        ('recording',   '🎥 Web Recording ✨'),
        ('crawl',       '🕸️ Web Crawl'),
    ]
    buttons = [InlineKeyboardButton(label, callback_data=f'scrape:{action}') for action, label in items]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton('🔄 Change URL', callback_data='change_url'))
    return kb


def short_url(url: str, max_len: int = 55) -> str:
    return url if len(url) <= max_len else url[:max_len - 3] + '...'


def send_as_file(chat_id: int, content: str, filename: str, caption: str = ''):
    """Send content as a .txt or .json file."""
    buf = io.BytesIO(content.encode('utf-8'))
    buf.name = filename
    bot.send_document(chat_id, InputFile(buf, filename), caption=caption)


def fmt_list(items: list[str], title: str, bullet: str = '•') -> str:
    if not items:
        return f'<b>{title}</b>\n<i>None found.</i>'
    lines = [f'<b>{title}</b> ({len(items)} found)\n']
    for i, item in enumerate(items[:200], 1):
        lines.append(f'{bullet} <code>{item}</code>')
    if len(items) > 200:
        lines.append(f'\n… and <b>{len(items)-200}</b> more.')
    return '\n'.join(lines)


def send_chunked(chat_id: int, text: str, parse_mode: str = 'HTML'):
    """Send long text in ≤4096-char Telegram chunks."""
    for i in range(0, len(text), 4000):
        bot.send_message(chat_id, text[i:i+4000], parse_mode=parse_mode)


def run_async(coro):
    """Run an async coroutine from a sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ─────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────

WELCOME = """
🕷️ <b>WebscraperBot</b> — Simple, Powerful &amp; Versatile

I can extract <b>any data</b> from any website:

📄 Full Content  🗂️ HTML  🔗 Links
📝 Paragraphs  🖼️ Images  🎵 Audio  🎬 Video
📑 PDFs  🍪 Cookies  💾 LocalStorage  🔎 Metadata
📸 Screenshot ✨  🎥 Recording ✨  🕸️ Web Crawl

<b>New Patch:</b> Web Crawling is now supported! 🎉

<b>To start, send me a URL:</b>
<code>https://example.com</code>
"""

@bot.message_handler(commands=['start', 'help'])
def cmd_start(msg):
    uid = msg.from_user.id
    VISITS[uid] = VISITS.get(uid, 0) + 1
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton('🌐 Send a URL to begin', callback_data='noop'))
    bot.send_message(msg.chat.id, WELCOME, reply_markup=kb)


# ─────────────────────────────────────────────────────────
#  URL input
# ─────────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text and (
    m.text.startswith('http://') or m.text.startswith('https://')
))
def handle_url(msg):
    uid = msg.from_user.id
    url = msg.text.strip()
    USER_STATE[uid] = {'url': url, 'crawl_depth': 3, 'crawl_pages': 50}
    VISITS[uid] = VISITS.get(uid, 0) + 1

    text = (
        f'✅ <b>URL set!</b>\n'
        f'🔗 <code>{short_url(url)}</code>\n\n'
        f'<b>Choose a scraping option:</b>'
    )
    bot.send_message(msg.chat.id, text, reply_markup=make_menu_kb(True))


@bot.message_handler(commands=['url'])
def cmd_url(msg):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, '❓ Usage: <code>/url https://example.com</code>')
        return
    fake_msg = msg
    fake_msg.text = parts[1]
    handle_url(fake_msg)


@bot.message_handler(commands=['visits'])
def cmd_visits(msg):
    uid = msg.from_user.id
    v = VISITS.get(uid, 0)
    bot.reply_to(msg, f'👁️ You\'ve made <b>{v}</b> visits/requests so far.')


@bot.message_handler(commands=['crawl'])
def cmd_crawl(msg):
    """Quick crawl: /crawl https://example.com [depth] [max_pages]"""
    parts = msg.text.split()
    if len(parts) < 2:
        bot.reply_to(msg, '❓ Usage: <code>/crawl https://example.com [depth] [max_pages]</code>')
        return
    uid = msg.from_user.id
    url = parts[1]
    depth = int(parts[2]) if len(parts) > 2 else 3
    max_pages = int(parts[3]) if len(parts) > 3 else 50
    USER_STATE[uid] = {'url': url, 'crawl_depth': depth, 'crawl_pages': max_pages}
    do_crawl(msg.chat.id, uid)


# ─────────────────────────────────────────────────────────
#  Inline button dispatcher
# ─────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith('scrape:'))
def cb_scrape(call):
    bot.answer_callback_query(call.id)
    action = call.data.split(':', 1)[1]
    uid = call.from_user.id
    cid = call.message.chat.id

    if uid not in USER_STATE or not USER_STATE[uid].get('url'):
        bot.send_message(cid, '⚠️ Please send me a URL first!')
        return

    url = USER_STATE[uid]['url']
    VISITS[uid] = VISITS.get(uid, 0) + 1

    # Dispatch
    if action == 'crawl':
        threading.Thread(target=do_crawl, args=(cid, uid), daemon=True).start()
    elif action in ('screenshot', 'recording', 'cookies', 'localstorage'):
        threading.Thread(target=do_playwright, args=(cid, uid, url, action), daemon=True).start()
    else:
        threading.Thread(target=do_static, args=(cid, uid, url, action), daemon=True).start()


@bot.callback_query_handler(func=lambda c: c.data == 'change_url')
def cb_change_url(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, '🔗 Send me the new URL:')


@bot.callback_query_handler(func=lambda c: c.data == 'noop')
def cb_noop(call):
    bot.answer_callback_query(call.id, 'Send a URL first!')


# ─────────────────────────────────────────────────────────
#  Static scraper runner
# ─────────────────────────────────────────────────────────

def do_static(chat_id: int, uid: int, url: str, action: str):
    emoji = MENU_EMOJI.get(action, '⚙️')
    status = bot.send_message(chat_id, f'{emoji} <i>Scraping…</i>')

    try:
        if action == 'full':
            result = scraper.full_content(url)
            if len(result) > 3500:
                send_as_file(chat_id, result, 'full_content.txt', f'📄 Full content of <code>{short_url(url)}</code>')
            else:
                send_chunked(chat_id, f'📄 <b>Full Content</b>\n<code>{short_url(url)}</code>\n\n{result}')

        elif action == 'html':
            result = scraper.html_data(url)
            send_as_file(chat_id, result, 'source.html', f'🗂️ HTML source of <code>{short_url(url)}</code>')

        elif action == 'links':
            links = scraper.all_links(url)
            text = fmt_list(links, '🔗 All Links')
            if len(text) > 3800:
                send_as_file(chat_id, '\n'.join(links), 'links.txt', f'🔗 {len(links)} links from <code>{short_url(url)}</code>')
            else:
                bot.send_message(chat_id, text)

        elif action == 'paragraphs':
            paras = scraper.all_paragraphs(url)
            joined = '\n\n'.join(paras)
            if len(joined) > 3500:
                send_as_file(chat_id, joined, 'paragraphs.txt', f'📝 {len(paras)} paragraphs from <code>{short_url(url)}</code>')
            else:
                send_chunked(chat_id, f'📝 <b>Paragraphs</b> ({len(paras)})\n\n{joined}')

        elif action == 'images':
            imgs = scraper.all_images(url)
            text = fmt_list(imgs, '🖼️ All Images')
            if len(text) > 3800:
                send_as_file(chat_id, '\n'.join(imgs), 'images.txt', f'🖼️ {len(imgs)} images from <code>{short_url(url)}</code>')
            else:
                bot.send_message(chat_id, text)

        elif action == 'audio':
            items = scraper.all_audio(url)
            text = fmt_list(items, '🎵 All Audio')
            if len(text) > 3800:
                send_as_file(chat_id, '\n'.join(items), 'audio.txt', f'🎵 {len(items)} audio from <code>{short_url(url)}</code>')
            else:
                bot.send_message(chat_id, text)

        elif action == 'video':
            items = scraper.all_video(url)
            text = fmt_list(items, '🎬 All Video')
            if len(text) > 3800:
                send_as_file(chat_id, '\n'.join(items), 'video.txt', f'🎬 {len(items)} videos from <code>{short_url(url)}</code>')
            else:
                bot.send_message(chat_id, text)

        elif action == 'pdfs':
            items = scraper.all_pdfs(url)
            text = fmt_list(items, '📑 All PDFs')
            if len(text) > 3800:
                send_as_file(chat_id, '\n'.join(items), 'pdfs.txt', f'📑 {len(items)} PDFs from <code>{short_url(url)}</code>')
            else:
                bot.send_message(chat_id, text)

        elif action == 'metadata':
            meta = scraper.metadata(url)
            lines = [f'🔎 <b>Metadata</b> — <code>{short_url(url)}</code>\n']
            for k, v in meta.items():
                if isinstance(v, list):
                    v = ', '.join(v) if v else '—'
                lines.append(f'<b>{k}:</b> <code>{str(v)[:120] if v else "—"}</code>')
            text = '\n'.join(lines)
            if len(text) > 3800:
                send_as_file(chat_id, json.dumps(meta, indent=2, ensure_ascii=False), 'metadata.json',
                             f'🔎 Metadata from <code>{short_url(url)}</code>')
            else:
                bot.send_message(chat_id, text)

        bot.delete_message(chat_id, status.message_id)
        # Re-show menu
        bot.send_message(chat_id, '✅ <b>Done!</b> Choose another option:', reply_markup=make_menu_kb(True))

    except Exception as e:
        bot.edit_message_text(f'❌ <b>Error:</b> <code>{e}</code>', chat_id, status.message_id)
        traceback.print_exc()


# ─────────────────────────────────────────────────────────
#  Playwright runner
# ─────────────────────────────────────────────────────────

def do_playwright(chat_id: int, uid: int, url: str, action: str):
    emoji = MENU_EMOJI.get(action, '⚙️')
    status = bot.send_message(chat_id, f'{emoji} <i>Launching browser… This may take 20–40s.</i>')

    try:
        if action == 'screenshot':
            img_bytes = run_async(scraper.screenshot(url))
            bot.delete_message(chat_id, status.message_id)
            buf = io.BytesIO(img_bytes)
            buf.name = 'screenshot.png'
            bot.send_photo(chat_id, InputFile(buf, 'screenshot.png'),
                           caption=f'📸 <b>Screenshot</b>\n<code>{short_url(url)}</code>')

        elif action == 'recording':
            bot.edit_message_text(f'🎥 <i>Recording scroll session (~15s)…</i>', chat_id, status.message_id)
            video_path = run_async(scraper.recording(url))
            bot.delete_message(chat_id, status.message_id)
            with open(video_path, 'rb') as vf:
                bot.send_document(chat_id, InputFile(vf, 'recording.webm'),
                                  caption=f'🎥 <b>Recording</b>\n<code>{short_url(url)}</code>')
            try:
                os.remove(video_path)
            except Exception:
                pass

        elif action == 'cookies':
            ck = run_async(scraper.cookies(url))
            if ck:
                text_lines = [f'🍪 <b>Cookies</b> ({len(ck)} found)\n<code>{short_url(url)}</code>\n']
                for c in ck:
                    text_lines.append(
                        f'▸ <b>{c.get("name","?")}</b>: <code>{str(c.get("value",""))[:80]}</code>\n'
                        f'  domain: <i>{c.get("domain","")}</i>  path: <i>{c.get("path","")}</i>'
                    )
                text = '\n'.join(text_lines)
                if len(text) > 3800:
                    send_as_file(chat_id,
                                 json.dumps(ck, indent=2, ensure_ascii=False),
                                 'cookies.json',
                                 f'🍪 {len(ck)} cookies from <code>{short_url(url)}</code>')
                else:
                    bot.send_message(chat_id, text)
            else:
                bot.send_message(chat_id, '🍪 <i>No cookies found on this page.</i>')
            bot.delete_message(chat_id, status.message_id)

        elif action == 'localstorage':
            ls = run_async(scraper.local_storage(url))
            if ls:
                text_lines = [f'💾 <b>LocalStorage</b> ({len(ls)} keys)\n<code>{short_url(url)}</code>\n']
                for k, v in ls.items():
                    text_lines.append(f'▸ <b>{k}</b>: <code>{str(v)[:120]}</code>')
                text = '\n'.join(text_lines)
                if len(text) > 3800:
                    send_as_file(chat_id,
                                 json.dumps(ls, indent=2, ensure_ascii=False),
                                 'localstorage.json',
                                 f'💾 LocalStorage from <code>{short_url(url)}</code>')
                else:
                    bot.send_message(chat_id, text)
            else:
                bot.send_message(chat_id, '💾 <i>LocalStorage is empty or not supported.</i>')
            bot.delete_message(chat_id, status.message_id)

        bot.send_message(chat_id, '✅ <b>Done!</b> Choose another option:', reply_markup=make_menu_kb(True))

    except Exception as e:
        bot.edit_message_text(f'❌ <b>Error:</b> <code>{e}</code>', chat_id, status.message_id)
        traceback.print_exc()


# ─────────────────────────────────────────────────────────
#  Web Crawler runner
# ─────────────────────────────────────────────────────────

def do_crawl(chat_id: int, uid: int):
    state = USER_STATE.get(uid, {})
    url       = state.get('url', '')
    max_depth = state.get('crawl_depth', 3)
    max_pages = state.get('crawl_pages', 50)

    if not url:
        bot.send_message(chat_id, '⚠️ No URL set. Send a URL first.')
        return

    status = bot.send_message(chat_id,
        f'🕸️ <b>Web Crawling…</b>\n'
        f'🔗 <code>{short_url(url)}</code>\n'
        f'📊 Max pages: <b>{max_pages}</b>  |  Depth: <b>{max_depth}</b>\n\n'
        f'<i>This may take a while…</i>'
    )
    visited_count = [0]

    def on_page(count, page_url, title):
        visited_count[0] = count
        if count % 5 == 0:  # update every 5 pages
            try:
                bot.edit_message_text(
                    f'🕸️ <b>Crawling…</b>  [{count}/{max_pages}]\n'
                    f'📄 <i>{title[:50]}</i>\n'
                    f'🔗 <code>{short_url(page_url, 45)}</code>',
                    chat_id, status.message_id
                )
            except Exception:
                pass

    try:
        crawler = scraper.WebCrawler(max_pages=max_pages, max_depth=max_depth)
        result = crawler.crawl(url, on_page=on_page)

        pages   = result['pages']
        stats   = result['stats']
        links   = result['all_links']
        images  = result['all_images']

        # Summary message
        summary = (
            f'🕸️ <b>Crawl Complete!</b>\n\n'
            f'🔗 Start URL: <code>{short_url(url)}</code>\n'
            f'📄 Pages crawled: <b>{stats["total_pages_crawled"]}</b>\n'
            f'✅ Successful: <b>{stats["successful"]}</b>\n'
            f'❌ Failed: <b>{stats["failed"]}</b>\n'
            f'🔗 Total links found: <b>{stats["total_links"]}</b>\n'
            f'🖼️ Total images found: <b>{stats["total_images"]}</b>\n'
        )
        bot.edit_message_text(summary, chat_id, status.message_id)

        # Pages report
        pages_text = '📋 <b>Crawled Pages:</b>\n\n'
        for i, p in enumerate(pages, 1):
            err = p.get('error')
            st  = p.get('status', 0)
            kb  = p.get('size_kb', '')
            d   = p.get('depth', 0)
            title = p.get('title', p['url'])[:60]
            if err:
                pages_text += f'{i}. ❌ [{d}] {title}\n   <code>{p["url"][:70]}</code>\n   <i>{err[:50]}</i>\n\n'
            else:
                pages_text += f'{i}. ✅ [{d}] {title}\n   <code>{p["url"][:70]}</code>  ({st}) {kb}KB\n\n'

        if len(pages_text) > 3800:
            send_as_file(chat_id, pages_text.replace('<b>','').replace('</b>','')
                         .replace('<code>','').replace('</code>','')
                         .replace('<i>','').replace('</i>','')
                         .replace('<br>','\n'),
                         'crawl_pages.txt',
                         f'📋 Pages crawled from <code>{short_url(url)}</code>')
        else:
            bot.send_message(chat_id, pages_text)

        # Full JSON report as file
        report = {
            'crawl_url': url,
            'crawl_time': datetime.utcnow().isoformat(),
            'settings': {'max_depth': max_depth, 'max_pages': max_pages},
            'stats': stats,
            'pages': pages,
            'all_links': links,
            'all_images': images,
        }
        send_as_file(chat_id, json.dumps(report, indent=2, ensure_ascii=False),
                     'crawl_report.json', f'📊 Full crawl report for <code>{short_url(url)}</code>')

        bot.send_message(chat_id, '✅ <b>Crawl complete!</b> Choose another option:',
                         reply_markup=make_menu_kb(True))

    except Exception as e:
        bot.edit_message_text(f'❌ <b>Crawl error:</b> <code>{e}</code>', chat_id, status.message_id)
        traceback.print_exc()


# ─────────────────────────────────────────────────────────
#  Fallback handler
# ─────────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: True)
def fallback(msg):
    bot.reply_to(msg,
        '❓ Send me a URL to scrape (e.g. <code>https://example.com</code>) '
        'or use /start to see the help menu.'
    )


# ─────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('🕷️  WebscraperBot is running...')
    print('⚡  Polling for messages...')
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
