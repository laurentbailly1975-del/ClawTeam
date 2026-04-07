"""Scrape a job offer from a URL.

Strategy:
1. Fetch HTML with httpx (fast, no JS needed for most job boards)
2. Parse with BeautifulSoup, extract main content heuristically
3. Return structured dict with title, company, location, text, etc.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# CSS selectors for known job boards (title, company, description)
SELECTORS: dict[str, dict[str, str]] = {
    "linkedin.com": {
        "title": ".top-card-layout__title, h1.t-24",
        "company": ".topcard__org-name-link, .top-card-layout__company",
        "location": ".topcard__flavor--bullet",
        "description": ".show-more-less-html__markup, .description__text",
    },
    "indeed.com": {
        "title": "h1.jobsearch-JobInfoHeader-title",
        "company": "[data-testid='inlineHeader-companyName']",
        "location": "[data-testid='job-location']",
        "description": "#jobDescriptionText",
    },
    "welcometothejungle.com": {
        "title": "h1",
        "company": "[data-testid='job-header-company-name']",
        "location": "[data-testid='job-metadata-location']",
        "description": "[data-testid='job-section-description']",
    },
    "apec.fr": {
        "title": "h1.titleOffer",
        "company": ".company-title",
        "location": ".job-place",
        "description": ".details-post",
    },
}


def _get_selectors(url: str) -> dict[str, str]:
    for domain, sel in SELECTORS.items():
        if domain in url:
            return sel
    return {}


def _extract(soup: BeautifulSoup, selector: str) -> str:
    if not selector:
        return ""
    el = soup.select_one(selector)
    return el.get_text(separator=" ", strip=True) if el else ""


def _generic_description(soup: BeautifulSoup) -> str:
    """Heuristic: find the largest text block in main/article/section."""
    for tag in ("main", "article", "[role='main']", ".job-description",
                ".job-content", "#job-details", ".offer-description"):
        el = soup.select_one(tag)
        if el:
            return el.get_text(separator="\n", strip=True)

    # Fallback: largest <div> or <section> by text length
    candidates = soup.find_all(["div", "section", "article"])
    if not candidates:
        return soup.get_text(separator="\n", strip=True)[:8000]

    best = max(candidates, key=lambda el: len(el.get_text()))
    return best.get_text(separator="\n", strip=True)[:8000]


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scrape(url: str, timeout: int = 20) -> dict[str, Any]:
    """Fetch and parse a job offer. Returns a dict with keys:
    title, company, location, contract_type, salary, text, url.
    """
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    sel = _get_selectors(url)

    title = _extract(soup, sel.get("title", "")) or _extract(soup, "h1")
    company = _extract(soup, sel.get("company", ""))
    location = _extract(soup, sel.get("location", ""))
    contract_type = _extract(soup, sel.get("contract_type", ""))
    salary = _extract(soup, sel.get("salary", ""))

    if sel.get("description"):
        description = _extract(soup, sel["description"])
    else:
        description = _generic_description(soup)

    return {
        "url": url,
        "title": _clean(title),
        "company": _clean(company),
        "location": _clean(location),
        "contract_type": _clean(contract_type),
        "salary": _clean(salary),
        "text": _clean(description),
    }
