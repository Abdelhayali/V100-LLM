// LocalAI Bridge Desktop: navigation, chat list, connecting to a server, start-up.
'use strict';

const NAV = [
  ['chat', '💬', 'Chat'], ['organizer', '📅', 'Notes, tasks & calendar'], ['models', '🧩', 'Models'], ['api', '🔑', 'API key'],
  ['memory', '🧠', 'Memory'], ['files', '📁', 'Files on PC'], ['terminal', '⌨', 'Terminal'], ['running', '⚙', 'Running tasks'], ['settings', '⚙️', 'Settings'],
];

function go(view) { S.view = view; render(); }
function render() {
  renderNav();
  const main = $('#main');
  main._refresh = null;
  ({ chat: renderChat, organizer: viewOrganizer, models: viewModels, api: viewApi, memory: viewMemory, files: viewFiles,
     terminal: viewTerminal, running: viewRunning, settings: viewSettings })[S.view](main);
}
function renderNav() {
  $('#nav').replaceChildren(...NAV.map(([k, ic, label]) => h('button', { class: 'navbtn' + (S.view === k ? ' on' : ''), onclick: () => go(k) },
    h('span', { class: 'ni' }, ic), h('span', {}, label))));
}
function renderSessions() {
  const q = ($('#sessq').value || '').toLowerCase();
  const list = S.sessions.filter(s => !q || (s.title || '').toLowerCase().includes(q));
  $('#sesscount').textContent = `Chats (${S.sessions.length})`;
  $('#sessions').replaceChildren(...list.map(s => h('div', { class: 'sess' + (s.id === S.sid ? ' on' : ''), onclick: () => openSession(s.id), title: s.title },
    h('span', { class: 'stitle', dir: 'auto' }, (s.running ? '● ' : '') + s.title),
    h('button', { class: 'mini', title: 'Rename', onclick: async e => { e.stopPropagation(); const t = await promptBox('Rename chat', s.title); if (t) { await api(`/api/sessions/${s.id}`, { method: 'PATCH', body: { title: t } }).catch(fail); if (s.id === S.sid) S.title = t; loadSessions(); render(); } } }, '✎'),
    h('button', { class: 'mini', title: 'Delete', onclick: async e => { e.stopPropagation(); if (await confirmBox('Delete this chat?', 'This removes the conversation from the PC.', 'Delete', true)) { await api(`/api/sessions/${s.id}`, { method: 'DELETE' }).catch(fail); if (s.id === S.sid) newChat(); loadSessions(); } } }, '🗑'))));
}
function applyTheme() {
  const t = S.prefs.theme;
  document.documentElement.dataset.theme = t === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : t;
}
async function refreshInfo() {
  try { S.info = await api('/api/info'); if (!S.model) S.model = S.info.default_model || ''; if (S.view === 'chat') renderHeader(); } catch {}
}

// ---------------------------------------------------------------- connecting to a server
async function pairScreen(again = false) {
  let local = {};
  try { local = await (await fetch('/local/settings')).json(); } catch {}
  const err = h('p', { class: 'err' });
  const url = h('input', { placeholder: 'Server URL, e.g. https://xxxx.trycloudflare.com' }), tok = h('input', { type: 'password', placeholder: 'Access token' });
  const code = h('textarea', { rows: 3, placeholder: 'Or paste the pairing code: the text {"url": …, "token": …} shown under the QR' });
  const pair = async body => {
    err.textContent = '';
    const r = await fetch('/local/pair', { method: 'POST', body: JSON.stringify(body) });
    const j = await r.json();
    if (!r.ok) { err.textContent = j.error || 'Could not connect'; return; }
    toast('Connected to ' + j.url); start();
  };
  $('#app').classList.add('pairing');
  $('#main').replaceChildren(h('div', { class: 'pair' }, h('img', { src: 'icon.svg', class: 'big' }), h('h1', {}, 'Connect to your PC'),
    h('p', { class: 'muted' }, 'LocalAI Bridge Desktop uses the same server as the phone app (LocalAI Bridge V100 on the PC with the GPU).'),
    local.local?.length ? card(h('h3', {}, 'This PC runs the server'), h('p', { class: 'small' }, local.local.map(s => s.url).join(', ')),
      h('button', { class: 'primary', onclick: () => pair({ local: true }) }, 'Connect to the server on this PC')) : null,
    card(h('h3', {}, 'From another computer'), h('p', { class: 'small' }, 'On the PC, open the server window (or http://127.0.0.1:8766/pair) and copy the URL and the access token, or the pairing code.'),
      url, tok, h('button', { class: 'primary', onclick: () => pair({ url: url.value, token: tok.value }) }, 'Connect'), code,
      h('button', { onclick: () => pair({ code: code.value }) }, 'Connect with the pairing code')),
    err, again && local.paired ? h('button', { class: 'link', onclick: start }, 'Cancel') : null));
}

// ---------------------------------------------------------------- start-up
async function start() {
  let local;
  try { local = await (await fetch('/local/settings')).json(); } catch { document.body.textContent = 'LocalAI Bridge Desktop is not running.'; return; }
  Object.assign(S.prefs, local.prefs || {});
  applyTheme();
  if (!local.paired) return pairScreen();
  $('#app').classList.remove('pairing');
  try { await api('/api/health'); } catch {}
  await refreshInfo();
  loadSessions();
  render();
  pollPc(); clearInterval(start.pc); start.pc = setInterval(pollPc, 3000);
  clearInterval(start.ss); start.ss = setInterval(() => { if (!S.streaming) loadSessions(); }, 20000);
}
$('#newchat').onclick = () => newChat();
$('#pcbar').onclick = () => go('models');
$('#sessq').oninput = renderSessions;
$('#theme').onclick = () => { S.prefs.theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; savePrefs(); applyTheme(); };
$('#modal').addEventListener('mousedown', e => { if (e.target.id === 'modal' && !S.approvals.length) closeModal(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !S.approvals.length) closeModal();
  if (e.ctrlKey && e.key.toLowerCase() === 'n') { e.preventDefault(); newChat(); }
});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
start();
