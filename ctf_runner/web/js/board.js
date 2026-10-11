/* Projector scoreboard: big, animated, no interaction needed. Open /board on the TV. */
const ROW = 70;
const CAT_COLOR = {web: 'var(--blue)', crypto: 'var(--red)', forensics: 'var(--yellow)', rev: 'var(--green)', pwn: 'var(--red)', misc: 'var(--blue)'};
const rowsEl = $('#rows');
const rowEls = new Map();      // player -> element
const lastScore = new Map();
let seen = null, lastChals = '', lastWait = '', lastFeed = '';

$('#join-url').textContent = location.host;
bindThemeToggle($('#theme'));

function renderRows(rows) {
  const top = rows.slice(0, 12);
  rowsEl.style.height = (top.length * ROW) + 'px';
  const keep = new Set(top.map(r => r.player));
  rowEls.forEach((el, name) => { if (!keep.has(name)) { el.remove(); rowEls.delete(name); } });
  top.forEach((r, i) => {
    let el = rowEls.get(r.player);
    if (!el) {
      el = document.createElement('div');
      el.innerHTML = `<span class="rank"></span>${avatarHTML(r.player)}<span class="name"></span><span class="solved-n"></span><span class="score"></span>`;
      el.querySelector('.name').textContent = r.player;
      rowsEl.appendChild(el); rowEls.set(r.player, el);
    }
    el.className = 'rrow' + (i === 0 ? ' r1' : '');
    el.style.transform = `translateY(${i * ROW}px)`;
    el.querySelector('.rank').textContent = i < 3 ? ['\u{1F947}', '\u{1F948}', '\u{1F949}'][i] : i + 1;
    el.querySelector('.solved-n').textContent = r.solves + ' solved';
    el.querySelector('.score').textContent = r.score;
    if (lastScore.has(r.player) && lastScore.get(r.player) !== r.score) { el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1600); }
    lastScore.set(r.player, r.score);
  });
}

function renderFeed(feed) {
  const sig = JSON.stringify(feed);
  if (sig === lastFeed) return;          // do not rebuild (and re-animate) an unchanged list
  lastFeed = sig;
  const fresh = seen ? feed.filter(f => !seen.has(f.id)) : [];
  $('#feed').innerHTML = feed.map(f => `<li>${esc(f.player)} solved <b>${esc(f.title)}</b> <span class="pts" style="color:var(--yellow-ink);font-weight:700">+${f.points}</span></li>`).join('')
    || '<li class="empty">The first solve will show up here&hellip;</li>';
  if (fresh.length) celebrate();
  seen = new Set(feed.map(f => f.id));
}

function renderChals(list, total) {
  const sig = JSON.stringify([list.map(c => [c.name, c.solves]), total]);
  if (sig === lastChals) return;
  lastChals = sig;
  $('#chals').innerHTML = list.map(c => `<div class="chal-line"><div class="top"><span>${esc(c.title)}</span><span class="muted">${c.solves} / ${total}</span></div>
    <div class="bar"><div style="width:${total ? Math.min(100, c.solves / total * 100) : 0}%;background:${CAT_COLOR[c.category] || 'var(--blue)'}"></div></div></div>`).join('');
}

async function tick() {
  const r = await api('/api/state');
  if (!r.data) return;
  const s = r.data;
  paintBrand(s);
  const waiting = s.phase !== 'active';
  $('#stage-wait').hidden = !waiting; $('#stage-main').hidden = waiting;
  if (waiting) {
    const sig = JSON.stringify(s.players);
    $('#wait-title').textContent = s.phase === 'starting' ? 'Get ready\u2026 \u{1F680}' : `Waiting for players\u2026 (${(s.players || []).length} joined)`;
    if (sig !== lastWait) { lastWait = sig; $('#wait-players').innerHTML = (s.players || []).map(p => `<span class="chip-player">${avatarHTML(p)}${esc(p)}</span>`).join(''); }
    return;
  }
  renderRows(s.scoreboard); renderFeed(s.feed || []);
  renderChals(s.challenges, Math.max(1, s.scoreboard.length));
}
smartInterval(tick, () => 2500);
