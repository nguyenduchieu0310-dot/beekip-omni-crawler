import logging
import random
import threading
import time
from typing import Dict
from urllib.parse import urlparse

from core.config import (
    MAX_DOMAIN_DELAY_SECONDS,
    MIN_DOMAIN_DELAY_SECONDS,
    RATE_LIMIT_BACKOFF_SECONDS,
)

logger = logging.getLogger("beekip.rate_limiter")

class DomainRateLimiter:
    """
    Domain-bound rate limiter with jitter and selective exponential backoff.
    Ensures politeness to target servers and isolation between domains.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._domain_locks: Dict[str, threading.Lock] = {}
        self._last_request_time: Dict[str, float] = {}
        self._paused_until: Dict[str, float] = {}
        self._domain_base_delay: Dict[str, float] = {}

    def _get_domain_lock(self, domain: str) -> threading.Lock:
        with self._lock:
            if domain not in self._domain_locks:
                self._domain_locks[domain] = threading.Lock()
            return self._domain_locks[domain]

    @staticmethod
    def extract_domain(url_or_domain: str) -> str:
        """Extract clean domain name from URL or raw domain string."""
        if not url_or_domain:
            return "unknown"
        if url_or_domain.startswith("http://") or url_or_domain.startswith("https://"):
            parsed = urlparse(url_or_domain)
            return (parsed.netloc or "unknown").lower()
        return url_or_domain.lower().split("/")[0]

    def set_domain_base_delay(self, domain: str, delay: float) -> None:
        """Configure baseline delay for specific domain."""
        clean_domain = self.extract_domain(domain)
        with self._lock:
            self._domain_base_delay[clean_domain] = max(MIN_DOMAIN_DELAY_SECONDS, delay)

    def wait_if_needed(self, url_or_domain: str) -> None:
        """
        Block current thread until the domain is eligible for request.
        Applies jitter and honors backoff pauses.
        """
        domain = self.extract_domain(url_or_domain)
        domain_lock = self._get_domain_lock(domain)

        with domain_lock:
            now = time.time()

            # Check if domain is currently paused due to HTTP 429/503
            pause_expiry = self._paused_until.get(domain, 0.0)
            if pause_expiry > now:
                wait_pause = pause_expiry - now
                logger.warning(
                    "Domain [%s] is temporarily paused due to rate-limit. Waiting %.1fs...",
                    domain, wait_pause
                )
                time.sleep(wait_pause)
                now = time.time()

            # Calculate jittered delay
            base_delay = self._domain_base_delay.get(domain, 2.5)
            jitter = random.uniform(-0.4, 0.6)
            target_delay = max(MIN_DOMAIN_DELAY_SECONDS, min(MAX_DOMAIN_DELAY_SECONDS, base_delay + jitter))

            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = now - last_time

            if elapsed < target_delay:
                sleep_needed = target_delay - elapsed
                time.sleep(sleep_needed)

            self._last_request_time[domain] = time.time()

    def report_rate_limit(self, url_or_domain: str, backoff_seconds: float = RATE_LIMIT_BACKOFF_SECONDS) -> None:
        """
        Trigger temporary pause for this domain when encountering HTTP 429 or 503.
        Increases domain base delay by 1.5s for future requests.
        """
        domain = self.extract_domain(url_or_domain)
        domain_lock = self._get_domain_lock(domain)

        with domain_lock:
            now = time.time()
            self._paused_until[domain] = now + backoff_seconds
            current_delay = self._domain_base_delay.get(domain, 2.5)
            self._domain_base_delay[domain] = min(current_delay + 1.5, 10.0)
            logger.warning(
                "Rate limit triggered for [%s]. Paused for %.0fs. New base delay: %.1fs",
                domain, backoff_seconds, self._domain_base_delay[domain]
            )

    def is_domain_paused(self, url_or_domain: str) -> bool:
        """Check if domain is currently paused."""
        domain = self.extract_domain(url_or_domain)
        return self._paused_until.get(domain, 0.0) > time.time()

# Global default instance
global_rate_limiter = DomainRateLimiter()
