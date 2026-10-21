import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
import requests

from adapters.base_adapter import BaseSourceAdapter, DiscoveredItem, DownloadCandidate
from adapters.link_extractor import extract_candidates_from_html
from core.config import DEFAULT_USER_AGENT
from core.rate_limiter import global_rate_limiter

logger = logging.getLogger("beekip.adapter.sitemap")

class SitemapAdapter(BaseSourceAdapter):
    """Adapter for XML Sitemap and Sitemap Index sources."""

    def __init__(self, source_info: Dict[str, Any]):
        super().__init__(source_info)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.sitemap_url = source_info.get("sitemap_url") or self.feed_url

    def _fetch_xml(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
        global_rate_limiter.wait_if_needed(self.domain)
        try:
            resp = self.session.get(url, headers=headers or {}, timeout=25)
            if resp.status_code == 304:
                return None
            if resp.status_code != 200:
                logger.warning("Sitemap fetch failed [%s] status %s", url, resp.status_code)
                return None
            return ET.fromstring(resp.content)
        except Exception as e:
            logger.error("Error fetching/parsing sitemap [%s]: %s", url, e)
            return None

    def fetch_latest_posts(
        self,
        since_timestamp: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ) -> List[DiscoveredItem]:
        """Fetch updated items from sitemap since last sync."""
        root = self._fetch_xml(self.sitemap_url)
        if root is None:
            return []

        discovered: List[DiscoveredItem] = []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # If this is a sitemap index, inspect sub-sitemaps
        sub_sitemaps = root.findall("sm:sitemap", ns) or root.findall("sitemap")
        if sub_sitemaps:
            for sm in sub_sitemaps:
                loc = (sm.findtext("sm:loc", default="", namespaces=ns) or sm.findtext("loc") or "").strip()
                lastmod = (sm.findtext("sm:lastmod", default="", namespaces=ns) or sm.findtext("lastmod") or "").strip()

                # Prioritize post sitemaps
                if loc and any(term in loc.lower() for term in ["post", "bai-viet", "tai-lieu", "document"]):
                    sub_root = self._fetch_xml(loc)
                    if sub_root is not None:
                        discovered.extend(self._parse_urlset(sub_root, since_timestamp))
                        if len(discovered) >= 100:
                            break
        else:
            discovered.extend(self._parse_urlset(root, since_timestamp))

        return discovered

    def _parse_urlset(self, root: ET.Element, since_timestamp: Optional[str] = None) -> List[DiscoveredItem]:
        items: List[DiscoveredItem] = []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        urls = root.findall("sm:url", ns) or root.findall("url")
        for u in urls:
            loc = (u.findtext("sm:loc", default="", namespaces=ns) or u.findtext("loc") or "").strip()
            lastmod = (u.findtext("sm:lastmod", default="", namespaces=ns) or u.findtext("lastmod") or "").strip()

            if not loc:
                continue

            year = None
            if lastmod:
                try:
                    dt = datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
                    year = dt.year
                except Exception:
                    match = re.search(r'\b(202[3-9]|20[12]\d)\b', lastmod)
                    if match:
                        year = int(match.group(1))

            # Infer year from slug if not in lastmod
            if not year:
                match = re.search(r'/(202[3-9])/', loc)
                if match:
                    year = int(match.group(1))

            items.append(
                DiscoveredItem(
                    url=loc,
                    source_id=self.source_id,
                    title="",
                    published_at=lastmod or None,
                    published_year=year
                )
            )

        return items

    def fetch_historical_archive(
        self,
        from_year: int = 2023,
        max_pages: int = 50
    ) -> Generator[DiscoveredItem, None, None]:
        """Traverse sitemap entries and yield documents with year >= from_year."""
        root = self._fetch_xml(self.sitemap_url)
        if root is None:
            return

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sub_sitemaps = root.findall("sm:sitemap", ns) or root.findall("sitemap")

        if sub_sitemaps:
            pages_processed = 0
            for sm in sub_sitemaps:
                if pages_processed >= max_pages:
                    break
                loc = (sm.findtext("sm:loc", default="", namespaces=ns) or sm.findtext("loc") or "").strip()
                if not loc:
                    continue

                # Filter sub-sitemaps (prioritize posts / documents, skip media/tags if possible)
                loc_lower = loc.lower()
                if any(skip_term in loc_lower for skip_term in ["author", "category", "tag", "image"]):
                    continue

                sub_root = self._fetch_xml(loc)
                if sub_root is not None:
                    items = self._parse_urlset(sub_root)
                    for item in items:
                        if item.published_year and item.published_year < from_year:
                            continue
                        yield item
                    pages_processed += 1
        else:
            items = self._parse_urlset(root)
            for item in items:
                if item.published_year and item.published_year < from_year:
                    continue
                yield item

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
