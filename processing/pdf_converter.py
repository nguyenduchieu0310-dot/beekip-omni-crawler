import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("beekip.converter")

class DocumentPDFConverter:
    """Handles DOCX to PDF conversions when needed."""

    @classmethod
    def can_convert(cls) -> bool:
        """Check if any conversion utility is available."""
        return bool(shutil.which("soffice") or shutil.which("libreoffice"))

    @classmethod
    def convert_docx_to_pdf(cls, docx_path: Path, output_dir: Optional[Path] = None) -> Optional[Path]:
        """Convert DOCX file to PDF using headless office if installed."""
        if not docx_path.is_file():
            return None

        out_dir = output_dir or docx_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / (docx_path.stem + ".pdf")

        office_cmd = shutil.which("soffice") or shutil.which("libreoffice")
        if office_cmd:
            try:
                cmd = [
                    office_cmd,
                    "--headless",
                    "--convert-to", "pdf",
                    str(docx_path),
                    "--outdir", str(out_dir)
                ]
                subprocess.run(cmd, check=True, timeout=60, capture_output=True)
                if pdf_path.is_file():
                    return pdf_path
            except Exception as e:
                logger.error("Failed converting DOCX to PDF via office [%s]: %s", docx_path, e)

        return None
