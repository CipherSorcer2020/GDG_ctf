/* Main player page: lobby -> countdown -> challenges + scoreboard.
 *
 * One request per poll (/api/state). The server answers 304 when nothing
 * changed, and only the cards that did change are redrawn, so open hints,
 * half-typed flags and the cursor are never lost.
 */
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const els = {
  lobby: $('#lobby'), join: $('#lobby-join'), wait: $('#lobby-wait'), count: $('#lobby-count'),
  joinForm: $('#join-form'), joinName: $('#join-name'), joinErr: $('#join-err'), joinText: $('#lobby-join-text'), joinTitle: $('#join-title'),
  players: $('#player-list'), nPlayers: $('#player-count'), countNum: $('#count-num'),
  me: $('#me'), challenges: $('#challenges'), board: $('#scoreboard'), feed: $('#feed'),
  progText: $('#prog-text'), progPts: $('#prog-pts'), progBar: $('#prog-bar'), howto: $('#howto'), offline: $('#offline'),
};
const CATS = {web: ['\u{1F310}', 'blue'], crypto: ['\u{1F510}', 'red'], forensics: ['\u{1F50D}', 'yellow'],
              rev: ['\u2699\uFE0F', 'green'], pwn: ['\u{1F4A5}', 'red'], misc: ['\u{1F9E9}', 'blue']};
const TIERS = ['a gentle nudge', 'which tool?', 'walkthrough'];
const MEDALS = ['\u{1F947}', '\u{1F948}', '\u{1F949}'];

let lastSig = {}, lastBoard = '', lastLobby = '', lastFeed = '';
let failures = 0, phase = null, prevPhase = null, rejoining = false;
let seenFeed = null;            // Set of feed ids already shown (null until the first active poll)
let countdownEnd = 0, countdownTimer = null;
let pulseName = '';

/* ------------------------------------------------------------ lobby */

function showOverlay(which) {
  els.lobby.classList.add('show');
  els.join.hidden = which !== 'join'; els.wait.hidden = which !== 'wait'; els.count.hidden = which !== 'count';
}
function showJoin(message) {
  showOverlay('join');
  if (message !== undefined) els.joinErr.textContent = message;     // never wipe an error on a poll
  const live = phase === 'active' || phase === 'starting';
  els.joinTitle.textContent = live ? 'The game is on! \u{1F680}' : 'Welcome! \u{1F44B}';
  els.joinText.textContent = live ? 'Pick a name to jump in.' : 'Pick a name to join the game. Your friends will see it on the scoreboard.';
}
function showWaiting(players, me) {
  showOverlay('wait');
  const sig = JSON.stringify([players, me]);
  if (sig === lastLobby) return;
  lastLobby = sig;
  els.nPlayers.textContent = players.length;
  els.players.innerHTML = players.map(p =>
    `<span class="chip-player ${p === me ? 'you' : ''}">${avatarHTML(p)}${esc(p)}</span>`).join('') || '<span class="empty">No players yet&hellip;</span>';
}
function showCountdown(ms) {
  showOverlay('count');
  countdownEnd = performance.now() + ms;
  if (countdownTimer) return;
  const paint = () => {
    const left = countdownEnd - performance.now();
    const n = Math.ceil(left / 1000);
    const text = n > 0 ? String(n) : 'GO!';
    if (els.countNum.textContent !== text) { els.countNum.textContent = text; els.countNum.style.animation = 'none'; void els.countNum.offsetWidth; els.countNum.style.animation = ''; }
  };
  paint(); countdownTimer = setInterval(paint, 80);
}
function stopCountdown() { clearInterval(countdownTimer); countdownTimer = null; }

els.joinForm.addEventListener('submit', async ev => {
  ev.preventDefault();
  const name = els.joinName.value.trim();
  if (!name) return;
  els.joinErr.textContent = '';
  const r = await api('/api/lobby/register', {player: name});
  if (!r.data) { els.joinErr.textContent = 'Could not reach the server - try again.'; return; }
  if (!r.data.success) { els.joinErr.textContent = r.data.message; return; }
  setPlayer(r.data.player);
  poller.now();
});

