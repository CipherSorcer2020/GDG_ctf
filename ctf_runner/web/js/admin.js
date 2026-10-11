const tokenBox = $('#token');
tokenBox.value = sessionStorage.getItem('ctf-admin-token') || '';
tokenBox.addEventListener('input', () => sessionStorage.setItem('ctf-admin-token', tokenBox.value.trim()));
bindThemeToggle($('#theme'));

const say = (ok, text) => { const m = $('#msg'); m.className = 'msg ' + (ok ? 'ok' : 'bad'); m.textContent = text; };
let lastSig = '';

async function refresh() {
  const r = await api('/api/lobby/state');
  if (!r.data) return;
  const sig = JSON.stringify(r.data);
  if (sig === lastSig) return;
  lastSig = sig;
  const phase = r.data.phase || r.data.state;
  $('#state').textContent = phase;
  $('#state').className = 'status big ' + phase;
  $('#count').textContent = r.data.players.length;
  $('#players').innerHTML = r.data.players.map(p => `<span class="chip-player">${avatarHTML(p)}${esc(p)}</span>`).join('') || '<span class="empty">Nobody yet</span>';
  $('#start').disabled = r.data.state === 'active';
}

async function action(path, extra, okText, confirmText) {
  const token = tokenBox.value.trim();
  if (!token) return say(false, 'Paste the admin token from the server console first.');
  if (confirmText && !confirm(confirmText)) return;
  const r = await api(path, {admin_token: token, ...extra});
  if (r.data && r.data.success) say(true, okText); else say(false, (r.data && r.data.message) || 'Could not reach the server.');
  lastSig = ''; refresh();
}

$('#start').addEventListener('click', () => action('/api/lobby/start', {countdown: Number($('#cd').value)}, 'Game started - challenges unlock for everyone.'));
$('#reset').addEventListener('click', () => action('/api/lobby/reset', {}, 'Lobby reset - everybody is back in the waiting room.',
  'Reset the lobby? All players are removed and the game goes back to waiting.'));
$('#wipe').addEventListener('click', () => action('/api/event/reset', {}, 'Scores cleared.', 'Clear ALL scores? Players and challenges stay.'));

api('/api/state').then(r => { if (r.data && r.data.brand.club) $('#club').textContent = r.data.brand.club; });
smartInterval(refresh, () => 1500);
