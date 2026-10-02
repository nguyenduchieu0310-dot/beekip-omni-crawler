from adapters.base_adapter import BaseSourceAdapter, DiscoveredItem, DownloadCandidate
from adapters.blogger_api_adapter import BloggerAPIAdapter
from adapters.factory import get_adapter_for_source
from adapters.html_spider_adapter import HTMLSpiderAdapter
from adapters.rss_adapter import RSSAdapter
from adapters.sitemap_adapter import SitemapAdapter

__all__ = [
    "BaseSourceAdapter",
    "DiscoveredItem",
    "DownloadCandidate",
    "RSSAdapter",
    "BloggerAPIAdapter",
    "SitemapAdapter",
    "HTMLSpiderAdapter",
    "get_adapter_for_source",
]
