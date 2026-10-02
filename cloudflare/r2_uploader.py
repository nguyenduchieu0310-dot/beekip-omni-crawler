import io
import logging
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Union
import requests

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

    def upload_document(
        self,
        file_input: Union[bytes, str, Path],
        subject_slug: str,
        academic_year: str,
        document_slug: str,
        mime_type: str = "application/pdf",
        ext: str = "pdf"
    ) -> Tuple[str, str]:
        """
        Upload document to R2 with partitioning:
        files/{subject_slug}/{academic_year}/{document_slug}_{short_uuid}.{ext}
        Returns: (r2_storage_key, public_file_url)
        """
        if not self.api_token:
            raise RuntimeError("Cloudflare API token not found for R2 upload.")

        if isinstance(file_input, (str, Path)):
            file_bytes = Path(file_input).read_bytes()
        else:
            file_bytes = file_input

        digest = hashlib.sha256(file_bytes).hexdigest()
        storage_key = f"files/crawler/{subject_slug}/{academic_year}/{digest}.{ext}"
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

        resp = requests.put(endpoint_url, data=file_bytes, headers=headers, timeout=40)
        if resp.status_code not in (200, 201):
            logger.error("R2 Upload failed for [%s] status %s: %s", storage_key, resp.status_code, resp.text[:200])
            raise RuntimeError(f"R2 upload failed with HTTP {resp.status_code}")

        public_url = f"{self.public_base_url}/{storage_key}"
        logger.info("Successfully uploaded R2 object: %s", storage_key)
        return storage_key, public_url
