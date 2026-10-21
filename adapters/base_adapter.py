import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

@dataclass
class DiscoveredItem:
    url: str
    source_id: str
    title: str = ""
    published_at: Optional[str] = None
    published_year: Optional[int] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DownloadCandidate:
    url: str
    source_url: str
    file_type: str = "PDF"  # PDF, DOCX, ZIP, etc.
    file_name: Optional[str] = None
    is_direct_cdn: bool = False
    is_gdrive: bool = False
    extra_headers: Dict[str, str] = field(default_factory=dict)

class BaseSourceAdapter(abc.ABC):
    """Abstract interface for all K-12 source adapters."""

    def __init__(self, source_info: Dict[str, Any]):
        self.source_info = source_info
        self.source_id = source_info.get("source_id", "unknown")
        self.domain = source_info.get("domain", "")
        self.feed_url = source_info.get("feed_url") or source_info.get("sitemap_url") or f"https://{self.domain}"
        self.rate_delay = float(source_info.get("rate_delay_seconds", 2.5))

    @abc.abstractmethod
    def fetch_latest_posts(
        self,
        since_timestamp: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ) -> List[DiscoveredItem]:
        """Fetch recently published items using conditional HTTP caching."""
        pass

    @abc.abstractmethod
    def fetch_historical_archive(
        self,
        from_year: int = 2023,
        max_pages: int = 50
    ) -> Generator[DiscoveredItem, None, None]:
        """Yield historical articles published from from_year to present."""
        pass

    @abc.abstractmethod
    def extract_download_links(self, post_url: str, html_content: Optional[str] = None) -> List[DownloadCandidate]:
        """Extract candidate PDF/DOCX download links from article URL or content."""
        pass

    def get_rate_limit_policy(self) -> Dict[str, Any]:
        """Return rate limiting rules for this source."""
        return {
            "domain": self.domain,
            "rate_delay_seconds": self.rate_delay,
            "concurrency_limit": int(self.source_info.get("concurrency_limit", 2))
        }
