"""
Naukri job-description scraper.

IMPORTANT — read before running against production traffic:
  * Naukri's markup changes frequently; the CSS selectors below are a
    best-effort starting point, not guaranteed to be stable. Expect to
    inspect the live DOM (DevTools) and update SELECTOR constants.
  * Respect the site's robots.txt / Terms of Use, add delays between
    requests (SCRAPE_MIN_DELAY_S), and keep volumes modest — this tool
    is designed for a single user pulling ~30-50 JDs for personal CV
    analysis, not bulk harvesting.
  * If Naukri exposes an official jobs API or RSS feed for your use
    case, prefer that over scraping.
  * As a resilience fallback, `manual_jd_texts` lets the pipeline run
    entirely on JD text the user pastes in, bypassing scraping if the
    site blocks automation (logins, captchas, etc).
"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import List, Optional

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from app.core.config import get_settings
from app.models.schemas import ScrapedJob

logger = logging.getLogger(__name__)
settings = get_settings()

# --- Selectors: Updated to handle modern Naukri structures defensively ---
SEL_JOB_CARD = "div.srp-jobtuple-wrapper, article.jobTuple, div.cust-job-tuple"
SEL_JOB_LINK = "a.title, a.comp-name-link"

# Individual Detail Page Layout Selectors
SEL_JOB_TITLE = "h1.jd-header-title, h1.title, .styles_jd-header-title__18mS_"
SEL_JOB_COMPANY = "div.jd-header-comp-name a, .styles_jd-header-comp-name__2379Z"
SEL_JOB_LOCATION = "span.location, .styles_jdc__styles-main-header__3n_v5"
SEL_JD_BODY = "section.job-desc, div.clearBoth.description, .styles_JDC__dang-inner-html"

# Desktop Browser Spoofing String
USER_AGENT_STRING = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


class ScrapeError(Exception):
    """Raised when the scraper cannot retrieve any usable job data."""


def _build_search_url(role_query: str, location: Optional[str]) -> str:
    params = {"k": role_query}
    if location:
        params["l"] = location
    return f"{settings.NAUKRI_BASE_URL}/{urllib.parse.quote(role_query.replace(' ', '-'))}-jobs?{urllib.parse.urlencode(params)}"


async def _extract_job_card_links(page: Page, max_jobs: int) -> List[str]:
    try:
        await page.wait_for_selector(SEL_JOB_CARD, timeout=settings.SCRAPE_TIMEOUT_MS)
    except PlaywrightTimeoutError as exc:
        raise ScrapeError(
            "Search results didn't load in time — Naukri may be rate-limiting, "
            "showing a captcha, or the selector is stale."
        ) from exc

    cards = await page.query_selector_all(SEL_JOB_CARD)
    links: List[str] = []
    for card in cards[:max_jobs]:
        anchor = await card.query_selector(SEL_JOB_LINK)
        if anchor:
            href = await anchor.get_attribute("href")
            if href:
                links.append(href)
    return links


async def _scrape_single_jd(browser: Browser, url: str) -> Optional[ScrapedJob]:
    for attempt in range(1, settings.SCRAPE_MAX_RETRIES + 2):
        # Attach User-Agent here to prevent blank page/captcha walls on detail pages
        page = await browser.new_page(user_agent=USER_AGENT_STRING)
        try:
            await page.goto(url, timeout=settings.SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_selector(SEL_JD_BODY, timeout=settings.SCRAPE_TIMEOUT_MS)

            title_el = await page.query_selector(SEL_JOB_TITLE)
            company_el = await page.query_selector(SEL_JOB_COMPANY)
            location_el = await page.query_selector(SEL_JOB_LOCATION)
            body_el = await page.query_selector(SEL_JD_BODY)

            # Safely check if elements exist before calling await .inner_text()
            title = (await title_el.inner_text()).strip() if title_el else "Unknown title"
            company = (await company_el.inner_text()).strip() if company_el else "Unknown company"
            location = (await location_el.inner_text()).strip() if location_el else "Unknown location"
            body = (await body_el.inner_text()).strip() if body_el else ""

            # This print will now execute safely even if some fields are missing!
            print(f"💼 Found Job Title: {title} | Company: {company}")

            if not body:
                print(f"⚠️ Warning: Job body element was empty for URL: {url}")
                return None

            return ScrapedJob(
                title=title, company=company, location=location, raw_description=body, url=url
            )
        except PlaywrightTimeoutError:
            logger.warning("Timeout scraping %s (attempt %d)", url, attempt)
            if attempt > settings.SCRAPE_MAX_RETRIES:
                return None
            await asyncio.sleep(settings.SCRAPE_MIN_DELAY_S * attempt)
        finally:
            await page.close()
    return None

async def scrape_naukri_jobs(
    role_query: str,
    location: Optional[str] = None,
    max_jobs: int = 40,
) -> List[ScrapedJob]:
    search_url = _build_search_url(role_query, location)
    results: List[ScrapedJob] = []

    # flush=True forces the terminal to display text immediately without buffering
    print(f"🚀 [STAGE 1] Initiating Playwright pipeline...", flush=True)

    async with async_playwright() as p:
        print(f"🤖 [STAGE 2] Launching headless browser wrapper...", flush=True)
        browser = await p.chromium.launch(headless=True)
        
        try:
            page = await browser.new_page(user_agent=USER_AGENT_STRING)
            
            print(f"🌐 [STAGE 3] Navigating to: {search_url}", flush=True)
            await page.goto(search_url, timeout=15000, wait_until="commit") # Using shorter 15s timeout
            
            print("⏳ [STAGE 4] Checking for Naukri elements DOM visibility...", flush=True)
            try:
                # Wait for the main container layout wrapper
                await page.wait_for_selector(SEL_JOB_CARD, timeout=8000)
                print("🎯 [STAGE 4.5] Success! Container tags identified on page.", flush=True)
            except Exception as e:
                print(f"❌ [BLOCKER] Failed to locate job cards. Element layout may be hidden or blocked by a captcha verification screen.", flush=True)
                # Take a debug snapshot image inside your virtual container file system
                await page.screenshot(path="naukri_error_debug.png")
                print("📸 Saved error screenshot to: backend/naukri_error_debug.png", flush=True)
                raise e

            job_links = await _extract_job_card_links(page, max_jobs)
            print(f"✅ [STAGE 5] Found {len(job_links)} URLs. Processing description details...", flush=True)
            await page.close()

            for i, link in enumerate(job_links, start=1):
                print(f"🕵️‍♂️ [LINK {i}/{len(job_links)}] Accessing: {link}", flush=True)
                await asyncio.sleep(settings.SCRAPE_MIN_DELAY_S)
                job = await _scrape_single_jd(browser, link)
                if job:
                    results.append(job)
                    
        except Exception as main_err:
            print(f"💥 Runtime Exception intercepted in tracking loop: {str(main_err)}", flush=True)
            raise ScrapeError(
                f"Scraping failed before any jobs could be collected: {main_err}"
            ) from main_err
        finally:
            await browser.close()

    if not results:
        raise ScrapeError(
            "Scraped the search page but got 0 usable job descriptions — "
            "selectors are likely stale, or Naukri showed a captcha/block. "
            "Check backend/naukri_error_debug.png."
        )

    return results



def load_manual_jd_texts(texts: List[str]) -> List[ScrapedJob]:
    """Fallback path: build ScrapedJob objects directly from pasted JD text,
    for when live scraping is blocked or unreliable."""
    return [
        ScrapedJob(title=f"Manual JD #{i+1}", raw_description=t)
        for i, t in enumerate(texts)
        if t.strip()
    ]