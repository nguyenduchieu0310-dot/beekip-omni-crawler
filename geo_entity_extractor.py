import re
import unicodedata
from typing import Dict, Any, Optional, Tuple, List

# Danh sách 63 tỉnh/thành phố và vùng địa lý
PROVINCES_DICT = {
    # Miền Bắc
    "Hà Nội": {"region": "Miền Bắc", "aliases": ["hà nội", "ha noi", "hanoi", "hn", "hà tây", "ha tay"]},
    "Hải Phòng": {"region": "Miền Bắc", "aliases": ["hải phòng", "hai phong", "hp"]},
    "Quảng Ninh": {"region": "Miền Bắc", "aliases": ["quảng ninh", "quang ninh"]},
    "Bắc Ninh": {"region": "Miền Bắc", "aliases": ["bắc ninh", "bac ninh"]},
    "Hà Nam": {"region": "Miền Bắc", "aliases": ["hà nam", "ha nam"]},
    "Hải Dương": {"region": "Miền Bắc", "aliases": ["hải dương", "hai duong"]},
    "Hưng Yên": {"region": "Miền Bắc", "aliases": ["hưng yên", "hung yen"]},
    "Nam Định": {"region": "Miền Bắc", "aliases": ["nam định", "nam dinh", "nđ"]},
    "Ninh Bình": {"region": "Miền Bắc", "aliases": ["ninh bình", "ninh binh"]},
    "Thái Bình": {"region": "Miền Bắc", "aliases": ["thái bình", "thai binh"]},
    "Vĩnh Phúc": {"region": "Miền Bắc", "aliases": ["vĩnh phúc", "vinh phuc", "vp"]},
    "Phú Thọ": {"region": "Miền Bắc", "aliases": ["phú thọ", "phu tho", "pt"]},
    "Bắc Giang": {"region": "Miền Bắc", "aliases": ["bắc giang", "bac giang"]},
    "Thái Nguyên": {"region": "Miền Bắc", "aliases": ["thái nguyên", "thai nguyen"]},
    "Lạng Sơn": {"region": "Miền Bắc", "aliases": ["lạng sơn", "lang son"]},
    "Tuyên Quang": {"region": "Miền Bắc", "aliases": ["tuyên quang", "tuyen quang"]},
    "Yên Bái": {"region": "Miền Bắc", "aliases": ["yên bái", "yen bai"]},
    "Lào Cai": {"region": "Miền Bắc", "aliases": ["lào cai", "lao cai"]},
    "Hà Giang": {"region": "Miền Bắc", "aliases": ["hà giang", "ha giang"]},
    "Cao Bằng": {"region": "Miền Bắc", "aliases": ["cao bằng", "cao bang"]},
    "Bắc Kạn": {"region": "Miền Bắc", "aliases": ["bắc kạn", "bac kan"]},
    "Điện Biên": {"region": "Miền Bắc", "aliases": ["điện biên", "dien bien"]},
    "Lai Châu": {"region": "Miền Bắc", "aliases": ["lai châu", "lai chau"]},
    "Sơn La": {"region": "Miền Bắc", "aliases": ["sơn la", "son la"]},
    "Hòa Bình": {"region": "Miền Bắc", "aliases": ["hòa bình", "hoa binh"]},

    # Miền Trung
    "Thanh Hóa": {"region": "Miền Trung", "aliases": ["thanh hóa", "thanh hoa", "th"]},
    "Nghệ An": {"region": "Miền Trung", "aliases": ["nghệ an", "nghe an", "na"]},
    "Hà Tĩnh": {"region": "Miền Trung", "aliases": ["hà tĩnh", "ha tinh"]},
    "Quảng Bình": {"region": "Miền Trung", "aliases": ["quảng bình", "quang binh"]},
    "Quảng Trị": {"region": "Miền Trung", "aliases": ["quảng trị", "quang tri"]},
    "Thừa Thiên Huế": {"region": "Miền Trung", "aliases": ["thừa thiên huế", "thua thien hue", "huế", "hue"]},
    "Đà Nẵng": {"region": "Miền Trung", "aliases": ["đà nẵng", "da nang", "đn"]},
    "Quảng Nam": {"region": "Miền Trung", "aliases": ["quảng nam", "quang nam"]},
    "Quảng Ngãi": {"region": "Miền Trung", "aliases": ["quảng ngãi", "quang ngai"]},
    "Bình Định": {"region": "Miền Trung", "aliases": ["bình định", "binh dinh"]},
    "Phú Yên": {"region": "Miền Trung", "aliases": ["phú yên", "phu yen"]},
    "Khánh Hòa": {"region": "Miền Trung", "aliases": ["khánh hòa", "khanh hoa", "nha trang"]},
    "Ninh Thuận": {"region": "Miền Trung", "aliases": ["ninh thuận", "ninh thuan"]},
    "Bình Thuận": {"region": "Miền Trung", "aliases": ["bình thuận", "binh thuan"]},

    # Tây Nguyên
    "Kon Tum": {"region": "Tây Nguyên", "aliases": ["kon tum", "kontum"]},
    "Gia Lai": {"region": "Tây Nguyên", "aliases": ["gia lai", "gialai"]},
    "Đắk Lắk": {"region": "Tây Nguyên", "aliases": ["đắk lắk", "dak lak", "đắc lắc", "buôn ma thuột"]},
    "Đắk Nông": {"region": "Tây Nguyên", "aliases": ["đắk nông", "dak nong", "đắc nông"]},
    "Lâm Đồng": {"region": "Tây Nguyên", "aliases": ["lâm đồng", "lam dong", "đà lạt"]},

    # Miền Nam (Đông Nam Bộ & ĐBSCL)
    "Hồ Chí Minh": {"region": "Miền Nam", "aliases": ["hồ chí minh", "ho chi minh", "tp hcm", "tp.hcm", "tphcm", "sài gòn", "sai gon", "tp. hcm"]},
    "Bình Dương": {"region": "Miền Nam", "aliases": ["bình dương", "binh duong"]},
    "Đồng Nai": {"region": "Miền Nam", "aliases": ["đồng nai", "dong nai", "biên hòa"]},
    "Bà Rịa - Vũng Tàu": {"region": "Miền Nam", "aliases": ["bà rịa", "vũng tàu", "ba ria", "vung tau", "brvt"]},
    "Tây Ninh": {"region": "Miền Nam", "aliases": ["tây ninh", "tay ninh"]},
    "Bình Phước": {"region": "Miền Nam", "aliases": ["bình phước", "binh phuoc"]},
    "Long An": {"region": "Miền Nam", "aliases": ["long an"]},
    "Tiền Giang": {"region": "Miền Nam", "aliases": ["tiền giang", "tien giang", "mỹ tho"]},
    "Bến Tre": {"region": "Miền Nam", "aliases": ["bến tre", "ben tre"]},
    "Trà Vinh": {"region": "Miền Nam", "aliases": ["trà vinh", "tra vinh"]},
    "Vĩnh Long": {"region": "Miền Nam", "aliases": ["vĩnh long", "vinh long"]},
    "Đồng Tháp": {"region": "Miền Nam", "aliases": ["đồng tháp", "dong thap", "cao lãnh"]},
    "An Giang": {"region": "Miền Nam", "aliases": ["an giang", "long xuyên"]},
    "Kiên Giang": {"region": "Miền Nam", "aliases": ["kiên giang", "kien giang", "rạch giá"]},
    "Cần Thơ": {"region": "Miền Nam", "aliases": ["cần thơ", "can tho"]},
    "Hậu Giang": {"region": "Miền Nam", "aliases": ["hậu giang", "hau giang"]},
    "Sóc Trăng": {"region": "Miền Nam", "aliases": ["sóc trăng", "soc trang"]},
    "Bạc Liêu": {"region": "Miền Nam", "aliases": ["bạc liêu", "bac lieu"]},
    "Cà Mau": {"region": "Miền Nam", "aliases": ["cà mau", "ca mau"]}
}

