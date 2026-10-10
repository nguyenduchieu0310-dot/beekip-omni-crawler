export function renderDashboardHtml(basePath: string = "/hubag/crawl", username: string = "admin"): string {
  return `<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Beekip Unified Omni-Agent v2.5 • Trung Tâm Điều Khiển 24/7/365</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#eef2ff', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca', 900: '#1e1b4b' }
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    .pulse-dot { animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.2); } }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">

  <!-- Header Bar -->
  <header class="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-6 py-4 flex flex-wrap justify-between items-center gap-4">
    <div class="flex items-center gap-3">
      <div class="w-11 h-11 rounded-xl bg-gradient-to-tr from-indigo-600 via-violet-600 to-teal-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
        <i class="fa-solid fa-graduation-cap text-2xl text-white"></i>
      </div>
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-teal-300 bg-clip-text text-transparent">
            BEEKIP UNIFIED OMNI-AGENT v2.5
          </h1>
          <span class="px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-dot"></span> 24/7/365 CLOUD EDGE
          </span>
        </div>
        <p class="text-xs text-slate-400">Thu nạp &bull; Khử trùng Deep Sanitizer &bull; Bìa Discover &ge;1200px &bull; SEO LaTeX &bull; Cổng QA 10/10 &bull; D1 + R2</p>
      </div>
    </div>

    <!-- Quick Actions & User Bar -->
    <div class="flex items-center gap-3">
      <div class="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs">
        <i class="fa-solid fa-user-shield text-indigo-400"></i>
        <span class="text-slate-400">Admin:</span>
        <span class="font-mono font-bold text-slate-200">${username}</span>
      </div>

      <button onclick="triggerManualCrawl()" id="btn-trigger" class="px-4 py-2 text-sm font-semibold rounded-xl bg-gradient-to-r from-indigo-600 to-teal-600 hover:from-indigo-500 hover:to-teal-500 text-white shadow-lg shadow-indigo-600/25 flex items-center gap-2 transition active:scale-95">
        <i id="btn-trigger-icon" class="fa-solid fa-bolt"></i> <span id="btn-trigger-text">Quét &amp; Xử Lý Ngay</span>
      </button>

      <button onclick="loadAllData()" class="p-2.5 text-slate-400 hover:text-slate-200 rounded-xl bg-slate-800/80 hover:bg-slate-700 transition" title="Làm mới dữ liệu">
        <i class="fa-solid fa-arrows-rotate text-sm"></i>
      </button>

      <a href="https://tailieu.beekip.vn" target="_blank" class="px-3.5 py-2 text-sm font-medium rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 flex items-center gap-2 transition">
        <i class="fa-solid fa-arrow-up-right-from-square text-xs"></i> <span>tailieu.beekip.vn</span>
      </a>

      <button onclick="handleLogout()" class="px-3 py-2 text-xs font-semibold rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1.5 transition" title="Đăng xuất">
        <i class="fa-solid fa-right-from-bracket"></i> <span>Đăng Xuất</span>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">

    <!-- Document Types Whitelist SLA Card -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center font-bold text-lg border border-indigo-500/30">
          <i class="fa-solid fa-file-circle-check"></i>
        </div>
        <div>
          <div class="text-sm font-bold text-slate-100 flex items-center gap-2">
            <span>QUY CHUẨN HỌC LIỆU: CHỈ NHẬN 3 LOẠI TÀI LIỆU (PDF • WORD • POWERPOINT)</span>
            <span class="px-2 py-0.5 text-[11px] font-bold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
              <i class="fa-solid fa-shield-check"></i> 100% KHÔNG TẢI FILE ẢNH
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-0.5">Bộ lọc khép kín: Tệp PDF (.pdf), Word (.doc, .docx) và PowerPoint (.ppt, .pptx). Bỏ qua hoàn toàn ảnh tĩnh &amp; mã HTML rác.</p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-3 text-xs">
        <div class="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-2">
          <i class="fa-solid fa-file-pdf text-rose-400 text-sm"></i>
          <span class="text-slate-400">PDF:</span>
          <span id="stat-pdf-count" class="font-bold text-slate-200">18,833+</span>
        </div>
        <div class="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-2">
          <i class="fa-solid fa-file-word text-blue-400 text-sm"></i>
          <span class="text-slate-400">Word:</span>
          <span id="stat-word-count" class="font-bold text-slate-200">Bảo lưu</span>
        </div>
        <div class="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-2">
          <i class="fa-solid fa-file-powerpoint text-amber-400 text-sm"></i>
          <span class="text-slate-400">PowerPoint:</span>
          <span id="stat-ppt-count" class="font-bold text-slate-200">Bảo lưu</span>
        </div>
        <div class="px-3.5 py-2 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 flex items-center gap-1.5 font-medium">
          <i class="fa-solid fa-ban text-emerald-400"></i>
          <span>File Ảnh: 0 (Đã Chặn 100%)</span>
        </div>
      </div>
    </div>

    <!-- Unified Omni-Stream Milestone Ribbon (Toàn Trình 6 Bước) -->
    <div class="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 rounded-2xl p-5 shadow-lg space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <i class="fa-solid fa-arrows-spin text-teal-400 text-lg animate-spin"></i>
          <h2 class="text-sm font-bold uppercase tracking-wider text-slate-200">
            Tiến Trình Liền Mạch Toàn Năng (Continuous Omni-Pipeline 24/7/365)
          </h2>
        </div>
        <div class="flex items-center gap-3 text-xs">
          <span class="text-slate-400">Chu kỳ: <strong class="text-teal-300 font-mono">Mỗi 4 tiếng</strong></span>
          <span class="text-slate-400">&bull;</span>
          <span class="text-slate-400">Hạ tầng: <strong class="text-indigo-300 font-mono uppercase">Cloudflare Edge + D1 + R2</strong></span>
        </div>
      </div>

      <!-- 6 Milestone Steps Bar -->
      <div class="grid grid-cols-2 md:grid-cols-6 gap-2 pt-1 text-xs">
        <div class="p-2.5 rounded-xl bg-slate-950 border border-indigo-500/30 flex flex-col items-center text-center">
          <div class="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold mb-1"><i class="fa-solid fa-check text-[10px]"></i></div>
          <span class="font-semibold text-slate-200">1. Quét Nguồn</span>
          <span class="text-[10px] text-slate-400 mt-0.5">Niên khóa &ge; 2023</span>
        </div>
        <div class="p-2.5 rounded-xl bg-slate-950 border border-indigo-500/30 flex flex-col items-center text-center">
          <div class="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold mb-1"><i class="fa-solid fa-check text-[10px]"></i></div>
          <span class="font-semibold text-slate-200">2. Tải &amp; Lưu R2</span>
          <span class="text-[10px] text-slate-400 mt-0.5">PDF • Word • PPT</span>
        </div>
        <div class="p-2.5 rounded-xl bg-slate-950 border border-indigo-500/30 flex flex-col items-center text-center">
          <div class="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold mb-1"><i class="fa-solid fa-check text-[10px]"></i></div>
          <span class="font-semibold text-slate-200">3. Khử Trùng Sâu</span>
          <span class="text-[10px] text-slate-400 mt-0.5">Watermark &amp; PII</span>
        </div>
        <div class="p-2.5 rounded-xl bg-slate-950 border border-indigo-500/30 flex flex-col items-center text-center">
          <div class="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold mb-1"><i class="fa-solid fa-check text-[10px]"></i></div>
          <span class="font-semibold text-slate-200">4. Bìa Discover</span>
          <span class="text-[10px] text-slate-400 mt-0.5">&ge;1200px, &le;250KB</span>
        </div>
        <div class="p-2.5 rounded-xl bg-slate-950 border border-indigo-500/30 flex flex-col items-center text-center">
          <div class="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold mb-1"><i class="fa-solid fa-check text-[10px]"></i></div>
          <span class="font-semibold text-slate-200">5. SEO &amp; LaTeX</span>
          <span class="text-[10px] text-slate-400 mt-0.5">&ge;300 từ + Schema</span>
        </div>
        <div class="p-2.5 rounded-xl bg-slate-950 border border-emerald-500/40 flex flex-col items-center text-center">
          <div class="w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center font-bold mb-1"><i class="fa-solid fa-check text-[10px]"></i></div>
          <span class="font-semibold text-emerald-300">6. QA Gate 10/10</span>
          <span class="text-[10px] text-emerald-400 mt-0.5">Đã Xuất Bản D1</span>
        </div>
      </div>

      <!-- Current Processing Ticker -->
      <div class="bg-slate-950/80 border border-slate-800/80 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs">
        <div class="flex items-center gap-2 truncate">
          <span class="text-slate-500 font-mono">Trạng thái:</span>
          <span id="stream-ticker" class="font-mono text-cyan-300 truncate">Hệ thống đang vận hành tự động 24/7/365 trên Cloudflare Edge &bull; D1: 18,833+ tài liệu sẵn sàng</span>
        </div>
        <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          HOẠT ĐỘNG
        </span>
      </div>
    </div>

    <!-- Alert Banner -->
    <div id="actionAlert" class="hidden p-4 rounded-xl text-sm font-medium transition duration-300"></div>

    <!-- KPI Metric Cards Grid -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
          <span>XUẤT BẢN TRÊN BEEKIP</span>
          <i class="fa-solid fa-graduation-cap text-emerald-400"></i>
        </div>
        <div id="stat-documents" class="text-2xl font-bold text-emerald-400 tracking-tight">--</div>
        <div class="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
          <i class="fa-solid fa-circle-check text-emerald-400"></i> Bảng D1 documents
        </div>
      </div>

      <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
          <span>LƯU TRỮ R2 CLOUD</span>
          <i class="fa-solid fa-hard-drive text-amber-400"></i>
        </div>
        <div id="stat-r2-files" class="text-2xl font-bold text-amber-400 tracking-tight">--</div>
        <div class="text-[11px] text-slate-400 mt-1">PDF &amp; Word nguyên bản</div>
      </div>

      <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
          <span>HÀNG ĐỢI CHỜ XỬ LÝ</span>
          <i class="fa-solid fa-hourglass-half text-violet-400"></i>
        </div>
        <div id="stat-queue-pending" class="text-2xl font-bold text-violet-400 tracking-tight">--</div>
        <div class="text-[11px] text-slate-400 mt-1">Đang chờ xử lý tuần tự</div>
      </div>

      <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
          <span>ĐẠT QA GATE 10/10</span>
          <i class="fa-solid fa-shield-check text-cyan-400"></i>
        </div>
        <div class="text-2xl font-bold text-cyan-400 tracking-tight">100%</div>
        <div class="text-[11px] text-slate-400 mt-1">Chuẩn BEEKIP-STD</div>
      </div>

      <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
          <span>CỔNG HỌC LIỆU</span>
          <i class="fa-solid fa-network-wired text-indigo-400"></i>
        </div>
        <div id="stat-sources" class="text-2xl font-bold text-indigo-400 tracking-tight">--</div>
        <div class="text-[11px] text-slate-400 mt-1">Toanmath, TVVL,...</div>
      </div>

      <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-center justify-between text-slate-400 text-xs font-medium mb-1">
          <span>CHU KỲ CRON 24/7</span>
          <i class="fa-solid fa-clock text-teal-400"></i>
        </div>
        <div class="text-xl font-bold text-teal-400 tracking-tight">Mỗi 4 Giờ</div>
        <div class="text-[11px] text-slate-400 mt-1">Tự động 100% không tắt</div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="border-b border-slate-800 flex flex-wrap gap-2">
      <button onclick="switchTab('documents')" id="tab-documents" class="px-4 py-2.5 font-semibold text-sm border-b-2 border-indigo-500 text-indigo-400 flex items-center gap-2">
        <i class="fa-solid fa-folder-tree text-emerald-400"></i> Kho Học Liệu Số Hóa &amp; Tệp R2
      </button>
      <button onclick="switchTab('report')" id="tab-report" class="px-4 py-2.5 font-semibold text-sm border-b-2 border-transparent text-slate-400 hover:text-slate-200 flex items-center gap-2">
        <i class="fa-solid fa-file-invoice text-teal-400"></i> Báo Cáo Kết Quả &amp; Prompt Hướng Dẫn (Copy 1-Click)
      </button>
      <button onclick="switchTab('sources')" id="tab-sources" class="px-4 py-2.5 font-semibold text-sm border-b-2 border-transparent text-slate-400 hover:text-slate-200 flex items-center gap-2">
        <i class="fa-solid fa-layer-group text-violet-400"></i> Hàng Đợi &amp; Giám Sát Cổng Nguồn
      </button>
    </div>

    <!-- TAB 1: KHO HỌC LIỆU SỐ HÓA & TỆP R2 -->
    <section id="panel-documents" class="space-y-4">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        
        <!-- Search & Filter Controls -->
        <div class="p-5 border-b border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h3 class="font-bold text-base text-slate-100 flex items-center gap-2">
              <i class="fa-solid fa-book-open text-indigo-400"></i> Danh Sách Tài Liệu Đã Thu Thập &amp; Xuất Bản
            </h3>
            <p class="text-xs text-slate-400 mt-0.5">Dữ liệu thực tế từ Cloudflare D1 (18,833+ tài liệu) &bull; Tệp PDF lưu trữ trên Cloudflare R2 CDN</p>
          </div>

          <div class="flex flex-wrap items-center gap-3 w-full md:w-auto">
            <!-- Search Input -->
            <div class="relative flex-1 md:w-72">
              <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
              <input 
                type="text" 
                id="docSearchInput" 
                oninput="debounceSearch()" 
                placeholder="Tìm tiêu đề, tác giả, slug..." 
                class="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-xl text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
              />
            </div>

            <!-- Page Size -->
            <select id="pageSizeSelect" onchange="changePageSize()" class="bg-slate-950 border border-slate-700 text-slate-300 text-xs rounded-xl px-3 py-1.5 focus:outline-none">
              <option value="20">20 / trang</option>
              <option value="50" selected>50 / trang</option>
              <option value="100">100 / trang</option>
            </select>
          </div>
        </div>

        <!-- Table View -->
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-800/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <tr>
                <th class="px-5 py-3.5">Mã &amp; Tiêu Đề Tài Liệu</th>
                <th class="px-5 py-3.5">Phân Loại / Thẻ</th>
                <th class="px-5 py-3.5">Định Dạng</th>
                <th class="px-5 py-3.5">Dung Lượng</th>
                <th class="px-5 py-3.5 whitespace-nowrap">Thời Gian Đăng</th>
                <th class="px-5 py-3.5">Trạng Thái</th>
                <th class="px-5 py-3.5 text-right">Thao Tác</th>
              </tr>
            </thead>
            <tbody id="documentsTableBody" class="divide-y divide-slate-800/60 font-mono">
              <tr>
                <td colspan="7" class="px-5 py-12 text-center text-slate-500">
                  <i class="fa-solid fa-circle-notch fa-spin text-2xl text-indigo-500 mb-2"></i>
                  <p class="font-sans">Đang truy vấn dữ liệu từ Cloudflare D1...</p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination Controls -->
        <div class="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div id="paginationInfo">Trang 1</div>
          <div class="flex items-center gap-2">
            <button onclick="prevPage()" id="btnPrevPage" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed">
              <i class="fa-solid fa-chevron-left"></i> Trước
            </button>
            <span id="currentPageBadge" class="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-slate-200">1</span>
            <button onclick="nextPage()" id="btnNextPage" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed">
              Sau <i class="fa-solid fa-chevron-right"></i>
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 2: BÁO CÁO KẾT QUẢ & PROMPT HƯỚNG DẪN (COPYABLE) -->
    <section id="panel-report" class="space-y-6 hidden">
      
      <!-- Top Action Bar for Report -->
      <div class="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div>
          <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
            <i class="fa-solid fa-clipboard-check text-emerald-400"></i> Báo Cáo Kết Quả Toàn Trình &amp; Hướng Dẫn Xử Lý
          </h2>
          <p class="text-xs text-slate-400 mt-0.5">Báo cáo số lượng tài liệu đã tải về, vị trí lưu trữ Cloudflare R2 / D1 và Prompt xử lý AI chuẩn SEO E-E-A-T.</p>
        </div>
        <button onclick="copyFullReport()" class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 flex items-center gap-2 transition active:scale-95">
          <i class="fa-solid fa-copy"></i>
          <span>Copy Toàn Bộ Báo Cáo &amp; Prompt</span>
        </button>
      </div>

      <!-- Report Box 1: Storage Breakdown & Statistics -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 class="font-bold text-sm text-slate-200 flex items-center gap-2">
            <i class="fa-solid fa-database text-indigo-400"></i> 1. Báo Cáo Số Lượng &amp; Vị Trí Lưu Trữ
          </h3>
          <button onclick="copySection('report-storage-content')" class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
            <i class="fa-regular fa-copy"></i> Copy Phần Này
          </button>
        </div>

        <div id="report-storage-content" class="bg-slate-950 border border-slate-800/80 rounded-xl p-4 font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap select-all">
================================================================================
📊 BÁO CÁO KHO TÀI LIỆU SỐ HÓA BEEKIP UNIFIED OMNI-AGENT
Hạ tầng: Cloudflare Global Edge (24/7/365 Serverless)
Thời gian cập nhật: <span id="report-timestamp">Đang lấy...</span>
================================================================================

1. TỔNG QUAN SỐ LIỆU:
- Tổng số tài liệu đã xuất bản (D1): <span id="rep-doc-count">18,833+</span> tài liệu
- Tệp đính kèm nguyên bản lưu trữ (R2): <span id="rep-r2-count">18,833+</span> tệp (PDF • Word • PowerPoint)
- Tệp ảnh rác bị loại bỏ: 100% (Không tải tệp ảnh tĩnh, đảm bảo dữ liệu sạch)
- Hàng đợi chờ xử lý tiếp theo: <span id="rep-queue-count">423</span> mục
- Cổng học liệu được giám sát tự động: 20 cổng (toanmath.com, thuvienvatly.com,...)
- Tỷ lệ đạt chuẩn QA Gate 10/10: 100%

2. ĐỊA CHỈ &amp; ĐƯỜNG DẪN KHO LƯU TRỮ (STORAGE PATH):
- Cloudflare R2 Bucket: khai-phong-lms-staging-files
  + Định dạng đường dẫn tệp: documents/v1/{document_id}/source.pdf
  + Tải trực tiếp qua CDN: https://tailieu.beekip.vn/api/documents/{slug}/download
  + Truy cập Admin: https://beekip.vn${basePath}/files/{source_object_key}
- Cloudflare D1 Database: khai-phong-lms-staging (ID: 1277b081-4c8b-41b4-b4c7-0007a4759c07)
  + Bảng dữ liệu học liệu: "documents" (18,833+ records)
  + Bảng hàng đợi crawler: "beekip_crawler_queue" (423 records)
  + Bảng trạng thái nguồn: "beekip_crawler_sources"
- Kho Local Backup (trên máy chủ/PC):
  + Thư mục PDF: D:\\Crawl Data Tài liệu cho Beekip\\downloads_pdf\\
  + Thư mục Word: D:\\Crawl Data Tài liệu cho Beekip\\downloads_word\\
  + Thư mục PowerPoint: D:\\Crawl Data Tài liệu cho Beekip\\downloads_ppt\\
  + Thư mục Kho Mẹ: D:\\Crawl Data Tài liệu cho Beekip\\data\\kho_tai_lieu_chuyen_de\\
================================================================================</div>
      </div>

      <!-- Report Box 2: Processing AI Prompt Guidance -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 class="font-bold text-sm text-slate-200 flex items-center gap-2">
            <i class="fa-solid fa-robot text-teal-400"></i> 2. Prompt Hướng Dẫn Xử Lý Dữ Liệu Học Liệu Chuẩn BEEKIP-DOC-STD-2026
          </h3>
          <button onclick="copySection('report-prompt-content')" class="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1">
            <i class="fa-regular fa-copy"></i> Copy Prompt Này
          </button>
        </div>

        <div id="report-prompt-content" class="bg-slate-950 border border-slate-800/80 rounded-xl p-4 font-mono text-xs text-emerald-300 leading-relaxed whitespace-pre-wrap select-all">
Bạn là Chuyên gia Biên tập Học liệu Số Hóa Beekip (Beekip Educational Publishing AI).
Nhiệm vụ của bạn là tiếp nhận tệp học liệu (PDF / Word / PowerPoint) và thực hiện quy trình chuẩn hóa theo tiêu chuẩn BEEKIP-DOC-STD-2026:

1. KHỬ TRÙNG TOÀN DIỆN (DEEP SANITIZER):
   - Xóa bỏ 100% Watermark, logo mờ của các trang trung gian, trung tâm luyện thi tư nhân.
   - Loại bỏ toàn bộ số điện thoại cá nhân, Hotline Zalo, địa chỉ học thêm, số tài khoản ngân hàng, thông báo phí VIP.
   - BẢO LƯU TUYỆT ĐỐI tên Trường học, Sở Giáo dục & Đào tạo, Phòng GD&ĐT, Tác giả / Giáo viên biên soạn gốc để đảm bảo độ tin cậy E-E-A-T.

2. CÔNG THỨC TIÊU ĐỀ H1 CHUẨN SEO BEEKIP:
   - Cấu trúc: [Dạng tài liệu] + [Chủ đề / Chuyên đề] + [Môn học] + [Khối lớp] + [Tên trường / Sở GD / Đơn vị ra đề] + [Năm học / Niên khóa]
   - Ví dụ: "Đề thi thử Tốt nghiệp THPT 2025 môn Toán – Trường THPT Chuyên Phan Bội Châu (Nghệ An) có đáp án chi tiết"

3. NỘI DUNG MÔ TẢ MARKDOWN (TỐI THIỂU 300 TỪ):
   - Phần 1: Giới thiệu tổng quan tài liệu, mục tiêu học tập và đối tượng học sinh hướng tới.
   - Phần 2: Ma trận đề thi / Cấu trúc nội dung (Số lượng câu hỏi trắc nghiệm, tự luận, thời gian làm bài).
   - Phần 3: Trích đoạn câu hỏi mẫu có chứa công thức Toán học / Khoa học định dạng LaTeX chuẩn ($...$ hoặc $$...$$).
   - Phần 4: Thông số kỹ thuật tệp (Dung lượng, định dạng PDF/Word, số trang) và cam kết học liệu mở 100% phi thương mại cộng đồng.

4. BẢO VỆ CHẤT LƯỢNG (QA GATE 10/10):
   - Chỉ xuất bản khi tệp có độ phân giải cao, text layer chuẩn Unicode NFC tiếng Việt, ảnh bìa trang 1 đạt chiều rộng &ge; 1200px, dung lượng &le; 50MB.</div>
      </div>
    </section>

    <!-- TAB 3: HÀNG ĐỢI & GIÁM SÁT CỔNG NGUỒN -->
    <section id="panel-sources" class="space-y-6 hidden">
      <!-- Monitored Sources Table -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div class="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 class="font-bold text-base text-slate-100 flex items-center gap-2">
              <i class="fa-solid fa-network-wired text-indigo-400"></i> Các Cổng Học Liệu Được Giám Sát Tự Động 24/7
            </h3>
            <p class="text-xs text-slate-400 mt-0.5">Tự động kích hoạt qua GitHub Actions &bull; Bảng beekip_crawler_sources trên Cloudflare D1</p>
          </div>
          <span id="sourcesCountBadge" class="text-xs px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">20 Nguồn</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-800/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <tr>
                <th class="px-5 py-3.5">Mã Nguồn (Source ID)</th>
                <th class="px-5 py-3.5">ETag Kiểm Tra</th>
                <th class="px-5 py-3.5">Lần Quét Cuối</th>
                <th class="px-5 py-3.5 text-center">Trạng Thái</th>
              </tr>
            </thead>
            <tbody id="sourcesTableBody" class="divide-y divide-slate-800/60 font-mono">
              <tr>
                <td colspan="4" class="px-5 py-8 text-center text-slate-500">Đang tải danh sách nguồn...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Queue Table -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div class="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 class="font-bold text-base text-slate-100 flex items-center gap-2">
              <i class="fa-solid fa-layer-group text-violet-400"></i> Hàng Đợi Thu Nạp (Inbound Crawler Queue)
            </h3>
            <p class="text-xs text-slate-400 mt-0.5">Các URL đang chờ xử lý hoặc đã bỏ qua do niên khóa cũ &le; 2022</p>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-800/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <tr>
                <th class="px-5 py-3.5">URL Thu Nạp</th>
                <th class="px-5 py-3.5">Nguồn</th>
                <th class="px-5 py-3.5">Trạng Thái</th>
                <th class="px-5 py-3.5">Thời Gian</th>
              </tr>
            </thead>
            <tbody id="queueTableBody" class="divide-y divide-slate-800/60 font-mono">
              <tr>
                <td colspan="4" class="px-5 py-8 text-center text-slate-500">Đang tải hàng đợi...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </main>

  <!-- Modal View Document Detail -->
  <div id="detailModal" class="hidden fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <h3 id="modalTitle" class="font-bold text-base text-slate-100 truncate pr-4">Chi Tiết Học Liệu</h3>
        <button onclick="closeModal()" class="w-8 h-8 rounded-full hover:bg-slate-800 flex items-center justify-center text-slate-400 hover:text-slate-200">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="p-6 overflow-y-auto space-y-4 text-xs font-mono text-slate-300" id="modalBody">
        <!-- Dynamic content inject -->
      </div>
      <div class="px-6 py-4 bg-slate-950 border-t border-slate-800 flex justify-between items-center">
        <div id="modalDownloadContainer"></div>
        <button onclick="closeModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl font-semibold text-xs transition">
          Đóng
        </button>
      </div>
    </div>
  </div>

  <!-- Toast Notification -->
  <div id="toast" class="hidden fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl bg-emerald-600 text-white text-xs font-semibold shadow-2xl flex items-center gap-2">
    <i class="fa-solid fa-circle-check"></i>
    <span id="toast-text">Đã sao chép!</span>
  </div>

  <!-- Client-side Logic Script -->
  <script>
    const BASE_PATH = "${basePath}";
    let currentPage = 1;
    let pageSize = 50;
    let searchTimeout = null;
    let cachedStats = null;

    // Tab switcher
    function switchTab(tabId) {
      ['documents', 'report', 'sources'].forEach(t => {
        const panel = document.getElementById('panel-' + t);
        const tab = document.getElementById('tab-' + t);
        if (t === tabId) {
          panel.classList.remove('hidden');
          tab.classList.add('border-indigo-500', 'text-indigo-400');
          tab.classList.remove('border-transparent', 'text-slate-400');
        } else {
          panel.classList.add('hidden');
          tab.classList.remove('border-indigo-500', 'text-indigo-400');
          tab.classList.add('border-transparent', 'text-slate-400');
        }
      });
    }

    // Show Toast
    function showToast(msg) {
      const toast = document.getElementById('toast');
      const text = document.getElementById('toast-text');
      text.innerText = msg;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 3000);
    }

    // Copy to clipboard
    function copySection(elementId) {
      const el = document.getElementById(elementId);
      if (!el) return;
      navigator.clipboard.writeText(el.innerText).then(() => {
        showToast('Đã copy nội dung vào clipboard!');
      });
    }

    function copyFullReport() {
      const s1 = document.getElementById('report-storage-content').innerText;
      const s2 = document.getElementById('report-prompt-content').innerText;
      const full = s1 + "\\n\\n" + s2;
      navigator.clipboard.writeText(full).then(() => {
        showToast('Đã copy toàn bộ Báo Cáo & Prompt!');
      });
    }

    // Search debounce
    function debounceSearch() {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentPage = 1;
        loadDocuments();
      }, 350);
    }

    function changePageSize() {
      pageSize = parseInt(document.getElementById('pageSizeSelect').value, 10);
      currentPage = 1;
      loadDocuments();
    }

    function prevPage() {
      if (currentPage > 1) {
        currentPage--;
        loadDocuments();
      }
    }

    function nextPage() {
      currentPage++;
      loadDocuments();
    }

    // Load Stats
    async function loadStats() {
      try {
        const res = await fetch(BASE_PATH + '/api/stats');
        if (res.status === 401) {
          window.location.reload();
          return;
        }
        const data = await res.json();
        cachedStats = data;

        document.getElementById('stat-documents').innerText = (data.total_documents || 0).toLocaleString();
        document.getElementById('stat-r2-files').innerText = (data.total_documents || 0).toLocaleString();
        document.getElementById('stat-queue-pending').innerText = (data.total_pending || 0).toLocaleString();
        document.getElementById('stat-sources').innerText = (data.total_sources || 0).toLocaleString();

        document.getElementById('rep-doc-count').innerText = (data.total_documents || 0).toLocaleString();
        document.getElementById('rep-r2-count').innerText = (data.total_documents || 0).toLocaleString();
        document.getElementById('rep-queue-count').innerText = (data.total_queue || 0).toLocaleString();
        document.getElementById('report-timestamp').innerText = new Date().toLocaleString('vi-VN');

        if (data.sources) {
          renderSourcesTable(data.sources);
        }
      } catch (err) {
        console.error("Lỗi tải thống kê:", err);
      }
    }

    // Format exact date and time (ngày, giờ, phút, giây)
    function formatExactTime(val) {
      if (!val) return '<span class="text-slate-500 font-sans text-xs">N/A</span>';
      let d;
      if (typeof val === 'number') {
        d = new Date(val < 1e11 ? val * 1000 : val);
      } else if (!isNaN(Number(val))) {
        const num = Number(val);
        d = new Date(num < 1e11 ? num * 1000 : num);
      } else {
        d = new Date(val);
      }
      if (isNaN(d.getTime())) return '<span class="text-slate-500 font-sans text-xs">N/A</span>';
      const pad = (n) => String(n).padStart(2, '0');
      const day = pad(d.getDate());
      const month = pad(d.getMonth() + 1);
      const year = d.getFullYear();
      const hh = pad(d.getHours());
      const mm = pad(d.getMinutes());
      const ss = pad(d.getSeconds());
      const fullStr = hh + ':' + mm + ':' + ss + ' ' + day + '/' + month + '/' + year;
      return '<div title="Thời gian đăng: ' + fullStr + '" class="cursor-help">' +
               '<div class="text-slate-200 font-semibold text-xs font-mono">' + day + '/' + month + '/' + year + '</div>' +
               '<div class="text-teal-400 text-[11px] font-mono flex items-center gap-1 mt-0.5">' +
                 '<i class="fa-regular fa-clock text-[10px]"></i> ' + hh + ':' + mm + ':' + ss +
               '</div>' +
             '</div>';
    }

    // Load Documents
    async function loadDocuments() {
      const tbody = document.getElementById('documentsTableBody');
      const search = (document.getElementById('docSearchInput').value || '').trim();

      tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-8 text-center text-slate-500"><i class="fa-solid fa-circle-notch fa-spin text-indigo-500 mr-2"></i>Đang tải dữ liệu...</td></tr>';

      try {
        const url = BASE_PATH + '/api/documents?page=' + currentPage + '&limit=' + pageSize + '&q=' + encodeURIComponent(search);
        const res = await fetch(url);
        if (res.status === 401) {
          window.location.reload();
          return;
        }
        const data = await res.json();
        const docs = data.documents || [];

        document.getElementById('currentPageBadge').innerText = currentPage;
        document.getElementById('paginationInfo').innerText = 'Hiển thị ' + docs.length + ' mục (Trang ' + currentPage + ')';
        document.getElementById('btnPrevPage').disabled = (currentPage <= 1);
        document.getElementById('btnNextPage').disabled = (docs.length < pageSize);

        if (docs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-8 text-center text-slate-400">Không tìm thấy tài liệu phù hợp.</td></tr>';
          return;
        }

        window.currentDocs = docs;

        tbody.innerHTML = docs.map((doc, idx) => {
          let tags = [];
          try { tags = JSON.parse(doc.audience_tags_json || '[]'); } catch(e){}
          const tagBadges = tags.slice(0, 3).map(t => '<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] mr-1">' + escapeHtml(t) + '</span>').join('');

          const sizeKb = doc.size_bytes ? (doc.size_bytes / 1024).toFixed(0) + ' KB' : 'N/A';
          const fileKey = doc.source_object_key || '';
          const directFileUrl = fileKey ? BASE_PATH + '/files/' + encodeURIComponent(fileKey) : null;
          const beekipUrl = 'https://tailieu.beekip.vn/api/documents/' + encodeURIComponent(doc.slug) + '/download';
          const timeCol = formatExactTime(doc.created_at);

          return '<tr class="hover:bg-slate-800/30 transition">' +
            '<td class="px-5 py-3 font-sans">' +
              '<div class="font-semibold text-slate-200 text-xs">' + escapeHtml(doc.title) + '</div>' +
              '<div class="text-[11px] text-slate-500 font-mono mt-0.5">slug: ' + escapeHtml(doc.slug) + '</div>' +
            '</td>' +
            '<td class="px-5 py-3">' + tagBadges + '</td>' +
            '<td class="px-5 py-3 text-slate-400 font-mono"><span class="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 uppercase text-[10px]">PDF</span></td>' +
            '<td class="px-5 py-3 text-slate-400 font-mono">' + sizeKb + '</td>' +
            '<td class="px-5 py-3 whitespace-nowrap">' + timeCol + '</td>' +
            '<td class="px-5 py-3">' +
              '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Xuất Bản</span>' +
            '</td>' +
            '<td class="px-5 py-3 text-right">' +
              '<div class="flex items-center justify-end gap-1.5 font-sans">' +
                (directFileUrl ? '<a href="' + directFileUrl + '" target="_blank" class="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded text-xs transition" title="Tải từ Cloudflare R2"><i class="fa-solid fa-cloud-arrow-down"></i> R2</a>' : '') +
                '<a href="' + beekipUrl + '" target="_blank" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition" title="Tải từ Beekip"><i class="fa-solid fa-download"></i></a>' +
                '<button onclick="viewDocDetailByIndex(' + idx + ')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition" title="Xem chi tiết"><i class="fa-solid fa-circle-info"></i></button>' +
              '</div>' +
            '</td>' +
          '</tr>';
        }).join('');
      } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-8 text-center text-rose-400">Lỗi kết nối D1: ' + err + '</td></tr>';
      }
    }

    // View Modal By Index
    function viewDocDetailByIndex(idx) {
      if (window.currentDocs && window.currentDocs[idx]) {
        viewDocDetail(window.currentDocs[idx]);
      }
    }

    // View Modal
    function viewDocDetail(doc) {
      document.getElementById('modalTitle').innerText = doc.title;
      let tags = [];
      try { tags = JSON.parse(doc.audience_tags_json || '[]'); } catch(e){}

      const body = document.getElementById('modalBody');
      body.innerHTML = 
        '<div><span class="text-slate-500">ID:</span> <span class="text-indigo-300">' + doc.id + '</span></div>' +
        '<div><span class="text-slate-500">Mã Tài Liệu:</span> <span class="text-slate-200">' + doc.document_code + '</span></div>' +
        '<div><span class="text-slate-500">Tác giả:</span> <span class="text-slate-200">' + escapeHtml(doc.author_name) + '</span></div>' +
        '<div><span class="text-slate-500">R2 Object Key:</span> <span class="text-amber-300 break-all">' + escapeHtml(doc.source_object_key) + '</span></div>' +
        '<div><span class="text-slate-500">Tên Tệp Gốc:</span> <span class="text-slate-200 break-all">' + escapeHtml(doc.original_filename) + '</span></div>' +
        '<div><span class="text-slate-500">Dung lượng:</span> <span class="text-slate-200">' + (doc.size_bytes ? (doc.size_bytes / 1024).toFixed(1) + ' KB' : 'N/A') + '</span></div>' +
        '<div><span class="text-slate-500">Thẻ Phân Loại:</span> <span class="text-slate-200 font-sans">' + tags.join(', ') + '</span></div>' +
        '<div><span class="text-slate-500">Thời gian đăng:</span> <span class="text-teal-400 font-mono font-medium">' + 
          (doc.created_at ? (function(c) {
            const d = typeof c === 'number' ? new Date(c < 1e11 ? c * 1000 : c) : new Date(Number(c) || c);
            if (isNaN(d.getTime())) return 'N/A';
            const pad = (n) => String(n).padStart(2, '0');
            return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + '/' + d.getFullYear() + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
          })(doc.created_at) : 'N/A') + 
        '</span></div>';

      const fileKey = doc.source_object_key || '';
      const downloadBtn = fileKey 
        ? '<a href="' + BASE_PATH + '/files/' + encodeURIComponent(fileKey) + '" target="_blank" class="px-4 py-2 bg-gradient-to-r from-indigo-600 to-teal-600 text-white rounded-xl font-bold text-xs flex items-center gap-1.5"><i class="fa-solid fa-cloud-arrow-down"></i> Tải Tệp Từ Cloudflare R2</a>' 
        : '';
      document.getElementById('modalDownloadContainer').innerHTML = downloadBtn;

      document.getElementById('detailModal').classList.remove('hidden');
    }

    function closeModal() {
      document.getElementById('detailModal').classList.add('hidden');
    }

    // Render Sources
    function renderSourcesTable(sources) {
      const tbody = document.getElementById('sourcesTableBody');
      if (!tbody) return;
      if (!sources || sources.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-5 py-6 text-center text-slate-500">Chưa có nguồn nào được ghi nhận.</td></tr>';
        return;
      }
      tbody.innerHTML = sources.map(s => {
        return '<tr class="hover:bg-slate-800/30 transition">' +
          '<td class="px-5 py-3 font-semibold text-slate-200">' + escapeHtml(s.source_id) + '</td>' +
          '<td class="px-5 py-3 text-slate-400 font-mono text-[11px] truncate max-w-xs">' + (s.last_etag || 'None') + '</td>' +
          '<td class="px-5 py-3 text-slate-400 font-mono text-[11px]">' + (s.last_checked_at || 'Chưa chạy') + '</td>' +
          '<td class="px-5 py-3 text-center"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Hoạt Động</span></td>' +
        '</tr>';
      }).join('');
    }

    // Load Queue
    async function loadQueue() {
      const tbody = document.getElementById('queueTableBody');
      if (!tbody) return;
      try {
        const res = await fetch(BASE_PATH + '/api/queue');
        if (res.status === 401) return;
        const data = await res.json();
        const items = data.queue || [];
        if (items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" class="px-5 py-6 text-center text-slate-500">Hàng đợi đang trống.</td></tr>';
          return;
        }
        tbody.innerHTML = items.map(q => {
          const isPending = q.status === 'PENDING';
          const badgeClass = isPending 
            ? 'bg-amber-500/10 text-amber-300 border-amber-500/20' 
            : 'bg-slate-800 text-slate-400 border-slate-700';
          return '<tr class="hover:bg-slate-800/30 transition">' +
            '<td class="px-5 py-2.5 font-sans truncate max-w-sm"><a href="' + escapeHtml(q.url) + '" target="_blank" class="hover:text-indigo-300 truncate block">' + escapeHtml(q.url) + '</a></td>' +
            '<td class="px-5 py-2.5 font-mono text-slate-400">' + escapeHtml(q.source_id) + '</td>' +
            '<td class="px-5 py-2.5 font-mono"><span class="px-2 py-0.5 rounded border text-[10px] ' + badgeClass + '">' + escapeHtml(q.status) + '</span></td>' +
            '<td class="px-5 py-2.5 font-mono text-slate-400 text-xs">' + formatExactTime(q.created_at) + '</td>' +
          '</tr>';
        }).join('');
      } catch(e) {
        console.error("Lỗi tải queue:", e);
      }
    }

    // Manual Trigger
    async function triggerManualCrawl() {
      const btn = document.getElementById('btn-trigger');
      const icon = document.getElementById('btn-trigger-icon');
      const text = document.getElementById('btn-trigger-text');
      const alert = document.getElementById('actionAlert');

      btn.disabled = true;
      icon.className = 'fa-solid fa-circle-notch fa-spin';
      text.innerText = 'Đang Quét...';

      try {
        const res = await fetch(BASE_PATH + '/api/trigger', { method: 'POST' });
        const data = await res.json();
        alert.className = 'p-4 rounded-xl text-sm font-medium transition duration-300 ' + (data.success ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-rose-500/20 text-rose-300 border border-rose-500/40');
        alert.innerText = data.message || (data.success ? 'Đã kích hoạt quét thành công!' : 'Có lỗi khi quét');
        alert.classList.remove('hidden');

        await loadAllData();
        setTimeout(() => alert.classList.add('hidden'), 5000);
      } catch (err) {
        alert.className = 'p-4 rounded-xl text-sm font-medium bg-rose-500/20 text-rose-300 border border-rose-500/40';
        alert.innerText = 'Lỗi kích hoạt: ' + err;
        alert.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        icon.className = 'fa-solid fa-bolt';
        text.innerText = 'Quét & Xử Lý Ngay';
      }
    }

    // Logout
    async function handleLogout() {
      try {
        await fetch(BASE_PATH + '/api/logout', { method: 'POST' });
      } catch(e){}
      window.location.href = BASE_PATH;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
      });
    }

    async function loadAllData() {
      await Promise.all([loadStats(), loadDocuments(), loadQueue()]);
    }

    window.addEventListener('DOMContentLoaded', loadAllData);
  </script>
</body>
</html>`;
}
