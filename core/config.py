import os
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 console output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Base project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("BEEKIP_DATA_DIR", str(BASE_DIR / "data")))
LOGS_DIR = DATA_DIR / "logs"
DOWNLOADS_DIR = DATA_DIR / "downloads"
DOWNLOADS_PDF_DIR = DOWNLOADS_DIR / "pdf"
DOWNLOADS_WORD_DIR = DOWNLOADS_DIR / "word"
DOWNLOADS_PPT_DIR = DOWNLOADS_DIR / "powerpoint"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"

# Allowed canonical document formats: Strictly PDF, Word, PowerPoint (Reject all standalone images)
ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt"}
DISALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff", ".avif"}

DB_PATH = DATA_DIR / "crawler_state.db"
SOURCES_REGISTRY_PATH = BASE_DIR / "data" / "sources_registry.json"
SITEMAP_PATH = DATA_DIR / "beekip_sitemap.xml"

# Ensure runtime directories exist
for path in [DATA_DIR, LOGS_DIR, DOWNLOADS_DIR, DOWNLOADS_PDF_DIR, DOWNLOADS_WORD_DIR, DOWNLOADS_PPT_DIR, PROCESSED_DIR, EXPORTS_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# User-Agent simulation
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Minimum eligible academic/publication year
MIN_ELIGIBLE_YEAR = 2023

# Sources whose historical data is already 100% indexed and are restricted to real-time delta monitoring only
MONITOR_ONLY_SOURCE_IDS = {"toanmath_rss", "tailieumontoan_rss"}

# Concurrency & Rate Limiting SLAs
MAX_WORKER_THREADS = int(os.getenv("MAX_WORKER_THREADS", "20"))
FAST_DOWNLOAD_WORKERS = int(os.getenv("FAST_DOWNLOAD_WORKERS", "20"))
MAX_DOMAIN_CONCURRENCY = int(os.getenv("MAX_DOMAIN_CONCURRENCY", "4"))
MIN_DOMAIN_DELAY_SECONDS = float(os.getenv("MIN_DOMAIN_DELAY_SECONDS", "0.4"))
MAX_DOMAIN_DELAY_SECONDS = float(os.getenv("MAX_DOMAIN_DELAY_SECONDS", "1.0"))
RATE_LIMIT_BACKOFF_SECONDS = float(os.getenv("RATE_LIMIT_BACKOFF_SECONDS", "30.0"))

# Scheduler Config
MONITOR_INTERVAL_HOURS = 4
SCHEDULED_RUN_HOURS = [0, 4, 8, 12, 16, 20]  # UTC+7 Operating schedule

# Cloudflare Configuration
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "f486ca0e5773032c7bf96c231489a0ea")
CLOUDFLARE_D1_DATABASE_ID = os.getenv("CLOUDFLARE_D1_DATABASE_ID", "1277b081-4c8b-41b4-b4c7-0007a4759c07")
CLOUDFLARE_R2_BUCKET = os.getenv("CLOUDFLARE_R2_BUCKET", "khai-phong-lms-staging-files")
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL", "https://files.beekip.vn")
BEEKIP_BASE_URL = os.getenv("BEEKIP_BASE_URL", "https://tailieu.beekip.vn")

def get_cloudflare_token() -> Optional[str]:
    """
    Resolve Cloudflare API token dynamically:
    1. CLOUDFLARE_API_TOKEN environment variable.
    2. Local or user wrangler configuration file (default.toml).
    """
    env_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if env_token:
        return env_token.strip()

    candidate_toml_paths = [
        Path(os.environ.get("APPDATA", "")) / "Roaming" / "xdg.config" / ".wrangler" / "config" / "default.toml",
        Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Roaming" / "xdg.config" / ".wrangler" / "config" / "default.toml",
        Path.home() / ".wrangler" / "config" / "default.toml",
        BASE_DIR / ".wrangler" / "config" / "default.toml",
    ]

    for p in candidate_toml_paths:
        try:
            if p.is_file():
                for line in p.read_text(encoding="utf-8").splitlines():
                    clean_line = line.strip()
                    if clean_line.startswith("oauth_token"):
                        token = clean_line.split("=", 1)[1].strip().strip('"').strip("'")
                        if token:
                            return token
        except Exception:
            continue

    return None
