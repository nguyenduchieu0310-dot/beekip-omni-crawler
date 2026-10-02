"""Cloud publishing boundary: validate derivatives and QA before any upload."""
import hashlib
import logging
import tempfile
from pathlib import Path

from adapters.factory import get_adapter_for_source
from processing.file_downloader import ResilientFileDownloader
from processing.pdf_converter import DocumentPDFConverter
from processing.seo_geo_enricher import SEOGEOEnricher
from processing.temporal_guard import TemporalYearGuard, NEW_CURRICULUM_KEYWORDS
from services.derivative_renderer import DerivativeRendererEngine
from services.qa_gate_inspector import QAGateInspector
from services.sanitizer import DeepSanitizerEngine

logger = logging.getLogger('beekip.cloud_pipeline')


def cloud_description(meta, count, size, source_url):
    """Factual metadata and study guidance; never invent answers or sample questions."""
    return f'''## 1. THÔNG TIN TÀI LIỆU
Tài liệu được giới thiệu với tiêu đề **{meta.title}**. Tệp PDF sau xử lý gồm {count} trang,
dung lượng {size / 1048576:.2f} MiB. Nguồn phát hiện bài viết: {source_url}.
Thông tin môn học, khối lớp và năm học được phân loại tự động từ tiêu đề nguồn;
người đọc nên đối chiếu với nội dung ở trang đầu trước khi lựa chọn tài liệu để học.
Nếu thông tin trong tiêu đề khác với nội dung tệp, ưu tiên kiểm tra bản gốc và nguồn phát hành.
Việc số hóa không thay đổi tác giả hoặc đơn vị biên soạn tài liệu.

## 2. KIỂM TRA NỘI DUNG TRƯỚC KHI HỌC
Hãy xem các trang mở đầu, mục lục nếu có và phần cuối tài liệu để nhận biết phạm vi kiến thức.
Kiểm tra xem tài liệu có hướng dẫn, đáp án hoặc lời giải hay không trước khi dùng để tự chấm bài.
Hệ thống chưa xác minh độc lập tính chính xác của từng câu hỏi, lời giải, hình vẽ hoặc công thức.
Không nên suy ra rằng tài liệu có đáp án đầy đủ, bám sát một kỳ thi cụ thể hoặc thuộc một bộ sách
chỉ dựa vào nhãn phân loại tự động. Khi cần sử dụng trong lớp học, giáo viên nên đọc và lựa chọn
những phần phù hợp với chương trình, tiến độ giảng dạy và năng lực thực tế của học sinh.

## 3. GỢI Ý SỬ DỤNG
Người học có thể chia tài liệu thành các phần ngắn theo chủ đề hoặc nhóm bài tập để ôn tập từng bước.
Trước mỗi phần, ghi lại kiến thức cần nhớ và đánh dấu những nội dung chưa hiểu rõ.
Khi làm bài, nên trình bày cách giải hoặc lập luận của mình trước khi tham khảo phần hướng dẫn nếu có.
Sau khi hoàn thành, kiểm tra kết quả, đơn vị, điều kiện áp dụng và các bước biến đổi quan trọng.
Với câu hỏi chưa giải được, ghi lại vướng mắc để trao đổi với giáo viên hoặc bạn học.
Việc theo dõi các lỗi thường gặp qua nhiều lần luyện tập giúp lựa chọn nội dung cần ôn tiếp theo.

## 4. ĐỊNH DẠNG VÀ NGUỒN GỐC
Ảnh bìa được tạo từ trang đầu của bản PDF đã xử lý và không thay thế việc đọc toàn bộ tài liệu.
Các kiểm tra tự động đánh giá khả năng mở tệp, lớp chữ, kích thước và một số dấu hiệu nội dung cần xử lý.
Kết quả kiểm tra không phải bảo đảm tuyệt đối về độ chính xác học thuật hay khả năng phát hiện mọi thông tin cá nhân.
Nếu phát hiện trang thiếu, lỗi hiển thị hoặc thông tin nguồn chưa chính xác, cần kiểm tra lại trước khi chia sẻ rộng rãi.
Nguồn bài viết được giữ ở phần thông tin trên để thuận tiện đối chiếu và truy xuất.
Người sử dụng cần tuân thủ điều kiện sử dụng do chủ sở hữu tài liệu công bố.
'''


def eligible_year(item):
    # Curriculum names alone are not evidence that publication was >= 2023.
    evidence = dict(item)
    evidence['title'] = (item.get('title') or '').lower()
    for keyword in NEW_CURRICULUM_KEYWORDS:
        evidence['title'] = evidence['title'].replace(keyword, '')
    result = TemporalYearGuard.evaluate(**{k: evidence.get(k) for k in
        ('title', 'url', 'published_at', 'published_year')})
    return result.is_eligible


