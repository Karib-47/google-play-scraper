import logging
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

from utils.request_client import RequestClient

logger = logging.getLogger(__name__)

def _parse_title(soup: BeautifulSoup) -> Optional[str]:
    # New layout: meta property
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    # Legacy h1
    h1 = soup.find("h1")
    if h1 and h1.text:
        return h1.text.strip()

    return None

def _parse_description(soup: BeautifulSoup) -> Optional[str]:
    meta_desc = soup.find("meta", property="og:description")
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()

    desc_div = soup.find("div", attrs={"itemprop": "description"})
    if desc_div:
        return desc_div.get_text(separator="\n").strip()

    return None

def _parse_score(soup: BeautifulSoup) -> Optional[float]:
    try:
        rating_meta = soup.find("meta", itemprop="ratingValue")
        if rating_meta and rating_meta.get("content"):
            return float(rating_meta["content"])
    except (TypeError, ValueError):
        logger.debug("Failed to parse rating score from meta.", exc_info=True)

    try:
        rating_span = soup.find("div", attrs={"aria-label": True})
        if rating_span and rating_span.has_attr("aria-label"):
            # e.g. "Rated 4.2 stars out of five"
            text = rating_span["aria-label"]
            for token in text.split():
                try:
                    return float(token)
                except ValueError:
                    continue
    except Exception:  # noqa: BLE001
        logger.debug("Failed to parse rating score from aria-label.", exc_info=True)

    return None

def _parse_installs(soup: BeautifulSoup) -> Optional[str]:
    # Google Play layout changes frequently; use data-testid labels where possible.
    try:
        elements = soup.select("[data-testid='play-review-header-info'] div")
        for el in elements:
            text = el.get_text(strip=True)
            if "+" in text and any(ch.isdigit() for ch in text):
                return text
    except Exception:  # noqa: BLE001
        logger.debug("Failed to parse installs from data-testid block.", exc_info=True)

    # Fallback: search for patterns like "1,000,000+ downloads"
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if "downloads" in text.lower() and "+" in text:
            parts = text.split()
            for part in parts:
                if "+" in part and any(ch.isdigit() for ch in part):
                    return part
    return None

def _parse_developer_email(soup: BeautifulSoup) -> Optional[str]:
    # Email often appears in the "Contact" section as a mailto link
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            return href.replace("mailto:", "").strip()
    return None

def _parse_developer_website(soup: BeautifulSoup) -> Optional[str]:
    # Developer website also appears in contact section
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "http" in href and "support.google.com" not in href and "policies.google.com" not in href:
            # avoid store internal links
            if "/store/apps/details" not in href and "/store/apps/dev" not in href:
                return href
    return None

def _parse_developer_address(soup: BeautifulSoup) -> Optional[str]:
    # Address often rendered as text block; detect via "Address" label
    for div in soup.find_all("div"):
        text = div.get_text(" ", strip=True)
        if "Address" in text and "\n" in div.text:
            parts = [line.strip() for line in div.text.splitlines() if line.strip()]
            if len(parts) >= 2:
                return " ".join(parts[1:])
    return None

def _parse_genre(soup: BeautifulSoup) -> Optional[str]:
    # Genre/category usually shown as a link near title
    for a in soup.find_all("a", href=True):
        if "/store/apps/category/" in a["href"]:
            return a.get_text(strip=True)
    return None

def _parse_categories(soup: BeautifulSoup) -> Optional[list[str]]:
    categories: list[str] = []
    for a in soup.find_all("a", href=True):
        if "/store/apps/category/" in a["href"]:
            label = a.get_text(strip=True)
            if label and label not in categories:
                categories.append(label)
    return categories or None

def _parse_screenshots(soup: BeautifulSoup) -> list[str]:
    screenshots: list[str] = []
    # Common pattern: <img ... data-src="https://play-lh.googleusercontent.com/...">
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if isinstance(src, str) and "play-lh.googleusercontent.com" in src:
            if src not in screenshots:
                screenshots.append(src)
    return screenshots

def _parse_video(soup: BeautifulSoup) -> Optional[str]:
    og_video = soup.find("meta", property="og:video")
    if og_video and og_video.get("content"):
        return og_video["content"].strip()
    return None

def fetch_app_details(
    client: RequestClient,
    app_id: str,
    base_url: str,
    language: str = "en_US",
) -> Dict[str, Any]:
    """
    Fetch app details for a single app ID from Google Play.
    """
    params = {"id": app_id, "hl": language}
    logger.debug("Requesting app details for %s with params %s", app_id, params)
    response = client.get(base_url, params=params)

    soup = BeautifulSoup(response.text, "html.parser")

    title = _parse_title(soup)
    description = _parse_description(soup)
    score = _parse_score(soup)
    installs = _parse_installs(soup)
    developer_email = _parse_developer_email(soup)
    developer_website = _parse_developer_website(soup)
    developer_address = _parse_developer_address(soup)
    genre = _parse_genre(soup)
    categories = _parse_categories(soup)
    screenshots = _parse_screenshots(soup)
    video = _parse_video(soup)

    details: Dict[str, Any] = {
        "title": title,
        "appId": app_id,
        "description": description,
        "score": score,
        "ratings": None,  # can be added by more advanced parsing
        "reviews": None,  # will be replaced by reviews parser
        "installs": installs,
        "screenshots": screenshots,
        "video": video,
        "developerEmail": developer_email,
        "developerWebsite": developer_website,
        "developerAddress": developer_address,
        "genre": genre,
        "categories": categories,
    }

    logger.debug("Parsed details for %s: %s", app_id, details)
    return details