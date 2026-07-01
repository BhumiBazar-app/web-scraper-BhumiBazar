from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse


def slugify(value: str, fallback: str = "item") -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return value or fallback


def domain_slug(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    host = host.split("@").pop().split(":")[0]
    return slugify(host.replace("www.", ""), "website")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1
