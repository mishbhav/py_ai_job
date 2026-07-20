"""
Adzuna Job Description API Client.

Replaces the fragile Naukri web scraper with an official, reliable 
REST API. Fully asynchronous using httpx.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional
import httpx

from app.core.config import get_settings
from app.models.schemas import ScrapedJob

logger = logging.getLogger(__name__)
settings = get_settings()

class ScrapeError(Exception):
    """Raised when the client cannot retrieve data from the Adzuna API."""


async def scrape_naukri_jobs(
    role_query: str,
    location: Optional[str] = None,
    max_jobs: int = 40,
) -> List[ScrapedJob]:
    """
    Fetches up to `max_jobs` descriptions using the official Adzuna API for India.
    
    Maintains the original function signature so no major changes are needed 
    in your background tasks or endpoints.
    """
    results: List[ScrapedJob] = []
    
    # Adzuna API defaults to 10-50 results per page. We will request 50 per page.
    results_per_page = min(max_jobs, 50)
    current_page = 1
    
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "what": role_query,
        "results_per_page": results_per_page,
        "content-type": "application/json"
    }
    
    if location:
        params["where"] = location

    # Async HTTP client with strict connection timeouts
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            while len(results) < max_jobs:
                # FIXED URL: Complete valid REST API endpoint tracking path
                url = f"https://api.adzuna.com/v1/api/jobs/in/search/{current_page}"
                
                # Immediate tracking trace print out to ensure the line is live
                print(f"📡 Dispatching Adzuna Network Request to: {url}", flush=True)
                
                response = await client.get(url, params=params)
                
                if response.status_code == 401 or response.status_code == 403:
                    raise ScrapeError("Adzuna API Authentication failed. Verify App ID and Key.")
                elif response.status_code != 200:
                    raise ScrapeError(f"Adzuna API returned an error status: {response.status_code}")
                
                data = response.json()
                listings = data.get("results", [])
                
                if not listings:
                    break  # Exit loop if no more jobs are returned for this search phrase
                
                for item in listings:
                    if len(results) >= max_jobs:
                        break
                        
                    # Extract and safely format nested company/location values
                    company_name = item.get("company", {}).get("display_name", "Unknown Company")
                    location_names = item.get("location", {}).get("area", [])
                    location_str = ", ".join(location_names) if location_names else "India"
                    
                    # Adzuna text payloads provide a clean, pre-parsed 'description' string
                    raw_desc = item.get("description", "").strip()
                    
                    if raw_desc:
                        results.append(
                            ScrapedJob(
                                title=item.get("title", "Unknown Title").strip(),
                                company=company_name,
                                location=location_str,
                                raw_description=raw_desc,
                                url=item.get("redirect_url", "")
                            )
                        )
                
                # If we received fewer items than requested, we've exhausted all available results
                if len(listings) < results_per_page:
                    break
                    
                current_page += 1
                await asyncio.sleep(0.2)
                
        except httpx.RequestError as exc:
            logger.error(f"Network connectivity error while calling Adzuna API: {exc}")
            raise ScrapeError("Failed to reach the job API endpoints due to a connection issue.") from exc

    return results


def load_manual_jd_texts(texts: List[str]) -> List[ScrapedJob]:
    """Preserves fallback path: builds ScrapedJob objects directly from pasted text."""
    return [
        ScrapedJob(title=f"Manual JD #{i+1}", raw_description=t)
        for i, t in enumerate(texts)
        if t.strip()
    ]
