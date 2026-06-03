import os
import re
import json
import asyncio
import tempfile
import urllib.parse
from collections import deque
from io import BytesIO
from typing import Optional

import requests
from bs4 import BeautifulSoup


# ─────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _abs(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def _get(url: str, timeout: int = 15) -> requests.Response:
    s = _session()
    return s.get(url, timeout=timeout, allow_redirects=True)


def _soup(url: str) -> tuple[requests.Response, BeautifulSoup]:
    r = _get(url)
    soup = BeautifulSoup(r.text, 'lxml')
    return r, soup


# ─────────────────────────────────────────
#  Static scraping (no JS needed)
# ─────────────────────────────────────────

def full_content(url: str) -> str:
    """Extract all visible text from the page."""
    _, soup = _soup(url)
    for tag in soup(['script', 'style', 'noscript', 'head']):
        tag.decompose()
    text = soup.get_text(separator='\n', strip=True)
    # Collapse blank lines
    lines = [l for l in text.splitlines() if l.strip()]
    return '\n'.join(lines)


def html_data(url: str) -> str:
    """Return raw HTML source."""
    r = _get(url)
    return r.text


def all_links(url: str) -> list[str]:
    """All hyperlinks on the page (absolute URLs)."""
    _, soup = _soup(url)
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            links.add(_abs(url, href))
    return sorted(links)


def all_paragraphs(url: str) -> list[str]:
    """All non-empty <p> tag texts."""
    _, soup = _soup(url)
    return [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]


def all_images(url: str) -> list[str]:
    """All image URLs (img[src], source[src], og:image)."""
    r, soup = _soup(url)
    imgs = set()
    for img in soup.find_all('img', src=True):
        src = img.get('src', '') or img.get('data-src', '')
        if src and not src.startswith('data:'):
            imgs.add(_abs(url, src))
    for source in soup.find_all('source', src=True):
        imgs.add(_abs(url, source['src']))
    # OG image
    og = soup.find('meta', property='og:image')
    if og and og.get('content'):
        imgs.add(_abs(url, og['content']))
    # regex scan for missed ones
    for m in re.findall(r'https?://[^\s"\'<>]+\.(?:png|jpg|jpeg|gif|webp|svg|ico)', r.text, re.I):
        imgs.add(m)
    return sorted(imgs)


def all_audio(url: str) -> list[str]:
    """All audio file URLs."""
    r, soup = _soup(url)
    audio = set()
    for tag in soup.find_all(['audio', 'source']):
        src = tag.get('src', '')
        if src:
            audio.add(_abs(url, src))
    for m in re.findall(
        r'https?://[^\s"\'<>]+\.(?:mp3|ogg|wav|aac|flac|m4a|opus|weba)',
        r.text, re.I
    ):
        audio.add(m)
    return sorted(audio)


def all_video(url: str) -> list[str]:
    """All video file URLs."""
    r, soup = _soup(url)
    videos = set()
    for tag in soup.find_all(['video', 'source', 'iframe']):
        src = tag.get('src', '') or tag.get('data-src', '')
        if src:
            videos.add(_abs(url, src))
    for m in re.findall(
        r'https?://[^\s"\'<>]+\.(?:mp4|webm|ogv|avi|mov|mkv|m3u8|ts)',
        r.text, re.I
    ):
        videos.add(m)
    # YouTube embeds
    for m in re.findall(r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})', r.text):
        videos.add(f'https://www.youtube.com/watch?v={m}')
    return sorted(videos)


def all_pdfs(url: str) -> list[str]:
    """All PDF file links."""
    r, soup = _soup(url)
    pdfs = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.lower().endswith('.pdf'):
            pdfs.add(_abs(url, href))
    for m in re.findall(r'https?://[^\s"\'<>]+\.pdf(?:\?[^\s"\'<>]*)?', r.text, re.I):
        pdfs.add(m)
    return sorted(pdfs)


def metadata(url: str) -> dict:
    """Extract page metadata: title, meta tags, OG tags, HTTP headers."""
    r, soup = _soup(url)
    meta: dict = {
        'url': url,
        'final_url': r.url,
        'status_code': r.status_code,
        'content_type': r.headers.get('Content-Type', ''),
        'server': r.headers.get('Server', ''),
        'x_powered_by': r.headers.get('X-Powered-By', ''),
        'content_length': r.headers.get('Content-Length', ''),
        'charset': r.encoding or '',
        'title': (soup.title.string.strip() if soup.title and soup.title.string else ''),
        'description': '',
        'keywords': '',
        'author': '',
        'robots': '',
        'og_title': '',
        'og_description': '',
        'og_image': '',
        'og_type': '',
        'og_site_name': '',
        'twitter_card': '',
        'canonical': '',
        'h1_tags': [h.get_text(strip=True) for h in soup.find_all('h1')],
        'lang': soup.html.get('lang', '') if soup.html else '',
        'scripts_count': len(soup.find_all('script')),
        'stylesheets_count': len(soup.find_all('link', rel=lambda v: v and 'stylesheet' in v)),
        'images_count': len(soup.find_all('img')),
        'links_count': len(soup.find_all('a', href=True)),
    }
    for tag in soup.find_all('meta'):
        n = tag.get('name', '').lower()
        p = tag.get('property', '').lower()
        c = tag.get('content', '')
        if n == 'description':       meta['description'] = c
        elif n == 'keywords':        meta['keywords'] = c
        elif n == 'author':          meta['author'] = c
        elif n == 'robots':          meta['robots'] = c
        elif n == 'twitter:card':    meta['twitter_card'] = c
        if p == 'og:title':          meta['og_title'] = c
        elif p == 'og:description':  meta['og_description'] = c
        elif p == 'og:image':        meta['og_image'] = c
        elif p == 'og:type':         meta['og_type'] = c
        elif p == 'og:site_name':    meta['og_site_name'] = c
    canon = soup.find('link', rel='canonical')
    if canon:
        meta['canonical'] = canon.get('href', '')
    return meta


