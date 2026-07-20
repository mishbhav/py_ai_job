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

# --- Selectors: verify these against the current Naukri DOM before relying on them ---
SEL_JOB_CARD = "div.srp-jobtuple-wrapper, article.jobTuple"
SEL_JOB_TITLE = "a.title, a.title.fw500"
SEL_JOB_COMPANY = "a.comp-name, .comp-name"
SEL_JOB_LOCATION = "span.locWdth, .location"
SEL_JOB_LINK = "a.title"
SEL_JD_BODY = "div.styles_JDC__dang-inner-html, .dang-inner-html, section.job-desc"


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
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=settings.SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_selector(SEL_JD_BODY, timeout=settings.SCRAPE_TIMEOUT_MS)

            title_el = await page.query_selector(SEL_JOB_TITLE)
            company_el = await page.query_selector(SEL_JOB_COMPANY)
            location_el = await page.query_selector(SEL_JOB_LOCATION)
            body_el = await page.query_selector(SEL_JD_BODY)

            title = (await title_el.inner_text()).strip() if title_el else "Unknown title"
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            body = (await body_el.inner_text()).strip() if body_el else ""

            if not body:
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
    """
    Scrape up to `max_jobs` job descriptions for a given role query.

    Returns whatever it manages to collect rather than failing all-or-nothing:
    a partial result set (e.g. 22 of 40) is still useful for keyword
    aggregation and match scoring.
    """
    search_url = _build_search_url(role_query, location)
    results: List[ScrapedJob] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.SCRAPE_HEADLESS)
        try:
            page = await browser.new_page()
            await page.goto(search_url, timeout=settings.SCRAPE_TIMEOUT_MS, wait_until="domcontentloaded")

            job_links = await _extract_job_card_links(page, max_jobs)
            await page.close()

            if not job_links:
                raise ScrapeError("No job listings found for this search — try a broader role query.")

            for link in job_links:
                await asyncio.sleep(settings.SCRAPE_MIN_DELAY_S)
                job = await _scrape_single_jd(browser, link)
                if job:
                    results.append(job)
        finally:
            await browser.close()

    if not results:
        raise ScrapeError(
            "Found listings but couldn't extract any job description text — "
            "selectors are likely out of date."
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
