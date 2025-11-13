import logging
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from utils.request_client import RequestClient

logger = logging.getLogger(__name__)

SEARCH_BASE_URL = "https://play.google.com/store/search"
CATEGORY_BASE_URL = "https://play.google.com/store/apps/category"

def _extract_app_cards(soup: BeautifulSoup, max_results: int) -> List[Dict[str, Any]]:
    apps: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/store/apps/details" not in href or "id=" not in href:
            continue
        # href may be "/store/apps/details?id=com.example.app&hl=en"
        parts = href.split("id=")
        if len(parts) < 2:
            continue
        app_id = parts[1].split("&", 1)[0]
        if not app_id or app_id in seen_ids:
            continue

        title = a.get_text(strip=True) or None
        apps.append({"appId": app_id, "title": title})
        seen_ids.add(app_id)

        if len(apps) >= max_results:
            break

    return apps

def search_apps_by_keyword(
    client: RequestClient,
    keyword: str,
    max_results: int = 50,
    language: str = "en_US",
) -> List[Dict[str, Any]]:
    params = {
        "q": keyword,
        "c": "apps",
        "hl": language,
    }
    logger.debug("Searching apps by keyword '%s' with params %s", keyword, params)
    response = client.get(SEARCH_BASE_URL, params=params)
    soup = BeautifulSoup(response.text, "html.parser")
    apps = _extract_app_cards(soup, max_results=max_results)
    logger.info("Found %d apps for keyword '%s'", len(apps), keyword)
    return apps

def fetch_category_top_apps(
    client: RequestClient,
    category_id: str,
    max_results: int = 50,
    language: str = "en_US",
) -> List[Dict[str, Any]]:
    url = f"{CATEGORY_BASE_URL}/{category_id}"
    params = {"hl": language}
    logger.debug("Fetching category '%s' apps from %s", category_id, url)
    response = client.get(url, params=params)
    soup = BeautifulSoup(response.text, "html.parser")
    apps = _extract_app_cards(soup, max_results=max_results)
    logger.info("Found %d apps for category '%s'", len(apps), category_id)
    return apps