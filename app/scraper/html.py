from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

try:  # Prefer BeautifulSoup when installed, but keep the scraper runnable with stdlib only.
    from bs4 import BeautifulSoup as _BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover - depends on environment
    _BeautifulSoup = None


class _Node:
    def __init__(self, name: str, attrs: dict[str, str], text: str = "") -> None:
        self.name = name
        self.attrs = attrs
        self._text = text
        self.string = text

    def get(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key, default)

    def get_text(self, separator: str = " ", strip: bool = False) -> str:
        text = self._text
        return text.strip() if strip else text

    def decompose(self) -> None:
        self._text = ""


class _FallbackParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[_Node] = []
        self.images: list[_Node] = []
        self.metas: list[_Node] = []
        self.headings: list[_Node] = []
        self.title: _Node | None = None
        self._current: str | None = None
        self._buffer: list[str] = []

        self._active_link: _Node | None = None
        self._active_link_text: list[str] = []

        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: v or "" for k, v in attrs}
        if tag == "a" and attr_map.get("href"):

            self._active_link = _Node(tag, attr_map)
            self._active_link_text = []
            self.links.append(self._active_link)

            self.links.append(_Node(tag, attr_map))

        elif tag == "img":
            self.images.append(_Node(tag, attr_map))
        elif tag == "meta":
            self.metas.append(_Node(tag, attr_map))
        elif tag in {"title", "h1", "h2"}:
            self._current = tag
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data)
        if self._active_link is not None:
            self._active_link_text.append(data)

        if self._current:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_link is not None:
            self._active_link._text = " ".join(self._active_link_text).strip()
            self._active_link.string = self._active_link._text
            self._active_link = None
            self._active_link_text = []
        if tag in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

        if self._current == tag:
            node = _Node(tag, {}, " ".join(self._buffer).strip())
            if tag == "title":
                self.title = node
            else:
                self.headings.append(node)
            self._current = None
            self._buffer = []


class FallbackSoup:
    def __init__(self, html: str) -> None:
        self.parser = _FallbackParser()
        self.parser.feed(html)
        self.title = self.parser.title

    def __call__(self, names: list[str] | tuple[str, ...]) -> list[_Node]:
        return []

    def get_text(self, separator: str = " ", strip: bool = False) -> str:
        joiner = separator if separator != " " else ""
        text = joiner.join(self.parser.text_parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n+", "\n", text)

        text = separator.join(self.parser.text_parts)
        text = re.sub(r"\s+", " ", text)
        return text.strip() if strip else text

    def find_all(self, name: str, **kwargs: Any) -> list[_Node]:
        if name == "a":
            return self.parser.links
        if name == "img":
            return self.parser.images
        if isinstance(name, (list, tuple, set)):
            return [node for node in self.parser.headings if node.name in name]
        return []

    def find(self, name: Any = None, **kwargs: Any) -> _Node | None:
        if isinstance(name, (list, tuple, set)):
            return next((node for node in self.parser.headings if node.name in name), None)
        if name == "meta":
            prop = kwargs.get("property")
            return next((node for node in self.parser.metas if node.get("property") == prop), None)
        if name == "a":
            href_pattern = kwargs.get("href")
            for node in self.parser.links:
                href = node.get("href", "")
                if hasattr(href_pattern, "search") and href_pattern.search(href):
                    return node
        return None


def parse_html(html: str):
    if _BeautifulSoup is not None:
        return _BeautifulSoup(html, "lxml")
    return FallbackSoup(html)
