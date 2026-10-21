import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from geo_entity_extractor import extract_geo_and_metadata, remove_accents
except ImportError:
    def remove_accents(s: str) -> str:
        if not s:
            return ""
        nfkd = unicodedata.normalize('NFKD', s)
        res = "".join(c for c in nfkd if not unicodedata.combining(c))
        return res.replace('đ', 'd').replace('Đ', 'D')

    def extract_geo_and_metadata(title: str, categories=None):
        return {"geo_province": None, "geo_school": None, "geo_region": None}

SUBJECTS_LIST = [
    ("Toán", ["toán", "hình học", "đại số", "giải tích", "math"]),
    ("Vật lý", ["vật lý", "vật lí", "physics"]),
    ("Hóa học", ["hóa học", "chemistry"]),
    ("Sinh học", ["sinh học", "biology"]),
    ("Tiếng Anh", ["tiếng anh", "english", "ielts", "chuyên anh"]),
    ("Ngữ văn", ["ngữ văn", "văn học"]),
    ("Lịch sử", ["lịch sử"]),
    ("Địa lý", ["địa lý", "địa lí"]),
    ("Tin học", ["tin học", "lập trình", "informatics"]),
    ("Giáo dục công dân", ["gdcd", "giáo dục công dân", "ktpl"])
]

DOC_TYPES = [
    ("Đề thi thử", ["đề thi thử", "thi thử tốt nghiệp", "thi thử thpt"]),
    ("Đề kiểm tra giữa kỳ 1", ["giữa học kỳ 1", "giữa kì 1", "giữa kỳ 1"]),
    ("Đề kiểm tra cuối kỳ 1", ["cuối học kỳ 1", "cuối kì 1", "cuối kỳ 1", "học kỳ 1"]),
    ("Đề kiểm tra giữa kỳ 2", ["giữa học kỳ 2", "giữa kì 2", "giữa kỳ 2"]),
    ("Đề kiểm tra cuối kỳ 2", ["cuối học kỳ 2", "cuối kì 2", "cuối kỳ 2", "học kỳ 2"]),
    ("Đề thi HSG", ["học sinh giỏi", "hsg", "olympic"]),
    ("Chuyên đề", ["chuyên đề", "phân dạng", "tổng hợp kiến thức"]),
    ("Giáo án", ["giáo án", "kế hoạch bài dạy", "5512", "bài giảng điện tử", "powerpoint"])
]

@dataclass
class EnrichedMetadata:
    title: str
    slug: str
    description: str
    subject: str
    grade: str
    academic_year: str
    geo_province: Optional[str]
    geo_school: Optional[str]
    curriculum: str
    document_type: str

class SEOGEOEnricher:
    """Enriches and standardizes article metadata for SEO, GEO search, and Beekip taxonomy."""

    @classmethod
    def generate_slug(cls, title: str) -> str:
        clean_text = remove_accents(title).lower()
        slug = re.sub(r'[^a-z0-9]+', '-', clean_text).strip('-')
        return slug[:120] if slug else "tai-lieu-k12"

    @classmethod
    def enrich(
        cls,
        title: str,
        default_subject: str = "Đa môn",
        raw_metadata: Optional[Dict[str, Any]] = None
    ) -> EnrichedMetadata:
        title_clean = title.strip()
        lower_title = title_clean.lower()

        # 1. Extract GEO (Province, School)
        geo_info = extract_geo_and_metadata(title_clean)
        province = geo_info.get("geo_province")
        school = geo_info.get("geo_school")
        if school and not school.startswith(("THPT ", "THCS ", "Tiểu học ")):
            school = f"THPT {school}"

        # 2. Extract Subject
        detected_subject = default_subject
        for sub_name, keywords in SUBJECTS_LIST:
            if any(k in lower_title for k in keywords):
                detected_subject = sub_name
                break

        # 3. Extract Grade
        grade = "THPT"
        grade_match = re.search(r'\b(?:lớp\s*|khối\s*)(\d{1,2})\b', lower_title)
        if grade_match:
            grade = f"Lớp {grade_match.group(1)}"
        else:
            if "12" in lower_title or "thpt" in lower_title:
                grade = "Lớp 12"
            elif "11" in lower_title:
                grade = "Lớp 11"
            elif "10" in lower_title:
                grade = "Lớp 10"
            elif "9" in lower_title or "vào 10" in lower_title:
                grade = "Lớp 9"

        # 4. Extract Academic Year
        academic_year = "2024-2025"
        year_match = re.search(r'\b(202[2-6]\s*[-–/]\s*202[3-7])\b', title_clean)
        if year_match:
            academic_year = re.sub(r'\s*[-–/]\s*', '-', year_match.group(1))
        else:
            single_year = re.search(r'\b(202[3-6])\b', title_clean)
            if single_year:
                y = int(single_year.group(1))
                academic_year = f"{y-1}-{y}"

        # 5. Extract Curriculum
        curriculum = "GDPT 2018"
        if "kết nối tri thức" in lower_title:
            curriculum = "Kết nối tri thức"
        elif "chân trời sáng tạo" in lower_title:
            curriculum = "Chân trời sáng tạo"
        elif "cánh diều" in lower_title:
            curriculum = "Cánh diều"

        # 6. Extract Document Type
        doc_type = "Tài liệu học tập"
        for dt_name, dt_keywords in DOC_TYPES:
            if any(k in lower_title for k in dt_keywords):
                doc_type = dt_name
                break

        # 7. Generate Slug
        slug = cls.generate_slug(title_clean)

        # 8. Compose SEO Description
        school_text = f" trường {school}" if school else ""
        province_text = f" tỉnh {province}" if province else ""
        description = (
            f"Tài liệu {title_clean}{school_text}{province_text}. "
            f"Học liệu {detected_subject} {grade} chuẩn chương trình {curriculum}, "
            f"năm học {academic_year}, hỗ trợ tải file PDF miễn phí tại tailieu.beekip.vn."
        )

        return EnrichedMetadata(
            title=title_clean,
            slug=slug,
            description=description,
            subject=detected_subject,
            grade=grade,
            academic_year=academic_year,
            geo_province=province,
            geo_school=school,
            curriculum=curriculum,
            document_type=doc_type
        )