/** Saved name unknown to the server (new event / restart): claim it again quietly. */
async function reclaimName(saved) {
  if (rejoining) return;
  rejoining = true;
  const r = await api('/api/lobby/register', {player: saved});
  rejoining = false;
  if (!r.data) return;                       // network hiccup: retry on the next poll
  if (!r.data.success) { clearPlayer(); showJoin(r.data.message); return; }
  setPlayer(r.data.player);
  poller.now();
}

/* ------------------------------------------------------- challenges */

const difficulty = pts => pts <= 100 ? 'Beginner' : pts <= 150 ? 'Easy' : pts <= 250 ? 'Medium' : 'Epic';

function cardHTML(c) {
  const [emoji, color] = CATS[c.category] || CATS.misc;
  const files = c.files.length ? `
    <div class="files"><h4>Files</h4><ul>${c.files.map(f =>
      `<li>&#128196; <a href="/api/challenge/files/${encodeURIComponent(c.name)}/${f.name.split('/').map(encodeURIComponent).join('/')}" download>${esc(f.name)}</a>
        <span class="muted">(${fmtSize(f.size)})</span></li>`).join('')}</ul>
      ${c.files.length > 1 ? `<a class="zip" href="/api/challenge/zip/${encodeURIComponent(c.name)}">&#128230; download all (.zip)</a>` : ''}</div>` : '';
  const hints = c.hints.length ? `<div class="hints">${c.hints.map((h, i) =>
    `<details><summary>&#128161; ${esc(h.title)} <span class="muted">&middot; ${TIERS[i] || ''}</span></summary><div>${h.html}</div></details>`).join('')}</div>` : '';
  const lesson = c.lesson ? `<div class="lesson"><b>&#127891; You just learned:</b> ${c.lesson}</div>` : '';
  const form = c.solved ? '<div class="done">&#9989; Solved &mdash; nice work!</div>' : `
    <form class="submit" autocomplete="off">
      <input type="text" name="flag" placeholder="flag{...}" spellcheck="false" autocomplete="off" autocapitalize="off" aria-label="Your flag">
      <button type="submit" class="btn-go">Submit flag</button>
    </form>`;
  const first = c.first ? `<div class="firstblood">&#127942; First solved by <b>${esc(c.first)}</b></div>` : '';
  return `
    <div class="chal-head">
      <span class="chal-title">${esc(c.title)}</span>
      <span class="chal-meta"><span class="chip ${color}">${emoji} ${esc(c.category)}</span><span class="chip">${difficulty(c.points)}</span>
        <span class="pts">${c.points} pts</span></span>
    </div>
    ${first}
    <div class="story">${c.story || '<p class="empty">No description.</p>'}</div>
    ${files}${hints}${lesson}${form}
    <div class="msg" role="status"></div>`;
}

/** Snapshot what the player is doing inside a card so a rebuild can put it back. */
function snapshot(card) {
  const input = card.querySelector('input[name=flag]');
  const msg = card.querySelector('.msg');
  return {
    open: $$('details', card).map(d => d.open),
    flag: input ? input.value : '',
    focus: input && document.activeElement === input,
    caret: input ? input.selectionStart : 0,
    msgClass: msg ? msg.className : 'msg', msgText: msg ? msg.textContent : '',
  };
}
function restore(card, st) {
  $$('details', card).forEach((d, i) => { if (st.open[i]) d.open = true; });
  const input = card.querySelector('input[name=flag]');
  if (input && st.flag) input.value = st.flag;
  if (input && st.focus) { input.focus(); input.setSelectionRange(st.caret, st.caret); }
  const msg = card.querySelector('.msg');
  if (msg && st.msgText) { msg.className = st.msgClass; msg.textContent = st.msgText; }
}

