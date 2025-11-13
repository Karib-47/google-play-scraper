import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from extractors.app_details import fetch_app_details
from extractors.reviews_parser import fetch_app_reviews
from extractors.categories_parser import search_apps_by_keyword, fetch_category_top_apps
from utils.request_client import RequestClient
from utils.validators import (
    validate_app_ids,
    validate_output_format,
    validate_mode,
)
from utils.formatters import merge_app_and_reviews
from outputs.writer_json import write_json
from outputs.writer_csv import write_csv
from outputs.writer_excel import write_excel

CONFIG_RELATIVE_PATH = Path("src/config/settings.example.json")

def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_config(root_dir: Path) -> Dict[str, Any]:
    config_path = root_dir / CONFIG_RELATIVE_PATH
    if not config_path.exists():
        logging.warning("Config file %s not found, using defaults.", config_path)
        return {
            "mode": "app_ids",
            "input_app_ids_file": "data/sample_app_ids.txt",
            "output_dir": "data",
            "output_format": "json",
            "language": "en_US",
            "max_apps": 50,
            "max_reviews_per_app": 50,
            "base_url": "https://play.google.com/store/apps/details",
            "reviews_url": "https://play.google.com/store/apps/details",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data

def resolve_paths(root_dir: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = config.copy()
    input_path = cfg.get("input_app_ids_file", "data/sample_app_ids.txt")
    output_dir = cfg.get("output_dir", "data")

    cfg["input_app_ids_file"] = str(root_dir / input_path)
    cfg["output_dir"] = str(root_dir / output_dir)
    return cfg

def read_app_ids(file_path: Path, max_apps: int) -> List[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"App IDs file not found: {file_path}")

    app_ids: List[str] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            app_id = line.strip()
            if app_id:
                app_ids.append(app_id)
            if len(app_ids) >= max_apps:
                break

    validate_app_ids(app_ids)
    return app_ids

def build_client(user_agent: str) -> RequestClient:
    return RequestClient(user_agent=user_agent)

def run_with_app_ids(
    client: RequestClient,
    cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    app_ids = read_app_ids(
        Path(cfg["input_app_ids_file"]), cfg.get("max_apps", 50)
    )

    language = cfg.get("language", "en_US")
    base_url = cfg.get("base_url")
    reviews_url = cfg.get("reviews_url", base_url)
    max_reviews_per_app = cfg.get("max_reviews_per_app", 50)

    results: List[Dict[str, Any]] = []
    for idx, app_id in enumerate(app_ids, start=1):
        logging.info("Processing app %d/%d: %s", idx, len(app_ids), app_id)
        try:
            details = fetch_app_details(
                client=client,
                app_id=app_id,
                base_url=base_url,
                language=language,
            )
            reviews = fetch_app_reviews(
                client=client,
                app_id=app_id,
                reviews_url=reviews_url,
                language=language,
                max_reviews=max_reviews_per_app,
            )
            record = merge_app_and_reviews(details, reviews)
            results.append(record)
        except Exception as e:  # noqa: BLE001
            logging.exception("Failed to fetch data for app %s: %s", app_id, e)

    return results

def run_with_keyword_search(
    client: RequestClient,
    cfg: Dict[str, Any],
    keyword: str,
) -> List[Dict[str, Any]]:
    logging.info("Searching apps by keyword: %s", keyword)
    language = cfg.get("language", "en_US")
    max_apps = cfg.get("max_apps", 50)
    base_url = cfg.get("base_url")
    search_results = search_apps_by_keyword(
        client=client,
        keyword=keyword,
        max_results=max_apps,
        language=language,
    )

    app_ids = [item["appId"] for item in search_results]
    cfg_local = cfg.copy()
    cfg_local["max_apps"] = len(app_ids)

    # Temporarily write app IDs to process them with shared logic
    tmp_app_ids_path = Path(cfg["output_dir"]) / "tmp_keyword_app_ids.txt"
    tmp_app_ids_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_app_ids_path.open("w", encoding="utf-8") as f:
        for app_id in app_ids:
            f.write(app_id + "\n")

    cfg_local["input_app_ids_file"] = str(tmp_app_ids_path)
    return run_with_app_ids(client, cfg_local)

def run_with_category(
    client: RequestClient,
    cfg: Dict[str, Any],
    category_id: str,
) -> List[Dict[str, Any]]:
    logging.info("Fetching apps for category: %s", category_id)
    language = cfg.get("language", "en_US")
    max_apps = cfg.get("max_apps", 50)

    search_results = fetch_category_top_apps(
        client=client,
        category_id=category_id,
        max_results=max_apps,
        language=language,
    )

    app_ids = [item["appId"] for item in search_results]
    cfg_local = cfg.copy()
    cfg_local["max_apps"] = len(app_ids)

    tmp_app_ids_path = Path(cfg["output_dir"]) / "tmp_category_app_ids.txt"
    tmp_app_ids_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_app_ids_path.open("w", encoding="utf-8") as f:
        for app_id in app_ids:
            f.write(app_id + "\n")

    cfg_local["input_app_ids_file"] = str(tmp_app_ids_path)
    return run_with_app_ids(client, cfg_local)

def write_output(
    records: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    output_format: str,
) -> Path:
    validate_output_format(output_format)
    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"google_play_data.{output_format if output_format != 'excel' else 'xlsx'}"

    if output_format == "json":
        write_json(records, output_path)
    elif output_format == "csv":
        write_csv(records, output_path)
    elif output_format == "excel":
        write_excel(records, output_path)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    logging.info("Wrote %d records to %s", len(records), output_path)
    return output_path

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Play Scraper - extract app details and reviews from Google Play Store."
    )
    parser.add_argument(
        "--mode",
        choices=["app_ids", "keyword", "category"],
        help="Scraping mode: app_ids, keyword, or category (overrides config).",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        help="Keyword for search mode.",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Category ID for category mode (e.g., APPLICATION, GAME_ARCADE).",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "csv", "excel"],
        help="Output format (overrides config).",
    )
    parser.add_argument(
        "--max-apps",
        type=int,
        help="Maximum number of apps to process.",
    )
    parser.add_argument(
        "--max-reviews-per-app",
        type=int,
        help="Maximum reviews to fetch per app.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv).",
    )
    return parser.parse_args(argv)

def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)
    setup_logging(args.verbose)

    root_dir = Path(__file__).resolve().parents[1]
    raw_config = load_config(root_dir)
    config = resolve_paths(root_dir, raw_config)

    if args.max_apps is not None:
        config["max_apps"] = args.max_apps
    if args.max_reviews_per_app is not None:
        config["max_reviews_per_app"] = args.max_reviews_per_app
    if args.output_format:
        config["output_format"] = args.output_format

    mode = args.mode or config.get("mode", "app_ids")
    validate_mode(mode)

    user_agent = config.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
    )

    client = build_client(user_agent=user_agent)

    if mode == "app_ids":
        records = run_with_app_ids(client, config)
    elif mode == "keyword":
        keyword = args.keyword or config.get("keyword")
        if not keyword:
            raise ValueError("Keyword mode requires a --keyword argument or 'keyword' in config.")
        records = run_with_keyword_search(client, config, keyword)
    elif mode == "category":
        category_id = args.category or config.get("category_id")
        if not category_id:
            raise ValueError("Category mode requires a --category argument or 'category_id' in config.")
        records = run_with_category(client, config, category_id)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    if not records:
        logging.warning("No records scraped. Exiting.")
        return 1

    output_format = config.get("output_format", "json")
    write_output(records, config, output_format)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())