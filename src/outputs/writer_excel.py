from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

def write_excel(records: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Write records into an Excel file with two sheets:
    - apps: one row per app
    - reviews: one row per individual review with appId back-reference
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not records:
        # Create an empty workbook with a note
        df_empty = pd.DataFrame([{"message": "No records to write."}])
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_empty.to_excel(writer, sheet_name="info", index=False)
        return

    apps_rows: List[Dict[str, Any]] = []
    reviews_rows: List[Dict[str, Any]] = []

    for record in records:
        app_copy = {k: v for k, v in record.items() if k != "reviews"}
        apps_rows.append(app_copy)

        for review in record.get("reviews", []):
            row = {"appId": record.get("appId")}
            row.update(review)
            reviews_rows.append(row)

    apps_df = pd.DataFrame(apps_rows)
    reviews_df = pd.DataFrame(reviews_rows) if reviews_rows else pd.DataFrame(
        columns=["appId", "userName", "score", "text", "date", "version", "thumbsUp"]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        apps_df.to_excel(writer, sheet_name="apps", index=False)
        reviews_df.to_excel(writer, sheet_name="reviews", index=False)