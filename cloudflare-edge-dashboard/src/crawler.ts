import { Env } from './types';
import {
  generateSeoSlug,
  buildSeoTitle,
  buildMetaDescription,
  buildEdge4PartMarkdown,
  buildSchemaJsonLd,
  extractGeoEntity,
  sanitizePiiFromEdgeText,
} from './seo';

const TOANMATH_API = "https://toanmath.com/wp-json/wp/v2/posts";
const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36";

export async function logToD1(env: Env, level: string, message: string): Promise<void> {
  try {
    await env.DB.prepare(
      "INSERT INTO crawler_logs (level, message, timestamp) VALUES (?, ?, datetime('now'))"
    ).bind(level, message).run();
  } catch (err) {
    console.error("Loi ghi log vao D1:", err);
  }
}

interface ExtractedFiles {
  pdfUrl: string | null;
  wordUrl: string | null;
}

function extractFilesFromHtml(html: string): ExtractedFiles {
  let pdfUrl: string | null = null;
  let wordUrl: string | null = null;

  // 1. Tim qua WonderPlugin embedder
  const iframeMatch = html.match(/<iframe[^>]+src=["']([^"']+)["']/i);
  if (iframeMatch) {
    const src = iframeMatch[1];
    const fileParam = src.match(/[?&]file=([^&'"]+)/i);
    if (fileParam && (fileParam[1].toLowerCase().includes('.pdf') || fileParam[1].includes('/toanmath-pdf/'))) {
      pdfUrl = decodeURIComponent(fileParam[1]);
    }
  }

  // 2. Tim qua cac the <a href="...">
  const aRegex = /<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gi;
  let match;
  while ((match = aRegex.exec(html)) !== null) {
    const href = match[1].trim();
    const hrefLower = href.toLowerCase();

    if (!pdfUrl && (hrefLower.includes('.pdf') || hrefLower.includes('/toanmath-pdf/'))) {
      pdfUrl = href;
    } else if (!wordUrl && (hrefLower.includes('.docx') || hrefLower.includes('.doc') || hrefLower.includes('.rar') || hrefLower.includes('.zip') || hrefLower.includes('/toanmath-word/'))) {
      wordUrl = href;
    }
  }

  // Chuan hoa URL
  if (pdfUrl && pdfUrl.startsWith('/')) {
    pdfUrl = 'https://toanmath.com' + pdfUrl;
  }
  if (wordUrl && wordUrl.startsWith('/')) {
    wordUrl = 'https://toanmath.com' + wordUrl;
  }

  return { pdfUrl, wordUrl };
}

function extractSampleQuestions(html: string): string[] {
  const questions: string[] = [];
  const pRegex = /<(?:p|li)[^>]*>(.*?)<\/(?:p|li)>/gi;
  let match;
  while ((match = pRegex.exec(html)) !== null) {
    const rawText = match[1]
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&#8211;/g, '-')
      .replace(/&amp;/g, '&')
      .trim();
    const cleaned = sanitizePiiFromEdgeText(rawText);
    if (
      cleaned.length >= 15 &&
      (cleaned.startsWith('+') ||
        cleaned.startsWith('-') ||
        /^(?:Câu|Bài|Phần|Chuyên đề)\s+/i.test(cleaned) ||
        /trích\s*đề/i.test(cleaned))
    ) {
      questions.push(cleaned);
      if (questions.length >= 8) break;
    }
  }
  return questions;
}

export async function runServerlessCrawlCycle(env: Env, limit: number = 10): Promise<{ scanned: number; newPosts: number; errors: number }> {
  await logToD1(env, "info", `[Cloudflare Worker] Bắt đầu chu kỳ quét tự động (tối đa ${limit} bài từ toanmath.com)...`);

  let rawPosts: any[] = [];
  try {
    const res = await fetch(`${TOANMATH_API}?per_page=${limit}&_embed=1`, {
      headers: {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
      }
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    rawPosts = await res.json();
  } catch (err: any) {
    const errMsg = `[Crawler] Lỗi fetch toanmath.com API: ${err.message}`;
    await logToD1(env, "error", errMsg);
    return { scanned: 0, newPosts: 0, errors: 1 };
  }

  let scanned = rawPosts.length;
  let newPosts = 0;
  let errors = 0;

  for (const item of rawPosts) {
    const postId = item.id;
    const rawRenderedTitle = item.title?.rendered
      ? item.title.rendered.replace(/&amp;/g, '&').replace(/&#8211;/g, '-').replace(/&#8230;/g, '...').trim()
      : `Đề thi Toán ${postId}`;
    const originalTitle = sanitizePiiFromEdgeText(rawRenderedTitle);
    const originalUrl = item.link || `https://toanmath.com/?p=${postId}`;
    const contentHtml = item.content?.rendered || "";

    // Kiem tra bai da co trong D1 chua
    const existing = await env.DB.prepare("SELECT post_id FROM crawled_posts WHERE post_id = ?").bind(postId).first();
    if (existing) {
      continue;
    }

    newPosts++;
    await logToD1(env, "info", `[Crawler] Phát hiện bài mới ID ${postId}: "${originalTitle.substring(0, 50)}..."`);

    try {
      // 1. Trich xuat link files & cau hoi mau da khu PII
      const { pdfUrl, wordUrl } = extractFilesFromHtml(contentHtml);
      const sampleQuestions = extractSampleQuestions(contentHtml);

      // 2. Lay categories
      const categories: string[] = [];
      if (item._embedded && item._embedded["wp:term"]) {
        for (const termList of item._embedded["wp:term"]) {
          for (const term of termList) {
            if (term.taxonomy === "category" && term.name) {
              categories.push(sanitizePiiFromEdgeText(term.name));
            }
          }
        }
      }
      if (categories.length === 0) categories.push("Tài liệu Toán THPT");

      // 3. Toi uu SEO & GEO metadata + Sinh bai viet 4 phan trung thuc, khong bia dap an
      const geo = extractGeoEntity(originalTitle, contentHtml);
      const slug = generateSeoSlug(originalTitle);
      const seoTitle = buildSeoTitle(originalTitle, geo.hasVerifiedAnswers);
      const metaDesc = buildMetaDescription(seoTitle, categories, geo);
      const descriptionMarkdown = buildEdge4PartMarkdown({
        seoTitle,
        originalTitle,
        categories,
        sampleQuestions,
        geo,
      });
      const schemaJsonLd = buildSchemaJsonLd(slug, seoTitle, categories, sampleQuestions, geo);

      let pdfR2Key: string | null = null;
      let pdfSize = 0;
      let wordR2Key: string | null = null;
      let wordSize = 0;

      // 4. Tai file va luu tru truc tiep vao Cloudflare R2
      if (pdfUrl) {
        try {
          const pdfRes = await fetch(pdfUrl, { headers: { "User-Agent": USER_AGENT } });
          if (pdfRes.ok) {
            const pdfBytes = await pdfRes.arrayBuffer();
            pdfSize = pdfBytes.byteLength;
            pdfR2Key = `files/${slug}-tailieu-beekip.pdf`;

            await env.DOCS_BUCKET.put(pdfR2Key, pdfBytes, {
              httpMetadata: {
                contentType: 'application/pdf',
                contentDisposition: `inline; filename="${slug}-tailieu-beekip.pdf"`
              },
              customMetadata: {
                original_url: pdfUrl,
                seo_title: seoTitle,
                has_verified_answers: String(geo.hasVerifiedAnswers),
                crawled_by: 'Beekip Cloudflare Serverless Agent'
              }
            });
            await logToD1(env, "info", `[R2] Đã lưu PDF thành công: ${pdfR2Key} (${(pdfSize / 1024).toFixed(1)} KB)`);
          }
        } catch (e: any) {
          await logToD1(env, "warning", `[R2] Không thể tải PDF từ ${pdfUrl}: ${e.message}`);
        }
      }

      if (wordUrl) {
        try {
          const wordRes = await fetch(wordUrl, { headers: { "User-Agent": USER_AGENT } });
          if (wordRes.ok) {
            const wordBytes = await wordRes.arrayBuffer();
            wordSize = wordBytes.byteLength;
            wordR2Key = `files/${slug}-tailieu-beekip.docx`;

            await env.DOCS_BUCKET.put(wordR2Key, wordBytes, {
              httpMetadata: {
                contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                contentDisposition: `attachment; filename="${slug}-tailieu-beekip.docx"`
              }
            });
            await logToD1(env, "info", `[R2] Đã lưu Word thành công: ${wordR2Key} (${(wordSize / 1024).toFixed(1)} KB)`);
          }
        } catch (e: any) {
          await logToD1(env, "warning", `[R2] Không thể tải Word từ ${wordUrl}: ${e.message}`);
        }
      }

      // 5. Dong goi payload JSON hoan chinh voi bai viet 4 phan chuan hoa
      const payload = {
        post_id: postId,
        title: seoTitle,
        original_url: originalUrl,
        original_title: originalTitle,
        seo_title: seoTitle,
        slug: slug,
        subject: geo.subject,
        grade: geo.grade,
        academic_year: geo.year,
        has_answers: geo.hasVerifiedAnswers,
        meta_description: metaDesc,
        description_markdown: descriptionMarkdown,
        categories: categories,
        sample_questions: sampleQuestions,
        schema_json_ld: schemaJsonLd,
        r2_files: {
          pdf: pdfR2Key ? `/files/${pdfR2Key}` : null,
          word: wordR2Key ? `/files/${wordR2Key}` : null,
          pdf_size: pdfSize,
          word_size: wordSize
        },
        beekip_live_url: `https://tailieu.beekip.vn/tai-lieu/${slug}`,
        crawled_at: new Date().toISOString()
      };

      // 6. Luu vao Cloudflare D1 (crawled_posts + dong bo sang beekip_crawler_queue cho Multi-Agent QA 10/10)
      await env.DB.prepare(`
        INSERT INTO crawled_posts (
          post_id, original_url, original_title, seo_title, slug,
          categories, pdf_r2_key, word_r2_key, pdf_size, word_size,
          status, crawled_at, sample_questions, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', datetime('now'), ?, ?)
      `).bind(
        postId, originalUrl, originalTitle, seoTitle, slug,
        JSON.stringify(categories), pdfR2Key, wordR2Key, pdfSize, wordSize,
        JSON.stringify(sampleQuestions), JSON.stringify(payload)
      ).run();

      try {
        await env.DB.prepare(`
          INSERT OR IGNORE INTO beekip_crawler_queue (
            url, source_id, payload, status, retry_count, created_at, updated_at
          ) VALUES (?, 'toanmath', ?, 'PENDING', 0, datetime('now'), datetime('now'))
        `).bind(originalUrl, JSON.stringify(payload)).run();

        await env.DB.prepare(`
          UPDATE beekip_crawler_sources SET last_checked_at = datetime('now') WHERE id = 'toanmath'
        `).run();
      } catch (queueErr: any) {
        await logToD1(env, "warning", `[D1 Queue Sync] Không thể đồng bộ hàng đợi beekip_crawler_queue cho bài ${postId}: ${queueErr.message}`);
      }

      await logToD1(env, "info", `[D1] Đã lưu bài ID ${postId} (${slug}) vào crawled_posts & đồng bộ beekip_crawler_queue.`);

    } catch (err: any) {
      errors++;
      await logToD1(env, "error", `[Crawler] Lỗi xử lý bài ID ${postId}: ${err.message}`);
    }
  }

  await logToD1(env, "info", `[Cloudflare Worker] Kết thúc chu kỳ quét: Đã duyệt ${scanned} bài | Mới: ${newPosts} bài | Lỗi: ${errors}.`);
  return { scanned, newPosts, errors };
}
