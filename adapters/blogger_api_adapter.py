import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
import requests

from adapters.base_adapter import BaseSourceAdapter, DiscoveredItem, DownloadCandidate
from adapters.link_extractor import extract_candidates_from_html
from core.config import DEFAULT_USER_AGENT
from core.rate_limiter import global_rate_limiter

logger = logging.getLogger("beekip.adapter.blogger")

class BloggerAPIAdapter(BaseSourceAdapter):
    """Adapter for Google Blogger JSON API feeds (e.g., MathVN)."""

    def __init__(self, source_info: Dict[str, Any]):
        super().__init__(source_info)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[DiscoveredItem]:
        title = entry.get("title", {}).get("$t", "").strip()

        # Find alternate link
        post_url = None
        for link in entry.get("link", []):
            if link.get("rel") == "alternate":
                post_url = link.get("href")
                break

        if not post_url:
            return None

        published_str = entry.get("published", {}).get("$t", "")
        year = None
        if published_str:
            try:
                dt = datetime.fromisoformat(published_str)
                year = dt.year
            except Exception:
                match = re.search(r'\b(202[3-9]|20[12]\d)\b', published_str)
                if match:
                    year = int(match.group(1))

        content_html = entry.get("content", {}).get("$t", "")

        return DiscoveredItem(
            url=post_url,
            source_id=self.source_id,
            title=title,
            published_at=published_str,
            published_year=year,
            raw_metadata={"content_html": content_html}
        )

    def fetch_latest_posts(
        self,
        since_timestamp: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ) -> List[DiscoveredItem]:
        """Fetch latest posts via Blogger JSON feed."""
        headers: Dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        global_rate_limiter.wait_if_needed(self.domain)

        url = self.feed_url
        if "max-results" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}max-results=30"

        try:
            resp = self.session.get(url, headers=headers, timeout=20)
            if resp.status_code == 304:
                return []

            if resp.status_code != 200:
                logger.warning("Blogger API [%s] returned HTTP %s", self.source_id, resp.status_code)
                return []

            data = resp.json()
            entries = data.get("feed", {}).get("entry", [])
            items = []
            for entry in entries:
                parsed = self._parse_entry(entry)
                if parsed:
                    items.append(parsed)
            return items

        except Exception as e:
            logger.error("Error fetching Blogger JSON [%s]: %s", self.source_id, e)
            return []

    def fetch_historical_archive(
        self,
        from_year: int = 2023,
        max_pages: int = 50
    ) -> Generator[DiscoveredItem, None, None]:
        """Page backwards using Blogger start-index pagination."""
        start_index = 1
        page_size = 50
        stop_crawling = False

        for _ in range(max_pages):
            if stop_crawling:
                break

            sep = "&" if "?" in self.feed_url else "?"
            paged_url = f"{self.feed_url}{sep}start-index={start_index}&max-results={page_size}"
            global_rate_limiter.wait_if_needed(self.domain)

            try:
                resp = self.session.get(paged_url, timeout=20)
                if resp.status_code != 200:
                    break

                data = resp.json()
                entries = data.get("feed", {}).get("entry", [])
                if not entries:
                    break

                for entry in entries:
                    parsed = self._parse_entry(entry)
                    if parsed:
                        if parsed.published_year and parsed.published_year < from_year:
                            stop_crawling = True
                            break
                        yield parsed

                start_index += page_size

            except Exception as e:
                logger.error("Error paging Blogger archive [%s]: %s", self.source_id, e)
                break

    def extract_download_links(self, post_url: str, html_content: Optional[str] = None) -> List[DownloadCandidate]:
        """Extract candidate download files from post content."""
        if html_content is None:
            global_rate_limiter.wait_if_needed(self.domain)
            try:
                resp = self.session.get(post_url, timeout=20)
                if resp.status_code != 200:
                    return []
                html_content = resp.text
            except Exception as e:
                logger.error("Error fetching article [%s]: %s", post_url, e)
                return []

        return extract_candidates_from_html(post_url, html_content)
