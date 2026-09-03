"""
Anti-detection & human-simulation utilities. Production v2.
"""

import asyncio
import csv
import logging
import logging.handlers
import math
import random
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import config as cfg


# ── Logger ───────────────────────────────────────────────────
def setup_logger() -> logging.Logger:
    log = logging.getLogger("dice_bot")
    log.setLevel(logging.DEBUG if cfg.DEBUG else logging.INFO)

    if log.handlers:
        return log

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if cfg.DEBUG else logging.INFO)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    # Rotating file — 5MB max, keep 5 backups
    fh = logging.handlers.RotatingFileHandler(
        cfg.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    return log


logger = setup_logger()


# ── Delays ───────────────────────────────────────────────────
async def human_delay(lo: float = None, hi: float = None):
    lo = lo or cfg.MIN_DELAY
    hi = hi or cfg.MAX_DELAY
    delay = random.triangular(lo, hi, lo + (hi - lo) * 0.3)
    await asyncio.sleep(delay)


async def short_delay():
    lo, hi = cfg.PAGE_LOAD_WAIT
    await asyncio.sleep(random.uniform(lo, hi))


async def micro_delay():
    await asyncio.sleep(random.uniform(0.1, 0.3))


async def break_delay():
    lo, hi = cfg.BREAK_DURATION
    delay = random.uniform(lo, hi)
    logger.info(f"Taking a break for {delay:.0f}s to avoid detection...")
    await asyncio.sleep(delay)


# ── Bezier Curve Mouse Movement ──────────────────────────────
def _bezier_point(t: float, p0, p1, p2, p3):
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def _generate_bezier_path(start, end, steps=None):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.sqrt(dx**2 + dy**2)
    steps = steps or max(15, int(dist / 8))

    cp1 = (
        start[0] + dx * random.uniform(0.1, 0.4) + random.uniform(-50, 50),
        start[1] + dy * random.uniform(0.1, 0.4) + random.uniform(-50, 50),
    )
    cp2 = (
        start[0] + dx * random.uniform(0.6, 0.9) + random.uniform(-50, 50),
        start[1] + dy * random.uniform(0.6, 0.9) + random.uniform(-50, 50),
    )

    points = []
    for i in range(steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)  # ease-in-out
        x, y = _bezier_point(t, start, cp1, cp2, end)
        x += random.uniform(-1, 1)
        y += random.uniform(-1, 1)
        points.append((int(x), int(y)))
    return points


async def bezier_mouse_move(page, x: int, y: int):
    try:
        current = await page.evaluate("() => ({x: window._mouseX || 0, y: window._mouseY || 0})")
        start = (current.get("x", random.randint(100, 500)), current.get("y", random.randint(100, 400)))
    except Exception:
        start = (random.randint(100, 500), random.randint(100, 400))

    path = _generate_bezier_path(start, (x, y))
    for px, py in path:
        await page.mouse.move(px, py)
        await asyncio.sleep(random.uniform(0.003, 0.012))

    await page.evaluate(f"() => {{ window._mouseX = {x}; window._mouseY = {y}; }}")


async def random_mouse_wander(page):
    vp = page.viewport_size
    if not vp:
        return
    x = random.randint(100, vp["width"] - 100)
    y = random.randint(100, vp["height"] - 100)
    await bezier_mouse_move(page, x, y)
    await asyncio.sleep(random.uniform(0.1, 0.4))


# ── Human-like Typing ────────────────────────────────────────
async def human_type(locator, text: str):
    await locator.click()
    await asyncio.sleep(random.uniform(0.2, 0.5))

    lo, hi = cfg.TYPING_SPEED
    for char in text:
        delay = random.randint(lo, hi)
        if random.random() < 0.04:
            await asyncio.sleep(random.uniform(0.2, 0.8))
        if random.random() < 0.1:
            delay = max(20, delay // 2)
        await locator.press(char, delay=delay)

    await asyncio.sleep(random.uniform(0.1, 0.3))


# ── Scrolling ────────────────────────────────────────────────
async def human_scroll(page, direction: str = "down", amount: int = None):
    if amount is None:
        amount = random.randint(150, 400)
    sign = 1 if direction == "down" else -1
    chunks = random.randint(2, 4)
    for _ in range(chunks):
        chunk = amount // chunks + random.randint(-20, 20)
        await page.mouse.wheel(0, chunk * sign)
        await asyncio.sleep(random.uniform(0.08, 0.25))


async def scroll_to_read(page):
    """One quick scroll — fast but still human-like."""
    await human_scroll(page, "down", random.randint(200, 350))
    await asyncio.sleep(random.uniform(0.4, 0.9))


# ── Stealth Scripts ──────────────────────────────────────────
STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete navigator.__proto__.webdriver;

    window.chrome = {
        runtime: { onConnect: { addListener: () => {} }, id: undefined },
        loadTimes: function(){}, csi: function(){}
    };

    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
            ];
            plugins.length = 3;
            return plugins;
        }
    });

    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });

    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);

    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, param);
    };

    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
        if (type === 'image/png') {
            const ctx = this.getContext('2d');
            if (ctx) {
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += (Math.random() * 2 - 1) | 0;
                }
                ctx.putImageData(imageData, 0, 0);
            }
        }
        return toDataURL.apply(this, arguments);
    };

    for (let frame of window.frames) {
        try {
            Object.defineProperty(frame.navigator, 'webdriver', { get: () => undefined });
        } catch(e) {}
    }
}
"""


# ── Viewport & User Agent ─────────────────────────────────────
def random_viewport():
    bases = [
        (1920, 1080), (1440, 900), (1536, 864),
        (1366, 768), (1280, 800), (1680, 1050),
    ]
    w, h = random.choice(bases)
    w += random.randint(-20, 20)
    h += random.randint(-10, 10)
    return {"width": w, "height": h}


def random_user_agent():
    versions = [
        "130.0.6723.116", "131.0.6778.139", "132.0.6834.83",
        "133.0.6943.141", "134.0.6998.165", "135.0.7049.84",
        "136.0.7103.113",
    ]
    v = random.choice(versions)
    return (
        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{v} Safari/537.36"
    )


# ── Application Tracker ──────────────────────────────────────
class ApplicationTracker:
    def __init__(self, csv_path=None):
        self.csv_path: Path = Path(csv_path) if csv_path else Path(cfg.CSV_LOG)
        self.session_apps = []
        self._cache: set = set()
        self._ensure_header()

    def _ensure_header(self):
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                csv.writer(f).writerow([
                    "timestamp", "title", "company", "location",
                    "url", "status", "notes",
                ])

    def log(self, title, company, location, url, status, notes=""):
        row = [datetime.now().isoformat(), title, company, location, url, status, notes]
        self.session_apps.append(row)
        with open(self.csv_path, "a", newline="") as f:
            csv.writer(f).writerow(row)
        if status == "applied":
            self._cache.add(url)
        logger.info(f"[{status.upper()}] {title}")

    def get_all_applied_urls(self) -> set:
        urls = set()
        if not self.csv_path.exists():
            return urls
        with open(self.csv_path) as f:
            for row in csv.DictReader(f):
                if row.get("status") == "applied":
                    urls.add(row.get("url", ""))
        self._cache = urls
        return urls

    def already_applied(self, url: str) -> bool:
        return url in self._cache

    @property
    def session_count(self) -> int:
        return sum(1 for r in self.session_apps if r[5] == "applied")

    def summary(self) -> dict:
        """Count logged rows by status. Returns only statuses that actually
        occurred — callers should use .get(status, 0), not [status]."""
        counts = {}
        for r in self.session_apps:
            counts[r[5]] = counts.get(r[5], 0) + 1
        return counts


# ── Screening Question Matching ────────────────────────────────
def match_screening_answer(question: str, answers: dict):
    """Case-insensitive substring match of a form question against
    configured answers. Returns None (not a guess) when nothing matches."""
    q = (question or "").lower()
    for key, answer in answers.items():
        if key in q:
            return answer
    return None


# ── Telegram Notifications ──────────────────────────────────────
def _send_telegram_sync(text: str):
    url = f"https://api.telegram.org/bot{cfg.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": cfg.TELEGRAM_CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception as e:
        logger.warning(f"Telegram notify failed: {e}")


async def send_telegram(text: str):
    """Fire-and-forget Telegram notification. No-op if not configured —
    safe to call unconditionally from anywhere in the bot."""
    if not (cfg.TELEGRAM_BOT_TOKEN and cfg.TELEGRAM_CHAT_ID):
        return
    if cfg.BOT_LABEL:
        text = f"[{cfg.BOT_LABEL}] {text}"
    await asyncio.to_thread(_send_telegram_sync, text)
