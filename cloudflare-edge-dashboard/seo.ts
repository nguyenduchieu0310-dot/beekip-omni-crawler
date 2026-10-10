/**
 * Module toi uu hoa SEO doc ban va Schema.org JSON-LD chay tren Cloudflare Edge
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

export function generateSeoSlug(title: string): string {
  let clean = removeVietnameseTones(title).toLowerCase();
  clean = clean.replace(/[^a-z0-9\s-]/g, "");
  clean = clean.replace(/\s+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  if (!clean) clean = "tai-lieu-toan";
  return clean;
}

export interface GeoEntity {
  location: string;
  grade: string;
  year: string;
  examType: string;
}

export function extractGeoEntity(title: string): GeoEntity {
  // 1. Trich xuat tinh thanh / so GD / truong THPT
  let location = "Toàn quốc";
  const locMatch = title.match(/(sở\s*gd&?đ?t\s*[^,\.\(\)-]+|trường\s*thpt\s*[^,\.\(\)-]+|chuyên\s*[^,\.\(\)-]+|tp\.?\s*hcm|hà\s*nội|đà\s*nẵng|quảng\s*trị|lâm\s*đồng|ninh\s*bình|bắc\s*ninh|quảng\s*ngãi|phú\s*thọ|hải\s*phòng|đắk\s*lắk|tây\s*ninh|khánh\s*hòa)/i);
  if (locMatch) {
    location = locMatch[0].trim();
  }

  // 2. Khoi lop
  let grade = "THPT";
  const gradeMatch = title.match(/(toán\s*|lớp\s*)(10|11|12)/i);
  if (gradeMatch) {
    grade = `Lớp ${gradeMatch[2]}`;
  }

  // 3. Nam hoc
  let year = "2026 - 2027";
  const yearMatch = title.match(/202\d(\s*[-–]\s*202\d)?/);
  if (yearMatch) {
    year = yearMatch[0];
  }

  // 4. Loai de thi
  let examType = "Đề thi & Tài liệu ôn tập";
  const lower = title.toLowerCase();
  if (lower.includes("chọn đội tuyển") || lower.includes("lập đội tuyển")) {
    examType = "Đề chọn đội tuyển thi HSG Quốc Gia";
  } else if (lower.includes("hsg") || lower.includes("học sinh giỏi")) {
    examType = "Đề thi Học sinh giỏi";
  } else if (lower.includes("giữa học kỳ") || lower.includes("giữa kỳ")) {
    examType = "Đề kiểm tra giữa học kỳ";
  } else if (lower.includes("tốt nghiệp") || lower.includes("đại học")) {
    examType = "Đề thi thử tốt nghiệp THPT Quốc gia";
  }

  return { location, grade, year, examType };
}

export function buildSeoTitle(originalTitle: string): string {
  let title = originalTitle.trim();
  // Loai bo cac hau to copyright cu neu co
  title = title.replace(/\s*-\s*toanmath\.com/gi, "");
  title = title.replace(/\s*\(toanmath\.com\)/gi, "");
  title = title.replace(/\s*toanmath/gi, "");

  if (!title.toLowerCase().includes("beekip")) {
    title = `${title} [Có Đáp Án & Lời Giải Chi Tiết] - Thư Viện Beekip`;
  }
  return title;
}

export function buildMetaDescription(title: string, categories: string[], geo: GeoEntity): string {
  return `Tải miễn phí trọn bộ ${title}. Tài liệu ${geo.examType} ${geo.grade} (${geo.location}) năm học ${geo.year} chuẩn cấu trúc Bộ GD&ĐT kèm bảng đáp án chi tiết tại Thư viện Beekip Education.`;
}

export function buildSchemaJsonLd(slug: string, seoTitle: string, categories: string[], sampleQuestions: string[], geo: GeoEntity): any[] {
  const beekipUrl = `https://tailieu.beekip.vn/tai-lieu/${slug}`;

  // 1. LearningResource Schema (kem GEO & Entity)
  const learningResource = {
    "@context": "https://schema.org",
    "@type": ["LearningResource", "DigitalDocument"],
    "name": seoTitle,
    "description": `Tài liệu ôn tập và đề thi môn Toán ${geo.grade} (${geo.location}) chất lượng cao được biên soạn và số hóa bởi Beekip Education.`,
    "educationalLevel": geo.grade,
    "learningResourceType": geo.examType,
    "inLanguage": "vi-VN",
    "isAccessibleForFree": true,
    "spatialCoverage": {
      "@type": "Place",
      "name": geo.location
    },
    "about": [
      { "@type": "Thing", "name": "Môn Toán" },
      { "@type": "Place", "name": geo.location }
    ],
    "provider": {
      "@type": "Organization",
      "name": "Beekip Education",
      "url": "https://tailieu.beekip.vn"
    },
    "publisher": {
      "@type": "Organization",
      "name": "Beekip Education",
      "url": "https://tailieu.beekip.vn"
    },
    "url": beekipUrl
  };

  // 2. FAQPage Schema
  const faqs = [
    {
      "@type": "Question",
      "name": `Tài liệu ${seoTitle} có kèm đáp án và lời giải chi tiết không?`,
      "acceptedAnswer": {
        "@type": "Answer",
        "text": `Có. Bộ tài liệu được chia sẻ trên Beekip đã bao gồm toàn bộ đề thi chính thức kèm bảng đáp án trắc nghiệm và lời giải tự luận chi tiết từng câu.`
      }
    },
    {
      "@type": "Question",
      "name": "Tôi có thể tải file PDF hoặc Word về máy tính để in ấn không?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Bạn hoàn toàn có thể tải tệp PDF chuẩn hoặc file Word chỉnh sửa miễn phí trực tiếp từ hệ thống Beekip với tốc độ cao."
      }
    }
  ];

  const faqPage = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": faqs
  };

  // 3. BreadcrumbList Schema
  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Trang chủ",
        "item": "https://tailieu.beekip.vn"
      },
      {
        "@type": "ListItem",
        "position": 2,
        "name": categories[0] || "Tài liệu Toán",
        "item": "https://tailieu.beekip.vn/danh-muc/toan"
      },
      {
        "@type": "ListItem",
        "position": 3,
        "name": seoTitle,
        "item": beekipUrl
      }
    ]
  };

  return [learningResource, faqPage, breadcrumb];
}
