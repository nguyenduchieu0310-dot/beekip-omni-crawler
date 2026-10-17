"""Mock-only contract probes: authentication checks must never publish content."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.run_cloud_cycle import preflight, verify_document_consumer_contract

APP = "https://tailieu.beekip.vn"
ENV = {
    "CLOUDFLARE_ACCOUNT_ID": "account-test",
    "CLOUDFLARE_D1_DATABASE_ID": "database-test",
    "CLOUDFLARE_R2_BUCKET": "bucket-test",
    "CLOUDFLARE_API_TOKEN": "cloudflare-only-token",
    "DOCUMENT_INGEST_TOKEN": "dedicated-ingest-token",
    "DOCUMENT_INGEST_BASE_URL": APP,
}
BASE_COLUMNS = {"id", "slug", "source_object_key", "cover_url", "is_published", "audience_tags_json"}
CONTENT_COLUMNS = {"description_format", "source_provenance_json", "content_quality_json"}


def rejection(error, status=422):
    response = MagicMock(status_code=status)
    response.iter_content.return_value = [json.dumps({"error": error}).encode("utf-8")]
    return response


class DocumentConsumerPreflightTests(unittest.TestCase):
    def test_authentication_uses_only_fixed_invalid_payloads_and_dedicated_token(self):
        responses = [rejection("Unsupported schemaVersion."), rejection("Invalid asset key or SHA-256.")]
        with patch.dict(os.environ, ENV, clear=True), patch("requests.post", side_effect=responses) as post, \
                patch("requests.Session") as session:
            verify_document_consumer_contract(APP)
        session.assert_not_called()
        self.assertEqual(post.call_count, 2)
        ingest, asset = post.call_args_list
        self.assertEqual(ingest.args, (APP + "/api/internal/documents/ingest",))
        self.assertEqual(ingest.kwargs["json"], {})
        self.assertNotIn("data", ingest.kwargs)
        self.assertEqual(asset.args, (APP + "/api/internal/documents/assets?key=invalid-preflight-key",))
        self.assertEqual(asset.kwargs["data"], b"")
        self.assertNotIn("json", asset.kwargs)
        for request in [ingest, asset]:
            self.assertEqual(request.kwargs["headers"], {
                "Authorization": "Bearer dedicated-ingest-token", "Content-Type": "application/json"})
            self.assertNotIn("X-Content-Sha256", request.kwargs["headers"])
            self.assertFalse(request.kwargs["allow_redirects"])
            self.assertTrue(request.kwargs["stream"])
            self.assertEqual(request.kwargs["timeout"], 15)
        for response in responses:
            response.close.assert_called_once()

    def test_rejected_auth_redirects_and_unexpected_success_stop_preflight(self):
        for status in [401, 403, 302, 307, 200, 201, 500]:
            response = rejection("Unsupported schemaVersion.", status)
            with self.subTest(status=status), patch.dict(os.environ, ENV, clear=True), \
                    patch("requests.post", return_value=response) as post:
                with self.assertRaisesRegex(RuntimeError, "HTTP " + str(status)):
                    verify_document_consumer_contract(APP)
                self.assertEqual(post.call_count, 1)
                response.close.assert_called_once()

    def test_asset_rejection_is_required_after_ingest_rejection(self):
        for status in [401, 302, 201]:
            response = rejection("Invalid asset key or SHA-256.", status)
            with self.subTest(status=status), patch.dict(os.environ, ENV, clear=True), \
                    patch("requests.post", side_effect=[rejection("Unsupported schemaVersion."), response]) as post:
                with self.assertRaisesRegex(RuntimeError, "asset rejection probe failed"):
                    verify_document_consumer_contract(APP)
                self.assertEqual(post.call_count, 2)
                response.close.assert_called_once()

    def test_unrecognized_rejection_cannot_certify_consumer_authentication(self):
        for raw in [b'{"error":"Unauthorized."}', b'{"error":"Wrong validator"}', b'[]', b'{}', b'not json', b'\xff']:
            response = MagicMock(status_code=422)
            response.iter_content.return_value = [raw]
            with self.subTest(raw=raw), patch.dict(os.environ, ENV, clear=True), \
                    patch("requests.post", return_value=response) as post:
                with self.assertRaisesRegex(RuntimeError, "contract differs|not valid JSON"):
                    verify_document_consumer_contract(APP)
                self.assertEqual(post.call_count, 1)
                response.close.assert_called_once()
        with patch.dict(os.environ, ENV, clear=True), patch("requests.post", side_effect=[
                rejection("Unsupported schemaVersion."), rejection("Unsupported schemaVersion.")]):
            with self.assertRaisesRegex(RuntimeError, "asset rejection contract differs"):
                verify_document_consumer_contract(APP)

    def test_response_size_is_bounded_and_stream_is_closed(self):
        response = MagicMock(status_code=422)
        response.iter_content.return_value = [b"x" * 1024] * 5
        with patch.dict(os.environ, ENV, clear=True), patch("requests.post", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "exceeds 4 KiB"):
                verify_document_consumer_contract(APP)
        response.close.assert_called_once()

    def test_wrong_app_or_ingest_origin_cannot_receive_any_token(self):
        for app in ["http://tailieu.beekip.vn", "https://example.test", "https://tailieu.beekip.vn/else",
                    "https://tailieu.beekip.vn?redirect=example.test", "https://tailieu.beekip.vn#fragment",
                    "https://tailieu.beekip.vn@evil.test"]:
            with self.subTest(app=app), patch.dict(os.environ, ENV, clear=True), patch("requests.post") as post:
                with self.assertRaisesRegex(RuntimeError, "verified production app origin"):
                    verify_document_consumer_contract(app)
                post.assert_not_called()
        with patch.dict(os.environ, {**ENV, "DOCUMENT_INGEST_BASE_URL": "https://hoc-staging.beekip.vn"}, clear=True), \
                patch("requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "origin differs"):
                verify_document_consumer_contract(APP)
            post.assert_not_called()

    def test_missing_ingest_token_cannot_use_cloudflare_token_as_fallback(self):
        env = {name: value for name, value in ENV.items() if name != "DOCUMENT_INGEST_TOKEN"}
        with patch.dict(os.environ, env, clear=True), patch("requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "DOCUMENT_INGEST_TOKEN"):
                verify_document_consumer_contract(APP)
            post.assert_not_called()

    def test_remote_preflight_requires_each_additive_content_column_before_network(self):
        for missing in CONTENT_COLUMNS:
            d1 = MagicMock()
            d1._get_columns.return_value = BASE_COLUMNS | (CONTENT_COLUMNS - {missing})
            with self.subTest(missing=missing), patch.dict(os.environ, ENV, clear=True), \
                    patch("core.config.get_cloudflare_token", return_value=ENV["CLOUDFLARE_API_TOKEN"]), \
                    patch("cloudflare.d1_deployer.CloudflareD1Deployer", return_value=d1), \
                    patch("requests.Session") as session, patch("requests.post") as post:
                with self.assertRaisesRegex(RuntimeError, "D1 schema is incompatible"):
                    preflight()
                session.assert_not_called()
                post.assert_not_called()
                d1.execute_raw_sql.assert_not_called()

    def test_remote_preflight_calls_consumer_probe_but_local_resource_check_does_not(self):
        for local in [False, True]:
            d1 = MagicMock()
            d1._get_columns.return_value = BASE_COLUMNS | (set() if local else CONTENT_COLUMNS)
            session = MagicMock()
            session.get.return_value.status_code = 200
            session.get.return_value.json.return_value = {"success": True, "result": {}}
            env = {} if local else ENV
            with self.subTest(local=local), patch.dict(os.environ, env, clear=True), \
                    patch("core.config.get_cloudflare_token", return_value=ENV["CLOUDFLARE_API_TOKEN"]), \
                    patch("core.config.BEEKIP_BASE_URL", APP), \
                    patch("cloudflare.d1_deployer.CloudflareD1Deployer", return_value=d1), \
                    patch("requests.Session", return_value=session), \
                    patch("services.run_cloud_cycle.verify_private_app_route") as cover, \
                    patch("services.run_cloud_cycle.verify_document_consumer_contract") as consumer:
                self.assertIs(preflight(local_read_only=local), d1)
                cover.assert_called_once()
                if local:
                    consumer.assert_not_called()
                else:
                    consumer.assert_called_once_with(APP)
                session.post.assert_not_called()
                session.put.assert_not_called()
                session.delete.assert_not_called()
                d1.execute_raw_sql.assert_not_called()

    def test_legacy_snapshot_uses_identical_rejection_probe(self):
        import ast
        from services import run_cloud_cycle
        def probe_tree(source):
            tree = ast.parse(source)
            return ast.dump(next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                                 and node.name == "verify_document_consumer_contract"))
        snapshot = Path(__file__).resolve().parents[1] / "integrations/legacy-crawler/source/services/run_cloud_cycle.py"
        self.assertEqual(probe_tree(Path(run_cloud_cycle.__file__).read_text(encoding="utf-8")),
                         probe_tree(snapshot.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