function renderChallenges(list) {
  if (!list.length) { els.challenges.innerHTML = '<p class="empty">No challenges yet.</p>'; lastSig = {}; return; }
  const existing = new Map($$('.chal', els.challenges).map(el => [el.dataset.name, el]));
  const wanted = new Set(list.map(c => c.name));
  existing.forEach((el, name) => { if (!wanted.has(name)) { el.remove(); delete lastSig[name]; } });
  els.challenges.querySelector('.empty')?.remove();

  list.forEach((c, index) => {
    const sig = JSON.stringify(c);
    let el = existing.get(c.name);
    if (!(el && lastSig[c.name] === sig)) {
      const fresh = document.createElement('article');
      fresh.className = `card chal cat-${(CATS[c.category] || CATS.misc)[1]}` + (c.solved ? ' solved' : '');
      fresh.dataset.name = c.name;
      fresh.innerHTML = cardHTML(c);
      if (el) { restore(fresh, snapshot(el)); el.replaceWith(fresh); } else { els.challenges.appendChild(fresh); }
      if (pulseName === c.name && c.solved) { fresh.classList.add('pulse'); pulseName = ''; }
      el = fresh;
      lastSig[c.name] = sig;
    }
    if (els.challenges.children[index] !== el) els.challenges.insertBefore(el, els.challenges.children[index] || null);
  });

  const done = list.filter(c => c.solved).length;
  $('#n-all').textContent = list.length; $('#n-todo').textContent = list.length - done; $('#n-done').textContent = done;
}

function renderProgress(list, mine) {
  const done = list.filter(c => c.solved).length;
  els.progText.textContent = done === list.length && list.length ? 'All solved \u2014 you are a legend! \u{1F451}' : `${done} of ${list.length} solved`;
  els.progPts.textContent = '\u2B50 ' + (mine ? mine.score : 0) + ' pts';
  els.progBar.style.width = (list.length ? done / list.length * 100 : 0) + '%';
}

/* ------------------------------------------------ scoreboard + feed */

function rowHTML(r, rank, me) {
  const medal = rank <= 3 ? MEDALS[rank - 1] : rank;
  return `<div class="row ${r.player === me ? 'me' : ''}"><span class="rank">${medal}</span>${avatarHTML(r.player)}
    <span class="name">${esc(r.player)}${r.player === me ? ' <span class="muted">(you)</span>' : ''}</span>
    <span><span class="score">${r.score}</span> <span class="solved-n">pts</span></span></div>`;
}
function renderBoard(rows, me) {
  const sig = JSON.stringify([rows, me]);
  if (sig === lastBoard) return;
  lastBoard = sig;
  if (!rows.length) { els.board.innerHTML = '<p class="empty" style="padding:.8rem">No solves yet &mdash; be the first! &#127937;</p>'; return; }
  const top = rows.slice(0, 10);
  let html = top.map((r, i) => rowHTML(r, i + 1, me)).join('');
  const idx = rows.findIndex(r => r.player === me);
  if (idx >= 10) html += `<div class="row gap">&hellip;</div>` + rowHTML(rows[idx], idx + 1, me);
  els.board.innerHTML = html;
}
function renderFeed(feed, me) {
  const sig = JSON.stringify(feed);
  if (sig === lastFeed) return;
  lastFeed = sig;
  const fresh = seenFeed ? feed.filter(f => !seenFeed.has(f.id)) : [];
  els.feed.innerHTML = feed.map(f => {
    const emoji = (CATS[f.category] || CATS.misc)[0];
    return `<li class="${fresh.includes(f) ? 'new' : ''}">${emoji} <b>${esc(f.player)}</b> solved <b>${esc(f.title)}</b> <span class="pts">+${f.points}</span></li>`;
  }).join('') || '<li class="empty">Nothing yet &mdash; the first solve will show up here.</li>';
  const others = fresh.filter(f => f.player !== me);
  if (others.length) { const f = others[0]; toast(`${(CATS[f.category] || CATS.misc)[0]} <b>${esc(f.player)}</b> just solved <b>${esc(f.title)}</b>`); }
  seenFeed = new Set(feed.map(f => f.id));
}

/* ---------------------------------------------------- submitting */