# Trường chuyên nổi tiếng gắn với tỉnh
SPECIALIZED_SCHOOLS = {
    "Chuyên Hà Nội - Amsterdam": "Hà Nội",
    "Chuyên Chu Văn An": "Hà Nội",
    "Chuyên Sư Phạm": "Hà Nội",
    "Chuyên Khoa Học Tự Nhiên": "Hà Nội",
    "Chuyên Ngoại Ngữ": "Hà Nội",
    "Chuyên Nguyễn Huệ": "Hà Nội",
    "Chuyên Lam Sơn": "Thanh Hóa",
    "Chuyên Phan Bội Châu": "Nghệ An",
    "Chuyên Lê Hồng Phong": "Hồ Chí Minh",
    "Chuyên Trần Đại Nghĩa": "Hồ Chí Minh",
    "Chuyên Quốc Học Huế": "Thừa Thiên Huế",
    "Chuyên Bắc Ninh": "Bắc Ninh",
    "Chuyên Vĩnh Phúc": "Vĩnh Phúc",
    "Chuyên Hùng Vương": "Phú Thọ",
    "Chuyên Thái Bình": "Thái Bình",
    "Chuyên Lương Văn Tụy": "Ninh Bình",
    "Chuyên Biên Hòa": "Hà Nam",
    "Chuyên Nguyễn Trãi": "Hải Dương",
    "Chuyên Trần Phú": "Hải Phòng",
    "Chuyên Hạ Long": "Quảng Ninh",
    "Chuyên Hoàng Văn Thụ": "Hòa Bình",
    "Chuyên Lê Quý Đôn": "Đà Nẵng",
    "Chuyên Nguyễn Bỉnh Khiêm": "Quảng Nam",
    "Chuyên Lê Khiết": "Quảng Ngãi",
    "Chuyên Lương Thế Vinh": "Đồng Nai",
    "Chuyên Thoại Ngọc Hầu": "An Giang",
    "Chuyên Lý Tự Trọng": "Cần Thơ",
    "Chuyên Nguyễn Quang Diêu": "Đồng Tháp",
    "Chuyên Bến Tre": "Bến Tre",
    "Chuyên Huỳnh Mẫn Đạt": "Kiên Giang",
    "Chuyên Nguyễn Du": "Đắk Lắk",
    "Chuyên Thăng Long": "Lâm Đồng",
    "Chuyên Hùng Vương - Gia Lai": "Gia Lai"
}

