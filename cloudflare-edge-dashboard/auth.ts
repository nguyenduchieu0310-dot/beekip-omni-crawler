import { Env } from './types';

// Simple deterministic hash for edge runtime without external crypto dependencies
export function computeTokenSignature(payload: string, secret: string): string {
  let hash = 0;
  const combined = payload + "###" + secret;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36);
}

export function createSessionToken(username: string, env: Env): string {
  const ts = Date.now().toString();
  const secret = env.JWT_SECRET || "beekip_default_secret_2026";
  const signature = computeTokenSignature(`${username}:${ts}`, secret);
  const raw = `${username}:${ts}:${signature}`;
  return btoa(raw);
}

export function verifySessionToken(token: string, env: Env): { valid: boolean; username?: string } {
  try {
    const decoded = atob(token);
    const [user, tsStr, sig] = decoded.split(":");
    if (!user || !tsStr || !sig) return { valid: false };

    const ts = parseInt(tsStr, 10);
    const now = Date.now();
    // 30 days validity
    if (isNaN(ts) || now - ts > 30 * 24 * 60 * 60 * 1000) {
      return { valid: false };
    }

    const secret = env.JWT_SECRET || "beekip_default_secret_2026";
    const expectedSig = computeTokenSignature(`${user}:${tsStr}`, secret);

    const validUser = (env.ADMIN_USER || "admin");
    if (sig === expectedSig && user.toLowerCase() === validUser.toLowerCase()) {
      return { valid: true, username: user };
    }
  } catch (e) {
    // Malformed token
  }
  return { valid: false };
}

export function extractSessionUser(request: Request, env: Env): string | null {
  const cookieHeader = request.headers.get("Cookie") || "";
  const match = cookieHeader.match(/beekip_admin_session=([^;]+)/);
  if (!match) return null;

  const result = verifySessionToken(match[1], env);
  return result.valid ? (result.username || "admin") : null;
}

export function renderLoginHtml(basePath: string = "/hubag/crawl", errorMessage: string = ""): string {
  return `<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Đăng Nhập Quản Trị • Beekip Omni-Agent 24/7/365</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .glow-indigo { box-shadow: 0 0 40px rgba(99, 102, 241, 0.25); }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
  
  <!-- Background Glow Orbs -->
  <div class="absolute -top-32 -left-32 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>
  <div class="absolute -bottom-32 -right-32 w-96 h-96 bg-teal-600/20 rounded-full blur-3xl pointer-events-none"></div>

  <!-- Login Card -->
  <div class="max-w-md w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-8 shadow-2xl backdrop-blur-xl relative z-10 glow-indigo space-y-6">
    
    <!-- Branding Header -->
    <div class="text-center space-y-3">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 via-violet-600 to-teal-400 mx-auto flex items-center justify-center shadow-lg shadow-indigo-500/30">
        <i class="fa-solid fa-shield-halved text-3xl text-white"></i>
      </div>
      <div>
        <h1 class="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-teal-300 bg-clip-text text-transparent">
          BEEKIP OMNI-AGENT
        </h1>
        <p class="text-xs text-slate-400 mt-1">Cổng Quản Trị Hệ Thống Thu Nạp &amp; Xuất Bản 24/7/365</p>
      </div>
      <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-[11px] font-semibold text-emerald-400">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span>Khu Vực Bảo Mật Ban Quản Trị</span>
      </div>
    </div>

    <!-- Alert Message -->
    <div id="login-alert" class="${errorMessage ? '' : 'hidden'} p-3.5 rounded-xl bg-rose-500/20 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <span id="login-alert-text">${errorMessage || "ID Admin hoặc Mật khẩu không chính xác!"}</span>
    </div>

    <!-- Login Form -->
    <form id="form-login" onsubmit="handleLoginSubmit(event)" class="space-y-4">
      <div class="space-y-1.5">
        <label class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
          <i class="fa-solid fa-user-shield text-indigo-400"></i> ID Admin
        </label>
        <div class="relative">
          <input 
            type="text" 
            id="admin-id" 
            required 
            autocomplete="username"
            placeholder="Nhập ID Admin (ví dụ: admin)" 
            class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono transition"
          />
        </div>
      </div>

      <div class="space-y-1.5">
        <label class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
          <i class="fa-solid fa-key text-teal-400"></i> Mật Khẩu
        </label>
        <div class="relative">
          <input 
            type="password" 
            id="admin-password" 
            required 
            autocomplete="current-password"
            placeholder="Nhập Mật Khẩu Admin" 
            class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono transition pr-10"
          />
          <button type="button" onclick="togglePasswordVisibility()" class="absolute right-3 top-3 text-slate-400 hover:text-slate-200">
            <i id="eye-icon" class="fa-solid fa-eye text-sm"></i>
          </button>
        </div>
      </div>

      <div class="flex items-center justify-between text-xs text-slate-400 pt-1">
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" id="remember-me" checked class="rounded border-slate-700 bg-slate-950 text-indigo-500 focus:ring-0" />
          <span>Ghi nhớ phiên (30 ngày)</span>
        </label>
        <span class="text-[11px] text-slate-500 font-mono">SSL 256-Bit TLS</span>
      </div>

      <button 
        type="submit" 
        id="btn-login-submit"
        class="w-full py-3.5 rounded-xl bg-gradient-to-r from-indigo-600 via-violet-600 to-teal-500 hover:from-indigo-500 hover:to-teal-400 text-white font-bold text-sm shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 transition active:scale-95"
      >
        <i class="fa-solid fa-right-to-bracket"></i>
        <span>Xác Thực &amp; Truy Cập Hệ Thống</span>
      </button>
    </form>

    <!-- Footer info -->
    <div class="pt-4 border-t border-slate-800 text-center text-[11px] text-slate-500 space-y-1">
      <p>&copy; 2026 Beekip Education. Vận hành liên tục trên Cloudflare Edge.</p>
      <p class="font-mono text-[10px] text-slate-600">Route: beekip.vn${basePath}</p>
    </div>
  </div>

  <script>
    function togglePasswordVisibility() {
      const input = document.getElementById('admin-password');
      const icon = document.getElementById('eye-icon');
      if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fa-solid fa-eye-slash text-sm';
      } else {
        input.type = 'password';
        icon.className = 'fa-solid fa-eye text-sm';
      }
    }

    async function handleLoginSubmit(e) {
      e.preventDefault();
      const user = document.getElementById('admin-id').value.trim();
      const pass = document.getElementById('admin-password').value.trim();
      const alertBox = document.getElementById('login-alert');
      const alertText = document.getElementById('login-alert-text');
      const btn = document.getElementById('btn-login-submit');

      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang xác thực...</span>';
      alertBox.classList.add('hidden');

      try {
        const res = await fetch('${basePath}/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: user, password: pass })
        });
        const data = await res.json();
        if (data.success) {
          window.location.href = data.redirect || '${basePath}';
        } else {
          alertText.innerText = data.error || 'ID Admin hoặc Mật khẩu không chính xác!';
          alertBox.classList.remove('hidden');
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> <span>Xác Thực &amp; Truy Cập Hệ Thống</span>';
        }
      } catch (err) {
        alertText.innerText = 'Lỗi kết nối máy chủ Cloudflare: ' + err;
        alertBox.classList.remove('hidden');
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> <span>Xác Thực &amp; Truy Cập Hệ Thống</span>';
      }
    }
  </script>
</body>
</html>`;
}
