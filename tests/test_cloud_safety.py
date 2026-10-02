"""Offline regressions for the cloud publishing and persistence boundaries."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import requests
from cloudflare.cloud_ledger import CloudLedger
from cloudflare.d1_deployer import CloudflareD1Deployer
from cloudflare.r2_uploader import CloudflareR2Uploader
from processing.file_downloader import DownloadedFileResult, ResilientFileDownloader
from services.cloud_pipeline import CloudPipeline, eligible_year
from services.derivative_renderer import DerivativeRendererEngine
from services.run_cloud_cycle import preflight, verify_private_app_route
from services.sanitizer import DeepSanitizerEngine
from services.omni_scheduler import OmniSchedulerDaemon


class SQLiteD1:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def execute_raw_sql(self, sql, params=None):
        cursor = self.conn.execute(sql, params or [])
        rows = [dict(row) for row in cursor.fetchall()]
        self.conn.commit()
        return {'success': True, 'result': [{'success': True, 'results': rows}]}


class CloudSafety(unittest.TestCase):
    def test_private_bucket_route_matches_without_forwarding_credential(self):
        d1, session = MagicMock(), MagicMock()
        d1.execute_raw_sql.return_value = {'result': [{'results': [{'id': 'doc-id', 'slug': 'example-2025'}]}]}
        private, public = MagicMock(), MagicMock()
        for response in [private, public]:
            response.status_code = 200
            response.iter_content.return_value = [b'cover bytes']
        session.get.return_value = private
        with patch('requests.get', return_value=public) as public_request:
            verify_private_app_route(d1, session, 'https://api.cloudflare.com/bucket', 'https://tailieu.beekip.vn')
            self.assertNotIn('headers', public_request.call_args.kwargs)
            self.assertFalse(public_request.call_args.kwargs['allow_redirects'])
        session.put.assert_not_called()

    def test_private_bucket_route_mismatch_fails(self):
        d1, session = MagicMock(), MagicMock()
        d1.execute_raw_sql.return_value = {'result': [{'results': [{'id': 'doc-id', 'slug': 'example-2025'}]}]}
        session.get.return_value.status_code = 200
        session.get.return_value.iter_content.return_value = [b'actual cover']
        public = MagicMock(status_code=200)
        public.iter_content.return_value = [b'fallback image']
        with patch('requests.get', return_value=public), self.assertRaisesRegex(RuntimeError, 'Could not verify'):
            verify_private_app_route(d1, session, 'https://api.cloudflare.com/bucket', 'https://tailieu.beekip.vn')

    def test_failed_source_is_not_a_successful_empty_feed(self):
        db, pipeline = MagicMock(), MagicMock()
        pipeline.cloud_mode = True
        db.get_active_sources.return_value = [dict(source_id='one', domain='example.test')]
        db.get_pending_inbound_items.return_value = []
        adapter = MagicMock()
        adapter.source_info = {}
        adapter.session = requests.Session()
        adapter.session.request = MagicMock(return_value=MagicMock(status_code=503))
        def empty_after_failed_fetch(**kwargs):
            adapter.session.get('https://example.test/feed')
            return []
        adapter.fetch_latest_posts.side_effect = empty_after_failed_fetch
        daemon = OmniSchedulerDaemon(db=db, pipeline=pipeline)
        try:
            with patch('services.omni_scheduler.get_adapter_for_source', return_value=adapter):
                result = daemon.run_single_cycle(3)
            self.assertEqual(result['source_errors'], 1)
            self.assertEqual(result['sources_checked'], 0)
            self.assertEqual(db.complete_monitoring_cycle.call_args.kwargs['status'], 'FAILED')
        finally:
            daemon.worker_pool.shutdown()

    def test_sanitization_produces_stable_bytes_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pipeline = self.prepare_pipeline(folder)
            original = pipeline.downloader.download.return_value.file_path
            sanitizer = DeepSanitizerEngine()
            for name in ['first.pdf', 'retry.pdf']:
                self.assertTrue(sanitizer.sanitize_pdf_derivative(original, folder / name)['success'])
            self.assertEqual((folder / 'first.pdf').read_bytes(), (folder / 'retry.pdf').read_bytes())

    def test_ledger_survives_restart_and_preserves_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = SQLiteD1(Path(tmp) / 'state.db')
            ledger = CloudLedger(client)
            ledger.initialize()
            item = dict(url='https://example.test/doc', source_id='source', title='Test 2025')
            ledger.enqueue_inbound_items([item])
            ledger.update_inbound_status(item['url'], 'COMPLETED')
            client.conn.close()
            client2 = SQLiteD1(Path(tmp) / 'state.db')
            restarted = CloudLedger(client2)
            restarted.initialize()
            restarted.enqueue_inbound_items([item])
            self.assertEqual(restarted.get_pending_inbound_items(), [])
            client2.conn.close()

    def test_interruption_recovery_and_retry_limit(self):
        client = SQLiteD1(':memory:')
        ledger = CloudLedger(client)
        ledger.initialize()
        item = dict(url='https://example.test/1', source_id='a')
        ledger.enqueue_inbound_items([item])
        ledger.update_inbound_status(item['url'], 'PROCESSING')
        ledger.initialize()
        self.assertEqual(len(ledger.get_pending_inbound_items()), 1)
        for _ in range(3):
            ledger.update_inbound_status(item['url'], 'FAILED', increment_retry=True)
        ledger.enqueue_inbound_items([item])
        self.assertEqual(ledger.get_pending_inbound_items(), [])
        client.conn.close()

    def test_headers_and_source_rotation_are_durable(self):
        client = SQLiteD1(':memory:')
        ledger = CloudLedger(client)
        ledger.initialize()
        ledger.sources = [dict(source_id=s, status='ACTIVE') for s in ['a','b']]
        ledger.update_source_sync_meta('a', 'v1', 'yesterday')
        ledger.update_source_sync_meta('a')
        active = ledger.get_active_sources()
        self.assertEqual(active[0]['source_id'], 'b')
        self.assertEqual(active[1]['last_etag'], 'v1')
        client.conn.close()

    @patch('cloudflare.d1_deployer.requests.post')
    def test_d1_nested_failure_is_not_success(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'success': True, 'result': [{'success': False}]}
        with self.assertRaises(RuntimeError):
            CloudflareD1Deployer(api_token='test').execute_raw_sql('SELECT 1')

    @patch('cloudflare.r2_uploader.requests.put')
    def test_repeated_upload_uses_same_content_key(self, put):
        put.return_value.status_code = 200
        uploader = CloudflareR2Uploader(api_token='test')
        one = uploader.upload_document(b'pdf', 'toan', '2025', 'one')
        two = uploader.upload_document(b'pdf', 'toan', '2025', 'two')
        self.assertEqual(one, two)
        self.assertNotEqual(one, uploader.upload_document(b'other', 'toan', '2025', 'one'))

    def test_curriculum_is_not_a_date(self):
        self.assertFalse(eligible_year(dict(title='GDPT 2018 Kết nối tri thức', url='', published_year=2021)))
        self.assertFalse(eligible_year(dict(title='GDPT 2018 Kết nối tri thức', url='')))
        self.assertTrue(eligible_year(dict(title='GDPT 2018 đề thi 2025', url='')))

    def test_missing_secrets_stop_before_network(self):
        with patch.dict('os.environ', {}, clear=True), patch('requests.Session') as session:
            with self.assertRaisesRegex(RuntimeError, 'Missing repository secrets'):
                preflight()
            session.assert_not_called()

    def test_fake_pdf_and_images_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            response = MagicMock()
            response.headers = {'Content-Type': 'application/pdf'}
            response.iter_content.return_value = [b'<html>login required</html>']
            downloader = ResilientFileDownloader()
            self.assertIsNone(downloader._save_stream_to_disk(response, 'https://x/a.pdf', Path(tmp), 'a.pdf'))
            self.assertEqual(list(Path(tmp).iterdir()), [])
            response.headers = {'Content-Type': 'image/png'}
            self.assertIsNone(downloader._save_stream_to_disk(response, 'https://x/a.pdf', Path(tmp), 'a.pdf'))

    def test_each_page_needs_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'scanned.pdf'
            with pymupdf.open() as pdf:
                pdf.new_page().insert_text((40, 40), ('Algebra exercises x plus y equals z\n' * 20))
                pdf.new_page()
                pdf.save(path)
            self.assertFalse(DerivativeRendererEngine().validate_pdf_standards(path)['has_searchable_text'])

    def prepare_pipeline(self, folder):
        pdf_path = folder / 'test.pdf'
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((40, 40), 'Algebra exercises x plus y equals z\n' * 20)
            pdf.save(pdf_path)
        db, r2, d1 = MagicMock(), MagicMock(), MagicMock()
        db.stored_bytes.return_value = 0
        d1.check_document_exists.return_value = False
        r2.upload_document.side_effect = [('pdf/key.pdf', 'https://files.test/key.pdf'), ('cover/key.jpg', 'https://files.test/key.jpg')]
        pipeline = CloudPipeline(db, r2, d1)
        pipeline.downloader = MagicMock()
        pipeline.downloader.download.return_value = DownloadedFileResult(pdf_path, 'hash', pdf_path.stat().st_size,
            'application/pdf', 'test.pdf', 'https://example.test/file.pdf')
        return pipeline

    def test_sanitizer_failure_never_uploads_or_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self.prepare_pipeline(Path(tmp))
            with patch('services.cloud_pipeline.get_adapter_for_source') as adapter, patch('services.cloud_pipeline.DeepSanitizerEngine') as sanitizer:
                adapter.return_value.extract_download_links.return_value = [MagicMock(file_type='PDF', url='https://x/f.pdf', file_name='test.pdf')]
                sanitizer.return_value.sanitize_pdf_derivative.return_value = {'success': False}
                self.assertFalse(pipeline.process_inbound_url(dict(url='https://x/a', title='Đề thi Toán 12 2025', published_year=2025), {}))
            pipeline.r2.upload_document.assert_not_called()
            pipeline.d1.insert_document.assert_not_called()

    def test_valid_pdf_passes_real_sanitizer_render_and_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self.prepare_pipeline(Path(tmp))
            with patch('services.cloud_pipeline.get_adapter_for_source') as adapter:
                adapter.return_value.extract_download_links.return_value = [MagicMock(file_type='PDF', url='https://x/f.pdf', file_name='test.pdf')]
                result = pipeline.process_inbound_url(dict(url='https://x/a', title='Đề thi Toán 12 2025', published_year=2025), {})
            self.assertTrue(result, pipeline.db.update_inbound_status.call_args_list)
            self.assertEqual(pipeline.r2.upload_document.call_count, 2)
            pipeline.d1.insert_document.assert_called_once()
            self.assertGreater(pipeline.d1.insert_document.call_args.kwargs['page_count'], 0)
            self.assertTrue(pipeline.d1.insert_document.call_args.kwargs['cover_url'].endswith('/cover'))
            self.assertIn('/api/documents/', pipeline.d1.insert_document.call_args.args[1])
            cover_args = pipeline.r2.upload_document.call_args_list[1].kwargs
            self.assertRegex(cover_args['storage_key'], r'^documents/v1/[a-f0-9-]{36}/cover\.jpg$')

    def test_qa_rejection_never_uploads(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self.prepare_pipeline(Path(tmp))
            with patch('services.cloud_pipeline.get_adapter_for_source') as adapter, patch('services.cloud_pipeline.QAGateInspector') as qa:
                adapter.return_value.extract_download_links.return_value = [MagicMock(file_type='PDF', url='https://x/f.pdf', file_name='test.pdf')]
                qa.return_value.inspect_document.return_value = {'is_published_eligible': False, 'checklist': {'pii': {'pass': False}}}
                self.assertFalse(pipeline.process_inbound_url(dict(url='https://x/a', title='Đề thi Toán 12 2025', published_year=2025), {}))
            pipeline.r2.upload_document.assert_not_called()
            pipeline.d1.insert_document.assert_not_called()


if __name__ == '__main__':
    unittest.main()
