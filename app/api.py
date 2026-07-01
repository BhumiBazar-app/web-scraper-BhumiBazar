from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from app.scraper.crawler import RealEstateCrawler

app = FastAPI(title="Bhumi AI Real Estate Scraper Engine", version="0.1.0")


class CrawlRequest(BaseModel):
    url: HttpUrl


class CrawlResponse(BaseModel):
    website_id: str
    builder_name: str
    domain: str
    crawl_id: str
    status: str
    total_pages: int
    total_projects: int
    total_downloads: int
    output_path: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/crawl", response_model=CrawlResponse)
def crawl_site(payload: CrawlRequest) -> CrawlResponse:
    try:
        result = RealEstateCrawler().crawl(str(payload.url))
    except Exception as exc:  # FastAPI boundary: convert unexpected crawler errors to API errors.
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    latest = result.latest_payload()
    return CrawlResponse(**latest, output_path=str(result.output_path))


@app.post("/crawl/background")
def crawl_site_background(payload: CrawlRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(RealEstateCrawler().crawl, str(payload.url))
    return {"status": "queued", "url": str(payload.url)}
