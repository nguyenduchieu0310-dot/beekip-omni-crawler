import { Env, StatsResponse, DocumentItem, QueueItem, SourceItem } from './types';
import { runServerlessCrawlCycle, logToD1 } from './crawler';
import { renderDashboardHtml } from './dashboard';
import { createSessionToken, extractSessionUser, renderLoginHtml } from './auth';

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
        const expectedPass = (env.ADMIN_PASS || "Beekip@2026!Hub").trim();

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

        // API: /api/documents
        if (subpath === "/api/documents") {
          const page = Math.max(1, parseInt(url.searchParams.get("page") || "1", 10));
          const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") || "50", 10)));
          const offset = (page - 1) * limit;
          const searchQuery = (url.searchParams.get("q") || "").trim();

          let querySql = "SELECT id, document_code, slug, title, author_name, audience_tags_json, cover_url, source_object_key, original_filename, mime_type, size_bytes, page_count, is_published, created_at FROM documents";
          let bindings: any[] = [];

          if (searchQuery) {
            querySql += " WHERE (title LIKE ? OR slug LIKE ? OR author_name LIKE ?)";
            const pattern = `%${searchQuery}%`;
            bindings = [pattern, pattern, pattern, limit, offset];
          } else {
            bindings = [limit, offset];
          }
          querySql += " ORDER BY created_at DESC LIMIT ? OFFSET ?";

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
