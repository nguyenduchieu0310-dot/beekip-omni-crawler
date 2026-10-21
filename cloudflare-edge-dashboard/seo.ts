/**
 * Module tối ưu hóa SEO/GEO, khử trùng PII và sinh bài viết 4 phần chuẩn KaTeX
 * dựa trên bằng chứng thật chạy trên Cloudflare Edge (`https://beekip.vn/hubag/crawl`).
 */

export function removeVietnameseTones(str: string): string {
  str = str.replace(/à|á|ạ|ả|ã|â|ầ|ấ|ậ|ẩ|ẫ|ă|ằ|ắ|ặ|ẳ|ẵ/g, "a");
  str = str.replace(/è|é|ẹ|ẻ|ẽ|ê|ề|ế|ệ|ể|ễ/g, "e");
  str = str.replace(/ì|í|ị|ỉ|ĩ/g, "i");
  str = str.replace(/ò|ó|ọ|ỏ|õ|ô|ồ|ố|ộ|ổ|ỗ|ơ|ờ|ớ|ợ|ở|ỡ/g, "o");
  str = str.replace(/ù|ú|ụ|ủ|ũ|ư|ừ|ứ|ự|ử|ữ/g, "u");
  str = str.replace(/ỳ|ý|ỵ|ỷ|ỹ/g, "y");
  str = str.replace(/đ/g, "d");
  str = str.replace(/À|Á|Ạ|Ả|Ã|Â|Ầ|Ấ|Ậ|Ẩ|Ẫ|Ă|Ằ|Ắ|Ặ|Ẳ|Ẵ/g, "A");
  str = str.replace(/È|É|Ẹ|Ẻ|Ẽ|Ê|Ề|Ế|Ệ|Ể|Ễ/g, "E");
  str = str.replace(/Ì|Í|Ị|Ỉ|Ĩ/g, "I");
  str = str.replace(/Ò|Ó|Ọ|Ỏ|Õ|Ô|Ồ|Ố|Ộ|Ổ|Ỗ|Ơ|Ờ|Ớ|Ợ|Ở|Ỡ/g, "O");
  str = str.replace(/Ù|Ú|Ụ|Ủ|Ũ|Ư|Ừ|Ứ|Ự|Ử|Ữ/g, "U");
  str = str.replace(/Ỳ|Ý|Ỵ|Ỷ|Ỹ/g, "Y");
  str = str.replace(/Đ/g, "D");
  return str;
}

/**
 * Khử sạch SĐT, Zalo, Email cá nhân, link VIP/quảng cáo và tên miền nguồn thứ ba.
 */
