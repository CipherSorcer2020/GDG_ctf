/* Tutorial game front end.
 * The page never contains answers, hints or lessons: hints are fetched when
 * clicked and lessons arrive with a correct answer (see ctf_runner/game.py).
 */
const player = getPlayer();
const KEY = 'acme-game:' + (player || 'guest');
const BOTS = {5: ['\u{1F916}', 'HelperBot'], 6: ['\u{1F9F9}', 'FilterBot'], 7: ['\u{1F6E0}\uFE0F', 'DevBot']};
let LV = [];
let spoilerCost = 50;
let openId = 1;
const chatLog = {};      // level id -> [{who, text}]

let state = {solved: {}, answers: {}, hints: {}, learned: {}};
try { state = Object.assign(state, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) { /* fresh start */ }
const save = () => localStorage.setItem(KEY, JSON.stringify(state));

const $levels = $('#levels');
$('#who').innerHTML = player ? '\u{1F464} ' + esc(player) : '<a href="/">join on the main page first</a>';
bindThemeToggle($('#theme'));
api('/api/state').then(r => { if (r.data) paintBrand({...r.data, event: {name: 'Acme Corp: Your First Hack'}}); });

const solvedCount = () => [1, 2, 3, 4, 5, 6, 7].filter(n => state.solved[n]).length;
const isUnlocked = id => id === 1 || !!state.solved[id - 1] || !!state.solved[id];

function bubble(m) { return `<div class="bub ${m.who}">${esc(m.text)}</div>`; }

function levelHTML(lv) {
  const done = !!state.solved[lv.id];
  const unlocked = isUnlocked(lv.id);
  const hints = state.hints[lv.id] || [];
  const hintButtons = [0, 1, 2].map(i => {
    const spoiler = i === 2 && lv.spoiler;
    const label = `&#128161; hint ${i + 1}` + (spoiler ? ` (spoiler, &minus;${spoilerCost} pts)` : '');
    return `<button type="button" class="hint-btn ${spoiler ? 'spoiler' : ''}" data-n="${i + 1}" ${hints[i] ? 'disabled' : ''}>${label}</button>`;
  }).join('');
  const hintBoxes = hints.map((t, i) => t ? `<div class="hint"><b>Hint ${i + 1}:</b> ${esc(t)}</div>` : '').join('');

  let chat = '';
  if (BOTS[lv.id]) {
    const [face, name] = BOTS[lv.id];
    const msgs = chatLog[lv.id] && chatLog[lv.id].length ? chatLog[lv.id] : [{who: 'bot', text: `Hi, I'm ${name}! Say something to me.`}];
    chat = `
    <div class="chat" data-level="${lv.id}">
      <div class="chat-head"><span class="live"></span>${face} ${name}</div>
      <div class="chat-log" aria-live="polite">${msgs.map(bubble).join('')}</div>
      <form class="chat-form"><input type="text" maxlength="500" placeholder="type a message..." autocomplete="off" aria-label="Message to ${name}">
        <button type="submit" class="btn-go">Send</button></form>
    </div>`;
  }

  let action = '';
  if (lv.id < 8) {
    action = `
      <form class="ans" data-level="${lv.id}">
        <input type="text" maxlength="100" placeholder="enter the code" autocomplete="off" autocapitalize="off" spellcheck="false"
               value="${esc(state.answers[lv.id] || '')}" ${done ? 'disabled' : ''} aria-label="Code for level ${lv.id}">
        <button type="submit" class="${done ? '' : 'btn-go'}" ${done ? 'disabled' : ''}>${done ? '&#10003; Solved' : 'Check'}</button>
      </form><div class="msg" role="status"></div>`;
  } else {
    action = `
      <ul class="checklist">${[1, 2, 3, 4, 5, 6, 7].map(n =>
        `<li class="${state.solved[n] ? 'done' : ''}">${state.solved[n] ? '&#10003;' : '&#9675;'} level ${n}</li>`).join('')}</ul>
      <button id="assemble" class="btn-go" ${solvedCount() < 7 ? 'disabled' : ''}>&#127881; Assemble my flag</button>
      <div id="final"></div>`;
  }
  const next = (done && lv.id < 8) ? `<button type="button" class="next btn-go" data-next="${lv.id + 1}">Next level &rarr;</button>` : '';
  const learned = state.learned[lv.id] ? `<div class="learned"><b>&#127891; You just learned:</b> ${state.learned[lv.id]}</div>${next}` : '';

  return `
    <div class="lv-head">
      <div class="lv-num">${done ? '&#10003;' : lv.id}</div>
      <div class="lv-title">${esc(lv.title)}</div>
      <div class="lv-badge">${done ? 'solved' : unlocked ? 'open' : '&#128274; locked'}</div>
    </div>
    <div class="lv-body">
      <p class="story">${esc(lv.story)}</p>
      <div class="goal">&#127919; ${esc(lv.goal)}</div>
      <div class="hint-row">${hintButtons}</div>${hintBoxes}
      ${chat}${action}${learned}
    </div>`;
}

const sectionClass = lv => ['level', state.solved[lv.id] ? 'solved' : '', isUnlocked(lv.id) ? '' : 'locked', openId === lv.id ? 'open' : ''].join(' ');

function renderPath() {
  const current = (LV.find(l => !state.solved[l.id]) || {}).id;
  $('#path').innerHTML = LV.map((lv, i) =>
    `<li class="${state.solved[lv.id] ? 'done' : ''} ${lv.id === current ? 'now' : ''}" data-id="${lv.id}">
       <span class="dot" title="${esc(lv.title)}">${state.solved[lv.id] ? '\u2713' : lv.id}</span>${i < LV.length - 1 ? '<span class="line"></span>' : ''}</li>`).join('');
  $('#bar').style.width = (solvedCount() / 7 * 100) + '%';
}

function renderOne(id) {
  const lv = LV.find(l => l.id === id);
  const el = $levels.querySelector(`[data-id="${id}"]`);
  if (!lv || !el) return;
  el.className = sectionClass(lv);
  el.innerHTML = levelHTML(lv);
  renderPath();
  const log = el.querySelector('.chat-log');
  if (log) log.scrollTop = log.scrollHeight;
}
function renderAll() { $levels.innerHTML = LV.map(lv => `<section data-id="${lv.id}"></section>`).join(''); LV.forEach(lv => renderOne(lv.id)); }
function toggle(id) { const prev = openId; openId = prev === id ? 0 : id; if (prev) renderOne(prev); if (openId) renderOne(openId); }
function goTo(n) {
  const prev = openId; openId = n; if (prev) renderOne(prev); renderOne(n);
  $levels.querySelector(`[data-id="${n}"]`).scrollIntoView({behavior: REDUCED ? 'auto' : 'smooth', block: 'start'});
}

/* ---------------------------------------------------------------- events */

$('#path').addEventListener('click', ev => {
  const li = ev.target.closest('li[data-id]');
  if (li && isUnlocked(Number(li.dataset.id))) goTo(Number(li.dataset.id));
});

$levels.addEventListener('click', async ev => {
  const sec = ev.target.closest('section[data-id]');
  if (!sec) return;
  const id = Number(sec.dataset.id);

  if (ev.target.closest('.lv-head')) { if (isUnlocked(id)) toggle(id); return; }

  const next = ev.target.closest('[data-next]');
  if (next) { goTo(Number(next.dataset.next)); return; }

  const hb = ev.target.closest('.hint-btn');
  if (hb) {
    const n = Number(hb.dataset.n);
    const lv = LV.find(l => l.id === id);
    if (n === 3 && lv.spoiler && !confirm(`Hint 3 gives away most of the answer and costs ${spoilerCost} points. Show it anyway?`)) return;
    hb.disabled = true;
    const r = await api('/game/api/hint', {level: id, n, player});
    if (!r.data || !r.data.ok) { hb.disabled = false; alert((r.data && r.data.message) || 'Could not reach the server.'); return; }
    state.hints[id] = state.hints[id] || [];
    state.hints[id][n - 1] = r.data.hint;
    save(); renderOne(id);
    return;
  }

  if (ev.target.id === 'assemble') { assemble(); return; }
});

$levels.addEventListener('submit', async ev => {
  ev.preventDefault();
  const sec = ev.target.closest('section[data-id]');
  const id = Number(sec.dataset.id);

  if (ev.target.matches('form.ans')) {
    const input = ev.target.querySelector('input');
    const msg = sec.querySelector('.msg');
    const r = await api('/game/api/check', {level: id, answer: input.value});
    if (r.data && r.data.ok) {
      state.solved[id] = true; state.answers[id] = input.value.trim(); state.learned[id] = r.data.learned || '';
      save(); renderOne(id);
      if (id < 8) renderOne(id + 1);
      confetti({x: .5, y: .45, count: 90});
      toast(`\u2705 Level ${id} solved!`, 'big', 2400);
    } else {
      msg.className = 'msg bad'; msg.textContent = (r.data && r.data.message) || 'Could not reach the server.';
    }
    return;
  }

  if (ev.target.matches('form.chat-form')) {
    const input = ev.target.querySelector('input');
    const text = input.value.trim();
    if (!text) return;
    const log = sec.querySelector('.chat-log');
    const mine = (chatLog[id] = chatLog[id] && chatLog[id].length ? chatLog[id] : [{who: 'bot', text: log.querySelector('.bub')?.textContent || ''}]);
    mine.push({who: 'you', text});
    log.insertAdjacentHTML('beforeend', bubble({who: 'you', text}));
    input.value = '';
    log.insertAdjacentHTML('beforeend', '<div class="bub bot typing" id="typing"><i></i><i></i><i></i></div>');
    log.scrollTop = log.scrollHeight;
    const [r] = await Promise.all([api('/game/api/chat', {level: id, message: text}), new Promise(res => setTimeout(res, REDUCED ? 0 : 650))]);
    const reply = (r.data && r.data.reply) || '...(no answer)';
    mine.push({who: 'bot', text: reply});
    $('#typing')?.remove();
    log.insertAdjacentHTML('beforeend', bubble({who: 'bot', text: reply}));
    log.scrollTop = log.scrollHeight;
  }
});

async function assemble() {
  const out = $('#final');
  out.innerHTML = '<p class="muted">assembling...</p>';
  const r = await api('/game/api/assemble', {answers: state.answers});
  if (!r.data || r.data.status !== 'ok') {
    out.innerHTML = `<div class="msg bad">${esc((r.data && r.data.message) || 'Could not reach the server.')}</div>`; return;
  }
  celebrate();
  out.innerHTML = `
    <div class="flagbox">${esc(r.data.flag)}</div>
    <button id="claim" class="btn-go" style="margin-top:.7rem" ${player ? '' : 'disabled'}>Claim my points</button>
    <div class="msg" id="claim-msg">${player ? '' : 'Join on the main page first so the scoreboard can credit you.'}</div>`;
  $('#claim').addEventListener('click', async () => {
    const c = await api('/api/submit', {player, challenge: 'webgame', flag: r.data.flag});
    const d = c.data || {status: 'error', message: 'Could not reach the server.'};
    const msg = $('#claim-msg');
    const good = d.status === 'correct' || d.status === 'already_solved';
    msg.className = 'msg ' + (good ? 'ok' : 'bad');
    msg.textContent = d.message + (d.status === 'correct' ? ` (total: ${d.new_total}) - see the scoreboard!` : '');
    if (d.status === 'correct') { celebrate(); toast(`\u{1F389} +${d.points_awarded} pts \u2014 tutorial complete!`, 'big', 4500); }
    if (good) { state.solved[8] = true; state.learned[8] = r.data.learned || ''; save(); }
  });
}

/* ------------------------------------------------------------------ boot */

(async () => {
  const r = await api('/game/api/levels');
  if (!r.data || !r.data.ok) { $levels.innerHTML = `<p class="msg bad">${esc((r.data && r.data.message) || 'Could not load the game.')}</p>`; return; }
  LV = r.data.levels; spoilerCost = r.data.spoiler_cost;
  const firstOpen = LV.find(l => !state.solved[l.id]);
  openId = firstOpen ? firstOpen.id : 8;
  renderAll();
})();
