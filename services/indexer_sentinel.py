"""
Indexer Sentinel Connector for Beekip.
Notifies IndexNow (Bing, Yandex, Seznam) and Search Engines immediately upon publication.
Generates Google News Sitemap XML structures.
"""

import json
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("beekip.indexer_sentinel")

INDEXNOW_API_ENDPOINT = "https://api.indexnow.org/indexnow"
DEFAULT_HOST = "tailieu.beekip.vn"
DEFAULT_INDEXNOW_KEY = "beekip-indexnow-prod-2026"


class IndexerSentinel:
    """Instant Search Engine Notification & Indexing Dispatcher."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        indexnow_key: str = DEFAULT_INDEXNOW_KEY,
        timeout: int = 15,
    ):
        self.host = host
        self.key = indexnow_key
        self.key_location = f"https://{self.host}/{self.key}.txt"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Beekip-IndexerSentinel/1.0 (+https://tailieu.beekip.vn)",
            "Content-Type": "application/json; charset=utf-8",
        })

    def notify_indexnow(self, urls: List[str]) -> Dict[str, Any]:
        """
        Notify Bing, Yandex, Seznam instantly via IndexNow API.
        HTTP 200: Submitted OK
        HTTP 202: Accepted for processing
        """
        if not urls:
            return {"success": True, "count": 0, "message": "No URLs provided"}

        normalized_urls = []
        for u in urls:
            if u.startswith("/"):
                normalized_urls.append(f"https://{self.host}{u}")
            elif not u.startswith("http"):
                normalized_urls.append(f"https://{self.host}/{u.lstrip('/')}")
            else:
                normalized_urls.append(u)

        payload = {
            "host": self.host,
            "key": self.key,
            "keyLocation": self.key_location,
            "urlList": normalized_urls[:1000],  # IndexNow allows up to 10,000 URLs
        }

        try:
            resp = self.session.post(
                INDEXNOW_API_ENDPOINT,
                data=json.dumps(payload),
                timeout=self.timeout,
            )
            success = resp.status_code in (200, 202)
            if success:
                logger.info(
                    "IndexNow ping successful for %d URLs (Status %d)",
                    len(normalized_urls),
                    resp.status_code,
                )
            else:
                logger.warning(
                    "IndexNow ping returned status %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )

            return {
                "success": success,
                "status_code": resp.status_code,
                "count": len(normalized_urls),
                "response": resp.text[:200] if not success else "OK",
            }
        except Exception as e:
            logger.error("Failed to notify IndexNow: %s", e)
            return {"success": False, "error": str(e), "count": len(normalized_urls)}

    def ping_sitemaps(self, sitemap_url: Optional[str] = None) -> Dict[str, Any]:
        """Ping Google and Bing sitemap endpoints."""
        target_sitemap = sitemap_url or f"https://{self.host}/sitemap.xml"
        encoded = urllib.parse.quote(target_sitemap, safe="")
        ping_endpoints = {
            "google": f"https://www.google.com/ping?sitemap={encoded}",
            "bing": f"https://www.bing.com/ping?sitemap={encoded}",
        }

        results = {}
        for engine, ping_url in ping_endpoints.items():
            try:
                resp = requests.get(ping_url, timeout=10)
                results[engine] = {
                    "status_code": resp.status_code,
                    "success": resp.status_code in (200, 204),
                }
                logger.info("Pinged %s sitemap: HTTP %d", engine, resp.status_code)
            except Exception as e:
                results[engine] = {"success": False, "error": str(e)}
                logger.warning("Ping to %s sitemap failed: %s", engine, e)

        return results

    @staticmethod
    def build_google_news_xml_entry(
        url: str,
        title: str,
        publication_name: str = "Học Liệu Beekip",
        language: str = "vi",
        published_at: Optional[str] = None,
    ) -> str:
        """
        Generate Google News compliant sitemap entry.
        Standard: https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap
        """
        pub_date = published_at or datetime.now(timezone.utc).isoformat()
        escaped_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
        return f"""  <url>
    <loc>{url}</loc>
    <news:news>
      <news:publication>
        <news:name>{publication_name}</news:name>
        <news:language>{language}</news:language>
      </news:publication>
      <news:publication_date>{pub_date}</news:publication_date>
      <news:title>{escaped_title}</news:title>
    </news:news>
  </url>"""