els.challenges.addEventListener('submit', async ev => {
  const form = ev.target.closest('form.submit');
  if (!form) return;
  ev.preventDefault();
  const card = form.closest('.chal');
  const msg = card.querySelector('.msg');
  const flag = form.elements.flag.value.trim();
  if (!flag) { msg.className = 'msg meh'; msg.textContent = 'Type your flag first.'; return; }
  msg.className = 'msg'; msg.textContent = 'checking\u2026';
  const r = await api('/api/submit', {player: getPlayer(), challenge: card.dataset.name, flag});
  const d = r.data || {status: 'error', message: 'Could not reach the server - try again.'};
  const good = d.status === 'correct';
  msg.className = 'msg ' + (good || d.status === 'already_solved' ? 'ok' : 'bad');
  msg.textContent = d.status === 'incorrect' ? 'Not quite \u2014 check the format and try again. You can do it! \u{1F4AA}' : (d.message || d.status);
  if (good) {
    pulseName = card.dataset.name;
    celebrate();
    toast(`\u{1F389} +${d.points_awarded} pts \u2014 <b>${esc(card.querySelector('.chal-title').textContent)}</b> solved!`, 'big', 4200);
    if (d.first_blood) setTimeout(() => toast('\u{1F3C6} <b>First blood!</b> Nobody solved this before you.', 'big', 4200), 500);
  }
  if (good || d.status === 'already_solved') poller.now();
});

/* ---------------------------------------------------- chrome / UI */

$$('.filters button').forEach(b => b.addEventListener('click', () => {
  els.challenges.dataset.filter = b.dataset.f;
  $$('.filters button').forEach(x => x.classList.toggle('on', x === b));
}));
$$('.bottom-nav button[data-tab]').forEach(b => b.addEventListener('click', () => {
  document.body.dataset.tab = b.dataset.tab;
  $$('.bottom-nav button[data-tab]').forEach(x => x.classList.toggle('on', x === b));
  window.scrollTo({top: 0});
}));
$('#howto-x').addEventListener('click', () => { els.howto.hidden = true; localStorage.setItem('ctf-howto', '1'); });
let logoClicks = [];
$('#logo').addEventListener('click', e => {
  e.preventDefault(); const now = Date.now();
  logoClicks = logoClicks.filter(t => now - t < 2000).concat(now);
  if (logoClicks.length >= 5) { logoClicks = []; celebrate(); toast('\u{1F984} You found the secret! Nice clicking.'); }
});
bindThemeToggle($('#theme'));

/* ---------------------------------------------------------- poll */

async function tick() {
  const saved = getPlayer();
  const r = await api('/api/state?player=' + encodeURIComponent(saved));
  if (r.status === 304) { failures = 0; els.offline.hidden = true; return; }
  if (!r.data || !r.ok) { if (++failures >= 2) els.offline.hidden = false; return; }
  failures = 0; els.offline.hidden = true;
  const s = r.data;
  prevPhase = phase; phase = s.phase;
  paintBrand(s);

  if (!s.me.registered) {
    stopCountdown();
    if (saved) { reclaimName(saved); return; }
    showJoin(); return;
  }
  setPlayer(s.me.name);
  els.me.textContent = '\u{1F464} ' + s.me.name;

  if (s.phase === 'waiting') { stopCountdown(); showWaiting(s.players || [], s.me.name); return; }
  if (s.phase === 'starting') { showCountdown(s.starts_in_ms); return; }

  // ---- active
  if (prevPhase === 'starting' || prevPhase === 'waiting') {
    els.countNum.textContent = 'GO!';
    celebrate(); toast('\u{1F680} <b>Go go go!</b> The challenges are open.', 'big', 3000);
  }
  stopCountdown();
  els.lobby.classList.remove('show');
  els.howto.hidden = !!localStorage.getItem('ctf-howto');
  renderChallenges(s.challenges);
  const mine = s.scoreboard.find(row => row.player === s.me.name);
  renderProgress(s.challenges, mine);
  renderBoard(s.scoreboard, s.me.name);
  renderFeed(s.feed || [], s.me.name);
  els.me.innerHTML = '\u{1F464} ' + esc(s.me.name) + (mine ? ` <span class="me-pts">\u00b7 ${mine.score} pts</span>` : '');
}

const poller = smartInterval(tick, () =>
  failures ? Math.min(15000, 2000 * 2 ** failures) : (phase === 'waiting' ? 2000 : phase === 'starting' ? 1000 : 6000));
