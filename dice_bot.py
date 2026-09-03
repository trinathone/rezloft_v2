"""
Dice.com Auto-Apply Bot — Production v2
========================================
- Contract + Easy Apply filters only
- Broad queries: roles + states + government + cities
- Target: ~60 applications/hour
- Auto-recovers from crashes, tab deaths, CAPTCHAs
- Sleeps 2am-3am, polls every 60s to wake reliably
- No screenshots, rotating logs, clean dedup
"""

import asyncio
import json
import random
import sys
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Page, BrowserContext

import config as cfg
from utils import (
    logger, human_delay, short_delay, micro_delay, break_delay,
    bezier_mouse_move, random_mouse_wander, human_type,
    scroll_to_read, STEALTH_JS, random_viewport, random_user_agent,
    ApplicationTracker, match_screening_answer, send_telegram,
)

# Fallback chains — a site redesign breaks the first selector, not the bot.
JOB_LINK_SELECTORS = [
    ('a[data-testid="job-search-job-detail-link"]', 12_000),
    ('a[data-cy="job-title"]', 4_000),
    ('a[href*="/job-detail/"]', 4_000),
]


class DiceBot:
    def __init__(self):
        self.tracker   = ApplicationTracker()
        self.page: Page = None
        self.context: BrowserContext = None
        self.consecutive_fails = 0
        self.used_urls  = set()
        self.batch_applied = 0
        self.batch_target  = random.randint(*cfg.BATCH_SIZE)
        self.keywords: list = []
        self.query_index: int = 0
        self.unanswered_questions: list = []
        # Randomized once per run so the sleep window isn't the exact same
        # clock time every day — see config.SLEEP_JITTER_MINUTES.
        self.sleep_jitter = random.randint(-cfg.SLEEP_JITTER_MINUTES, cfg.SLEEP_JITTER_MINUTES)
        # Telegram status-digest bookkeeping.
        self.daily_applied = 0
        self.block_count = 0
        self.last_report_time = datetime.now()

    # ── Entry Point ──────────────────────────────────────────
    async def run(self):
        if not cfg.DICE_EMAIL or not cfg.DICE_PASSWORD:
            logger.error("DICE_EMAIL / DICE_PASSWORD not set in .env")
            return

        self.keywords = cfg.load_keywords()
        logger.info(f"Loaded {len(self.keywords)} keywords from keywords.txt")

        logger.info("=" * 55)
        logger.info("Dice Bot v2 — Contract + Easy Apply — ~60 apps/hr")
        logger.info(f"Keywords: {len(self.keywords)} | Sleep: {cfg.SLEEP_HOUR_START}:00-{cfg.SLEEP_HOUR_END}:00")
        logger.info("=" * 55)

        self.used_urls = self.tracker.get_all_applied_urls()
        logger.info(f"Loaded {len(self.used_urls)} previously applied URLs")

        cfg.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        consecutive_crashes = 0

        while True:
            if self._is_sleep_time():
                await self._sleep_until_wake()
                continue

            try:
                await self._run_session()
                consecutive_crashes = 0
            except AuthenticationError as e:
                logger.error(f"FATAL — not retrying: {e}")
                await send_telegram(f"DiceBot STOPPED (fatal): {e}")
                return
            except Exception as e:
                consecutive_crashes += 1
                logger.error(f"Session crashed (#{consecutive_crashes}): {e}", exc_info=True)
                wait = min(30 * consecutive_crashes, 300)
                logger.info(f"Auto-restarting in {wait}s...")
                await asyncio.sleep(wait)
                if consecutive_crashes >= 10:
                    logger.warning("10 consecutive crashes — cooling down 10 min")
                    page_state = await self._detect_page_state()
                    await send_telegram(
                        f"DiceBot unhealthy: 10 consecutive crashes, cooling down 10 min.\n"
                        f"Last error: {e}\nLast page seen: {page_state}"
                    )
                    await asyncio.sleep(600)
                    consecutive_crashes = 0

    # ── Session ───────────────────────────────────────────────
    async def _run_session(self):
        viewport = random_viewport()
        ua       = random_user_agent()

        async with async_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={viewport['width']},{viewport['height']}",
            ]

            launch_kwargs = dict(
                user_data_dir=cfg.BROWSER_PROFILE_DIR,
                headless=cfg.HEADLESS,
                args=launch_args,
                slow_mo=random.randint(15, 40),
                viewport=viewport,
                user_agent=ua,
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme=random.choice(["light", "dark", "no-preference"]),
            )

            if cfg.PROXY:
                launch_kwargs["proxy"] = {"server": cfg.PROXY}

            self.context = await p.chromium.launch_persistent_context(**launch_kwargs)

            # Everything from here on must be inside the try/finally: if setup
            # itself fails partway (page dies before bring_to_front, etc.), the
            # context still needs closing — otherwise it leaks a Chromium
            # process holding a lock on browser_data/, breaking every launch after it.
            try:
                await self.context.add_init_script(STEALTH_JS)

                self.page = (
                    self.context.pages[0]
                    if self.context.pages
                    else await self.context.new_page()
                )
                await self.page.bring_to_front()

                # Close any stray popup tabs that open during apply
                self.context.on("page", self._handle_popup)

                await self._login()
                await self._main_loop()
            except BotBlockedError:
                self.block_count += 1
                logger.error("Bot blocked — closing session to rotate fingerprint")
            except AuthenticationError:
                # Fatal — propagate past cleanup so run() stops the bot instead
                # of retrying the same bad credentials every ~10s forever.
                raise
            except Exception as e:
                logger.error(f"Session error: {e}", exc_info=True)
            finally:
                s = self.tracker.summary()
                logger.info(
                    f"Session done — Applied={s.get('applied', 0)} "
                    f"Skipped={s.get('skipped', 0)} Failed={s.get('failed', 0)}"
                )
                try:
                    await self.context.close()
                except Exception:
                    pass
                # Minimum cooldown before any browser restart attempt.
                # Prevents rapid-fire relaunch cycles on network dropout
                # (ERR_INTERNET_DISCONNECTED exits _run_session cleanly,
                # so consecutive_crashes never increments — without this
                # sleep the outer loop restarts immediately, causing 70+
                # relaunches per minute).
                await asyncio.sleep(10)

    # ── Popup / New Tab Handler ───────────────────────────────
    def _handle_popup(self, page):
        """Close any external ATS tabs that open on Apply click."""
        async def _close():
            try:
                await asyncio.sleep(1.5)
                logger.info(f"Closing external popup: {page.url}")
                await page.close()
            except Exception:
                pass
        asyncio.ensure_future(_close())

    # ── Session Guard — re-login if kicked out mid-run ────────
    async def _ensure_logged_in(self):
        url = self.page.url.lower()
        if "login" in url or "signin" in url or "sign-in" in url:
            logger.warning("Session expired — re-logging in automatically...")
            await self._login()

    # ── Login ─────────────────────────────────────────────────
    async def _login(self):
        logger.info("Checking login state...")
        await self.page.goto(
            "https://www.dice.com/dashboard",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        await short_delay()

        url = self.page.url.lower()
        if "login" not in url and "signin" not in url:
            logger.info("Already logged in.")
            return

        for attempt in range(1, 4):
            logger.info(f"Logging in... (attempt {attempt}/3)")

            # A stale/kicked-out session sometimes lands on a signup page
            # instead of the login form — re-navigating to the login entry
            # point clears that instead of getting stuck on the wrong form.
            if await self._on_signup_wall():
                logger.warning("Landed on signup page instead of login — retrying from login URL")
                await self.page.goto(
                    "https://www.dice.com/dashboard", wait_until="domcontentloaded", timeout=60_000
                )
                await short_delay()

            try:
                email_el = self.page.locator('input[name="email"], input[type="email"]').first
                await email_el.wait_for(state="visible", timeout=15_000)
                await bezier_mouse_move(self.page, random.randint(400, 800), random.randint(300, 500))
                await human_type(email_el, cfg.DICE_EMAIL)
                await short_delay()

                await self.page.locator('button[type="submit"]').first.click()
                await short_delay()

                pw_el = self.page.locator('input[type="password"]').first
                await pw_el.wait_for(state="visible", timeout=8_000)
                await human_type(pw_el, cfg.DICE_PASSWORD)
                await short_delay()
                await self.page.locator('button[type="submit"]').first.click()
                await short_delay()
            except Exception:
                logger.warning("Login fields not found as expected on this attempt.")

            # Fail fast on explicit bad-credentials/lockout messages instead of
            # waiting the full 5 minutes and looping forever on the same password.
            await asyncio.sleep(1.5)
            body = await self.page.evaluate("() => document.body?.innerText?.toLowerCase() || ''")
            for signal in [
                "invalid email or password", "incorrect password",
                "account has been locked", "account is locked",
                "account suspended", "too many failed attempts",
            ]:
                if signal in body:
                    raise AuthenticationError(
                        f"Dice reported '{signal}' — check DICE_EMAIL/DICE_PASSWORD in .env"
                    )

            url = self.page.url.lower()
            if "login" not in url and "signin" not in url and not await self._on_signup_wall():
                logger.info("Login successful.")
                return

            logger.warning(f"Still not logged in after attempt {attempt}/3")

        # Retries exhausted — fall back to waiting up to 5 min for manual
        # login / 2FA / CAPTCHA completion.
        logger.info("Falling back to manual-completion wait (up to 5 min)...")
        for i in range(60):
            await asyncio.sleep(5)
            url = self.page.url.lower()
            if "login" not in url and "signin" not in url and "verify" not in url:
                logger.info("Login successful.")
                return
            if i % 6 == 0 and i > 0:
                logger.info(f"Waiting for login... {i*5}s elapsed")

        raise RuntimeError("Login timed out after retries and 5 minute wait")

    async def _on_signup_wall(self) -> bool:
        """Detect a signup/register page instead of the login form — can
        happen if a dropped session bounces to the wrong entry point."""
        url = self.page.url.lower()
        if any(s in url for s in ("signup", "sign-up", "register", "create-account")):
            return True
        try:
            body = await self.page.evaluate("() => document.body?.innerText?.toLowerCase() || ''")
            return "create your account" in body or "create an account" in body
        except Exception:
            return False

    # ── Diagnostics / Notifications ─────────────────────────────
    async def _detect_page_state(self) -> str:
        """Classify the current page for logs and Telegram reports."""
        if not self.page:
            return "no_page"
        try:
            if await self._detect_block():
                return "blocked"
            if await self._on_signup_wall():
                return "signup_wall"
            url = self.page.url.lower()
            if "login" in url or "signin" in url:
                return "login"
            if "job-detail" in url:
                return "job_detail"
            if "/jobs" in url:
                return "job_search"
            if "dashboard" in url:
                return "dashboard"
            return "unknown"
        except Exception:
            return "unknown"

    async def _maybe_send_periodic_report(self):
        if datetime.now() - self.last_report_time < timedelta(hours=cfg.TELEGRAM_REPORT_HOURS):
            return
        self.last_report_time = datetime.now()

        counts = self.tracker.summary()
        remaining = max(0, cfg.DAILY_APPLICATION_TARGET - self.daily_applied)
        page_state = await self._detect_page_state()
        text = (
            f"DiceBot status ({cfg.TELEGRAM_REPORT_HOURS}h update)\n"
            f"Applied today: {self.daily_applied} | ~{remaining} more expected today\n"
            f"Applied (total this run): {counts.get('applied', 0)}\n"
            f"Needs review: {counts.get('needs_review', 0)} | "
            f"Failed: {counts.get('failed', 0)} | Skipped: {counts.get('skipped', 0)}\n"
            f"Blocked/restarted: {self.block_count} times\n"
            f"Current page: {page_state}"
        )
        await send_telegram(text)

    # ── Main Loop ─────────────────────────────────────────────
    async def _main_loop(self):
        page_num = 1
        current_query = self.keywords[self.query_index]
        consecutive_skipped_pages = 0

        while True:
            if self._is_sleep_time():
                return

            await self._maybe_send_periodic_report()

            # Batch break
            if self.batch_applied >= self.batch_target:
                mins = random.uniform(*cfg.BATCH_BREAK_MINUTES)
                logger.info(f"Batch of {self.batch_applied} done. Resting {mins:.1f} min...")
                await asyncio.sleep(mins * 60)
                self.batch_target  = random.randint(*cfg.BATCH_SIZE)
                self.batch_applied = 0
                self.query_index = (self.query_index + 1) % len(self.keywords)
                current_query = self.keywords[self.query_index]
                page_num = 1
                consecutive_skipped_pages = 0

            # Too many consecutive fails — rotate to next keyword
            if self.consecutive_fails >= cfg.MAX_CONSECUTIVE_FAILS:
                logger.warning("Too many failures — rotating keyword and pausing 90s")
                self.consecutive_fails = 0
                self.query_index = (self.query_index + 1) % len(self.keywords)
                current_query = self.keywords[self.query_index]
                page_num = 1
                consecutive_skipped_pages = 0
                await asyncio.sleep(90)

            # Page watchdog
            if not await self._ensure_page_alive():
                logger.error("Page unrecoverable — restarting session")
                return

            # Re-login if session was dropped
            await self._ensure_logged_in()

            logger.info(f"Query: '{current_query}' | Page {page_num}")
            await self._run_search(current_query, page_num)

            jobs = await self._collect_jobs()
            if not jobs:
                logger.info(f"No jobs on page {page_num} — switching to next keyword")
                self.query_index = (self.query_index + 1) % len(self.keywords)
                current_query = self.keywords[self.query_index]
                page_num = 1
                consecutive_skipped_pages = 0
                await asyncio.sleep(random.uniform(3, 8))
                continue

            random.shuffle(jobs)
            max_this_page  = random.randint(5, 10)
            applied_this_page = 0

            for job in jobs:
                if self._is_sleep_time():
                    return
                if applied_this_page >= max_this_page:
                    break
                if self.batch_applied >= self.batch_target:
                    break
                if self.consecutive_fails >= cfg.MAX_CONSECUTIVE_FAILS:
                    break
                if job["url"] in self.used_urls:
                    continue

                self.used_urls.add(job["url"])
                await self._apply_to_job(job)
                applied_this_page += 1
                self.batch_applied += 1

                if (
                    self.tracker.session_count > 0
                    and self.tracker.session_count % cfg.BREAK_EVERY_N_APPS == 0
                ):
                    await break_delay()

                await human_delay()
                await random_mouse_wander(self.page)

            # Exhaustion detection: jobs exist but all already applied to
            if applied_this_page == 0 and len(jobs) > 0:
                consecutive_skipped_pages += 1
                logger.debug(
                    f"All jobs on page {page_num} already applied — "
                    f"skipped page {consecutive_skipped_pages}/3"
                )
                if consecutive_skipped_pages >= 3:
                    logger.info(
                        f"Keyword '{current_query}' exhausted "
                        f"(3 consecutive all-skipped pages) — rotating"
                    )
                    self.query_index = (self.query_index + 1) % len(self.keywords)
                    current_query = self.keywords[self.query_index]
                    page_num = 1
                    consecutive_skipped_pages = 0
                    await asyncio.sleep(random.uniform(3, 8))
                    continue
            else:
                consecutive_skipped_pages = 0

            # Short rest then next page
            rest = random.uniform(3, 8)
            logger.info(f"Next page in {rest:.0f}s...")
            await asyncio.sleep(rest)
            page_num += 1

    # ── Search ────────────────────────────────────────────────
    async def _run_search(self, keyword: str, page: int = 1):
        params = f"?q={keyword.replace(' ', '+')}"
        if cfg.JOB_LOCATION:
            params += f"&location={cfg.JOB_LOCATION.replace(' ', '+')}"
        if cfg.REMOTE_ONLY:
            params += "&filters.isRemote=true"
        employment_codes = {"contract": "CONTRACTS", "fulltime": "FULLTIME"}
        for job_type in cfg.JOB_TYPES:
            code = employment_codes.get(job_type)
            if code:
                params += f"&filters.employmentType={code}"
        if cfg.EASY_APPLY_ONLY:
            params += "&filters.easyApply=true"
        params += f"&page={page}"

        url = f"https://www.dice.com/jobs{params}"
        logger.info(f"Loading search: {keyword} (page {page})")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        except Exception:
            # Fallback — just wait for network to settle a bit
            await asyncio.sleep(3)

        await short_delay()
        await scroll_to_read(self.page)

    # ── Collect Jobs ──────────────────────────────────────────
    async def _collect_jobs(self) -> list:
        jobs = []
        seen_urls = set()

        found_selector = None
        for sel, timeout in JOB_LINK_SELECTORS:
            try:
                await self.page.wait_for_selector(sel, timeout=timeout)
                found_selector = sel
                break
            except Exception:
                continue

        if not found_selector:
            return jobs

        raw = await self.page.evaluate("""(sel) => {
            const links = document.querySelectorAll(sel);
            const results = [];
            for (const a of links) {
                const title = (a.getAttribute('aria-label') || a.innerText || '').trim();
                const href = a.href;
                if (title && href) results.push({ title, url: href });
            }
            return results;
        }""", found_selector)

        for item in raw:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            jobs.append({
                "title":    item["title"],
                "company":  "",
                "location": "",
                "url":      url,
            })

        logger.info(f"Found {len(jobs)} jobs")
        return jobs

    # ── Page Watchdog ─────────────────────────────────────────
    async def _ensure_page_alive(self) -> bool:
        try:
            await self.page.evaluate("1")
            return True
        except Exception:
            logger.warning("Page died — attempting tab recovery...")
            try:
                self.page = await self.context.new_page()
                await self.context.add_init_script(STEALTH_JS)
                logger.info("Recovered: new tab opened.")
                return True
            except Exception as e:
                logger.error(f"Context also dead: {e}")
                return False

    # ── Apply ─────────────────────────────────────────────────
    async def _apply_to_job(self, job: dict):
        try:
            if not await self._ensure_page_alive():
                raise RuntimeError("Page unrecoverable")

            logger.info(f"Applying: {job['title']}")

            try:
                await self.page.goto(
                    job["url"], wait_until="domcontentloaded", timeout=45_000
                )
            except Exception:
                await asyncio.sleep(2)

            await short_delay()
            await scroll_to_read(self.page)

            # Re-login if job page redirected to login
            await self._ensure_logged_in()

            # Check for block BEFORE clicking anything
            if await self._detect_block():
                raise BotBlockedError("CAPTCHA or block detected")

            await self._scrape_job_details(job)

            # Find Apply button
            apply_btn = None
            for sel in [
                'a[data-testid="apply-button"]',
                'button[data-testid="apply-button"]',
                'a:has-text("Easy Apply")',
                'button:has-text("Easy Apply")',
                'a:has-text("Apply")',
            ]:
                loc = self.page.locator(sel).first
                try:
                    if await loc.is_visible(timeout=1_500):
                        apply_btn = loc
                        break
                except Exception:
                    continue

            if not apply_btn:
                self.tracker.log(
                    job["title"], job["company"], job["location"],
                    job["url"], "skipped", "No Apply button"
                )
                return

            # Skip if button is disabled — means already applied on Dice
            # Check via JS for instant response, no timeout needed
            is_disabled = await self.page.evaluate("""() => {
                const btn = document.querySelector('[data-testid="apply-button"]');
                return btn ? btn.disabled || btn.getAttribute('data-disabled') === 'true' : false;
            }""")
            if is_disabled:
                self.tracker.log(
                    job["title"], job["company"], job["location"],
                    job["url"], "skipped", "Already applied (button disabled)"
                )
                return

            if cfg.DRY_RUN:
                logger.info(f"[DRY RUN] Would apply: {job['title']}")
                self.tracker.log(
                    job["title"], job["company"], job["location"],
                    job["url"], "dry_run", "Apply button located but not clicked"
                )
                return

            # Bezier click
            box = await apply_btn.bounding_box()
            if box:
                await bezier_mouse_move(
                    self.page,
                    int(box["x"] + box["width"] / 2 + random.randint(-5, 5)),
                    int(box["y"] + box["height"] / 2 + random.randint(-3, 3)),
                )
                await micro_delay()

            await apply_btn.click()
            await asyncio.sleep(random.uniform(1.5, 3))

            result = await self._handle_apply_form()

            if result == "submitted":
                self.tracker.log(
                    job["title"], job["company"], job["location"],
                    job["url"], "applied"
                )
                self.consecutive_fails = 0
                self.daily_applied += 1
            else:
                if result == "needs_review":
                    asked = " | ".join(self.unanswered_questions)[:200]
                    note = f"Add to SCREENING_ANSWERS: {asked}"
                else:
                    note = "Form did not reach a confirmed submit"
                self.tracker.log(
                    job["title"], job["company"], job["location"],
                    job["url"], result, note
                )
                self.consecutive_fails += 1
                logger.warning(f"{result}: {job['title']} — {note}")

        except BotBlockedError:
            raise  # bubble up to session level — triggers full restart

        except Exception as e:
            self.consecutive_fails += 1
            page_state = await self._detect_page_state()
            logger.error(f"Failed: {job['title']} — {e} (page: {page_state})")
            self.tracker.log(
                job["title"], job["company"], job["location"],
                job["url"], "failed", f"{str(e)[:180]} (page: {page_state})"
            )

    # ── Form Handler ──────────────────────────────────────────
    async def _handle_apply_form(self) -> str:
        """Walk the multi-step apply form. Returns 'submitted',
        'needs_review' (a required question we can't confidently answer),
        or 'stuck' (ran out of steps or no Next/Submit found)."""
        await asyncio.sleep(1.5)
        self.unanswered_questions = []

        for _ in range(8):
            if await self._answer_questions():
                return "needs_review"

            # Try Submit first
            for sel in [
                'button:has-text("Submit Application")',
                'button:has-text("Submit")',
                'a:has-text("Submit Application")',
                'a:has-text("Submit")',
            ]:
                btn = self.page.locator(sel).first
                try:
                    if await btn.is_visible(timeout=1_000):
                        box = await btn.bounding_box()
                        if box:
                            await bezier_mouse_move(
                                self.page,
                                int(box["x"] + box["width"] / 2),
                                int(box["y"] + box["height"] / 2),
                            )
                        await micro_delay()
                        await btn.click()
                        # Verify it actually went through: a successful submit
                        # dismisses the button. If it's still there, validation
                        # blocked us — don't log that as "applied".
                        try:
                            await btn.wait_for(state="hidden", timeout=6_000)
                        except Exception:
                            logger.warning("Submit clicked but form didn't advance — likely a validation error")
                            return "stuck"
                        logger.info("Submitted.")
                        await asyncio.sleep(1)
                        return "submitted"
                except Exception:
                    continue

            # Try Next / Continue
            found_next = False
            for sel in [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'a:has-text("Next")',
                'a:has-text("Continue")',
            ]:
                btn = self.page.locator(sel).first
                try:
                    if await btn.is_visible(timeout=1_000):
                        await btn.click()
                        await short_delay()
                        found_next = True
                        break
                except Exception:
                    continue

            if not found_next:
                break

        await asyncio.sleep(1.5)
        return "stuck"

    # ── Screening Questions ────────────────────────────────────
    async def _get_unanswered_questions(self) -> list:
        """Best-effort scan of the current form step for radio groups,
        dropdowns, and text inputs that look required and unanswered.
        DOM walking runs in-browser (one round trip) since per-element
        round trips from Python would be far slower."""
        try:
            return await self.page.evaluate("""() => {
                function nearestText(el) {
                    let node = el;
                    for (let i = 0; i < 5 && node; i++) {
                        const legend = node.querySelector && node.querySelector('legend');
                        if (legend && legend.innerText.trim()) return legend.innerText.trim();
                        node = node.parentElement;
                    }
                    const container = el.closest('div,fieldset,section');
                    const prev = container && container.previousElementSibling;
                    if (prev && prev.innerText && prev.innerText.trim()) {
                        return prev.innerText.trim().slice(0, 200);
                    }
                    return '';
                }

                const out = [];

                const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                const seenGroups = new Set();
                for (const r of radios) {
                    if (!r.name || seenGroups.has(r.name)) continue;
                    seenGroups.add(r.name);
                    const group = radios.filter(x => x.name === r.name);
                    if (group.some(x => x.checked)) continue;
                    const question = nearestText(r.closest('fieldset,div[role="radiogroup"],div') || r);
                    const options = group.map(x => {
                        let label = '';
                        if (x.id) {
                            const lbl = document.querySelector(`label[for="${x.id}"]`);
                            if (lbl) label = lbl.innerText.trim();
                        }
                        if (!label && x.closest('label')) label = x.closest('label').innerText.trim();
                        if (!label) label = x.value || '';
                        return { id: x.id, name: x.name, value: x.value, label };
                    });
                    out.push({ type: 'radio', question, options });
                }

                // Radio groups are treated as always-required; everything else
                // is only blocking if the form marks it required.
                const isRequired = el => el.required || el.getAttribute('aria-required') === 'true';

                for (const s of document.querySelectorAll('select')) {
                    if (s.value) continue;
                    let label = '';
                    if (s.id) {
                        const lbl = document.querySelector(`label[for="${s.id}"]`);
                        if (lbl) label = lbl.innerText.trim();
                    }
                    if (!label) label = nearestText(s.closest('div,fieldset') || s);
                    out.push({ type: 'select', id: s.id, name: s.name, question: label, required: isRequired(s) });
                }

                const textSel = 'input[type="text"], input[type="number"], input[type="tel"], textarea';
                for (const t of document.querySelectorAll(textSel)) {
                    if (t.value || t.offsetParent === null) continue;
                    let label = '';
                    if (t.id) {
                        const lbl = document.querySelector(`label[for="${t.id}"]`);
                        if (lbl) label = lbl.innerText.trim();
                    }
                    if (!label) label = t.placeholder || nearestText(t.closest('div,fieldset') || t);
                    out.push({ type: 'text', id: t.id, name: t.name, question: label, required: isRequired(t) });
                }

                for (const c of document.querySelectorAll('input[type="checkbox"]')) {
                    if (c.checked || c.offsetParent === null) continue;
                    let label = '';
                    if (c.id) {
                        const lbl = document.querySelector(`label[for="${c.id}"]`);
                        if (lbl) label = lbl.innerText.trim();
                    }
                    if (!label && c.closest('label')) label = c.closest('label').innerText.trim();
                    if (!label) label = nearestText(c.closest('div,fieldset') || c);
                    out.push({ type: 'checkbox', id: c.id, name: c.name, question: label, required: isRequired(c) });
                }

                return out;
            }""")
        except Exception:
            return []

    async def _answer_questions(self) -> bool:
        """Fill any recognized screening questions on the current step.
        Returns True if a question was left unanswered — the caller
        aborts to 'needs_review' rather than guess and submit wrong data."""
        questions = await self._get_unanswered_questions()
        unresolved = False

        for q in questions:
            answer = match_screening_answer(q.get("question", ""), cfg.SCREENING_ANSWERS)
            if answer is None:
                # Optional unmatched fields are simply left blank. Required ones
                # (and any radio group) block, and get recorded so the CSV note
                # tells you exactly what to add to SCREENING_ANSWERS.
                if q.get("required", True):
                    unresolved = True
                    self.unanswered_questions.append(q.get("question") or f"<unlabeled {q['type']}>")
                continue

            try:
                if q["type"] == "radio":
                    target = next(
                        (o for o in q["options"]
                         if answer.lower() in o["label"].lower() or o["label"].lower() in answer.lower()),
                        None,
                    )
                    if target and target.get("id"):
                        await self.page.locator(f'#{target["id"]}').check(timeout=2_000)
                    elif target and target.get("name") and target.get("value"):
                        await self.page.locator(
                            f'input[name="{target["name"]}"][value="{target["value"]}"]'
                        ).first.check(timeout=2_000)
                    else:
                        unresolved = True

                elif q["type"] == "select":
                    locator = f'#{q["id"]}' if q.get("id") else f'select[name="{q.get("name", "")}"]'
                    if not q.get("id") and not q.get("name"):
                        unresolved = True
                    else:
                        try:
                            await self.page.locator(locator).select_option(label=answer, timeout=2_000)
                        except Exception:
                            await self.page.locator(locator).select_option(answer, timeout=2_000)

                elif q["type"] == "text":
                    locator = f'#{q["id"]}' if q.get("id") else f'[name="{q.get("name", "")}"]'
                    if not q.get("id") and not q.get("name"):
                        unresolved = True
                    else:
                        await human_type(self.page.locator(locator).first, answer)

                elif q["type"] == "checkbox":
                    locator = f'#{q["id"]}' if q.get("id") else f'input[name="{q.get("name", "")}"]'
                    if not q.get("id") and not q.get("name"):
                        unresolved = True
                    elif answer.strip().lower() in ("yes", "true", "checked", "agree"):
                        await self.page.locator(locator).first.check(timeout=2_000)
                    # answer says "No" — leave unchecked, which is already the current state

            except Exception:
                unresolved = True

            await micro_delay()

        return unresolved

    # ── Job Detail Scrape ───────────────────────────────────────
    async def _scrape_job_details(self, job: dict):
        """Company/location from Dice's own JSON-LD JobPosting structured
        data (verified live: [data-testid="jobDetailStructuredData"] holds
        a schema.org JobPosting block with hiringOrganization.name and
        jobLocation.address). Far more stable than guessing CSS selectors
        for elements Dice doesn't test-id. Any miss just leaves the field
        blank, same as before."""
        try:
            raw = await self.page.evaluate("""() => {
                const el = document.querySelector('[data-testid="jobDetailStructuredData"]');
                return el ? el.textContent : null;
            }""")
            if not raw:
                return
            data = json.loads(raw)

            company = (data.get("hiringOrganization") or {}).get("name", "")
            if company:
                job["company"] = company

            address = (data.get("jobLocation") or {}).get("address") or {}
            location = ", ".join(
                p for p in [address.get("addressLocality", ""), address.get("addressRegion", "")] if p
            )
            if location:
                job["location"] = location
        except Exception:
            pass

    # ── Block Detection ───────────────────────────────────────
    async def _detect_block(self) -> bool:
        try:
            for sel in [
                'iframe[src*="captcha"]',
                'iframe[src*="recaptcha"]',
                'iframe[src*="hcaptcha"]',
                '#captcha-container',
                '.captcha-wrapper',
                '[data-testid="captcha"]',
            ]:
                try:
                    if await self.page.locator(sel).first.is_visible(timeout=800):
                        return True
                except Exception:
                    continue

            title = (await self.page.title()).lower()
            for signal in ["access denied", "403", "blocked", "too many requests", "429"]:
                if signal in title:
                    return True

            # Also check page body for block signals
            body = await self.page.evaluate("() => document.body?.innerText?.toLowerCase() || ''")
            for signal in ["you have been blocked", "unusual traffic", "verify you are human"]:
                if signal in body:
                    return True

        except Exception:
            pass
        return False

    # ── Sleep Schedule ────────────────────────────────────────
    def _sleep_window(self):
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        offset = timedelta(minutes=self.sleep_jitter)
        start = base.replace(hour=cfg.SLEEP_HOUR_START) + offset
        end = base.replace(hour=cfg.SLEEP_HOUR_END) + offset
        return start, end

    def _is_sleep_time(self) -> bool:
        start, end = self._sleep_window()
        return start <= datetime.now() < end

    async def _send_eod_report(self):
        counts = self.tracker.summary()
        await send_telegram(
            f"DiceBot — End of Day Report\n"
            f"Applied today: {self.daily_applied} (target: {cfg.DAILY_APPLICATION_TARGET})\n"
            f"Needs review: {counts.get('needs_review', 0)} | "
            f"Failed: {counts.get('failed', 0)} | Skipped: {counts.get('skipped', 0)}\n"
            f"Blocked/restarted: {self.block_count} times today's run\n"
            f"Sleeping now, resuming tomorrow."
        )

    async def _sleep_until_wake(self):
        start, end = self._sleep_window()
        await self._send_eod_report()
        logger.info(
            f"Sleep time ({start.strftime('%H:%M')}-{end.strftime('%H:%M')}). "
            f"Polling every 60s until wake..."
        )
        while self._is_sleep_time():
            await self._maybe_send_periodic_report()
            await asyncio.sleep(60)
        logger.info("Woke up. Resuming...")
        # The daily sleep window is the bot's day boundary — reset the
        # "applied today" counter used in the Telegram digest.
        self.daily_applied = 0


# ── Custom Exceptions ─────────────────────────────────────────
class BotBlockedError(Exception):
    pass


class AuthenticationError(Exception):
    """Fatal — bad credentials or a locked/suspended account. Not retried."""
    pass


# ── Entry Point ───────────────────────────────────────────────
async def main():
    if "--dry-run" in sys.argv:
        cfg.DRY_RUN = True
        logger.info("DRY RUN mode — applications will be located but not submitted.")
    bot = DiceBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down (Ctrl+C) — browser session closed cleanly.")
