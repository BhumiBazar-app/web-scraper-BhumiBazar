from __future__ import annotations

from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urldefrag, urljoin, urlparse, urlunparse

from app.config import settings
from app.scraper.classifier import DOWNLOAD_EXTENSIONS


class UrlDiscovery:
    """Track crawl queues, internal URLs, document URLs, and pagination candidates."""

    def __init__(self, start_url: str) -> None:
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.seen: set[str] = set()
        self.queued: set[str] = {start_url}
        self.queue: deque[str] = deque([start_url])
        self.page_sources: dict[str, str] = {start_url: "seed"}
        self.pagination_urls: list[str] = []

    def next_url(self) -> str | None:
        while self.queue:
            url = self.queue.popleft()
            self.queued.discard(url)
            if url not in self.seen and self.is_internal(url):
                self.seen.add(url)
                return url
        return None

    def add_page_link(self, href: str, source: str = "internal") -> None:
        if href in self.seen or href in self.queued or not self.is_internal(href):
            return
        self.page_sources.setdefault(href, source)
        self.queue.append(href)
        self.queued.add(href)

    def add_pagination_link(self, href: str) -> None:
        if len(set(self.pagination_urls)) >= settings.max_pagination_pages:
            return
        self.pagination_urls.append(href)
        self.add_page_link(href, "pagination")

    def links_from_soup(self, soup: object, base_url: str) -> tuple[list[tuple[str, object]], list[tuple[str, object]]]:
        page_links: list[tuple[str, object]] = []
        download_links: list[tuple[str, object]] = []
        for link in soup.find_all("a", href=True):
            href = urldefrag(urljoin(base_url, link.get("href"))).url
            if not href.startswith(("http://", "https://")):
                continue
            ext = Path(urlparse(href).path).suffix.lower()
            if ext in DOWNLOAD_EXTENSIONS:
                download_links.append((href, link))
            elif self.is_internal(href):
                page_links.append((href, link))
        return page_links, download_links

    def pagination_candidates(self, url: str) -> list[str]:
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

    def is_pagination_link(self, link: object, href: str) -> bool:
        label = " ".join(str(value) for value in (link.get("rel"), link.get("class"), link.get_text(" ", strip=True), href)).lower()
        return any(token in label for token in ("next", "pagination", "page/", "paged=", "page="))

    def is_internal(self, url: str) -> bool:
        return urlparse(url).netloc.replace("www.", "") == self.domain.replace("www.", "")
