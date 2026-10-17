"""
Unit and Integration Tests for Beekip Multi-Agentic Architecture.
Covers Agent 1, Agent 2, Agent 3, Indexer Sentinel, and Self-Healing Feedback Loop.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

import pymupdf

from services.indexer_sentinel import IndexerSentinel
from services.agent_content_processor import ContentProcessorAgent
from services.agent_qa_sentinel import QASentinelAgent
from services.agent_auto_publisher import AutoPublisherAgent
from services.multi_agent_orchestrator import MultiAgentPipelineOrchestrator


def create_dummy_pdf(path: Path, num_pages: int = 3, text: str = "Tài liệu Toán học Beekip chuẩn GDPT 2018."):
    doc = pymupdf.open()
    for _ in range(num_pages):
        page = doc.new_page(width=595, height=842)
        # Add repeated text to satisfy min chars per page
        full_page_text = (text + "\n") * 15
        page.insert_text((50, 50), full_page_text, fontsize=11)
    doc.save(str(path))
    doc.close()


def create_dummy_cover(path: Path, width: int = 1200, height: int = 1697):
    img = Image.new("RGB", (width, height), color=(240, 245, 250))
    img.save(str(path), format="JPEG", quality=85)


class TestMultiAgenticFleet(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="beekip-test-fleet-")
        self.working_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_indexer_sentinel_payload_and_news_xml(self):
        indexer = IndexerSentinel(host="tailieu.beekip.vn", indexnow_key="test-key")

        # Test Google News XML builder
        xml_entry = indexer.build_google_news_xml_entry(
            url="https://tailieu.beekip.vn/tai-lieu/de-thi-toan-12",
            title="Đề thi thử THPT Quốc gia môn Toán 2026",
            published_at="2026-10-10T12:00:00Z",
        )
        self.assertIn("<news:publication>", xml_entry)
        self.assertIn("<news:name>Học Liệu Beekip</news:name>", xml_entry)
        self.assertIn("<news:language>vi</news:language>", xml_entry)
        self.assertIn("<news:title>Đề thi thử THPT Quốc gia môn Toán 2026</news:title>", xml_entry)

        # Test IndexNow mock request
        with patch.object(indexer.session, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, text="OK")
            res = indexer.notify_indexnow(["/tai-lieu/de-thi-1", "/tai-lieu/de-thi-2"])
            self.assertTrue(res["success"])
            self.assertEqual(res["count"], 2)

    def test_agent1_dual_schema_and_markdown(self):
        agent1 = ContentProcessorAgent()

        # Test Markdown content generation
        md = agent1.generate_geo_seo_markdown(
            meta_title="Đề thi khảo sát Toán 12 trường THPT Trần Phú",
            subject="Toán",
            grade=12,
            school="THPT Trần Phú - Hà Nội",
            source_url="https://toanmath.com/test-exam",
            page_count=6,
            file_size_bytes=1024 * 1024 * 2,
            detected_year=2026,
            extended_analysis=True,
        )
        self.assertIn("## 1. THÔNG TIN HỌC LIỆU & TỔNG QUAN XUẤT BẢN", md)
        self.assertIn("## 2. NỘI DUNG TRỌNG TÂM", md)
        self.assertIn("## 3. HƯỚNG DẪN HỌC TẬP", md)
        self.assertIn("## 4. BẢN QUYỀN HỌC LIỆU", md)
        self.assertIn("THPT Trần Phú - Hà Nội", md)
        self.assertIn("$", md)  # KaTeX verification

        # Test Dual Schema.org JSON-LD
        schema = agent1.build_dual_schema_jsonld(
            title="Đề thi Toán 12",
            slug="de-thi-toan-12",
            subject="Toán",
            grade=12,
            school="THPT Trần Phú",
            published_year=2026,
            cover_url="https://tailieu.beekip.vn/cover.jpg",
            file_url="https://tailieu.beekip.vn/download.pdf",
            date_published="2026-10-10T10:00:00Z",
        )
        self.assertIn("@graph", schema)
        types = [str(item.get("@type")) for item in schema["@graph"]]
        self.assertTrue(any("LearningResource" in t for t in types))
        self.assertTrue(any("NewsArticle" in t for t in types))

    def test_agent2_audit_clean_pass(self):
        pdf_path = self.working_dir / "clean.pdf"
        cover_path = self.working_dir / "cover.jpg"
        create_dummy_pdf(pdf_path, num_pages=3)
        create_dummy_cover(cover_path, width=1200, height=1600)

        agent1 = ContentProcessorAgent()
        desc = agent1.generate_geo_seo_markdown(
            meta_title="Đề thi giữa học kỳ 1 Toán 12 trường THPT Trần Phú Hà Nội",
            subject="Toán",
            grade=12,
            school="THPT Trần Phú - Hà Nội",
            source_url="https://toanmath.com/sample",
            page_count=3,
            file_size_bytes=pdf_path.stat().st_size,
            detected_year=2026,
        )
        schema = agent1.build_dual_schema_jsonld(
            title="Đề thi giữa học kỳ 1 Toán 12 trường THPT Trần Phú Hà Nội",
            slug="de-thi-giua-hoc-ky-1-toan-12-truong-thpt-tran-phu-ha-noi",
            subject="Toán",
            grade=12,
            school="THPT Trần Phú - Hà Nội",
            published_year=2026,
            cover_url="https://tailieu.beekip.vn/cover.jpg",
            file_url="https://tailieu.beekip.vn/download.pdf",
            date_published="2026-10-10T10:00:00Z",
        )

        draft = {
            "title": "Đề thi giữa học kỳ 1 Toán 12 trường THPT Trần Phú Hà Nội",
            "slug": "de-thi-giua-hoc-ky-1-toan-12-truong-thpt-tran-phu-ha-noi",
            "subject": "Toán",
            "grade": 12,
            "author_name": "THPT Trần Phú - Hà Nội",
            "description": desc,
            "clean_pdf_path": str(pdf_path),
            "cover_image_path": str(cover_path),
            "schema_jsonld": schema,
        }

        agent2 = QASentinelAgent()
        report = agent2.audit_draft_package(draft)

        self.assertTrue(report.is_approved, f"Audit unexpectedly failed with defects: {report.defects}")
        self.assertEqual(report.overall_score, 100.0)
        self.assertEqual(len(report.defects), 0)

    def test_agent1_agent2_self_healing_feedback_loop(self):
        pdf_path = self.working_dir / "clean_sh.pdf"
        cover_path = self.working_dir / "cover_sh.jpg"
        create_dummy_pdf(pdf_path, num_pages=2)
        # Deliberately create an undersized cover (800px instead of >= 1200px)
        create_dummy_cover(cover_path, width=800, height=1000)

        agent1 = ContentProcessorAgent()
        # Deliberately short description with no H2 tags
        flawed_desc = "Tài liệu học tập ngắn ngủi không đủ 300 từ."

        flawed_draft = {
            "title": "Đề thi khảo sát Toán 12 năm 2026 THPT Chu Văn An",
            "slug": "de-thi-khao-sat-toan-12-nam-2026-thpt-chu-van-an",
            "subject": "Toán",
            "grade": 12,
            "author_name": "THPT Chu Văn An",
            "academic_year": "2026",
            "raw_url": "https://toanmath.com/sample",
            "description": flawed_desc,
            "clean_pdf_path": str(pdf_path),
            "cover_image_path": str(cover_path),
            "schema_jsonld": {},  # missing schema
        }

        agent2 = QASentinelAgent()

        # Step 1: Agent 2 Audits flawed draft -> REJECTED
        initial_report = agent2.audit_draft_package(flawed_draft)
        self.assertFalse(initial_report.is_approved)
        self.assertGreater(len(initial_report.defects), 0)

        # Step 2: Agent 1 receives defect tickets and repairs the draft
        refined_draft = agent1.refine_draft_package(flawed_draft, initial_report.defects)

        # Step 3: Agent 2 re-audits the refined draft -> APPROVED
        re_audit = agent2.audit_draft_package(refined_draft)
        self.assertTrue(re_audit.is_approved, f"Self-healing failed to resolve defects: {re_audit.defects}")
        self.assertEqual(re_audit.overall_score, 100.0)

    def test_agent3_auto_publisher_execution(self):
        pdf_path = self.working_dir / "pub.pdf"
        cover_path = self.working_dir / "pub_cover.jpg"
        create_dummy_pdf(pdf_path, num_pages=2)
        create_dummy_cover(cover_path, width=1200, height=1600)

        mock_db = MagicMock()
        mock_r2 = MagicMock()
        mock_r2.upload_document.side_effect = [
            ("documents/v1/mock/source.pdf", "https://files.beekip.vn/source.pdf"),
            ("documents/v1/mock/cover.jpg", "https://files.beekip.vn/cover.jpg"),
        ]
        mock_d1 = MagicMock()
        mock_d1.find_existing_document.return_value = None
        mock_indexer = MagicMock()
        mock_indexer.notify_indexnow.return_value = {"success": True, "count": 1}
        mock_indexer.ping_sitemaps.return_value = {"google": {"success": True}}

        agent3 = AutoPublisherAgent(
            db=mock_db,
            r2_uploader=mock_r2,
            d1_deployer=mock_d1,
            indexer=mock_indexer,
        )

        draft = {
            "title": "Đề thi thử THPT Quốc gia môn Toán 2026 trường Lương Thế Vinh",
            "slug": "de-thi-thu-thpt-quoc-gia-mon-toan-2026-truong-luong-the-vinh",
            "subject": "Toán",
            "grade": 12,
            "category": "ĐỀ THI THỬ THPT",
            "author_name": "THPT Lương Thế Vinh",
            "academic_year": "2026",
            "description": "Nội dung bài viết chuẩn SEO...",
            "clean_pdf_path": str(pdf_path),
            "cover_image_path": str(cover_path),
            "page_count": 2,
        }

        res = agent3.publish_approved_draft(draft, source_url="https://toanmath.com/sample-exam")
        self.assertTrue(res["success"])
        self.assertEqual(res["slug"], draft["slug"])

        # Verify R2 was called twice (pdf and cover)
        self.assertEqual(mock_r2.upload_document.call_count, 2)
        # Verify D1 was called once
        self.assertEqual(mock_d1.insert_document.call_count, 1)
        # Verify queue status updated to COMPLETED
        mock_db.update_inbound_status.assert_called_with("https://toanmath.com/sample-exam", "COMPLETED")
        # Verify IndexNow notified
        mock_indexer.notify_indexnow.assert_called_once()


if __name__ == "__main__":
    unittest.main()
