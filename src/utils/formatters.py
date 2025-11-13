from copy import deepcopy
from typing import Any, Dict, List

def merge_app_and_reviews(
app_details: Dict[str, Any],
reviews: List[Dict[str, Any]],
) -> Dict[str, Any]:
"""
Combine app-level details with a list of review objects into a single record.
"""
record = deepcopy(app_details)
record["reviews"] = reviews
record["reviewsCount"] = len(reviews)
return record