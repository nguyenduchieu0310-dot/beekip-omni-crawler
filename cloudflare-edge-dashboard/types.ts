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
