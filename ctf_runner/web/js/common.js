/* Shared helpers for every page. */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/** JSON fetch. Never throws: returns {ok, status, data} (data is null on network/parse errors). */
async function api(path, body) {
  try {
    const res = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-cache',
    });
    let data = null;
    try { data = await res.json(); } catch (e) { /* 304 / non-JSON */ }
    return {ok: res.ok, status: res.status, data};
  } catch (e) {
    return {ok: false, status: 0, data: null};
  }
}

const PLAYER_KEY = 'ctf-player';
const getPlayer = () => localStorage.getItem(PLAYER_KEY) || '';
const setPlayer = n => localStorage.setItem(PLAYER_KEY, n);
const clearPlayer = () => localStorage.removeItem(PLAYER_KEY);

function fmtSize(n) {
  return n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
}

/** Run fn on a timer that pauses while the tab is hidden and fires at once when it returns. */
function smartInterval(fn, getDelay) {
  let timer = null, stopped = false;
  const loop = async () => {
    clearTimeout(timer);
    if (stopped) return;
    if (!document.hidden) await fn();
    timer = setTimeout(loop, getDelay());
  };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) loop(); });
  loop();
  return { now: loop, stop() { stopped = true; clearTimeout(timer); } };
}
