from typing import Any, Dict
from adapters.base_adapter import BaseSourceAdapter
from adapters.blogger_api_adapter import BloggerAPIAdapter
from adapters.html_spider_adapter import HTMLSpiderAdapter
from adapters.rss_adapter import RSSAdapter
from adapters.sitemap_adapter import SitemapAdapter

def get_adapter_for_source(source_info: Dict[str, Any]) -> BaseSourceAdapter:
    """Factory creating corresponding adapter instance based on source protocol."""
    protocol = source_info.get("protocol", "RSS_XML").upper()

    if protocol in ("RSS_XML", "WP_REST"):
        return RSSAdapter(source_info)
    elif protocol == "BLOGGER_JSON_API":
        return BloggerAPIAdapter(source_info)
    elif protocol == "SITEMAP_XML":
        return SitemapAdapter(source_info)
    elif protocol in ("HTML_POLL", "HEADLESS_SCRAPER", "INTERNAL_API"):
        return HTMLSpiderAdapter(source_info)
    else:
        # Default fallback to RSS
        return RSSAdapter(source_info)
