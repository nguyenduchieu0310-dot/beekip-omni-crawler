import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import requests

from core.config import BEEKIP_BASE_URL, SITEMAP_PATH

logger = logging.getLogger("beekip.sitemap")

class SitemapIndexer:
    """Maintains Beekip sitemap.xml and handles search engine indexing notifications."""

    def __init__(self, sitemap_path: Path = SITEMAP_PATH, base_url: str = BEEKIP_BASE_URL):
        self.sitemap_path = Path(sitemap_path)
        self.base_url = base_url.rstrip("/")
        self._ensure_sitemap_file()

    def _ensure_sitemap_file(self) -> None:
        if not self.sitemap_path.is_file():
            self.sitemap_path.parent.mkdir(parents=True, exist_ok=True)
            initial_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                '</urlset>'
            )
            self.sitemap_path.write_text(initial_xml, encoding="utf-8")

    def add_document_url(self, slug: str, priority: float = 0.8) -> None:
        """Add new document entry to local sitemap."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        full_url = f"{self.base_url}/tai-lieu/{slug}"

        try:
            tree = ET.parse(self.sitemap_path)
            root = tree.getroot()

            ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
            ET.register_namespace("", ns)

            # Check if URL already exists
            for url_elem in root.findall(f"{{{ns}}}url"):
                loc = url_elem.findtext(f"{{{ns}}}loc")
                if loc == full_url:
                    lastmod = url_elem.find(f"{{{ns}}}lastmod")
                    if lastmod is not None:
                        lastmod.text = now_iso
                    tree.write(self.sitemap_path, encoding="utf-8", xml_declaration=True)
                    return

            url_node = ET.SubElement(root, f"{{{ns}}}url")
            loc_node = ET.SubElement(url_node, f"{{{ns}}}loc")
            loc_node.text = full_url

            lastmod_node = ET.SubElement(url_node, f"{{{ns}}}lastmod")
            lastmod_node.text = now_iso

            changefreq_node = ET.SubElement(url_node, f"{{{ns}}}changefreq")
            changefreq_node.text = "weekly"

            priority_node = ET.SubElement(url_node, f"{{{ns}}}priority")
            priority_node.text = f"{priority:.1f}"

            tree.write(self.sitemap_path, encoding="utf-8", xml_declaration=True)
            logger.info("Added to sitemap: %s", full_url)

        except Exception as e:
            logger.error("Failed updating sitemap [%s]: %s", full_url, e)

    def ping_search_engines(self) -> None:
        """Inform search engines of sitemap update."""
        sitemap_url = f"{self.base_url}/sitemap.xml"
        ping_urls = [
            f"https://www.google.com/ping?sitemap={sitemap_url}",
            f"https://www.bing.com/ping?sitemap={sitemap_url}"
        ]
        for p_url in ping_urls:
            try:
                requests.get(p_url, timeout=10)
            except Exception as e:
                logger.debug("Ping failed for %s: %s", p_url, e)