class CloudPipeline:
    cloud_mode = True

    def __init__(self, db, r2, d1):
        self.db, self.r2, self.d1 = db, r2, d1
        self.downloader = ResilientFileDownloader()
        self.bytes_uploaded = 0

    def process_inbound_url(self, item, source):
        url = item['url']
        self.db.update_inbound_status(url, 'PROCESSING')
        downloaded = None
        try:
            if not eligible_year(item):
                self.db.update_inbound_status(url, 'SKIPPED_OLD', 'No verified year >= 2023')
                return False
            meta = SEOGEOEnricher.enrich(item['title'], default_subject=source.get('primary_subject', 'Đa môn'))
            meta.slug = meta.slug[:150] + '-' + hashlib.sha256(url.encode()).hexdigest()[:10]
            if self.d1.check_document_exists(meta.slug):
                self.db.update_inbound_status(url, 'COMPLETED')
                return True
            adapter = get_adapter_for_source(source)
            candidates = adapter.extract_download_links(url)
            if not candidates:
                raise RuntimeError('NO_DOWNLOAD_CANDIDATE')
            candidate = next((c for c in candidates if c.file_type == 'PDF'), candidates[0])
            downloaded = self.downloader.download(candidate.url, preferred_name=candidate.file_name)
            if downloaded is None:
                raise RuntimeError('DOWNLOAD_FAILED_OR_NOT_A_DOCUMENT')
            with tempfile.TemporaryDirectory(prefix='beekip-qa-') as tmp:
                folder = Path(tmp)
                pdf = downloaded.file_path
                if downloaded.mime_type != 'application/pdf':
                    if not DocumentPDFConverter.can_convert():
                        self.db.update_inbound_status(url, 'NEEDS_OFFICE_CONVERTER', 'No LibreOffice runtime')
                        return False
                    pdf = DocumentPDFConverter.convert_docx_to_pdf(pdf, folder)
                    if pdf is None:
                        raise RuntimeError('OFFICE_CONVERSION_FAILED')
                clean_pdf, cover = folder / 'clean.pdf', folder / 'cover.jpg'
                renderer = DerivativeRendererEngine()
                # Inspect input before cleaning, so embedded active content cannot be hidden.
                original_check = renderer.validate_pdf_standards(pdf)
                if not original_check.get('malware_free'):
                    self.db.update_inbound_status(url, 'QA_REJECTED', 'Active PDF content')
                    return False
                cleaned = DeepSanitizerEngine().sanitize_pdf_derivative(pdf, clean_pdf)
                if not cleaned.get('success'):
                    raise RuntimeError('SANITIZATION_FAILED')
                rendered = renderer.render_cover_thumbnail(clean_pdf, cover)
                if not rendered.get('meets_google_discover'):
                    raise RuntimeError('COVER_QA_FAILED')
                quality = renderer.validate_pdf_standards(clean_pdf)
                count = quality.get('page_count', 0)
                author = meta.geo_school or 'Beekip (số hóa; tác giả chưa xác minh)'
                description = cloud_description(meta, count, clean_pdf.stat().st_size, url)
                metadata = dict(title=meta.title, slug=meta.slug, grade=meta.grade,
                    subject=meta.subject, category=meta.document_type, topic=meta.document_type,
                    authorName=author, description=description, isAccessibleForFree=True)
                qa = QAGateInspector().inspect_document(clean_pdf, cover, metadata)
                if not qa['is_published_eligible']:
                    rejected = ','.join(k for k,v in qa['checklist'].items() if not v['pass'])
                    self.db.update_inbound_status(url, 'QA_REJECTED', rejected)
                    return False
                payload, cover_bytes = clean_pdf.read_bytes(), cover.read_bytes()
                total = len(payload) + len(cover_bytes)
                # Local safety ceilings, not an account-wide Cloudflare billing guarantee.
                if self.bytes_uploaded + total > 50 * 1024 * 1024:
                    raise RuntimeError('RUN_UPLOAD_LIMIT_50_MIB')
                if self.db.stored_bytes() + total > 2 * 1024 * 1024 * 1024:
                    raise RuntimeError('CRAWLER_STORAGE_LIMIT_2_GIB')
                self.bytes_uploaded += total
                subject = SEOGEOEnricher.generate_slug(meta.subject)
                key, file_url = self.r2.upload_document(payload, subject, meta.academic_year, meta.slug)
                cover_key, cover_url = self.r2.upload_document(cover_bytes, subject, meta.academic_year, meta.slug,
                                                               mime_type='image/jpeg', ext='jpg')
                for content, object_key, public_url in ((payload, key, file_url), (cover_bytes, cover_key, cover_url)):
                    self.db.record_file_blob(hashlib.sha256(content).hexdigest(), len(content), object_key, public_url, url)
                meta.description = description
                self.d1.insert_document(meta, file_url, len(payload), url, page_count=count,
                                        cover_url=cover_url, author_name=author, storage_key=key)
                self.db.update_inbound_status(url, 'COMPLETED')
                return True
        except Exception as exc:
            # Log a type/code, never HTTP headers, credentials or source response bodies.
            code = str(exc) if isinstance(exc, RuntimeError) and str(exc).isupper() else type(exc).__name__
            logger.error('Cloud document failed: %s', code)
            self.db.update_inbound_status(url, 'FAILED', code, increment_retry=True)
            return False
        finally:
            if downloaded:
                downloaded.file_path.unlink(missing_ok=True)
