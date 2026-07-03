from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.scraper.crawler import RealEstateCrawler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the BhumiBazar scraper from the command line and write TXT outputs."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Builder/project website URL to scrape. If omitted, you will be prompted for it.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Directory where SCRAPED_DATA-style output should be written.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional maximum number of pages to crawl for this run.",
    )
    return parser


def resolve_url(provided_url: str | None) -> str:
    url = provided_url or input("Enter website URL to scrape: ").strip()
    if not url:
        raise ValueError("A website URL is required.")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        url = resolve_url(args.url)
        result = RealEstateCrawler(data_root=args.data_root, max_pages=args.max_pages).crawl(url)
    except KeyboardInterrupt:
        print("Scrape cancelled by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Scrape failed: {exc}", file=sys.stderr)
        return 1

    payload = result.latest_payload()
    print(f"Scrape status: {payload['status']}")
    print(f"Pages scraped: {payload['total_pages']}")
    print(f"Projects found: {payload['total_projects']}")
    print(f"Downloads found: {payload['total_downloads']}")
    print(f"TXT output: {result.output_path / 'all_scraped_data.txt'}")
    return 0 if payload["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
