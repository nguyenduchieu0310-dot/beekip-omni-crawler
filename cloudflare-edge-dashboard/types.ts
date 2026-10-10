export interface Env {
  DB: D1Database;
  DOCS_BUCKET: R2Bucket;
  ADMIN_USER?: string;
  ADMIN_PASS?: string;
  BASE_PATH?: string;
  JWT_SECRET?: string;
  APP_ENV?: string;
  BEEKIP_API_URL?: string;
}

export interface DocumentItem {
  id: string;
  document_code: string;
  slug: string;
  title: string;
  author_name: string;
  audience_tags_json: string;
  cover_url: string | null;
  source_object_key: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  page_count: number | null;
  is_published: number;
  created_at: number;
}

export interface QueueItem {
  url: string;
  source_id: string;
  payload: string;
  status: string;
  retry_count: number;
  error_message: string | null;
  created_at: string;
}

export interface SourceItem {
  source_id: string;
  last_etag: string | null;
  last_modified_header: string | null;
  last_checked_at: string | null;
}

export interface SourceBreakdownItem {
  source_id: string;
  name: string;
  domain: string;
  count: number;
  percentage: number;
}

export interface AnalyticsResponse {
  period: string; // 'day' | 'week' | 'month' | 'quarter' | 'year' | 'all'
  period_label: string;
  time_range: {
    start: string;
    end: string;
  };
  crawled: {
    total: number;
    sources_count: number;
    sources_breakdown: SourceBreakdownItem[];
  };
  processing: {
    instant_selected: number;    // Số bài tuyển chọn được ngay
    needs_processing: number;    // Số bài cần xử lý xong rồi mới chọn được
    processed_done: number;      // Số bài đã xử lý xong
    total_processed_pipeline: number;
  };
  published: {
    total_published: number;     // Số bài đã đăng lên Beekip
    publish_rate: number;
  };
}

export interface CrawledArticleItem {
  url: string;
  source_id: string;
  source_name: string;
  title: string;
  status: string;
  created_at: string;
}

export const SOURCE_METADATA: Record<string, { name: string; domain: string; icon: string }> = {
  toanmath_rss: { name: "Toán Math", domain: "toanmath.com", icon: "fa-calculator" },
  thuvienvatly_moi: { name: "Thư Viện Vật Lý", domain: "thuvienvatly.com", icon: "fa-atom" },
  vndoc_portal: { name: "VnDoc Giáo Dục", domain: "vndoc.com", icon: "fa-book-open" },
  mathvn_blogger_json: { name: "MathVN Toán Học", domain: "mathvn.com", icon: "fa-square-root-variable" },
  tailieumontoan_rss: { name: "Tài Liệu Môn Toán", domain: "tailieumontoan.com", icon: "fa-shapes" },
  hoahoc_org_rss: { name: "Hóa Học Org", domain: "hoahoc.org", icon: "fa-flask-vial" },
  tailieuonthi_rss: { name: "Tài Liệu Ôn Thi", domain: "tailieuonthi.org", icon: "fa-graduation-cap" },
  tailieudieuky_rss: { name: "Tài Liệu Diệu Kỳ", domain: "tailieudieuky.com", icon: "fa-feather" },
  vnteach_sitemap: { name: "VnTeach Giáo Viên", domain: "vnteach.com", icon: "fa-chalkboard-user" },
  kenhgiaovien_sitemap: { name: "Kênh Giáo Viên", domain: "kenhgiaovien.com", icon: "fa-chalkboard" },
  tailieugiaovien_rss: { name: "Tài Liệu Giáo Viên", domain: "tailieugiaovien.com", icon: "fa-user-tie" },
  tailieugdso_sitemap: { name: "Sở GD&ĐT / GD Số", domain: "tailieugdso.vn", icon: "fa-building-columns" },
  igiaoduc_portal: { name: "Cổng iGiáo Dục", domain: "igiaoduc.vn", icon: "fa-school" },
  hanhtrangso_nxbgd: { name: "Hành Trang Số (NXB GD)", domain: "hanhtrangso.nxbgd.vn", icon: "fa-book-bookmark" },
  vnoi_informatics: { name: "VNOI Tin Học", domain: "vnoi.info", icon: "fa-code" }
};

export interface StatsResponse {
  total_documents: number;
  total_queue: number;
  total_pending: number;
  total_skipped: number;
  total_sources: number;
  total_r2_files: number;
  latest_document: {
    id: string;
    title: string;
    slug: string;
    created_at: number;
    filename: string;
  } | null;
  sources: SourceItem[];
  uptime_status: string;
  last_cron_time: string;
}

