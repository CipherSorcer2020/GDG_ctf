/* Feel-good effects shared by the pages: confetti, toasts, avatars, theme toggle. */
const REDUCED = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
const GOOGLE_COLORS = ['#4285f4', '#ea4335', '#fbbc04', '#34a853'];

/** Deterministic colour class for a player name (same name -> same colour everywhere). */
function avatarClass(name) {
  let h = 0; for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return 'av' + (h % 4);
}
function initials(name) {
  const parts = String(name).trim().split(/\s+/);
  return ((parts[0] || '?')[0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}
const avatarHTML = name => `<span class="avatar ${avatarClass(name)}" aria-hidden="true">${esc(initials(name))}</span>`;

/* ---------------- toasts ---------------- */
function toast(html, kind = '', ms = 3800) {
  let box = document.getElementById('toasts');
  if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
  while (box.children.length >= 3) box.firstChild.remove();
  const el = document.createElement('div');
  el.className = 'toast ' + kind; el.innerHTML = html; box.appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 320); }, ms);
}

/* ---------------- confetti (Google colours) ---------------- */
let _confetti = null;
function confetti({x = 0.5, y = 0.35, count = 140, spread = 1, duration = 2600} = {}) {
  if (REDUCED) return;
  let cv = document.getElementById('confetti');
  if (!cv) { cv = document.createElement('canvas'); cv.id = 'confetti'; document.body.appendChild(cv); }
  const dpr = window.devicePixelRatio || 1;
  cv.width = innerWidth * dpr; cv.height = innerHeight * dpr;
  const ctx = cv.getContext('2d'); if (!ctx) return; ctx.scale(dpr, dpr);
  const parts = Array.from({length: count}, () => {
    const a = (Math.random() * Math.PI * 2), v = (4 + Math.random() * 9) * spread;
    return {x: x * innerWidth, y: y * innerHeight, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 6, g: .28 + Math.random() * .15,
            w: 6 + Math.random() * 7, h: 4 + Math.random() * 6, r: Math.random() * 6, vr: (Math.random() - .5) * .4,
            c: GOOGLE_COLORS[(Math.random() * 4) | 0], round: Math.random() < .3};
  });
  const end = performance.now() + duration;
  cancelAnimationFrame(_confetti);
  (function frame(now) {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    const left = Math.max(0, (end - now) / duration);
    for (const p of parts) {
      p.vy += p.g; p.vx *= .992; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      ctx.save(); ctx.globalAlpha = Math.min(1, left * 2.2); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c;
      if (p.round) { ctx.beginPath(); ctx.arc(0, 0, p.w / 2.2, 0, 7); ctx.fill(); } else ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }
    if (now < end) _confetti = requestAnimationFrame(frame); else ctx.clearRect(0, 0, innerWidth, innerHeight);
  })(performance.now());
}
/** A big celebration: two side cannons + a centre burst. */
function celebrate() { confetti({x: .15, y: .8, count: 90}); confetti({x: .85, y: .8, count: 90}); setTimeout(() => confetti({x: .5, y: .3, count: 110}), 180); }

/* ---------------- theme toggle ---------------- */
function bindThemeToggle(btn) {
  if (!btn) return;
  const paint = () => { btn.textContent = document.documentElement.dataset.theme === 'dark' ? '\u2600\uFE0F' : '\u{1F319}'; btn.setAttribute('aria-label', 'Toggle light / dark theme'); };
  btn.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('ctf-theme', next); } catch (e) {}
    paint();
  });
  paint();
}

/** Fill the shared header brand (logo + club + event) from the /api/state payload. */
function paintBrand(state) {
  const club = (state.brand && state.brand.club) || '';
  document.querySelectorAll('[data-brand-club]').forEach(el => { el.textContent = club || el.dataset.fallback || ''; });
  document.querySelectorAll('[data-brand-event]').forEach(el => { el.textContent = state.event.name; });
  document.title = state.event.name + (club ? ' \u00b7 ' + club : '');
}
