from __future__ import annotations

import shutil
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlunparse, urldefrag, urljoin, urlparse
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from app.config import settings
from app.models import CrawlResult, DownloadedAsset
from app.scraper.browser import PlaywrightUnavailableError, fetch_with_playwright
from app.scraper.classifier import DOWNLOAD_EXTENSIONS, classify_document, looks_like_project
from app.scraper.html import parse_html
from app.scraper.listing_extractor import extract_listing_projects
from app.scraper.sitemap_extractor import extract_sitemap_projects
from app.scraper.extractor import extract_builder_name, extract_images, extract_project
from app.scraper.google_sheets import sync_crawl_to_google_sheets
from app.scraper.storage import persist_result, write_json
from app.scraper.utils import domain_slug, sha256_bytes, slugify, unique_path


class RealEstateCrawler:
    def __init__(self, data_root: Path | None = None, max_pages: int | None = None) -> None:
        self.data_root = data_root or settings.data_root
        self.max_pages = max_pages or settings.max_pages_per_crawl

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
        errors: list[dict[str, str]] = []
        downloads: list[DownloadedAsset] = []
        projects = []
        all_images = []
        builder_name = domain_slug(start_url).replace("_", " ").title()
        seen: set[str] = set()
        pagination_urls: list[str] = []
        page_sources: dict[str, str] = {start_url: "seed"}
        queue: deque[str] = deque([start_url])
        for entrypoint in self._site_entrypoints(start_url):
            page_sources.setdefault(entrypoint, "sitemap")
            queue.append(entrypoint)
        while queue and len(seen) < self.max_pages:
            url = queue.popleft()
            page_source = page_sources.get(url, "internal")
            if url in seen or not self._is_internal(url, domain):
                continue
            seen.add(url)
            try:
                fetched_url, content_type, body = self._fetch(url)
            except (HTTPError, URLError, TimeoutError) as exc:
                errors.append({"url": url, "error": str(exc)})
                continue
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
            for link in soup.find_all("a", href=True):
                href = urldefrag(urljoin(fetched_url, link.get("href"))).url
                if not href.startswith(("http://", "https://")):
                    continue
                ext = Path(urlparse(href).path).suffix.lower()
                if ext in DOWNLOAD_EXTENSIONS:
                    try:
                        _, _, doc_body = self._fetch(href)
                    except (HTTPError, URLError, TimeoutError) as exc:
                        errors.append({"url": href, "error": str(exc)})
                        continue
                    category = classify_document(href, link.get_text(" ", strip=True))
                    target_dir = (download_dir / category) if use_filesystem else None
                    downloads.append(self._store_download(target_dir, href, fetched_url, doc_body, category))
                elif self._is_internal(href, domain) and href not in seen:
                    if self._is_pagination_link(link, href):
                        pagination_urls.append(href)
                        page_sources[href] = "pagination"
                    else:
                        page_sources.setdefault(href, "internal")
                    queue.append(href)
            for href in self._pagination_candidates(fetched_url):
                if self._is_internal(href, domain) and href not in seen and href not in queue and len(pagination_urls) < settings.max_pagination_pages:
                    pagination_urls.append(href)
                    page_sources[href] = "pagination"
                    queue.append(href)
            sitemap_projects = extract_sitemap_projects(fetched_url, soup, builder_name)
            listing_projects = extract_listing_projects(fetched_url, soup, builder_name)
            if sitemap_projects:
                projects.extend(sitemap_projects)
            elif listing_projects:
                projects.extend(listing_projects)
            elif looks_like_project(fetched_url, soup):
                project = extract_project(fetched_url, soup, builder_name)
                projects.append(project)
        if use_filesystem:
            write_json(root / "images.json", all_images)
            if pagination_urls:
                write_json(root / "pagination.json", {"discovered": sorted(set(pagination_urls)), "total": len(set(pagination_urls))})
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

    def _fetch(self, url: str) -> tuple[str, str, bytes]:
        headers = self._request_headers(url)
        if settings.use_playwright:
            try:
                result = fetch_with_playwright(
                    url,
                    headers,
                    settings.request_timeout_seconds,
                    settings.playwright_headless,
                    settings.playwright_proxy,
                    settings.playwright_slow_mo_ms,
                )
                return result.final_url, result.content_type, result.body
            except PlaywrightUnavailableError:
                pass
        request = Request(url, headers=headers)
        with urlopen(request, timeout=settings.request_timeout_seconds) as response:
            return response.geturl(), response.headers.get("content-type", ""), response.read()

    def _request_headers(self, url: str) -> dict[str, str]:
        return {
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": settings.accept_language,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": settings.request_referer,
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    def _pagination_candidates(self, url: str) -> list[str]:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        candidates: list[str] = []
        for key in ("page", "paged", "p"):
            if key not in query:
                continue
            current = int(query[key][0]) if query[key][0].isdigit() else 1
            if current < settings.max_pagination_pages:
                next_query = {k: v[:] for k, v in query.items()}
                next_query[key] = [str(current + 1)]
                candidates.append(urlunparse(parsed._replace(query=urlencode(next_query, doseq=True))))
        return candidates

    def _is_pagination_link(self, link: object, href: str) -> bool:
        label = " ".join(str(value) for value in (link.get("rel"), link.get("class"), link.get_text(" ", strip=True), href)).lower()
        return any(token in label for token in ("next", "pagination", "page/", "paged=", "page="))

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

    def _site_entrypoints(self, start_url: str) -> list[str]:
        parsed = urlparse(start_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return [urljoin(base, "/site-map/")]

    def _is_internal(self, url: str, domain: str) -> bool:
        return urlparse(url).netloc.replace("www.", "") == domain.replace("www.", "")
