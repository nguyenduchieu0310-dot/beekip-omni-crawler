import logging
import re
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from adapters.base_adapter import BaseSourceAdapter, DiscoveredItem, DownloadCandidate
from adapters.link_extractor import extract_candidates_from_html
from core.config import DEFAULT_USER_AGENT
from core.rate_limiter import global_rate_limiter

logger = logging.getLogger("beekip.adapter.html")

class HTMLSpiderAdapter(BaseSourceAdapter):
    """Adapter for websites requiring HTML DOM polling (e.g., Thư Viện Vật Lý moi.php, VnDoc)."""

    def __init__(self, source_info: Dict[str, Any]):
        super().__init__(source_info)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def fetch_latest_posts(
        self,
        since_timestamp: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ) -> List[DiscoveredItem]:
        """Poll the recent documents page for newly listed items."""
        global_rate_limiter.wait_if_needed(self.domain)
        try:
            resp = self.session.get(self.feed_url, timeout=25)
            if resp.status_code != 200:
                logger.warning("HTML Poll [%s] returned HTTP %s", self.source_id, resp.status_code)
                return []

            return self._parse_listing_page(resp.text)

        except Exception as e:
            logger.error("Error polling HTML [%s]: %s", self.source_id, e)
            return []

    def _parse_listing_page(self, html: str) -> List[DiscoveredItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: List[DiscoveredItem] = []
        seen_urls = set()

        # Find all article/document links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)
            if not href or len(title) < 10:
                continue

            full_url = urljoin(self.feed_url, href)
            if full_url in seen_urls:
                continue

            # Filter out non-article navigational links
            lower_url = full_url.lower()
            if any(term in lower_url for term in ["login", "register", "logout", "contact", "about", "chinh-sach"]):
                continue

            year = None
            match = re.search(r'\b(202[3-9]|20[12]\d)\b', title + " " + full_url)
            if match:
                year = int(match.group(1))

            seen_urls.add(full_url)
            items.append(
                DiscoveredItem(
                    url=full_url,
                    source_id=self.source_id,
                    title=title,
                    published_year=year
                )
            )

        return items

    def fetch_historical_archive(
        self,
        from_year: int = 2023,
        max_pages: int = 30
    ) -> Generator[DiscoveredItem, None, None]:
        """Page through listings or sitemap for historical backfill."""
        sitemap_url = self.source_info.get("sitemap_url")
        if sitemap_url:
            from adapters.sitemap_adapter import SitemapAdapter
            sm_adapter = SitemapAdapter(self.source_info)
            yield from sm_adapter.fetch_historical_archive(from_year=from_year, max_pages=max_pages)
            return

        yield from self.fetch_latest_posts()

    def extract_download_links(self, post_url: str, html_content: Optional[str] = None) -> List[DownloadCandidate]:
        """Fetch post HTML and extract candidate download files."""
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
