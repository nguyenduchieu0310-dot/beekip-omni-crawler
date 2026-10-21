import { 
  Env, StatsResponse, DocumentItem, QueueItem, SourceItem, 
  AnalyticsResponse, SourceBreakdownItem, CrawledArticleItem, SOURCE_METADATA 
} from './types';
import { runServerlessCrawlCycle, logToD1 } from './crawler';
import { renderDashboardHtml } from './dashboard';
import { createSessionToken, extractSessionUser, renderLoginHtml } from './auth';

function getTimeBounds(period: string) {
  const now = Date.now();
  let startMs = 0;
  let label = "Tất Cả (Toàn Thời Gian)";
  
  if (period === "day") {
    startMs = now - 24 * 3600 * 1000;
    label = "Ngày (24 Giờ Qua)";
  } else if (period === "week") {
    startMs = now - 7 * 24 * 3600 * 1000;
    label = "Tuần (7 Ngày Qua)";
  } else if (period === "month") {
    startMs = now - 30 * 24 * 3600 * 1000;
    label = "Tháng (30 Ngày Qua)";
  } else if (period === "quarter") {
    startMs = now - 90 * 24 * 3600 * 1000;
    label = "Quý (90 Ngày Qua)";
  } else if (period === "year") {
    startMs = now - 365 * 24 * 3600 * 1000;
    label = "Năm (365 Ngày Qua)";
  } else {
    period = "all";
    startMs = 0;
    label = "Tất Cả (Toàn Thời Gian)";
  }

  const startIso = startMs > 0 ? new Date(startMs).toISOString() : "1970-01-01T00:00:00.000Z";
  const startSqlText = startIso.replace("T", " ").substring(0, 19);

  return { period, label, startMs, startSqlText, endMs: now };
}

