"""Source evidence regressions: no cloud access or corpus mutations."""
import unittest
from geo_entity_extractor import extract_geo_and_metadata

class ProvinceEvidenceTests(unittest.TestCase):
    def test_reported_dong_nai_authority_does_not_match_na(self):
        result = extract_geo_and_metadata("Đề tham khảo học sinh giỏi Toán 12 năm 2024 – 2025 sở GD&ĐT Đồng Nai")
        self.assertEqual(result["geo_province"], "Đồng Nai")
        self.assertEqual(result["geo_region"], "Miền Nam")
        self.assertEqual(result["metadata_review_status"], "verified")
        self.assertTrue(result["geo_evidence"])

    def test_full_authority_names_and_unaccented_aliases(self):
        for label, expected in [("Nghệ An", "Nghệ An"), ("Thanh Hóa", "Thanh Hóa"),
                                ("Bình Thuận", "Bình Thuận"), ("Huế", "Thừa Thiên Huế"), ("Dong Nai", "Đồng Nai")]:
            with self.subTest(label=label):
                self.assertEqual(extract_geo_and_metadata("Đề Toán 12 sở GD&ĐT " + label)["geo_province"], expected)

    def test_short_or_embedded_alias_is_not_evidence(self):
        for title in ["Đề thi Toán 12 sở GD&ĐT NA", "Đề toán sở GD&ĐT Banana", "Đề Toán Dong Naive"]:
            with self.subTest(title=title):
                result = extract_geo_and_metadata(title)
                self.assertEqual(result["geo_province"], "")
                self.assertEqual(result["metadata_review_status"], "needs_review")

    def test_conflicting_source_locations_require_review(self):
        result = extract_geo_and_metadata("Đề Toán trường chuyên Phan Bội Châu - Đồng Nai")
        self.assertEqual(result["geo_province"], "")
        self.assertEqual(result["metadata_review_status"], "needs_review")
        self.assertEqual(result["geo_conflicts"], ["Nghệ An", "Đồng Nai"])

    def test_historical_province_is_preserved(self):
        self.assertEqual(extract_geo_and_metadata("Đề Toán 12 năm 2024 sở GD&ĐT Bình Dương")["geo_province"], "Bình Dương")

if __name__ == "__main__":
    unittest.main()
