"""Mock-only publication boundary regressions; never connects to production."""
import json
import os
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from cloudflare.document_ingest import document_payload, ingest_document, source_provenance
from cloudflare.d1_deployer import CloudflareD1Deployer
from cloudflare.r2_uploader import CloudflareR2Uploader

class DocumentIngestTests(unittest.TestCase):
    def payload(self):
        id_ = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.test/source/31899"))
        doc = {"id": id_, "code": "crawl-" + id_, "slug": "test-document", "title": "Đề Toán sở GD&ĐT Đồng Nai",
               "shortDescription": "Tài liệu", "description": "<h2>Toàn bộ nội dung</h2>", "descriptionFormat": "html",
               "sourceObjectKey": "documents/v1/" + id_ + "/source.pdf"}
        provenance, review = source_provenance("https://example.test/source/31899", doc["title"], doc["description"])
        return document_payload(doc, provenance, review)

    def test_missing_configuration_cannot_send_or_fallback_to_d1(self):
        with patch.dict(os.environ, {}, clear=True), patch("requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "DOCUMENT_INGEST_TOKEN"):
                ingest_document(self.payload())
            post.assert_not_called()

    def test_https_post_preserves_body_and_does_not_follow_redirects(self):
        payload = self.payload()
        response = MagicMock(status_code=201)
        response.json.return_value = {"ok": True, "id": payload["document"]["id"], "created": True}
        transport = MagicMock()
        transport.post.return_value = response
        with patch.dict(os.environ, {"DOCUMENT_INGEST_TOKEN": "test-token", "DOCUMENT_INGEST_BASE_URL": "https://hoc-staging.beekip.vn"}):
            ingest_document(payload, transport)
        args = transport.post.call_args
        self.assertEqual(args.args[0], "https://hoc-staging.beekip.vn/api/internal/documents/ingest")
        self.assertEqual(args.kwargs["json"]["document"]["description"], "<h2>Toàn bộ nội dung</h2>")
        self.assertEqual(args.kwargs["json"]["quality"]["renderStatus"], "pending")
        self.assertFalse(args.kwargs["allow_redirects"])
        self.assertEqual(args.kwargs["headers"]["Authorization"], "Bearer test-token")

    def test_redirect_or_failure_is_not_success_and_has_no_fallback(self):
        for status in [302, 401, 409, 500]:
            transport = MagicMock()
            transport.post.return_value.status_code = status
            with self.subTest(status=status), patch.dict(os.environ, {"DOCUMENT_INGEST_TOKEN": "test-token"}):
                with self.assertRaisesRegex(RuntimeError, "HTTP " + str(status)):
                    ingest_document(self.payload(), transport)
                self.assertEqual(transport.post.call_count, 1)

    def test_oversize_body_is_rejected_without_truncation(self):
        payload = self.payload()
        payload["document"]["description"] = "x" * 12001
        with patch.dict(os.environ, {"DOCUMENT_INGEST_TOKEN": "test-token"}), patch("requests.post") as post:
            with self.assertRaisesRegex(ValueError, "must not be truncated"):
                ingest_document(payload)
            post.assert_not_called()

    def test_ledger_sql_remains_available_but_document_sql_is_blocked(self):
        deployer = CloudflareD1Deployer(api_token="test")
        for sql in ['INSERT INTO documents (id) VALUES (?)', 'UPDATE "documents" SET title=?',
                    'DELETE FROM [product_offers]', '-- comment\n REPLACE INTO documents (id) VALUES (?)']:
            with self.subTest(sql=sql), patch("requests.post") as post:
                with self.assertRaisesRegex(RuntimeError, "Direct document SQL"):
                    deployer.execute_raw_sql(sql, ["id"])
                post.assert_not_called()
        response = MagicMock(status_code=200)
        response.json.return_value = {"success": True, "result": [{"success": True, "results": []}]}
        with patch("requests.post", return_value=response) as post:
            deployer.execute_raw_sql("INSERT INTO beekip_crawler_queue (payload) VALUES (?)", ["documents"])
            self.assertEqual(post.call_count, 1)

    def test_modern_writer_uses_ingest_and_preserves_identity_and_no_offers(self):
        source = "https://example.test/source/31899"
        id_ = str(uuid.uuid5(uuid.NAMESPACE_URL, source))
        meta = SimpleNamespace(title="Đề Toán sở GD&ĐT Đồng Nai", slug="test-document", description="## Nội dung\nĐầy đủ",
                               description_format="markdown", subject="Toán", grade="Lớp 12", academic_year="2024-2025",
                               curriculum="GDPT 2018", document_type="Đề thi", geo_province="Đồng Nai", geo_school="")
        with patch("cloudflare.d1_deployer.ingest_document") as ingest, patch.object(CloudflareD1Deployer, "execute_raw_sql") as sql:
            returned = CloudflareD1Deployer(api_token="ledger-only").insert_document(meta, "https://tailieu.beekip.vn/api/documents/test-document/download", 1200,
                                         source, page_count=3, storage_key="documents/v1/" + id_ + "/source.pdf")
        self.assertEqual(returned, id_)
        sql.assert_not_called()
        payload = ingest.call_args.args[0]
        self.assertEqual(payload["document"]["id"], id_)
        self.assertEqual(payload["document"]["descriptionFormat"], "markdown")
        self.assertEqual(payload["offers"], [])
        self.assertEqual(payload["provenance"]["originalTitle"], meta.title)
        self.assertEqual(payload["quality"]["renderStatus"], "pending")

    def test_same_source_changed_slug_is_found_by_source_uuid_before_upload(self):
        from services.agent_auto_publisher import AutoPublisherAgent
        source = "https://example.test/original/31899"
        id_ = str(uuid.uuid5(uuid.NAMESPACE_URL, source))
        deployer = CloudflareD1Deployer(api_token="ledger-only")
        existing = {"id": id_, "slug": "edited-existing-slug", "source_object_key": "documents/v1/" + id_ + "/source.pdf"}
        with patch.object(deployer, "execute_raw_sql", return_value={"result": [{"results": [existing]}]}) as query:
            self.assertEqual(deployer.find_existing_document(source, "new-generated-slug"), existing)
        self.assertEqual(query.call_args.args[1][0], id_)
        d1, r2, ledger = MagicMock(), MagicMock(), MagicMock()
        d1.find_existing_document.return_value = existing
        agent = AutoPublisherAgent(ledger, r2, d1)
        result = agent.publish_approved_draft({"slug": "new-generated-slug"}, source, trigger_indexing=False)
        self.assertFalse(result["created"])
        self.assertEqual(result["slug"], "edited-existing-slug")
        r2.upload_document.assert_not_called()
        d1.insert_document.assert_not_called()

    def test_document_asset_conflict_cannot_fallback_to_management_api(self):
        r2 = CloudflareR2Uploader(api_token="ledger-only")
        key = "documents/v1/09bc8dee-8711-516d-8057-4d7169df90c2/source.pdf"
        with patch.dict(os.environ, {"DOCUMENT_INGEST_TOKEN": "asset-test"}), patch("requests.post", return_value=MagicMock(status_code=409)), patch("requests.put") as put:
            with self.assertRaisesRegex(RuntimeError, "HTTP 409"):
                r2.upload_document(b"changed bytes", "toan", "2025", "title", storage_key=key)
            put.assert_not_called()

    def test_identical_document_asset_is_reused_by_worker_without_management_put(self):
        import hashlib
        r2 = CloudflareR2Uploader(api_token="ledger-only")
        key = "documents/v1/09bc8dee-8711-516d-8057-4d7169df90c2/source.pdf"
        response = MagicMock(status_code=200)
        response.json.return_value = {"ok": True, "key": key, "size": 10, "sha256": hashlib.sha256(b"same bytes").hexdigest(), "created": False}
        with patch.dict(os.environ, {"DOCUMENT_INGEST_TOKEN": "asset-test"}), patch("requests.post", return_value=response), patch("requests.put") as put:
            result, _ = r2.upload_document(b"same bytes", "toan", "2025", "title", storage_key=key)
            self.assertEqual(result, key)
            put.assert_not_called()

    def test_new_document_asset_posts_exact_binary_digest_and_does_not_follow_redirects(self):
        import hashlib
        r2 = CloudflareR2Uploader(api_token=None)
        key = "documents/v1/09bc8dee-8711-516d-8057-4d7169df90c2/source.pdf"
        response = MagicMock(status_code=201)
        response.json.return_value = {"ok": True, "key": key, "size": 9, "sha256": hashlib.sha256(b"new bytes").hexdigest(), "created": True}
        with patch.dict(os.environ, {"DOCUMENT_INGEST_TOKEN": "asset-test"}), patch("requests.post", return_value=response) as post, patch("requests.put") as put:
            r2.upload_document(b"new bytes", "toan", "2025", "title", storage_key=key)
            self.assertIn("/api/internal/documents/assets?key=", post.call_args.args[0])
            self.assertEqual(post.call_args.kwargs["data"], b"new bytes")
            self.assertEqual(post.call_args.kwargs["headers"]["X-Content-Sha256"], hashlib.sha256(b"new bytes").hexdigest())
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
            put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