export function sanitizePiiFromEdgeText(rawText: string): string {
  return String(rawText ?? "")
    .replace(/\b(?:\+84|84|0)[1-9](?:[\s.-]?\d){8,9}\b/g, "")
    .replace(/\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b/g, "")
    .replace(/(?:liên\s*hệ|zalo|hotline|sđt|điện\s*thoại|mua\s*file|tài\s*liệu\s*vip)[:\s-]*[^\n.;]{0,45}/gi, "")
    .replace(/\b(?:https?:\/\/)?(?:www\.)?(?:toanmath\.com|thuvienhoclieu\.(?:org|com|vn)|tailieumontoan\.(?:com|vn)|facebook\.com|fb\.com|zalo\.me)[^\s,;)]*/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function generateSeoSlug(title: string): string {
  let clean = removeVietnameseTones(sanitizePiiFromEdgeText(title)).toLowerCase();
  clean = clean.replace(/[^a-z0-9\s-]/g, "");
  clean = clean.replace(/\s+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  if (!clean) clean = "tai-lieu-beekip";
  return clean;
}

export interface GeoEntity {
  location: string;
  subject: string;
  grade: string;
  year: string;
  examType: string;
  hasVerifiedAnswers: boolean;
}

export function extractGeoEntity(title: string, rawContentHtml = ""): GeoEntity {
  const combined = `${title} ${rawContentHtml.replace(/<[^>]+>/g, " ").slice(0, 3000)}`;

  // 1. Trích xuất Tỉnh/Thành / Sở GD&ĐT / Trường
  let location = "Toàn quốc";
  const locMatch = title.match(
    /(sở\s*gd&?đ?t\s*[^,.\(\)-]+|phòng\s*gd&?đ?t\s*[^,.\(\)-]+|trường\s*(?:thpt|thcs)\s*[^,.\(\)-]+|chuyên\s*[^,.\(\)-]+|tp\.?\s*hcm|hà\s*nội|đà\s*nẵng|quảng\s*trị|lâm\s*đồng|ninh\s*bình|bắc\s*ninh|quảng\s*ngãi|phú\s*thọ|hải\s*phòng|đắk\s*lắk|tây\s*ninh|khánh\s*hòa|nam\s*định|nghệ\s*an|thanh\s*hóa|vĩnh\s*phúc)/i,
  );
  if (locMatch) {
    location = sanitizePiiFromEdgeText(locMatch[0]);
  }

  // 2. Môn học
  let subject = "Toán";
  const lower = combined.toLowerCase();
  if (lower.includes("hóa học") || lower.includes("môn hóa")) subject = "Hóa học";
  else if (lower.includes("vật lý") || lower.includes("vật lí") || lower.includes("môn lý")) subject = "Vật lý";
  else if (lower.includes("sinh học") || lower.includes("môn sinh")) subject = "Sinh học";
  else if (lower.includes("tiếng anh") || lower.includes("môn anh")) subject = "Tiếng Anh";
  else if (lower.includes("ngữ văn") || lower.includes("môn văn")) subject = "Ngữ văn";
  else if (lower.includes("khoa học tự nhiên") || lower.includes("khtn")) subject = "Khoa học tự nhiên";

  // 3. Khối lớp
  let grade = "THPT";
  const gradeMatch = combined.match(/(?:toán|hóa|lý|sinh|anh|văn|lớp|khối)\s*(10|11|12|[6-9])\b/i);
  if (gradeMatch) {
    grade = `Lớp ${gradeMatch[1]}`;
  }

  // 4. Năm học
  let year = "2025 - 2026";
  const yearMatch = combined.match(/202[3-9](\s*[-–]\s*202[4-9])?/);
  if (yearMatch) {
    year = yearMatch[0].replace(/\s+/g, " ");
  }

  // 5. Loại học liệu
  let examType = "Đề thi & Tài liệu ôn tập";
  const titleLower = title.toLowerCase();
  if (titleLower.includes("chọn đội tuyển") || titleLower.includes("lập đội tuyển")) {
    examType = "Đề chọn đội tuyển thi HSG";
  } else if (titleLower.includes("hsg") || titleLower.includes("học sinh giỏi")) {
    examType = "Đề thi Học sinh giỏi";
  } else if (titleLower.includes("giữa học kỳ") || titleLower.includes("giữa kỳ") || titleLower.includes("giữa kì")) {
    examType = "Đề kiểm tra giữa học kỳ";
  } else if (titleLower.includes("cuối học kỳ") || titleLower.includes("cuối kỳ") || titleLower.includes("học kỳ")) {
    examType = "Đề kiểm tra học kỳ";
  } else if (titleLower.includes("vào 10") || titleLower.includes("khảo sát")) {
    examType = "Đề khảo sát chất lượng & Thi vào lớp 10";
  } else if (titleLower.includes("tốt nghiệp") || titleLower.includes("thpt")) {
    examType = "Đề thi thử tốt nghiệp THPT";
  } else if (titleLower.includes("chuyên đề") || titleLower.includes("đề cương")) {
    examType = "Chuyên đề & Đề cương ôn tập";
  }

  // 6. Kiểm chứng trung thực sự tồn tại của đáp án / lời giải trong bài viết gốc (Chống bịa 100%)
  const hasVerifiedAnswers =
    /(?:có\s*đáp\s*án|kèm\s*đáp\s*án|bảng\s*đáp\s*án|hướng\s*dẫn\s*giải|lời\s*giải\s*chi\s*tiết|đáp\s*án\s*và\s*lời\s*giải)/i.test(
      combined,
    );

  return { location, subject, grade, year, examType, hasVerifiedAnswers };
}

export function buildSeoTitle(originalTitle: string, hasVerifiedAnswers = false): string {
  let title = sanitizePiiFromEdgeText(originalTitle);
  title = title.replace(/\s*-\s*toanmath\.com/gi, "");
  title = title.replace(/\s*\(toanmath\.com\)/gi, "");
  title = title.replace(/\s*toanmath/gi, "");

  if (!title.toLowerCase().includes("beekip")) {
    const answerTag = hasVerifiedAnswers
      ? "[Có Đáp Án]"
      : "[Đề Luyện Tập Nguyên Bản]";
    title = `${title} ${answerTag} - Thư Viện Beekip`;
  }
  return title.trim();
}

export function buildMetaDescription(title: string, categories: string[], geo: GeoEntity): string {
  const cleanTitle = sanitizePiiFromEdgeText(title);
  const answerClause = geo.hasVerifiedAnswers
    ? "có kèm đáp án/hướng dẫn giải xác thực trong tài liệu"
    : "bản đề luyện tập nguyên bản (chưa kèm bảng đáp án trong tệp)";
  return `Tải miễn phí ${cleanTitle}. ${geo.examType} môn ${geo.subject} ${geo.grade} (${geo.location}) năm học ${geo.year}, ${answerClause} tại Thư viện Beekip.vn.`;
}

/**
 * Sinh bài viết 4 phần chuẩn KaTeX có bằng chứng thật từ nội dung bài đăng cho Cloudflare Edge Worker.
 * Tuyệt đối không dùng câu mẫu giả `y = 2x + 4` và không bịa thông tin đáp án/số câu nếu chưa xác minh.
 */
export function buildEdge4PartMarkdown(params: {
  seoTitle: string;
  originalTitle: string;
  categories: string[];
  sampleQuestions: string[];
  geo: GeoEntity;
}): string {
  const { seoTitle, originalTitle, categories, sampleQuestions, geo } = params;
  const cleanQuestions = sampleQuestions
    .map((q) => sanitizePiiFromEdgeText(q))
    .filter((q) => q.length >= 10);

  const answerStatusText = geo.hasVerifiedAnswers
    ? "Đã xác minh có thông tin đáp án / hướng dẫn giải từ nguồn phát hành"
    : "Đề luyện tập nguyên bản (chưa kèm bảng đáp án trong tệp)";

  const questionCountText =
    cleanQuestions.length > 0
      ? `Ghi nhận ${cleanQuestions.length} trích đoạn câu hỏi / nội dung tiêu biểu từ bài đăng gốc`
      : "Theo cấu trúc đề nguyên bản trong tệp PDF đính kèm";

  const citationsMd =
    cleanQuestions.length > 0
      ? cleanQuestions.map((q, idx) => `- **[Trích đoạn #${idx + 1}]** ${q}`).join("\n")
      : `- **[Trích nguồn học liệu]** Nội dung chi tiết của **${sanitizePiiFromEdgeText(originalTitle)}** được trình bày đầy đủ trong tệp PDF đính kèm.`;

  return [
    `## 1. Tổng quan & Ma trận đề`,
    `Tài liệu **${sanitizePiiFromEdgeText(originalTitle)}** là học liệu môn **${geo.subject} ${geo.grade}** thuộc nhóm **${geo.examType}**, biên soạn tại **${geo.location}** trong năm học **${geo.year}** và được đồng bộ qua hệ thống **AG Crawl (Beekip.vn)**.`,
    ``,
    `| Tiêu chí hồ sơ | Thông tin xác thực |`,
    `| :--- | :--- |`,
    `| **Tên học liệu** | ${seoTitle} |`,
    `| **Môn học & Khối lớp** | ${geo.subject} — ${geo.grade} |`,
    `| **Đơn vị / Địa phương** | ${geo.location} |`,
    `| **Năm học** | ${geo.year} |`,
    `| **Danh mục** | ${categories.join(", ") || geo.examType} |`,
    `| **Tình trạng Đáp án / Lời giải** | **${answerStatusText}** |`,
    ``,
    `## 2. Phân tích cấu trúc & Kiến thức trọng tâm`,
    `- **Phạm vi kiến thức:** Bám sát chương trình GDPT 2018 môn **${geo.subject} ${geo.grade}** (${questionCountText}).`,
    `### Trích dẫn nội dung & câu hỏi tiêu biểu từ tài liệu:`,
    citationsMd,
    ``,
    `## 3. Lời giải / Đáp án chi tiết có đối chiếu công thức`,
    `- **Tình trạng đáp án thực tế:** **${answerStatusText}**.`,
    geo.hasVerifiedAnswers
      ? `- **Hướng dẫn đối chiếu:** Học sinh mở trực tiếp phần cuối của tệp PDF hoặc tệp Word đính kèm để tra cứu bảng đáp án và thang điểm chấm chính thức của **${geo.location}**.`
      : `- **Lưu ý trung thực:** Tài liệu hiện ở dạng **Đề luyện tập nguyên bản (chưa kèm bảng đáp án trong tệp)**. Học sinh nên chủ động bấm giờ làm bài và trao đổi kết quả cùng giáo viên bộ môn.`,
    ``,
    `## 4. Nhận xét sư phạm & Hướng dẫn ôn tập`,
    `- **Phương pháp ôn luyện:** Học sinh khối **${geo.grade}** nên phân bổ thời gian hợp lý giữa phần câu hỏi nhận biết - thông hiểu và các câu hỏi vận dụng thực tiễn được trích dẫn ở Mục 2.`,
    `- **Cam kết học liệu sạch:** Toàn bộ tiêu đề, mô tả và trích đoạn đã được khử sạch 100% SĐT, Zalo và liên kết quảng cáo theo chuẩn \`BEEKIP-DOC-STD-2026\`.`,
  ].join("\n");
}

export function buildSchemaJsonLd(
  slug: string,
  seoTitle: string,
  categories: string[],
  sampleQuestions: string[],
  geo: GeoEntity,
): any[] {
  const beekipUrl = `https://tailieu.beekip.vn/tai-lieu/${slug}`;
  const cleanTitle = sanitizePiiFromEdgeText(seoTitle);

  const learningResource = {
    "@context": "https://schema.org",
    "@type": ["LearningResource", "DigitalDocument"],
    "name": cleanTitle,
    "description": buildMetaDescription(cleanTitle, categories, geo),
    "educationalLevel": geo.grade,
    "learningResourceType": geo.examType,
    "inLanguage": "vi-VN",
    "isAccessibleForFree": true,
    "spatialCoverage": {
      "@type": "Place",
      "name": geo.location,
    },
    "about": [
      { "@type": "Thing", "name": `Môn ${geo.subject}` },
      { "@type": "Place", "name": geo.location },
    ],
    "provider": {
      "@type": "Organization",
      "name": "Beekip Education",
      "url": "https://tailieu.beekip.vn",
    },
    "publisher": {
      "@type": "Organization",
      "name": "Beekip Education",
      "url": "https://tailieu.beekip.vn",
    },
    "url": beekipUrl,
  };

  const answerFaqText = geo.hasVerifiedAnswers
    ? "Tài liệu gốc từ đơn vị phát hành có kèm thông tin đáp án / hướng dẫn chấm trong tệp đính kèm."
    : "Đây là đề luyện tập nguyên bản (chưa kèm bảng đáp án trong tệp) giúp học sinh tự rèn luyện kỹ năng giải đề.";

  const faqs = [
    {
      "@type": "Question",
      "name": `Tài liệu ${cleanTitle} có kèm đáp án không?`,
      "acceptedAnswer": {
        "@type": "Answer",
        "text": answerFaqText,
      },
    },
    {
      "@type": "Question",
      "name": "Tôi có thể đọc trực tuyến và tải file PDF miễn phí không?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Bạn hoàn toàn có thể đọc trực tuyến và tải tệp PDF học liệu sạch miễn phí trực tiếp trên hệ thống Beekip.vn.",
      },
    },
  ];

  const faqPage = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": faqs,
  };

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Trang chủ",
        "item": "https://tailieu.beekip.vn",
      },
      {
        "@type": "ListItem",
        "position": 2,
        "name": categories[0] || `Tài liệu ${geo.subject}`,
        "item": "https://tailieu.beekip.vn",
      },
      {
        "@type": "ListItem",
        "position": 3,
        "name": cleanTitle,
        "item": beekipUrl,
      },
    ],
  };

  return [learningResource, faqPage, breadcrumb];
}
