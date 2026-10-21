import io
import logging
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Union
import requests
from cloudflare.document_ingest import ingest_config, upload_document_asset

from core.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_R2_BUCKET,
    R2_PUBLIC_BASE_URL,
    get_cloudflare_token,
)

logger = logging.getLogger("beekip.cloudflare.r2")

class CloudflareR2Uploader:
    """Uploads processed documents to Cloudflare R2 bucket."""

    def __init__(
        self,
        account_id: str = CLOUDFLARE_ACCOUNT_ID,
        bucket_name: str = CLOUDFLARE_R2_BUCKET,
        public_base_url: str = R2_PUBLIC_BASE_URL,
        api_token: Optional[str] = None
    ):
        self.account_id = account_id
        self.bucket_name = bucket_name
        self.public_base_url = public_base_url.rstrip("/")
        self.api_token = api_token or get_cloudflare_token()

    def ensure_document_assets_safe(self, assets):
        """Validate the entire pair locally; the Worker enforces atomic no-overwrite per object."""
        ingest_config()
        for key, content in assets:
            if not key.startswith("documents/v1/") or not 0 < len(content) <= (50 * 1024 * 1024 if key.endswith(".pdf") else 2 * 1024 * 1024):
                raise ValueError("Invalid document asset pair")

    def upload_document(
        self,
        file_input: Union[bytes, str, Path],
        subject_slug: str,
        academic_year: str,
        document_slug: str,
        mime_type: str = "application/pdf",
        ext: str = "pdf",
        storage_key: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Upload document to R2 with partitioning:
        Content-addressed files, or an explicit key required by the existing app.
        Returns: (r2_storage_key, public_file_url)
        """
        if isinstance(file_input, (str, Path)):
            file_bytes = Path(file_input).read_bytes()
        else:
            file_bytes = file_input

        explicit_document_key = bool(storage_key and storage_key.startswith("documents/"))
        digest = hashlib.sha256(file_bytes).hexdigest()
        storage_key = storage_key or f"files/crawler/{subject_slug}/{academic_year}/{digest}.{ext}"
        if storage_key.startswith('/') or '..' in storage_key.split('/'):
            raise ValueError('Invalid R2 storage key')
        if explicit_document_key:
            upload_document_asset(storage_key, file_bytes, mime_type)
            return storage_key, f"{self.public_base_url}/{storage_key}"
        if not self.api_token:
            raise RuntimeError("Cloudflare API token not found for non-document R2 upload")
        from urllib.parse import quote
        endpoint_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/"
            f"r2/buckets/{self.bucket_name}/objects/{quote(storage_key, safe='/')}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": mime_type,
            "Cache-Control": "public, max-age=31536000, immutable",
            "User-Agent": "wrangler/3.114.0",
        }

        resp = requests.put(endpoint_url, data=file_bytes, headers=headers, timeout=40, allow_redirects=False)
        if resp.status_code not in (200, 201):
            logger.error("R2 Upload failed for [%s] status %s: %s", storage_key, resp.status_code, resp.text[:200])
            raise RuntimeError(f"R2 upload failed with HTTP {resp.status_code}")

        public_url = f"{self.public_base_url}/{storage_key}"
        logger.info("Successfully uploaded R2 object: %s", storage_key)
        return storage_key, public_url