export default {
  /**
   * Cron Trigger chạy tự động mỗi 4 giờ trên Cloudflare Global Edge
   */
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    console.log(`[Cron Trigger] Kích hoạt lúc ${new Date(event.scheduledTime).toISOString()}`);
    ctx.waitUntil(
      (async () => {
        await logToD1(env, "info", `[Cron Trigger] Bắt đầu quét định kỳ 4 tiếng theo lịch Cloudflare (${new Date(event.scheduledTime).toLocaleTimeString('vi-VN')})`);
        await runServerlessCrawlCycle(env, 10);
      })()
    );
  },

  /**
   * HTTP Handler phục vụ Dashboard bảo mật và REST API tại /hubag/crawl
   */
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname;
    const basePath = env.BASE_PATH || "/hubag/crawl";

    // CORS Headers
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization, Cookie",
      "Access-Control-Allow-Credentials": "true"
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // Determine normalized subpath relative to basePath
    let subpath = pathname;
    if (pathname.startsWith(basePath)) {
      subpath = pathname.substring(basePath.length);
      if (!subpath.startsWith("/")) subpath = "/" + subpath;
    }

    try {
      // 1. Authentication Endpoint: POST /api/login
      if (subpath === "/api/login" && request.method === "POST") {
        let body: any = {};
        try {
          body = await request.json();
        } catch (e) {
          return new Response(JSON.stringify({ success: false, error: "Dữ liệu JSON không hợp lệ" }), {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        const username = (body.username || "").trim();
        const password = (body.password || "").trim();

        const expectedUser = (env.ADMIN_USER || "admin").trim();
        const expectedPass = (env.ADMIN_PASS || "").trim();

        if (!expectedPass) {
          return new Response(JSON.stringify({
            success: false,
            error: "Chưa cấu hình biến môi trường ADMIN_PASS trên Worker!"
          }), {
            status: 503,
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        if (username.toLowerCase() === expectedUser.toLowerCase() && password === expectedPass) {
          const sessionToken = createSessionToken(username, env);
          // Set secure HTTP-only cookie with 30-day lifetime
          const cookieHeader = `beekip_admin_session=${sessionToken}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000; Secure`;
          
          return new Response(JSON.stringify({
            success: true,
            redirect: basePath
          }), {
            status: 200,
            headers: {
              ...corsHeaders,
              "Content-Type": "application/json; charset=utf-8",
              "Set-Cookie": cookieHeader
            }
          });
        } else {
          return new Response(JSON.stringify({
            success: false,
            error: "ID Admin hoặc Mật khẩu không chính xác!"
          }), {
            status: 401,
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }
      }

      // 2. Authentication Endpoint: POST /api/logout
      if (subpath === "/api/logout" && request.method === "POST") {
        const cookieHeader = `beekip_admin_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0; Secure`;
        return new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json; charset=utf-8",
            "Set-Cookie": cookieHeader
          }
        });
      }

      // 3. Check Session for UI and Protected API
      const sessionUser = extractSessionUser(request, env);

      // 4. Dashboard View (Root or /dashboard)
      if (subpath === "/" || subpath === "" || subpath === "/dashboard") {
        if (!sessionUser) {
          // Unauthenticated: Present Admin Login Portal
          const loginHtml = renderLoginHtml(basePath);
          return new Response(loginHtml, {
            status: 200,
            headers: {
              "Content-Type": "text/html; charset=utf-8",
              "Cache-Control": "no-store, no-cache, must-revalidate"
            }
          });
        }

        // Authenticated: Present Full Unified Omni-Agent v2.5 Dashboard
        const dashboardHtml = renderDashboardHtml(basePath, sessionUser);
        return new Response(dashboardHtml, {
          status: 200,
          headers: {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store, no-cache, must-revalidate"
          }
        });
      }

      // 5. Protected APIs - Require Admin Authentication
      if (subpath.startsWith("/api/")) {
        if (!sessionUser) {
          return new Response(JSON.stringify({ error: "Unauthorized. Vui lòng đăng nhập ID Admin để truy cập!" }), {
            status: 401,
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/stats
        if (subpath === "/api/stats") {
          const countDocsRes = await env.DB.prepare("SELECT COUNT(*) as total FROM documents WHERE is_published = 1").first<{ total: number }>();
          const countQueueRes = await env.DB.prepare("SELECT COUNT(*) as total FROM beekip_crawler_queue").first<{ total: number }>();
          const countPendingRes = await env.DB.prepare("SELECT COUNT(*) as total FROM beekip_crawler_queue WHERE status = 'PENDING'").first<{ total: number }>();
          const countSkippedRes = await env.DB.prepare("SELECT COUNT(*) as total FROM beekip_crawler_queue WHERE status = 'SKIPPED_OLD'").first<{ total: number }>();
          const countSourcesRes = await env.DB.prepare("SELECT COUNT(*) as total FROM beekip_crawler_sources").first<{ total: number }>();

          const latestDoc = await env.DB.prepare(
            "SELECT id, title, slug, created_at, original_filename FROM documents ORDER BY created_at DESC LIMIT 1"
          ).first<{ id: string; title: string; slug: string; created_at: number; original_filename: string }>();

          const { results: sources } = await env.DB.prepare(
            "SELECT source_id, last_etag, last_modified_header, last_checked_at FROM beekip_crawler_sources ORDER BY last_checked_at DESC LIMIT 20"
          ).all<SourceItem>();

          const stats: StatsResponse = {
            total_documents: countDocsRes?.total || 0,
            total_queue: countQueueRes?.total || 0,
            total_pending: countPendingRes?.total || 0,
            total_skipped: countSkippedRes?.total || 0,
            total_sources: countSourcesRes?.total || 0,
            total_r2_files: countDocsRes?.total || 0,
            latest_document: latestDoc ? {
              id: latestDoc.id,
              title: latestDoc.title,
              slug: latestDoc.slug,
              created_at: latestDoc.created_at,
              filename: latestDoc.original_filename
            } : null,
            sources: sources || [],
            uptime_status: "24/7/365 Cloudflare Edge",
            last_cron_time: "Chu kỳ 4 giờ (GitHub Actions + Cloudflare Workers)"
          };

          return new Response(JSON.stringify(stats), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/analytics (Thống kê chuyên sâu theo Ngày, Tuần, Tháng, Quý, Năm, Tất Cả)
        if (subpath === "/api/analytics") {
          const periodParam = (url.searchParams.get("period") || "all").toLowerCase();
          const bounds = getTimeBounds(periodParam);

          // 1. Số bài đã đăng lên Beekip (published)
          let publishedCount = 0;
          if (bounds.startMs === 0) {
            const countDocsRes = await env.DB.prepare("SELECT COUNT(*) as total FROM documents WHERE is_published = 1").first<{ total: number }>();
            publishedCount = countDocsRes?.total || 0;
          } else {
            const countDocsRes = await env.DB.prepare("SELECT COUNT(*) as total FROM documents WHERE is_published = 1 AND created_at >= ?").bind(bounds.startMs).first<{ total: number }>();
            publishedCount = countDocsRes?.total || 0;
          }

          // 2. Số bài viết Crawl được & Phân bổ theo nguồn
          let queueTotal = 0;
          let sourceRows: { source_id: string; count: number }[] = [];

          if (bounds.startMs === 0) {
            const totRes = await env.DB.prepare("SELECT COUNT(*) as total FROM beekip_crawler_queue").first<{ total: number }>();
            queueTotal = totRes?.total || 0;
            const { results } = await env.DB.prepare(
              "SELECT source_id, COUNT(*) as count FROM beekip_crawler_queue GROUP BY source_id ORDER BY count DESC"
            ).all<{ source_id: string; count: number }>();
            sourceRows = results || [];
          } else {
            const totRes = await env.DB.prepare(
              "SELECT COUNT(*) as total FROM beekip_crawler_queue WHERE created_at >= ?"
            ).bind(bounds.startSqlText).first<{ total: number }>();
            queueTotal = totRes?.total || 0;
            const { results } = await env.DB.prepare(
              "SELECT source_id, COUNT(*) as count FROM beekip_crawler_queue WHERE created_at >= ? GROUP BY source_id ORDER BY count DESC"
            ).bind(bounds.startSqlText).all<{ source_id: string; count: number }>();
            sourceRows = results || [];
          }

          const sourcesBreakdown: SourceBreakdownItem[] = sourceRows.map(r => {
            const meta = SOURCE_METADATA[r.source_id] || { name: r.source_id, domain: r.source_id, icon: "fa-globe" };
            const pct = queueTotal > 0 ? parseFloat(((r.count / queueTotal) * 100).toFixed(1)) : 0;
            return {
              source_id: r.source_id,
              name: meta.name,
              domain: meta.domain,
              count: r.count,
              percentage: pct
            };
          });

          // 3. Số bài đã xử lý (3 chỉ số con)
          let instantSelected = 0;
          let needsProcessing = 0;
          let processedDone = 0;

          if (bounds.startMs === 0) {
            const qRes = await env.DB.prepare(`
              SELECT 
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as instant_selected,
                COUNT(CASE WHEN status IN ('NEEDS_OFFICE_CONVERTER', 'PENDING', 'QA_REJECTED') THEN 1 END) as needs_processing,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as processed_done
              FROM beekip_crawler_queue
            `).first<{ instant_selected: number; needs_processing: number; processed_done: number }>();
            instantSelected = qRes?.instant_selected || 0;
            needsProcessing = qRes?.needs_processing || 0;
            processedDone = qRes?.processed_done || 0;
          } else {
            const qRes = await env.DB.prepare(`
              SELECT 
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as instant_selected,
                COUNT(CASE WHEN status IN ('NEEDS_OFFICE_CONVERTER', 'PENDING', 'QA_REJECTED') THEN 1 END) as needs_processing,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as processed_done
              FROM beekip_crawler_queue
              WHERE created_at >= ?
            `).bind(bounds.startSqlText).first<{ instant_selected: number; needs_processing: number; processed_done: number }>();
            instantSelected = qRes?.instant_selected || 0;
            needsProcessing = qRes?.needs_processing || 0;
            processedDone = qRes?.processed_done || 0;
          }

          const publishRate = queueTotal > 0 ? Math.min(100, Math.round((publishedCount / (queueTotal || 1)) * 100)) : 100;

          const analytics: AnalyticsResponse = {
            period: bounds.period,
            period_label: bounds.label,
            time_range: {
              start: bounds.startSqlText,
              end: new Date(bounds.endMs).toISOString().replace("T", " ").substring(0, 19)
            },
            crawled: {
              total: queueTotal,
              sources_count: sourcesBreakdown.length,
              sources_breakdown: sourcesBreakdown
            },
            processing: {
              instant_selected: instantSelected,
              needs_processing: needsProcessing,
              processed_done: processedDone,
              total_processed_pipeline: instantSelected + needsProcessing
            },
            published: {
              total_published: publishedCount,
              publish_rate: publishRate
            }
          };

          return new Response(JSON.stringify(analytics), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/crawled-articles (Danh sách bài viết chi tiết của từng nguồn)
        if (subpath === "/api/crawled-articles") {
          const sourceId = (url.searchParams.get("source_id") || "").trim();
          const periodParam = (url.searchParams.get("period") || "all").toLowerCase();
          const bounds = getTimeBounds(periodParam);
          const searchQuery = (url.searchParams.get("q") || "").trim();
          const page = Math.max(1, parseInt(url.searchParams.get("page") || "1", 10));
          const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") || "50", 10)));
          const offset = (page - 1) * limit;

          let querySql = "SELECT url, source_id, json_extract(payload, '$.title') as title, status, created_at FROM beekip_crawler_queue WHERE 1=1";
          const bindings: any[] = [];

          if (sourceId) {
            querySql += " AND source_id = ?";
            bindings.push(sourceId);
          }
          if (bounds.startMs > 0) {
            querySql += " AND created_at >= ?";
            bindings.push(bounds.startSqlText);
          }
          if (searchQuery) {
            querySql += " AND (json_extract(payload, '$.title') LIKE ? OR url LIKE ?)";
            const p = `%${searchQuery}%`;
            bindings.push(p, p);
          }

          querySql += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
          bindings.push(limit, offset);

          const { results } = await env.DB.prepare(querySql).bind(...bindings).all<any>();
          const articles: CrawledArticleItem[] = (results || []).map((r: any) => {
            const meta = SOURCE_METADATA[r.source_id] || { name: r.source_id, domain: r.source_id, icon: "fa-globe" };
            return {
              url: r.url,
              source_id: r.source_id,
              source_name: meta.name,
              title: r.title || r.url,
              status: r.status,
              created_at: r.created_at
            };
          });

          return new Response(JSON.stringify({
            articles,
            source_id: sourceId,
            period: bounds.period,
            page,
            limit
          }), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/documents
        if (subpath === "/api/documents") {
          const page = Math.max(1, parseInt(url.searchParams.get("page") || "1", 10));
          const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") || "50", 10)));
          const offset = (page - 1) * limit;
          const searchQuery = (url.searchParams.get("q") || "").trim();
          const periodParam = (url.searchParams.get("period") || "all").toLowerCase();
          const bounds = getTimeBounds(periodParam);

          let querySql = "SELECT id, document_code, slug, title, author_name, audience_tags_json, cover_url, source_object_key, original_filename, mime_type, size_bytes, page_count, is_published, created_at FROM documents WHERE 1=1";
          let bindings: any[] = [];

          if (searchQuery) {
            querySql += " AND (title LIKE ? OR slug LIKE ? OR author_name LIKE ?)";
            const pattern = `%${searchQuery}%`;
            bindings.push(pattern, pattern, pattern);
          }
          if (bounds.startMs > 0) {
            querySql += " AND created_at >= ?";
            bindings.push(bounds.startMs);
          }

          querySql += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
          bindings.push(limit, offset);

          const { results } = await env.DB.prepare(querySql).bind(...bindings).all<DocumentItem>();

          return new Response(JSON.stringify({ documents: results || [] }), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/queue
        if (subpath === "/api/queue") {
          const { results } = await env.DB.prepare(
            "SELECT url, source_id, payload, status, retry_count, error_message, created_at FROM beekip_crawler_queue ORDER BY created_at DESC LIMIT 50"
          ).all<QueueItem>();

          return new Response(JSON.stringify({ queue: results || [] }), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/sources
        if (subpath === "/api/sources") {
          const { results } = await env.DB.prepare(
            "SELECT source_id, last_etag, last_modified_header, last_checked_at FROM beekip_crawler_sources ORDER BY last_checked_at DESC"
          ).all<SourceItem>();

          return new Response(JSON.stringify({ sources: results || [] }), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }

        // API: /api/trigger (Manual crawl trigger)
        if (subpath === "/api/trigger" && request.method === "POST") {
          const result = await runServerlessCrawlCycle(env, 10);
          return new Response(JSON.stringify({
            success: true,
            message: `Quét thành công: Duyệt ${result.scanned} bài, phát hiện ${result.newPosts} bài mới trên Cloudflare D1 & R2!`,
            result
          }), {
            headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
          });
        }
      }

      // 6. R2 File Delivery (/files/*)
      if (subpath.startsWith("/files/")) {
        const rawKey = subpath.replace(/^\/files\//, "");
        const key = decodeURIComponent(rawKey);

        if (!key) {
          return new Response("Key tệp tin không hợp lệ!", { status: 400 });
        }

        const object = await env.DOCS_BUCKET.get(key);
        if (!object) {
          return new Response(`Không tìm thấy tệp "${key}" trên Cloudflare R2!`, { status: 404 });
        }

        const headers = new Headers();
        object.writeHttpMetadata(headers);
        headers.set("etag", object.httpEtag);
        headers.set("Cache-Control", "public, max-age=86400, immutable");

        return new Response(object.body, { headers });
      }

      return new Response("Not Found", { status: 404 });
    } catch (err: any) {
      console.error("Worker Error:", err);
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
    }
  }
};
