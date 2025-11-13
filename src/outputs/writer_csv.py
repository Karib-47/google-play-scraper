import csv
import json
from pathlib import Path
from typing import Any, Dict, List

def _flatten_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested record so that it can be stored in a single CSV row.

    Reviews are serialized as JSON to keep the structure intact.
    """
    flat: Dict[str, Any] = {}
    for key, value in record.items():
        if key == "reviews":
            flat[key] = json.dumps(value, ensure_ascii=False)
        else:
            flat[key] = value
    return flat

def write_csv(records: List[Dict[str, Any]], output_path: Path) -> None:
    if not records:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["message"])
            writer.writerow(["No records to write."])
        return

    flat_records = [_flatten_record(r) for r in records]
    fieldnames = sorted(flat_records[0].keys())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in flat_records:
            writer.writerow(row)