# ─────────────────────────────────────────
#  Playwright-based (JS rendering required)
# ─────────────────────────────────────────

async def screenshot(url: str) -> bytes:
    """Full-page screenshot as PNG bytes."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent=HEADERS['User-Agent'],
        )
        page = await context.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30_000)
        await page.wait_for_timeout(1500)  # let animations settle
        img = await page.screenshot(full_page=True, type='png')
        await browser.close()
    return img


async def recording(url: str) -> str:
    """
    Record a 10-second scroll session.
    Returns path to the .webm video file.
    """
    from playwright.async_api import async_playwright
    tmpdir = tempfile.mkdtemp()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent=HEADERS['User-Agent'],
            record_video_dir=tmpdir,
            record_video_size={'width': 1366, 'height': 768},
        )
        page = await context.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30_000)
        await page.wait_for_timeout(2000)
        # Slow scroll down
        for i in range(10):
            await page.evaluate(f'window.scrollBy(0, {i * 150})')
            await page.wait_for_timeout(400)
        await page.wait_for_timeout(1000)
        video_path = await page.video.path()
        await context.close()
        await browser.close()
    return video_path


async def cookies(url: str) -> list[dict]:
    """Return all cookies after page load."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=HEADERS['User-Agent'])
        page = await context.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30_000)
        ck = await context.cookies()
        await browser.close()
    return ck


async def local_storage(url: str) -> dict:
    """Return localStorage key-value pairs after page load."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=HEADERS['User-Agent'])
        page = await context.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30_000)
        storage = await page.evaluate(
            '''() => {
                const s = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i);
                    s[k] = localStorage.getItem(k);
                }
                return s;
            }'''
        )
        await browser.close()
    return storage or {}


# ─────────────────────────────────────────
#  Web Crawler
# ─────────────────────────────────────────

class WebCrawler:
    def __init__(self, max_pages: int = 50, max_depth: int = 3):
        self.max_pages = max_pages
        self.max_depth = max_depth

    def crawl(self, start_url: str, on_page=None) -> dict:
        """
        BFS crawl staying within the same domain.
        on_page(visited_count, url, title) → called after each page.
        Returns {'pages': [...], 'all_links': [...], 'all_images': [...]}
        """
        parsed_start = urllib.parse.urlparse(start_url)
        base_domain = parsed_start.netloc

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start_url, 0)])
        pages: list[dict] = []
        all_links_set: set[str] = set()
        all_images_set: set[str] = set()

        s = _session()

        while queue and len(visited) < self.max_pages:
            url, depth = queue.popleft()
            if url in visited or depth > self.max_depth:
                continue
            visited.add(url)

            try:
                r = s.get(url, timeout=10, allow_redirects=True)
                soup = BeautifulSoup(r.text, 'lxml')
                title = soup.title.string.strip() if soup.title and soup.title.string else url

                pages.append({
                    'url': url,
                    'title': title,
                    'status': r.status_code,
                    'depth': depth,
                    'size_kb': round(len(r.content) / 1024, 1),
                })

                if on_page:
                    on_page(len(visited), url, title)

                # Collect links + enqueue same-domain ones
                for a in soup.find_all('a', href=True):
                    href = _abs(url, a['href'])
                    parsed = urllib.parse.urlparse(href)
                    all_links_set.add(href)
                    if parsed.netloc == base_domain and href not in visited:
                        queue.append((href, depth + 1))

                # Collect images
                for img in soup.find_all('img', src=True):
                    src = img.get('src') or img.get('data-src', '')
                    if src and not src.startswith('data:'):
                        all_images_set.add(_abs(url, src))

            except Exception as exc:
                pages.append({'url': url, 'error': str(exc), 'depth': depth, 'status': 0})

        return {
            'pages': pages,
            'all_links': sorted(all_links_set),
            'all_images': sorted(all_images_set),
            'stats': {
                'total_pages_crawled': len(pages),
                'successful': sum(1 for p in pages if p.get('status', 0) == 200),
                'failed': sum(1 for p in pages if 'error' in p),
                'total_links': len(all_links_set),
                'total_images': len(all_images_set),
            }
        }