def remove_accents(input_str: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu thành không dấu."""
    if not input_str:
        return ""
    nfkd = unicodedata.normalize('NFKD', input_str)
    no_accent = "".join([c for c in nfkd if not unicodedata.combining(c)])
    no_accent = no_accent.replace('đ', 'd').replace('Đ', 'D')
    return no_accent

def extract_geo_and_metadata(title: str, categories: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Trích xuất thực thể địa lý (GEO) và siêu dữ liệu sư phạm từ tiêu đề bài viết:
    - geo_province: Tỉnh/thành phố chuẩn hóa
    - geo_region: Vùng miền (Miền Bắc, Miền Trung, Miền Nam, Tây Nguyên)
    - geo_authority: Sở GD&ĐT / Phòng GD&ĐT nếu có
    - geo_school: Tên trường học nếu có
    - academic_year: Năm học (2025 - 2026, 2024 - 2025, v.v.)
    - doc_type: Loại hình tài liệu chuẩn hóa
    - grade_name: Tên lớp hiển thị chuẩn (Lớp 10, Lớp 11, Lớp 12, v.v.)
    - has_answers: Có đáp án chi tiết không
    """
    title_norm = title.replace("–", "-").replace("—", "-")
    title_lower = title_norm.lower()
    cat_text = " ".join(categories or []).lower()
    combined_text = f"{title_lower} {cat_text}"

    # 1. Trích xuất Năm học (Academic Year)
    year_match = re.search(r'(201\d|202\d)\s*[-–/]\s*(201\d|202\d)', title_norm)
    if year_match:
        academic_year = f"{year_match.group(1)} - {year_match.group(2)}"
    else:
        single_year = re.search(r'\b(201\d|202\d)\b', title_norm)
        if single_year:
            y = int(single_year.group(1))
            academic_year = f"{y - 1} - {y}"
        else:
            academic_year = "2025 - 2026"

    # 2. Nhận diện Trường học (School)
    school = ""
    # Kiểm tra trường chuyên nổi tiếng
    for spec_school, prov in SPECIALIZED_SCHOOLS.items():
        if spec_school.lower() in title_lower or spec_school.lower().replace("chuyên ", "") in title_lower:
            school = spec_school
            break

    if not school:
        m_school = re.search(r'(trường\s+(?:thpt\s+)?[a-z0-9\sà-ỹÀ-Ỵ\.\-]+?)(?=\s*[-–|,]|\s+năm|\s+lần|$)', title_norm, re.IGNORECASE)
        if m_school and len(m_school.group(1).strip()) > 8:
            school = m_school.group(1).strip().title()
        else:
            m_school_alt = re.search(r'(thpt\s+[a-z0-9\sà-ỹÀ-Ỵ\.\-]+?)(?=\s*[-–|,]|\s+năm|\s+lần|$)', title_norm, re.IGNORECASE)
            if m_school_alt and len(m_school_alt.group(1).strip()) > 7:
                school = m_school_alt.group(1).strip().title()

    # 3. Nhận diện Cơ quan quản lý / Ban hành (Authority: Sở GD / Phòng GD)
    authority = ""
    m_so = re.search(r'(sở\s+gd\s*(?:&|và)?\s*đt\s+[a-zà-ỹÀ-Ỵ\s]+?)(?=\s*[-–|,]|\s+năm|$)', title_norm, re.IGNORECASE)
    if m_so:
        authority = m_so.group(1).strip().title()
    else:
        m_phong = re.search(r'(phòng\s+gd\s*(?:&|và)?\s*đt\s+[a-zà-ỹÀ-Ỵ\s]+?)(?=\s*[-–|,]|\s+năm|$)', title_norm, re.IGNORECASE)
        if m_phong:
            authority = m_phong.group(1).strip().title()

    # Full location aliases only: short codes such as "na" must never match "Nai".
    # Keep historical province names as the source issued them, without merger remapping.
    def full_matches(value):
        normalized = unicodedata.normalize("NFC", value).casefold()
        found = set()
        for name, info in PROVINCES_DICT.items():
            for alias in info["aliases"]:
                if len(alias.replace(" ", "")) < 3 or alias.casefold() in {"hcm", "brvt"}:
                    continue
                if re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", normalized):
                    found.add(name)
                    break
        return found

    title_matches = full_matches(title_norm)
    authority_matches = full_matches(authority)
    school_match = SPECIALIZED_SCHOOLS.get(school)
    candidates = title_matches | authority_matches | ({school_match} if school_match else set())
    geo_conflicts = sorted(candidates) if len(candidates) > 1 else []
    province = next(iter(candidates)) if len(candidates) == 1 else ""
    region = PROVINCES_DICT[province]["region"] if province else ""
    geo_evidence = []
    if province and province in title_matches:
        geo_evidence.append({"field": "province", "value": province,
                             "reference": "original_title", "excerpt": title})
    if province and province in authority_matches:
        geo_evidence.append({"field": "province", "value": province,
                             "reference": "source_authority", "excerpt": authority})
    # School mappings alone are inferred and require review; they are not source text evidence.
    metadata_review_status = "verified" if geo_evidence and not geo_conflicts else "needs_review"
    if not province and not geo_conflicts:
        if "quốc tế" in title_lower or re.search(r"(?<!\w)imo(?!\w)", title_lower):
            province, region = "Quốc Tế", "Olympic Quốc Tế"
        elif any(term in title_lower for term in ["quốc gia", "thpt qg", "bộ giáo dục"]):
            province, region = "Toàn Quốc", "Toàn Quốc (Bộ GD&ĐT)"
        # Missing evidence stays unknown rather than being asserted as a national document.

    # 5. Phân loại Khối Lớp chuẩn
    grade_name = "THPT"
    if any(k in combined_text for k in ["lớp 12", "toán 12", "thpt qg", "thpt quốc gia", "tốt nghiệp thpt"]):
        grade_name = "Lớp 12"
    elif any(k in combined_text for k in ["lớp 11", "toán 11"]):
        grade_name = "Lớp 11"
    elif any(k in combined_text for k in ["lớp 10", "toán 10"]):
        grade_name = "Lớp 10"
    elif any(k in combined_text for k in ["lớp 9", "toán 9", "vào 10", "tuyển sinh 10"]):
        grade_name = "Lớp 9"
    elif any(k in combined_text for k in ["lớp 8", "toán 8"]):
        grade_name = "Lớp 8"
    elif any(k in combined_text for k in ["lớp 7", "toán 7"]):
        grade_name = "Lớp 7"
    elif any(k in combined_text for k in ["lớp 6", "toán 6"]):
        grade_name = "Lớp 6"
    elif any(k in combined_text for k in ["lớp 5", "toán 5"]):
        grade_name = "Lớp 5"
    elif any(k in combined_text for k in ["lớp 4", "toán 4"]):
        grade_name = "Lớp 4"
    elif any(k in combined_text for k in ["lớp 3", "toán 3"]):
        grade_name = "Lớp 3"
    elif any(k in combined_text for k in ["lớp 2", "toán 2"]):
        grade_name = "Lớp 2"
    elif any(k in combined_text for k in ["lớp 1", "toán 1"]):
        grade_name = "Lớp 1"

    # 6. Nhận diện Dạng Tài Liệu (Document Type)
    doc_type = "Đề thi & Tài liệu ôn tập"
    if any(k in title_lower for k in ["đề thi thử", "thi thử tốt nghiệp", "thi thử thpt"]):
        doc_type = "Đề thi thử Tốt nghiệp THPT"
    elif any(k in title_lower for k in ["đánh giá năng lực", "đgnl", "đánh giá tư duy", "đgtd"]):
        doc_type = "Đề thi Đánh giá năng lực"
    elif any(k in title_lower for k in ["hsg", "học sinh giỏi", "chọn đội tuyển", "olympic"]):
        doc_type = "Đề thi chọn Học sinh giỏi"
    elif any(k in title_lower for k in ["giữa hk1", "giữa kì 1", "giữa kỳ 1", "gki"]):
        doc_type = "Đề kiểm tra giữa học kỳ 1"
    elif any(k in title_lower for k in ["hk1", "học kì 1", "học kỳ 1", "cuối kì 1", "hki"]):
        doc_type = "Đề thi cuối học kỳ 1"
    elif any(k in title_lower for k in ["giữa hk2", "giữa kì 2", "giữa kỳ 2", "gkii"]):
        doc_type = "Đề kiểm tra giữa học kỳ 2"
    elif any(k in title_lower for k in ["hk2", "học kì 2", "học kỳ 2", "cuối kì 2", "hkii"]):
        doc_type = "Đề thi cuối học kỳ 2"
    elif any(k in title_lower for k in ["khảo sát", "kscl"]):
        doc_type = "Đề khảo sát chất lượng"
    elif any(k in title_lower for k in ["đề cương", "ôn tập"]):
        doc_type = "Đề cương ôn tập trọng tâm"
    elif any(k in title_lower for k in ["giáo án", "kế hoạch bài dạy"]):
        doc_type = "Giáo án & Kế hoạch bài dạy"
    elif any(k in title_lower for k in ["sách giáo khoa", "sgk", "chuyên đề học tập"]):
        doc_type = "Sách giáo khoa & Chuyên đề học tập"
    elif "chuyên đề" in title_lower:
        doc_type = "Chuyên đề ôn thi & Phương pháp giải"

    # 7. Có đáp án / lời giải hay không
    has_answers = True
    if any(k in title_lower for k in ["không đáp án", "chưa có đáp án"]):
        has_answers = False

    return {
        "geo_province": province,
        "geo_conflicts": geo_conflicts,
        "geo_evidence": geo_evidence,
        "geo_rule_version": "province-full-alias-v1",
        "metadata_review_status": metadata_review_status,
        "geo_region": region,
        "geo_authority": authority,
        "geo_school": school,
        "academic_year": academic_year,
        "doc_type": doc_type,
        "grade_name": grade_name,
        "has_answers": has_answers
    }

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    test_titles = [
        "Đề kiểm tra giữa HK1 Toán 10 năm 2019 – 2020 trường Huỳnh Thúc Kháng – Hà Nội",
        "Đề giữa kỳ 2 Toán 11 năm 2024 – 2025 trường chuyên Lương Thế Vinh – Đồng Nai",
        "Đề thi thử Toán THPTQG 2019 lần 2 trường chuyên Nguyễn Quang Diêu – Đồng Tháp",
        "Đề thi học kì 2 Toán 10 năm 2019 – 2020 trường THPT Marie Curie – TP HCM",
        "Đề thi chọn học sinh giỏi tỉnh Nam Định môn Toán 12 năm học 2025-2026",
        "Chuyên đề phương trình mũ và logarit bồi dưỡng HSG Toán 12"
    ]
    for t in test_titles:
        res = extract_geo_and_metadata(t)
        print(f"\nTiêu đề: {t}")
        print(f" -> Tỉnh/Thành: {res['geo_province']} ({res['geo_region']}) | Trường: {res['geo_school']} | Loại: {res['doc_type']} | Năm: {res['academic_year']}")
