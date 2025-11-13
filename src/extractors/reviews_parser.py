import logging
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from utils.request_client import RequestClient

logger = logging.getLogger(__name__)

def _parse_reviews_from_page(soup: BeautifulSoup, max_reviews: int) -> List[Dict[str, Any]]:
    """
    Attempt to parse review cards from the app details page.

    Google Play markup changes periodically; this function uses generic
    heuristics instead of relying on brittle selectors.
    """
    reviews: List[Dict[str, Any]] = []

    # Common structure: review containers with role="listitem" under a reviews list
    review_candidates = soup.find_all(attrs={"aria-label": lambda v: v and "stars" in v})
    seen = 0

    for candidate in review_candidates:
        # Move up to a container with text content
        container = candidate.parent
        if not container:
            continue

        try:
            rating_text = candidate["aria-label"]
            rating_value = None
            for token in rating_text.split():
                try:
                    rating_value = float(token)
                    break
                except ValueError:
                    continue
        except Exception:  # noqa: BLE001
            rating_value = None

        # Username often appears nearby as a strong/bold/spans
        user_name = None
        for possible in container.find_all(["span", "div"]):
            txt = possible.get_text(strip=True)
            if txt and "stars" not in txt.lower() and len(txt.split()) <= 4:
                user_name = txt
                break

        # Review text: longest paragraph-like block under container
        review_text = ""
        longest = 0
        for possible in container.find_all(["span", "div", "p"]):
            txt = possible.get_text(" ", strip=True)
            if txt and len(txt) > longest and "stars" not in txt.lower():
                longest = len(txt)
                review_text = txt

        if not review_text:
            continue

        reviews.append(
            {
                "userName": user_name or "Unknown",
                "score": rating_value,
                "text": review_text,
                "date": None,
                "version": None,
                "thumbsUp": None,
            }
        )
        seen += 1
        if seen >= max_reviews:
            break

    return reviews

def fetch_app_reviews(
    client: RequestClient,
    app_id: str,
    reviews_url: str,
    language: str = "en_US",
    max_reviews: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetch reviews for an app.

    For simplicity and robustness, this implementation scrapes reviews from the
    public app detail page. It aims to capture a useful subset of reviews even
    when the underlying HTML structure changes.
    """
    params = {"id": app_id, "hl": language}
    logger.debug("Requesting reviews for %s from %s", app_id, reviews_url)
    response = client.get(reviews_url, params=params)
    soup = BeautifulSoup(response.text, "html.parser")

    reviews = _parse_reviews_from_page(soup, max_reviews=max_reviews)
    if not reviews:
        logger.info("No reviews parsed from app page for %s.", app_id)

    logger.debug("Parsed %d reviews for %s", len(reviews), app_id)
    return reviews