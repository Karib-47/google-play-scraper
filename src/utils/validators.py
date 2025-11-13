from typing import Iterable, List

def validate_app_ids(app_ids: Iterable[str]) -> None:
    app_ids_list: List[str] = [a for a in app_ids if a]
    if not app_ids_list:
        raise ValueError("No app IDs provided. Please supply at least one app ID.")

def validate_output_format(output_format: str) -> None:
    allowed = {"json", "csv", "excel"}
    if output_format not in allowed:
        raise ValueError(f"Invalid output format '{output_format}'. Allowed: {', '.join(sorted(allowed))}.")

def validate_mode(mode: str) -> None:
    allowed = {"app_ids", "keyword", "category"}
    if mode not in allowed:
        raise ValueError(f"Invalid mode '{mode}'. Allowed: {', '.join(sorted(allowed))}.")