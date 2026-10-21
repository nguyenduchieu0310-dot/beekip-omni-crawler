import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

NEW_CURRICULUM_KEYWORDS = [
    "kết nối tri thức",
    "chân trời sáng tạo",
    "cánh diều",
    "gdpt 2018",
    "chương trình mới",
]

VALID_ACADEMIC_YEARS_REGEX = re.compile(
    r'\b(?:202[3-9]|203\d|2022\s*[-–/]\s*2023|2023\s*[-–/]\s*2024|2024\s*[-–/]\s*2025|2025\s*[-–/]\s*2026)\b',
    re.IGNORECASE
)

OLD_ACADEMIC_YEARS_REGEX = re.compile(
    r'\b(?:201\d|202[0-2]|2021\s*[-–/]\s*2022|2020\s*[-–/]\s*2021)\b',
    re.IGNORECASE
)

OLD_URL_SLUG_REGEX = re.compile(
    r'(?:/(?:201\d|2020|2021|2022)/|-nam-2022\.html|-nam-2021\.html|-nam-2020\.html)',
    re.IGNORECASE
)

@dataclass
class TemporalEvaluationResult:
    is_eligible: bool
    reason: str
    detected_year: Optional[int] = None
    curriculum: Optional[str] = None

class TemporalYearGuard:
    """
    Enforces strict publication year and curriculum filtering (>= 2023 and GDPT 2018).
    Rejects legacy documents older than 2023.
    """

    @classmethod
    def evaluate(
        cls,
        title: str = "",
        url: str = "",
        published_at: Optional[str] = None,
        published_year: Optional[int] = None,
        content_preview: str = ""
    ) -> TemporalEvaluationResult:
        combined_text = f"{title} {content_preview}".lower()

        # 1. Check GDPT 2018 textbook recognition
        for kw in NEW_CURRICULUM_KEYWORDS:
            if kw in combined_text:
                return TemporalEvaluationResult(
                    is_eligible=True,
                    reason="ACCEPTED_NEW_CURRICULUM_GDPT2018",
                    detected_year=published_year or 2024,
                    curriculum=kw.title()
                )

        # 2. Check System Published Date
        if published_year is not None:
            if published_year < 2023:
                return TemporalEvaluationResult(
                    is_eligible=False,
                    reason="SKIPPED_OLD_PUBDATE",
                    detected_year=published_year
                )
            elif published_year >= 2023:
                return TemporalEvaluationResult(
                    is_eligible=True,
                    reason="ACCEPTED_PUBDATE_GE_2023",
                    detected_year=published_year
                )

        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if dt.year < 2023:
                    return TemporalEvaluationResult(
                        is_eligible=False,
                        reason="SKIPPED_OLD_PUBDATE",
                        detected_year=dt.year
                    )
                elif dt.year >= 2023:
                    return TemporalEvaluationResult(
                        is_eligible=True,
                        reason="ACCEPTED_PUBDATE_GE_2023",
                        detected_year=dt.year
                    )
            except Exception:
                pass

        # 3. Check Old URL Slugs
        if url and OLD_URL_SLUG_REGEX.search(url):
            return TemporalEvaluationResult(
                is_eligible=False,
                reason="SKIPPED_OLD_URL_SLUG"
            )

        # 4. Check Academic Year in Title
        valid_match = VALID_ACADEMIC_YEARS_REGEX.search(title)
        old_match = OLD_ACADEMIC_YEARS_REGEX.search(title)

        if valid_match and not old_match:
            year_str = valid_match.group(0)
            year_int = int(re.search(r'\d{4}', year_str).group(0))
            return TemporalEvaluationResult(
                is_eligible=True,
                reason="ACCEPTED_ACADEMIC_YEAR_REGEX",
                detected_year=year_int
            )

        if old_match and not valid_match:
            year_str = old_match.group(0)
            year_int = int(re.search(r'\d{4}', year_str).group(0))
            return TemporalEvaluationResult(
                is_eligible=False,
                reason="SKIPPED_OLD_ACADEMIC_YEAR",
                detected_year=year_int
            )

        # Default fallback: check if title mentions 2024 or 2025 or 2026
        for year in [2026, 2025, 2024, 2023]:
            if str(year) in title:
                return TemporalEvaluationResult(
                    is_eligible=True,
                    reason=f"ACCEPTED_YEAR_IN_TITLE_{year}",
                    detected_year=year
                )

        # If uncertain and no year found, reject by default to safeguard quality
        return TemporalEvaluationResult(
            is_eligible=False,
            reason="SKIPPED_NO_ELIGIBLE_YEAR_FOUND"
        )
