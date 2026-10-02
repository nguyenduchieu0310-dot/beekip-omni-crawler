import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from core.config import MAX_DOMAIN_CONCURRENCY, MAX_WORKER_THREADS
from core.rate_limiter import DomainRateLimiter, global_rate_limiter

logger = logging.getLogger("beekip.worker_pool")

class DomainBoundWorkerPool:
    """
    Thread pool executor that strictly enforces maximum concurrency per domain
    alongside a global worker thread ceiling (12-16 threads).
    """

    def __init__(
        self,
        max_workers: int = MAX_WORKER_THREADS,
        max_domain_concurrency: int = MAX_DOMAIN_CONCURRENCY,
        rate_limiter: Optional[DomainRateLimiter] = None
    ):
        self.max_workers = max_workers
        self.max_domain_concurrency = max_domain_concurrency
        self.rate_limiter = rate_limiter or global_rate_limiter

        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="beekip-worker")
        self._lock = threading.Lock()
        self._domain_semaphores: Dict[str, threading.Semaphore] = {}
        self._is_shutdown = False

    def _get_domain_semaphore(self, domain: str) -> threading.Semaphore:
        with self._lock:
            if domain not in self._domain_semaphores:
                self._domain_semaphores[domain] = threading.Semaphore(self.max_domain_concurrency)
            return self._domain_semaphores[domain]

    def submit(self, domain: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        """
        Submit a task bound to a specific domain. The task will respect:
        1. Global thread pool capacity.
        2. Domain-level concurrency semaphore (max 2 active at once per domain).
        3. Rate-limiter delay & jitter.
        """
        if self._is_shutdown:
            raise RuntimeError("DomainBoundWorkerPool is shut down.")

        clean_domain = DomainRateLimiter.extract_domain(domain)
        semaphore = self._get_domain_semaphore(clean_domain)

        def wrapped_task() -> Any:
            with semaphore:
                self.rate_limiter.wait_if_needed(clean_domain)
                return fn(*args, **kwargs)

        return self._executor.submit(wrapped_task)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the underlying thread pool executor."""
        with self._lock:
            self._is_shutdown = True
        self._executor.shutdown(wait=wait)
        logger.info("Worker pool shut down successfully.")
