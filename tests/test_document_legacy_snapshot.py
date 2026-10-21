"""Exercise the tracked legacy source snapshot without importing its runtime entry points."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict
import unittest
from html import escape
import pypdf
from cloudflare.document_ingest import source_provenance

SOURCE = Path(__file__).resolve().parents[1] / "integrations/legacy-crawler/source"

def load_function(file, name, namespace):
    tree = ast.parse((SOURCE / file).read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE/file), "exec"), namespace)
    return namespace[name]

class LegacyDocumentContractTests(unittest.TestCase):
    def test_semantic_html_escapes_source_strings_but_keeps_article_structure(self):
        generate = load_function("seo_geo_pipeline.py", "generate_semantic_html", {
            "Dict": Dict, "Any": Any, "escape": escape, "BRAND_NAME": "Beekip", "BRAND_FULL_NAME": "Beekip Education",
            "BRAND_DOMAIN": "beekip.vn", "BRAND_URL": "https://beekip.vn"})
        result = generate('<img src=x onerror="bad()">', "A&B", {"grade_name": "Lớp 12", "geo_province": "Đồng Nai"}, "file.pdf")
        self.assertNotIn('<img src=x', result)
        self.assertIn('&lt;img', result)
        self.assertIn('A&amp;B', result)
        self.assertIn('<table', result)
        self.assertIn('4. Câu hỏi thường gặp', result)

    def test_manifest_never_fabricates_render_pass_or_drops_full_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pdf = folder / "source.pdf"
            writer = pypdf.PdfWriter()
            writer.add_blank_page(width=595, height=842)
            writer.write(pdf)
            body = '<h2>Nội dung đầy đủ</h2><p>Bảo toàn dữ liệu.</p>'
            payload = {"post_id": 31899, "slug": "sample-id31899", "original_url": "https://example.test/source/31899",
                       "original_title": "Đề Toán sở GD&ĐT Đồng Nai", "source_site": "test", "content_html": body, "description_format": "html"}
            row = {"post_id": 31899, "slug": "sample-id31899", "seo_title": payload["original_title"], "original_title": payload["original_title"],
                   "meta_description": "Mô tả", "payload_json": json.dumps(payload), "seo_file_path": str(pdf)}
            generate = load_function("build_beekip_upload_manifests.py", "process_manifest_item", {
                "Dict": Dict, "Any": Any, "Path": Path, "os": os, "json": json, "pypdf": pypdf, "SEO_GEO_DIR": folder,
                "calculate_sha256": lambda path: hashlib.sha256(path.read_bytes()).hexdigest(), "source_provenance": source_provenance})
            result = generate(row)
            self.assertEqual(result["description"], body)
            self.assertEqual(result["descriptionFormat"], "html")
            self.assertEqual(result["render_qa_pass"], "pending")
            self.assertEqual(result["scan_clean"], "unverified")
            self.assertEqual(result["automatic_google_indexing"], "false")
            self.assertEqual(json.loads(result["provenanceJson"])["originalUrl"], payload["original_url"])
            payload["content_html"] = "x" * 12001
            row["payload_json"] = json.dumps(payload)
            with self.assertRaisesRegex(ValueError, "do not truncate"):
                generate(row)

    def test_legacy_adapter_preserves_offers_and_requires_matching_source_identity(self):
        spec = importlib.util.spec_from_file_location("legacy_snapshot_adapter", SOURCE / "legacy_document_ingest.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "source.pdf"
            writer = pypdf.PdfWriter(); writer.add_blank_page(width=595, height=842); writer.write(pdf)
            provenance, _ = source_provenance("https://example.test/source/31899", "Đề Đồng Nai", "full", "test", 31899)
            row = {"document_code": "BK-TOAN-LOP_12-ID31899", "slug": "sample-id31899", "title": "Title", "description": "full",
                   "descriptionFormat": "plain", "pdf_path": str(pdf), "pageCount": 1, "audienceTags": '[]',
                   "provenanceJson": json.dumps(provenance), "onlinePrice": "0", "downloadPrice": "2000"}
            id_ = "09bc8dee-8711-516d-8057-4d7169df90c2"
            result = module.payload_for_manifest_row(row, id_, "documents/v1/" + id_ + "/source.pdf")
            self.assertEqual(result["document"]["description"], "full")
            self.assertEqual([offer["priceVnd"] for offer in result["offers"]], [0, 2000])
            self.assertEqual(result["quality"]["metadataReviewStatus"], "needs_review")
            provenance["sourceItemId"] = "other"
            row["provenanceJson"] = json.dumps(provenance)
            with self.assertRaisesRegex(ValueError, "post ID"):
                module.payload_for_manifest_row(row, id_, "documents/v1/" + id_ + "/source.pdf")

if __name__ == "__main__":
    unittest.main()
