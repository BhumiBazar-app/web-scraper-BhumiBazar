from __future__ import annotations

import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from app.config import settings
from app.models import CrawlResult, DownloadedAsset
from app.scraper.classifier import classify_document, looks_like_project
from app.scraper.html import parse_html
from app.scraper.extractor import extract_builder_name, extract_images, extract_project
from app.scraper.google_sheets import sync_crawl_to_google_sheets
from app.scraper.discovery import UrlDiscovery
from app.scraper.fetcher import PageFetcher
from app.scraper.storage import persist_result, write_json
from app.scraper.utils import domain_slug, sha256_bytes, slugify, unique_path


class RealEstateCrawler:
    def __init__(self, data_root: Path | None = None, max_pages: int | None = None) -> None:
        self.data_root = data_root or settings.data_root
        self.max_pages = max_pages or settings.max_pages_per_crawl
        self.fetcher = PageFetcher()

    def crawl(self, start_url: str) -> CrawlResult:
        started = datetime.now(timezone.utc)
        start_url = self._normalize_start(start_url)
        domain = urlparse(start_url).netloc
        website_id = domain_slug(start_url)
        root = self.data_root / website_id
        crawl_id = self._next_crawl_id(root)
        page_dir = root / "pages"
        download_dir = root / "downloads"
        use_filesystem = self._uses_filesystem_storage()
        use_google_sheets = self._uses_google_sheets_storage()
        if use_filesystem:
            page_dir.mkdir(parents=True, exist_ok=True)
            download_dir.mkdir(parents=True, exist_ok=True)
        pages: list[str] = []
        errors: list[dict[str, object]] = []
        downloads: list[DownloadedAsset] = []
        projects = []
        all_images = []
        builder_name = domain_slug(start_url).replace("_", " ").title()
        discovery = UrlDiscovery(start_url)
        fetch_logs: list[dict[str, object]] = []
        while len(discovery.seen) < self.max_pages:
            url = discovery.next_url()
            if url is None:
                break
            page_source = discovery.page_sources.get(url, "internal")
            try:
                fetched_url, content_type, body = self._fetch(url)
            except Exception as exc:
                errors.append(self._crawl_error(url, exc))
                continue
            fetch_logs.append(getattr(self, "_last_fetch_log", {}))
            if "text/html" not in content_type:
                asset = self._store_download(download_dir if use_filesystem else None, url, url, body, "documents")
                downloads.append(asset)
                continue
            html = body.decode("utf-8", errors="replace")
            pages.append(fetched_url)
            soup = parse_html(html)
            if len(pages) == 1:
                builder_name = extract_builder_name(start_url, soup)
            if use_filesystem:
                page_bucket = page_dir / ("paginated" if page_source == "pagination" else "standard")
                page_bucket.mkdir(parents=True, exist_ok=True)
                page_path = page_bucket / f"{slugify(urlparse(fetched_url).path or 'home')}.html"
                page_path = unique_path(page_path)
                page_path.write_text(html, encoding="utf-8")
            images = extract_images(fetched_url, soup)
            all_images.extend(asdict(image) for image in images)
            page_links, download_links = discovery.links_from_soup(soup, fetched_url)
            for href, link in download_links:
                try:
                    _, _, doc_body = self._fetch(href)
                    fetch_logs.append(getattr(self, "_last_fetch_log", {}))
                except Exception as exc:
                    errors.append(self._crawl_error(href, exc))
                    continue
                category = classify_document(href, link.get_text(" ", strip=True))
                target_dir = (download_dir / category) if use_filesystem else None
                downloads.append(self._store_download(target_dir, href, fetched_url, doc_body, category))
            for href, link in page_links:
                if discovery.is_pagination_link(link, href):
                    discovery.add_pagination_link(href)
                else:
                    discovery.add_page_link(href)
            for href in discovery.pagination_candidates(fetched_url):
                discovery.add_pagination_link(href)
            if looks_like_project(fetched_url, soup):
                project = extract_project(fetched_url, soup, builder_name)
                projects.append(project)
        if use_filesystem:
            write_json(root / "images.json", all_images)
            if discovery.pagination_urls:
                write_json(root / "pagination.json", {"discovered": sorted(set(discovery.pagination_urls)), "total": len(set(discovery.pagination_urls))})
            if fetch_logs:
                write_json(root / "logs" / f"{crawl_id}_fetches.json", fetch_logs)
            if errors:
                write_json(root / "logs" / f"{crawl_id}_errors.json", errors)
        finished = datetime.now(timezone.utc)
        status = "completed" if pages else "failed"
        result = CrawlResult(website_id, builder_name, domain, crawl_id, started.isoformat(), finished.isoformat(), pages, downloads, projects, root, status=status)
        if use_filesystem:
            persist_result(result)
        sheets_status = {"status": "skipped", "reason": "storage backend is filesystem"}
        if use_google_sheets:
            sheets_status = sync_crawl_to_google_sheets(result, write_pending=use_filesystem)
        if use_filesystem:
            write_json(root / "google_sheets_status.json", sheets_status)
            self._snapshot_latest(root, crawl_id)
        return result

    def _crawl_error(self, url: str, exc: Exception) -> dict[str, object]:
        if self.fetcher._is_access_blocked_error(exc):
            return {
                "url": url,
                "error": "Access blocked by the website or current network. Try again from a browser-enabled residential network or configure an allowed proxy.",
                "error_type": "FetchAccessBlockedError",
                "blocked": "true",
            }
        return {"url": url, "error": str(exc), "error_type": type(exc).__name__}

    def _fetch(self, url: str) -> tuple[str, str, bytes]:
        result = self.fetcher.fetch(url)
        self._last_fetch_log = {
            "url": result.url,
            "final_url": result.final_url,
            "status_code": result.status_code,
            "redirect_chain": result.redirect_chain,
            "response_time_seconds": round(result.response_time_seconds, 3),
            "retry_attempts": result.retry_attempts,
            "rendered": result.rendered,
            "rendering_error": result.rendering_error,
            "failure_reason": result.failure_reason,
        }
        if result.failure_reason in {"captcha", "access_blocked", "rate_limited", "rendering_error"}:
            self._last_fetch_log["manual_review"] = True
        return result.final_url, result.content_type, result.body

    def _request_headers(self, url: str) -> dict[str, str]:
        return self.fetcher.request_headers(url)

    def _pagination_candidates(self, url: str) -> list[str]:
        return UrlDiscovery(url).pagination_candidates(url)

    def _is_pagination_link(self, link: object, href: str) -> bool:
        return UrlDiscovery(href).is_pagination_link(link, href)

    def _store_download(self, directory: Path | None, url: str, source_page: str, content: bytes, category: str) -> DownloadedAsset:
        content_hash = sha256_bytes(content)
        if directory is None:
            return DownloadedAsset(url=url, source_page=source_page, path="", category=category, content_hash=content_hash)
        directory.mkdir(parents=True, exist_ok=True)
        parsed_name = Path(urlparse(url).path).name or f"download-{content_hash[:12]}"
        target = unique_path(directory / parsed_name)
        target.write_bytes(content)
        return DownloadedAsset(url=url, source_page=source_page, path=str(target), category=category, content_hash=content_hash)

    def _uses_filesystem_storage(self) -> bool:
        return settings.storage_backend.lower() in {"filesystem", "both"}

    def _uses_google_sheets_storage(self) -> bool:
        return settings.storage_backend.lower() in {"google_sheets", "both"}

    def _snapshot_latest(self, root: Path, crawl_id: str) -> None:
        version_root = root / "versions" / crawl_id
        version_root.mkdir(parents=True, exist_ok=True)
        for name in ("website.json", "latest.json", "crawl_history.json", "sitemap.xml", "master.xlsx", "images.json", "pagination.json", "google_sheets_status.json", "google_sheets_pending.json"):
            source = root / name
            if source.exists():
                shutil.copy2(source, version_root / name)

    def _next_crawl_id(self, root: Path) -> str:
        versions = root / "versions"
        count = len([p for p in versions.glob("crawl_*") if p.is_dir()]) if versions.exists() else 0
        return f"crawl_{count + 1:03d}"

    def _normalize_start(self, url: str) -> str:
        return url if url.startswith(("http://", "https://")) else f"https://{url}"

    def _is_internal(self, url: str, domain: str) -> bool:
        return urlparse(url).netloc.replace("www.", "") == domain.replace("www.", "")
