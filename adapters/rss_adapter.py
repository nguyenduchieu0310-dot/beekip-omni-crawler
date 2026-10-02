import email.utils
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from adapters.base_adapter import BaseSourceAdapter, DiscoveredItem, DownloadCandidate
from adapters.link_extractor import extract_candidates_from_html
from core.config import DEFAULT_USER_AGENT
from core.rate_limiter import global_rate_limiter

logger = logging.getLogger("beekip.adapter.rss")

class RSSAdapter(BaseSourceAdapter):
    """Adapter for RSS 2.0 / Atom XML feeds with automatic WordPress REST API and HTML fallbacks."""

    def __init__(self, source_info: Dict[str, Any]):
        super().__init__(source_info)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.wp_api_url = f"https://{self.domain}/wp-json/wp/v2/posts"

    def _parse_pubdate(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = date_str.strip()
        try:
            parsed_tuple = email.utils.parsedate_to_datetime(date_str)
            return parsed_tuple.astimezone(timezone.utc)
        except Exception:
            pass

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            pass

        match = re.search(r'\b(202[3-9]|20[12]\d)\b', date_str)
        if match:
            return datetime(int(match.group(1)), 1, 1, tzinfo=timezone.utc)

        return None

    def fetch_latest_posts(
        self,
        since_timestamp: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ) -> List[DiscoveredItem]:
        """Fetch latest posts using ETag / Last-Modified or WP REST API fallback."""
        headers: Dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        global_rate_limiter.wait_if_needed(self.domain)

        try:
            resp = self.session.get(self.feed_url, headers=headers, timeout=20)
            if resp.status_code == 304:
                logger.info("Source [%s] returned 304 Not Modified.", self.source_id)
                return []

            if resp.status_code == 200:
                self.source_info["_last_etag"] = resp.headers.get("ETag")
                self.source_info["_last_modified"] = resp.headers.get("Last-Modified")

                content_type = resp.headers.get("Content-Type", "")
                # If XML content returned, parse it
                if "xml" in content_type:
                    parsed = self._parse_feed_xml(resp.text)
                    if parsed:
                        return parsed

            # If XML was empty, failed, or feed returned HTML: try WP REST API
            wp_items = self._try_wp_rest()
            if wp_items:
                return wp_items

            # Fallback: parse HTML page links if feed returned HTML
            if resp.status_code == 200:
                return self._parse_html_links(resp.text)

            return []

        except Exception as e:
            logger.error("Error fetching RSS feed [%s]: %s", self.source_id, e)
            return self._try_wp_rest()

    def _try_wp_rest(self) -> List[DiscoveredItem]:
        """Attempt to fetch recent articles via WordPress REST API."""
        try:
            wp_resp = self.session.get(f"{self.wp_api_url}?per_page=20", timeout=15)
            if wp_resp.status_code == 200 and "application/json" in wp_resp.headers.get("Content-Type", ""):
                posts = wp_resp.json()
                items = []
                for p in posts:
                    link = p.get("link", "")
                    raw_title = p.get("title", {}).get("rendered", "")
                    title = html.unescape(raw_title).strip()
                    date_str = p.get("date_gmt") or p.get("date")
                    dt = self._parse_pubdate(date_str)
                    year = dt.year if dt else None

                    if link:
                        items.append(
                            DiscoveredItem(
                                url=link,
                                source_id=self.source_id,
                                title=title,
                                published_at=date_str,
                                published_year=year,
                                raw_metadata={"content_preview": p.get("content", {}).get("rendered", "")[:2000]}
                            )
                        )
                logger.info("WP REST API success for [%s]: fetched %s items", self.source_id, len(items))
                return items
        except Exception:
            pass
        return []

    def _parse_html_links(self, html_text: str) -> List[DiscoveredItem]:
        """Fallback for custom CMS pages serving HTML instead of XML."""
        soup = BeautifulSoup(html_text, "html.parser")
        items: List[DiscoveredItem] = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)
            if len(title) < 15 or not href.startswith("http"):
                continue

            # Skip utility navigation links
            if any(term in href.lower() for term in ["login", "register", "chuyen-muc", "category", "tag"]):
                continue

            if href not in seen:
                seen.add(href)
                year = None
                match = re.search(r'\b(202[3-9]|20[12]\d)\b', title + " " + href)
                if match:
                    year = int(match.group(1))

                items.append(
                    DiscoveredItem(
                        url=href,
                        source_id=self.source_id,
                        title=title,
                        published_year=year
                    )
                )
                if len(items) >= 25:
                    break

        return items

    def _parse_feed_xml(self, xml_content: str) -> List[DiscoveredItem]:
        # Try strict ElementTree first
        try:
            root = ET.fromstring(xml_content)
            channel = root.find("channel")
            if channel is not None:
                items = []
                for item in channel.findall("item"):
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    pub_date_str = item.findtext("pubDate")
                    dt = self._parse_pubdate(pub_date_str)
                    if link:
                        items.append(
                            DiscoveredItem(
                                url=link,
                                source_id=self.source_id,
                                title=html.unescape(title),
                                published_at=dt.isoformat() if dt else None,
                                published_year=dt.year if dt else None
                            )
                        )
                if items:
                    return items
        except Exception:
            pass

        # Resilient BeautifulSoup XML parsing
        try:
            soup = BeautifulSoup(xml_content, "xml")
            items = []
            for item in soup.find_all("item"):
                title_tag = item.find("title")
                link_tag = item.find("link")
                pubdate_tag = item.find("pubDate")

                link = link_tag.get_text(strip=True) if link_tag else ""
                title = title_tag.get_text(strip=True) if title_tag else ""
                pub_date_str = pubdate_tag.get_text(strip=True) if pubdate_tag else ""
                dt = self._parse_pubdate(pub_date_str)

                if link:
                    items.append(
                        DiscoveredItem(
                            url=link,
                            source_id=self.source_id,
                            title=html.unescape(title),
                            published_at=dt.isoformat() if dt else None,
                            published_year=dt.year if dt else None
                        )
                    )
            return items
        except Exception as e:
            logger.error("XML parse error on [%s]: %s", self.source_id, e)
            return []

    def fetch_historical_archive(
        self,
        from_year: int = 2023,
        max_pages: int = 50
    ) -> Generator[DiscoveredItem, None, None]:
        # If WP REST API works, page through WP REST API
        for page in range(1, max_pages + 1):
            try:
                resp = self.session.get(f"{self.wp_api_url}?per_page=50&page={page}", timeout=15)
                if resp.status_code == 200:
                    posts = resp.json()
                    if not posts:
                        break
                    for p in posts:
                        link = p.get("link", "")
                        raw_title = p.get("title", {}).get("rendered", "")
                        title = html.unescape(raw_title).strip()
                        date_str = p.get("date_gmt") or p.get("date")
                        dt = self._parse_pubdate(date_str)
                        year = dt.year if dt else None

                        if year and year < from_year:
                            return

                        if link:
                            yield DiscoveredItem(
                                url=link,
                                source_id=self.source_id,
                                title=title,
                                published_at=date_str,
                                published_year=year
                            )
                else:
                    break
            except Exception:
                break

    def extract_download_links(self, post_url: str, html_content: Optional[str] = None) -> List[DownloadCandidate]:
        if html_content is None:
            global_rate_limiter.wait_if_needed(self.domain)
            try:
                resp = self.session.get(post_url, timeout=20)
                if resp.status_code != 200:
                    return []
                html_content = resp.text
            except Exception as e:
                logger.error("Failed to fetch post HTML [%s]: %s", post_url, e)
                return []

        return extract_candidates_from_html(post_url, html_content)
