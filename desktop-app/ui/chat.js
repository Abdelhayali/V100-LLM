// LocalAI Bridge Desktop: the chat (streaming replies, tools, approvals, choices, steps, attachments).
'use strict';

const argText = (a, k) => (a && a[k] != null) ? String(a[k]) : '';
function toolSummary(name, a) {
  return ({
    run_code: `Run ${argText(a, 'language')} code`, list_dir: `List ${argText(a, 'path')}`, read_file: `Read ${argText(a, 'path')}`,
    write_file: `Write ${argText(a, 'path')}`, search_files: `Search ${argText(a, 'pattern')} in ${argText(a, 'root')}`,
    save_memory: `Remember: ${argText(a, 'content')}`, search_memory: `Recall: ${argText(a, 'query')}`,
    forget_memory: `Forget memory #${argText(a, 'id')}`, search_chats: `Search earlier chats: ${argText(a, 'query')}`,
    take_screenshot: 'Screenshot of the PC', web_search: `Web search: ${argText(a, 'query')}`, fetch_url: `Read ${argText(a, 'url')}`,
    send_file_to_user: `Send ${shortModel(argText(a, 'path'))}`, ask_user: `Ask you: ${argText(a, 'question')}`,
    update_tasks: 'Update the plan', tasks_list: 'Look at your tasks', tasks_add: `Add task: ${argText(a, 'title')}`,
    tasks_update: `Update task #${argText(a, 'id')}`, notes_add: `Save note: ${argText(a, 'title')}`,
    notes_search: `Search notes: ${argText(a, 'query')}`, calendar_list: `Check calendar ${argText(a, 'start')}`,
    calendar_add: `Add event: ${argText(a, 'title')} ${argText(a, 'start')}`, gmail_list: `Check email: ${argText(a, 'query') || 'inbox'}`,
    gmail_read: 'Read an email', gmail_draft: 'Write a draft email', gmail_update_draft: 'Edit a draft email',
    gmail_send: `Send email to ${argText(a, 'to') || 'the sender'}`, gmail_send_draft: 'Send the draft',
    google_calendar_add: `Add to Google Calendar: ${argText(a, 'title')}`,
  })[name] || name;
}
function toolDetail(name, a) {
  if (name === 'run_code') return argText(a, 'code').split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('#')).slice(0, 2).join('  ⏎  ');
  if (name === 'write_file') return `${argText(a, 'content').split('\n').length} lines`;
  if (name === 'ask_user') return (a.options || []).join(' · ');
  return '';
}

// ---------------------------------------------------------------- history -> items
let keyN = 0;
const nk = () => 'k' + (++keyN);
function toItems(msgs, summaryUpto) {
  const out = [], idx = {};
  const marker = summaryUpto != null ? [...msgs].reverse().find(m => m.id <= summaryUpto)?.id : null;
  for (const m of msgs) {
    if (marker != null && m.id > marker && !out.some(i => i.key === 'summary'))
      out.push({ t: 'notice', key: 'summary', text: 'Messages above were compressed into a summary: the AI remembers them in short form.' });
    if (m.role === 'user') out.push({ t: 'user', key: nk(), text: m.content || '', attachments: m.attachments || [], mid: m.id });
    else if (m.role === 'assistant') {
      if ((m.content || '').trim() || (m.reasoning || '').trim()) out.push({ t: 'assistant', key: nk(), text: m.content || '', reasoning: m.reasoning || '' });
      for (const tc of m.tool_calls || []) {
        let args = {}; try { args = JSON.parse(tc.function.arguments || '{}'); } catch {}
        idx[tc.id] = out.length;
        out.push({ t: 'tool', key: tc.id, name: tc.function.name, args, output: null, status: 'running', attachments: [] });
      }
    } else if (m.role === 'tool') {
      const i = idx[m.tool_call_id];
      if (i != null) Object.assign(out[i], { output: m.content, status: 'done', attachments: m.attachments || [] });
    }
  }
  return out;
}

// ---------------------------------------------------------------- sessions
async function loadSessions() {
  try { S.sessions = await api('/api/sessions'); } catch (e) { return fail(e); }
  renderSessions();
}
function newChat() {
  if (S.abort) S.abort.abort();
  Object.assign(S, { sid: null, title: 'New chat', items: [], approvals: [], questions: [], plan: [], stats: null, streaming: false, editId: null, pending: [] });
  S.model = S.info?.default_model || '';
  S.view = 'chat'; render();
}
async function openSession(sid) {
  if (S.abort) S.abort.abort();
  S.view = 'chat'; S.sid = sid; S.streaming = false; S.items = []; render();
  try {
    const s = await api(`/api/sessions/${sid}`);
    if (S.sid !== sid) return;
    Object.assign(S, { title: s.title, model: s.model || S.info?.default_model || '', stats: s.stats,
      items: toItems(s.messages || [], s.summary_upto), approvals: s.pending_approvals || [], questions: s.pending_questions || [], plan: s.plan || [] });
    render(); scrollDown(true);
    if (s.running) resume(sid);
  } catch (e) { fail(e); }
}
async function resume(sid) {
  startStream();
  try { await sse(`/api/sessions/${sid}/stream`, { signal: S.abort.signal }, onEvent); } catch (e) { if (e.name !== 'AbortError') fail(e); }
  endStream();
}

// ---------------------------------------------------------------- sending
async function send(text = null, { email = false, organizer = false } = {}) {
  const box = $('#composer');
  text = (text ?? box?.value ?? '').trim();
  if ((!text && !S.pending.length) || S.streaming) return;
  const atts = S.pending.slice(); S.pending = []; if (box) box.value = '';
  try {
    if (!S.sid) {
      const s = await api('/api/sessions', { method: 'POST', body: { model: S.model || '' } });
      S.sid = s.id; S.title = s.title;
    }
    if (S.editId) {
      await api(`/api/sessions/${S.sid}/truncate`, { method: 'POST', body: { message_id: S.editId } });
      const i = S.items.findIndex(x => x.t === 'user' && x.mid === S.editId);
      if (i >= 0) S.items.splice(i);
      S.editId = null;
    }
  } catch (e) { S.pending = atts; return fail(e); }
  S.plan = [];
  S.items.push({ t: 'user', key: nk(), text, attachments: atts, mid: null });
  render(); scrollDown(true);
  const body = { content: text, attachments: atts.map(a => a.id), model: S.model || null, web: S.prefs.web, auto_approve: S.prefs.autoApprove,
                 compress_at: S.prefs.autoCompress ? S.prefs.compressAt / 100 : 0,
                 email: S.prefs.email || email, organizer: S.prefs.organizer || organizer, thinking: S.prefs.thinking || 'auto', ocr: S.prefs.ocr || 'off' };
  const sid = S.sid;
  startStream();
  try { await sse(`/api/sessions/${sid}/chat`, { method: 'POST', body, signal: S.abort.signal }, onEvent); }
  catch (e) {
    if (e.code === 409) { toast('Your PC is still working on the previous reply: showing it'); endStream(); return resume(sid); }
    if (e.name !== 'AbortError') { S.items.push({ t: 'notice', key: nk(), text: e.message, error: true }); }
  }
  endStream();
  syncIds(sid);
  loadSessions();
}
/** After a reply, fetch message ids (needed to edit / regenerate). */
async function syncIds(sid) {
  try {
    const s = await api(`/api/sessions/${sid}`);
    if (S.sid !== sid || S.streaming) return;
    const users = (s.messages || []).filter(m => m.role === 'user');
    let j = 0;
    for (const it of S.items) if (it.t === 'user') { if (users[j]) it.mid = users[j].id; j++; }
    S.stats = s.stats || S.stats; S.title = s.title; render();
  } catch {}
}
function startStream() {
  S.streaming = true; S.abort = new AbortController(); S.phase = 'sending'; S.liveTokens = 0; S.liveTps = null; S.streamStart = Date.now();
  renderChatParts();
}
function endStream() { S.streaming = false; S.abort = null; S.phase = ''; renderChatParts(); }
async function stopReply() {
  if (S.sid) { try { await api(`/api/sessions/${S.sid}/stop`, { method: 'POST', body: {} }); } catch {} }
  S.approvals = []; S.questions = [];
  renderChatParts();
}

function lastAssistant() { const l = S.items.at(-1); if (l && l.t === 'assistant') return l; const n = { t: 'assistant', key: nk(), text: '', reasoning: '' }; S.items.push(n); return n; }
function tool(id) { return S.items.find(i => i.t === 'tool' && i.key === id); }
function onEvent(ev) {
  switch (ev.type) {
    case 'phase': S.phase = ev.phase; S.phaseTool = ev.name || ''; if (ev.phase === 'prompt') { S.liveTokens = 0; S.liveTps = null; } break;
    case 'progress': S.phase = ev.phase || S.phase; S.liveTokens = ev.tokens || S.liveTokens; S.liveTps = ev.tps ?? S.liveTps; break;
    case 'stats': S.stats = ev; break;
    case 'delta': case 'reasoning': {
      if (S.phase === 'prompt' || S.phase === 'sending') S.phase = ev.type === 'reasoning' ? 'thinking' : 'writing';
      const a = lastAssistant(); if (ev.type === 'reasoning') a.reasoning += ev.text; else a.text += ev.text;
      updateLastBubble(a); renderStatus(); return;
    }
    case 'tool_call': S.items.push({ t: 'tool', key: ev.id, name: ev.name, args: ev.args || {}, output: null, status: 'running', attachments: [] }); break;
    case 'approval_required': { const t = tool(ev.id); if (t) t.status = 'awaiting'; if (!S.approvals.some(a => a.id === ev.id)) S.approvals.push({ id: ev.id, name: ev.name, args: ev.args || {} }); break; }
    case 'question_required': { const t = tool(ev.id); if (t) t.status = 'awaiting'; if (!S.questions.some(q => q.id === ev.id)) S.questions.push(ev); break; }
    case 'question_answered': S.questions = S.questions.filter(q => q.id !== ev.id); break;
    case 'tasks': S.plan = ev.tasks || []; break;
    case 'tool_result': {
      S.approvals = S.approvals.filter(a => a.id !== ev.id); S.questions = S.questions.filter(q => q.id !== ev.id);
      const t = tool(ev.id); if (t) Object.assign(t, { output: ev.output, status: 'done', attachments: ev.attachments || [] }); break;
    }
    case 'title': S.title = ev.title; break;
    case 'done': {
      if (S.prefs.autoRead) { const a = [...S.items].reverse().find(i => i.t === 'assistant' && i.text.trim()); if (a) Speech.speak(splitThink(a.text)[1], a.key); }
      break;
    }
    case 'compressed': S.items.push({ t: 'notice', key: nk(), text: `Compressed ${ev.messages} earlier messages into a summary: context freed.` }); break;
    case 'notice': S.items.push({ t: 'notice', key: nk(), text: ev.text }); break;
    case 'error': S.items.push({ t: 'notice', key: nk(), text: ev.message, error: true }); break;
    case 'ping': return;
  }
  renderChatParts(); scrollDown();
}

async function respondApproval(a, ok) {
  S.approvals = S.approvals.filter(x => x.id !== a.id);
  const t = tool(a.id); if (t && ok) t.status = 'running';
  renderChatParts();
  try { await api(`/api/approvals/${a.id}`, { method: 'POST', body: { approve: ok } }); } catch (e) { fail(e); }
}
async function answerQuestion(q, answer) {
  if (!answer.trim()) return;
  S.questions = S.questions.filter(x => x.id !== q.id);
  const t = tool(q.id); if (t) t.status = 'running';
  renderChatParts();
  try { await api(`/api/questions/${q.id}`, { method: 'POST', body: { answer } }); } catch (e) { fail(e); }
}
async function regenerate() {
  const u = [...S.items].reverse().find(i => i.t === 'user');
  if (!u || !u.mid || S.streaming) return toast('Wait a moment: the message is still syncing');
  S.editId = u.mid; S.pending = u.attachments.slice(); send(u.text);
}
function editMessage(u) {
  if (S.streaming) return;
  if (!u.mid) return toast('Wait a moment: the message is still syncing');
  S.editId = u.mid; S.pending = u.attachments.slice();
  renderChatParts(); const box = $('#composer'); box.value = u.text; box.focus();
}
async function compressNow() {
  if (!S.sid || S.streaming) return toast('Nothing to compress yet');
  startStream(); S.phase = 'compressing';
  try { await sse(`/api/sessions/${S.sid}/compress`, { method: 'POST', body: {}, signal: S.abort.signal }, onEvent); } catch (e) { if (e.name !== 'AbortError') fail(e); }
  endStream(); openSession(S.sid);
}

// ---------------------------------------------------------------- attachments
async function uploadFiles(files) {
  for (const f of files) {
    const fd = new FormData(); fd.append('file', f, f.name || 'pasted.png');
    try { S.pending.push(await api('/api/uploads', { method: 'POST', form: fd })); } catch (e) { fail(e); }
    renderComposerChips();
  }
}
async function attachScreenshot() {
  try { S.pending.push(await api('/api/screenshot', { method: 'POST', body: {} })); renderComposerChips(); } catch (e) { fail(e); }
}
const attUrl = a => `/api/uploads/${a.id}`;

// ---------------------------------------------------------------- quick replies + email helpers
function suggestedReplies(text) {
  const lines = String(text).trimEnd().split('\n').slice(-14);
  const ask = /\?|\b(choose|select|pick|which|prefer|option|would you like|let me know)\b/i;
  if (!lines.length || !ask.test(lines.join('\n'))) return [];
  const opt = /^\s*(?:\(?(\d{1,2}|[A-Fa-f])[.):]|[-*•])\s+(.{1,160})$/;
  const opts = []; let started = false;
  for (const l of [...lines].reverse()) {
    const m = l.match(opt);
    if (m) { opts.push(m[2]); started = true; }
    else if (started && l.trim()) break;
    else if (!started && l.trim() && !opts.length && !ask.test(l)) return [];
  }
  const clean = [...new Set(opts.reverse().map(s => s.replace(/\*\*|__|`/g, '').split(' - ')[0].split(': ')[0].trim().replace(/[.,;]$/, '')).filter(s => s && s.length <= 80))];
  return clean.length >= 2 && clean.length <= 6 ? clean : [];
}
function emailIdOfChat() {
  for (const u of S.items) if (u.t === 'user') { const m = u.text.match(/email with id=([0-9a-fA-F]{8,})/); if (m) return m[1]; }
  return '';
}
function saveDraftDialog(text) {
  const eid = emailIdOfChat();
  let to = '', subject = ''; const keep = [];
  for (const l of Speech.clean(text).split('\n')) {
    const m = l.match(/^\s*(to|subject)\s*:\s*(.*)$/i);
    if (m && m[1].toLowerCase() === 'to' && !to) to = m[2].trim();
    else if (m && m[1].toLowerCase() === 'subject' && !subject) subject = m[2].trim();
    else keep.push(l);
  }
  while (keep.length && !keep[0].trim()) keep.shift();
  if (keep.length > 2 && keep[0].trim().endsWith(':') && keep[0].length < 120) keep.shift();
  while (keep.length && (!keep.at(-1).trim() || (/\?$/.test(keep.at(-1).trim()) && /send|change|edit|like me/i.test(keep.at(-1))))) keep.pop();
  const iTo = h('input', { value: to, placeholder: eid ? 'To (optional: replies to the sender)' : 'To' });
  const iSub = h('input', { value: subject, placeholder: 'Subject' });
  const iBody = h('textarea', { rows: 12 }); iBody.value = keep.join('\n').trim();
  const save = h('button', { class: 'primary', onclick: async () => {
    if (!iBody.value.trim() || (!eid && !iTo.value.trim())) return toast('Add a recipient and the text');
    save.disabled = true;
    try { await api('/api/google/draft', { method: 'POST', body: { body: iBody.value, to: iTo.value, subject: iSub.value, reply_to_id: eid } }); closeModal(); toast('Saved in Gmail Drafts'); }
    catch (e) { save.disabled = false; fail(e); }
  } }, 'Save draft');
  modal(h('div', {}, h('h3', {}, 'Save as Gmail draft'),
    eid ? h('p', { class: 'muted' }, 'Saved as a reply in the same email thread.') : null,
    iTo, iSub, iBody, h('p', { class: 'muted' }, 'Only saved in Gmail Drafts, not sent.'),
    h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Cancel'), save)), { wide: true });
}

// ---------------------------------------------------------------- rendering
function scrollDown(force) {
  const el = $('#msgs'); if (!el) return;
  if (force || el.scrollHeight - el.scrollTop - el.clientHeight < 220) el.scrollTop = el.scrollHeight;
}
function attachmentView(a) {
  if (a.kind === 'image') return h('img', { class: 'att-img', src: attUrl(a), alt: a.filename, onclick: () => modal(h('img', { src: attUrl(a), class: 'full' }), { wide: true }) });
  return h('a', { class: 'att-file', href: attUrl(a), download: a.filename }, '📎 ' + a.filename);
}
function bubble(it, isLast) {
  if (it.t === 'user') {
    return h('div', { class: 'msg user', 'data-key': it.key },
      h('div', { class: 'bubble' }, ...(it.attachments || []).map(attachmentView), h('div', { class: 'text', dir: 'auto' }, it.text)),
      h('div', { class: 'acts' }, h('button', { class: 'mini', title: 'Copy', onclick: () => { navigator.clipboard.writeText(it.text); toast('Copied'); } }, '⧉'),
        h('button', { class: 'mini', title: 'Edit and resend', onclick: () => editMessage(it) }, '✎')));
  }
  if (it.t === 'notice') return h('div', { class: 'notice' + (it.error ? ' err' : '') }, it.text);
  if (it.t === 'tool') {
    const st = it.status === 'running' ? h('span', { class: 'spin' }) : it.status === 'awaiting'
      ? h('span', { class: 'tag warn' }, it.name === 'ask_user' ? 'waiting for your choice' : 'needs approval') : h('span', { class: 'tag ok' }, '✓');
    return h('details', { class: 'tool', 'data-key': it.key },
      h('summary', {}, h('span', { class: 'ticon' }, '🔧'), h('span', { class: 'tname' }, toolSummary(it.name, it.args)), st),
      h('pre', { class: 'targs' }, JSON.stringify(it.args, null, 1)),
      it.output != null ? h('pre', { class: 'tout' }, String(it.output).slice(0, 6000)) : null,
      ...(it.attachments || []).map(attachmentView));
  }
  // assistant
  const [thinkInline, visible] = splitThink(it.text);
  const reasoning = (it.reasoning + thinkInline).trim();
  const streamingThis = S.streaming && isLast;
  const acts = !streamingThis && visible.trim() ? h('div', { class: 'acts' },
    h('button', { class: 'mini', title: 'Copy', onclick: () => { navigator.clipboard.writeText(visible.trim()); toast('Copied'); } }, '⧉'),
    h('button', { class: 'mini speak' + (Speech.key === it.key ? ' on' : ''), title: 'Read aloud', onclick: () => Speech.key === it.key ? Speech.stop() : Speech.speak(visible, it.key) }, Speech.key === it.key ? '■' : '🔊'),
    (emailIdOfChat() || /(^|\n)\s*\**subject\**\s*:/i.test(visible)) ? h('button', { class: 'mini', title: 'Save as Gmail draft', onclick: () => saveDraftDialog(visible) }, '✉ Draft') : null,
    isLast && !S.streaming ? h('button', { class: 'mini', title: 'Regenerate', onclick: regenerate }, '↻') : null) : null;
  const chips = isLast && !S.streaming && !S.questions.length ? suggestedReplies(visible) : [];
  return h('div', { class: 'msg bot', 'data-key': it.key },
    reasoning ? h('details', { class: 'think' }, h('summary', {}, 'Thinking'), h('div', { class: 'pre' }, reasoning)) : null,
    h('div', { class: 'md', dir: 'auto', html: md(visible) }),
    acts,
    chips.length ? h('div', { class: 'chips' }, ...chips.map(c => h('button', { class: 'chip', onclick: () => send(c) }, c))) : null);
}
function updateLastBubble(a) {
  const el = $(`#msgs [data-key="${a.key}"]`);
  if (!el) return renderMessages();
  const [thinkInline, visible] = splitThink(a.text);
  const reasoning = (a.reasoning + thinkInline).trim();
  const mdEl = $('.md', el); if (mdEl) mdEl.innerHTML = md(visible);
  let th = $('.think', el);
  if (reasoning && !th) { th = h('details', { class: 'think' }, h('summary', {}, 'Thinking'), h('div', { class: 'pre' })); el.prepend(th); }
  if (th) $('.pre', th).textContent = reasoning;
  scrollDown();
}
function renderMessages() {
  const el = $('#msgs'); if (!el) return;
  const lastA = [...S.items].reverse().find(i => i.t === 'assistant');
  const lastIsUser = S.items.at(-1)?.t === 'user';
  el.replaceChildren(...(S.items.length ? S.items.map(it => bubble(it, it === lastA && !lastIsUser)) : [emptyChat()]),
    ...(S.streaming && S.items.at(-1)?.t !== 'assistant' ? [h('div', { class: 'msg bot' }, h('span', { class: 'spin' }))] : []));
}
function emptyChat() {
  return h('div', { class: 'empty' }, h('img', { src: 'icon.svg' }), h('h2', {}, 'Your PC assistant'),
    h('p', {}, 'Chat with the model running on your PC. It can run code, read your files, look at images and PDFs, search the web, ' +
      'and (when you switch them on) use your email, tasks and calendar. It remembers what matters about you.'),
    h('div', { class: 'chips center' }, ...['What tasks do I have?', 'Summarize my unread email', 'Take a screenshot of my PC and describe it', 'ما هي أخبار اليوم؟']
      .map(t => h('button', { class: 'chip', onclick: () => send(t, { email: /email/i.test(t), organizer: /task/i.test(t) }) }, t))));
}
function renderStatus() {
  const el = $('#live'); if (!el) return;
  if (!S.streaming) { el.replaceChildren(); el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  const sp = S.liveTps ? ` · ${S.liveTps.toFixed(1)} t/s` : '';
  const running = [...S.items].reverse().find(i => i.t === 'tool' && i.status === 'running');
  const label = ({ sending: 'Sending to your PC…', prompt: 'Reading the conversation…', thinking: `Thinking… ${S.liveTokens} tokens${sp}`,
    writing: `Writing… ${S.liveTokens} tokens${sp}`, tool_args: `Preparing a tool call… ${S.liveTokens} tokens${sp}`,
    tool: 'Now: ' + (running ? toolSummary(running.name, running.args) : S.phaseTool.replace(/_/g, ' ')),
    approval: 'Waiting for your approval', question: 'Waiting for your choice', compressing: 'Compressing the conversation…' })[S.phase] || 'Working…';
  el.replaceChildren(h('div', { class: 'progress' }), h('span', {}, label), h('span', { class: 'muted' }, mmss((Date.now() - S.streamStart) / 1000)));
}
setInterval(() => { if (S.streaming) renderStatus(); }, 1000);

function activitySteps() {
  const lastUser = S.items.map(i => i.t).lastIndexOf('user');
  if (S.plan.length) return { plan: true, steps: S.plan.map(p => ({ title: p.title, detail: '', state: p.status === 'done' ? 'done' : p.status === 'in_progress' ? (S.streaming ? 'now' : 'done') : 'pending' })) };
  const tools = S.items.slice(lastUser + 1).filter(i => i.t === 'tool' && i.name !== 'update_tasks');
  return { plan: false, steps: tools.map(t => {
    const out = String(t.output || '');
    const failed = t.status === 'done' && /^(The user denied|The user did not answer|Error|Access denied)/.test(out);
    return { title: toolSummary(t.name, t.args), detail: toolDetail(t.name, t.args), state: t.status === 'running' ? 'now' : t.status === 'awaiting' ? 'waiting' : failed ? 'failed' : 'done' };
  }) };
}
function renderSidePanel() {
  const el = $('#chatside'); if (!el) return;
  const { plan, steps } = activitySteps();
  const icon = s => ({ now: h('span', { class: 'spin' }), waiting: '⧗', done: h('span', { class: 'ok' }, '✓'), failed: h('span', { class: 'err' }, '✗') })[s] || '○';
  const st = S.stats;
  const ctx = st && st.ctx_used ? h('div', { class: 'ctxline' },
    h('div', {}, `Context ${kfmt(st.ctx_used)}${st.ctx_size ? ' / ' + kfmt(st.ctx_size) : ''}`, st.tps ? ` · ${st.tps.toFixed(1)} t/s` : ''),
    st.ctx_size ? bar(st.ctx_used / st.ctx_size) : null) : null;
  el.replaceChildren(
    h('h4', {}, plan ? `Plan · ${steps.filter(s => s.state === 'done').length}/${steps.length} done` : 'What your PC is doing'),
    steps.length ? h('ol', { class: 'steps' }, ...steps.map(s => h('li', { class: s.state },
      h('span', { class: 'si' }, icon(s.state)), h('div', {}, h('div', {}, s.title + (s.state === 'now' ? '  (now)' : s.state === 'waiting' ? '  (waiting for you)' : '')),
        s.detail ? h('code', { class: 'muted' }, s.detail) : null))))
      : h('p', { class: 'muted' }, 'Every action the model takes on your PC (code, files, search, email, questions) shows here with a live status.'),
    ctx);
}
function renderQuestion() {
  const el = $('#question'); if (!el) return;
  const q = S.questions[0];
  if (!q) { el.replaceChildren(); el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  const picked = new Set();
  const other = h('input', { placeholder: 'Or type your own answer…', onkeydown: e => { if (e.key === 'Enter') answerQuestion(q, other.value); } });
  el.replaceChildren(h('div', { class: 'qhead' }, '❓ ' + q.question),
    h('div', { class: 'muted small' }, q.multiple ? 'Pick one or more, then Send. The reply continues on your PC.' : 'Choose: the reply continues on your PC.'),
    h('div', { class: 'qopts' }, ...(q.options || []).map((o, i) => q.multiple
      ? h('label', { class: 'qcheck' }, h('input', { type: 'checkbox', onchange: e => e.target.checked ? picked.add(o) : picked.delete(o) }), ' ' + o)
      : h('button', { class: 'qopt', onclick: () => answerQuestion(q, o) }, `${i + 1}. ${o}`))),
    q.multiple ? h('button', { class: 'primary', onclick: () => answerQuestion(q, [...picked].join('; ')) }, 'Send choices') : null,
    q.allow_other !== false ? h('div', { class: 'row' }, other, h('button', { onclick: () => answerQuestion(q, other.value) }, 'Send')) : null);
}
function renderApproval() {
  const a = S.approvals[0];
  if (!a) return;
  if ($('#modal').dataset.approval === a.id) return;
  $('#modal').dataset.approval = a.id;
  const title = ({ run_code: 'Run code on your PC?', gmail_send: 'Send this email?', gmail_send_draft: 'Send this email?', google_calendar_add: 'Add to Google Calendar?' })[a.name] || 'Write file on your PC?';
  const g = k => argText(a.args, k);
  const body = a.name === 'gmail_send' ? `To: ${g('to') || '(reply to the original sender)'}\nSubject: ${g('subject') || '(Re: original subject)'}\n\n${g('body')}`
    : a.name === 'gmail_send_draft' ? `Draft id: ${g('draft_id')}` : a.name === 'google_calendar_add' ? `${g('title')}\n${g('start')}${g('end') ? ' → ' + g('end') : ''}${g('location') ? '\n@ ' + g('location') : ''}`
    : (g('code') || g('content'));
  const done = ok => { $('#modal').dataset.approval = ''; closeModal(); respondApproval(a, ok); setTimeout(renderApproval, 50); };
  modal(h('div', {}, h('h3', {}, title), h('div', { class: 'muted' }, toolSummary(a.name, a.args)), h('pre', { class: 'code-pre' }, body),
    h('div', { class: 'row end' }, h('button', { class: 'danger', onclick: () => done(false) }, 'Deny'), h('button', { class: 'primary', onclick: () => done(true) }, 'Approve'))), { wide: true });
}
function renderComposerChips() {
  const el = $('#attchips'); if (!el) return;
  el.replaceChildren(...S.pending.map(a => h('span', { class: 'attchip' }, (a.kind === 'image' ? '🖼 ' : '📎 ') + a.filename,
    h('button', { class: 'x', onclick: () => { S.pending = S.pending.filter(x => x !== a); renderComposerChips(); } }, '×'))),
    S.editId ? h('span', { class: 'attchip edit' }, '✎ Editing a message: the chat continues from there',
      h('button', { class: 'x', onclick: () => { S.editId = null; renderComposerChips(); } }, '×')) : null);
  const send = $('#sendbtn'); if (send) send.replaceChildren(S.streaming ? '■ Stop' : 'Send ➤');
}
function renderChatParts() { renderMessages(); renderStatus(); renderSidePanel(); renderQuestion(); renderComposerChips(); renderApproval(); renderHeader(); }

// Thinking effort: how long the model may think before it acts (Off = fastest, Max = no limit)
const THINKING = [['auto', '🧠 Auto', 'Model default'], ['off', '🧠 Off', 'No thinking: fastest replies'],
  ['low', '🧠 Low', 'Thinks up to ~1k tokens'], ['medium', '🧠 Medium', 'Thinks up to ~4k tokens'],
  ['high', '🧠 High', 'Thinks up to ~16k tokens'], ['max', '🧠 Max', 'Thinks as long as it needs (slow)']];
function thinkingSelect(p) {
  const cur = THINKING.find(x => x[0] === (p.thinking || 'auto')) || THINKING[0];
  return h('select', { class: 'toggle think' + (cur[0] !== 'off' && cur[0] !== 'auto' ? ' on' : ''), title: 'Thinking: ' + cur[2],
    onchange: e => { p.thinking = e.target.value; savePrefs(); const x = THINKING.find(y => y[0] === p.thinking);
      toast('Thinking: ' + x[1].replace('🧠 ', '') + ' (' + x[2] + ')'); renderHeader(); } },
    ...THINKING.map(([v, label, tip]) => h('option', { value: v, selected: v === cur[0], title: tip }, label)));
}
// OCR sub-model (Unlimited-OCR) for scanned PDFs and images: A = GPU (swaps with the chat model), B = CPU
const OCR = [['off', '📄 OCR off', 'No OCR tool'],
  ['gpu', '📄 OCR A: GPU', 'Fast: unloads the chat model, reads on the V100, loads it again (~1 min extra)'],
  ['cpu', '📄 OCR B: CPU', 'The chat model stays loaded; slower (~1-2 min per page)']];
function ocrSelect(p) {
  const cur = OCR.find(x => x[0] === (p.ocr || 'off')) || OCR[0];
  return h('select', { class: 'toggle think' + (cur[0] !== 'off' ? ' on' : ''), title: 'OCR: ' + cur[2],
    onchange: e => { p.ocr = e.target.value; savePrefs(); const x = OCR.find(y => y[0] === p.ocr);
      toast(x[1].replace('📄 ', '') + ' (' + x[2] + ')'); renderHeader(); } },
    ...OCR.map(([v, label, tip]) => h('option', { value: v, selected: v === cur[0], title: tip }, label)));
}
function toggleChip(label, key, on, onToggle) {
  return h('button', { class: 'toggle' + (on ? ' on' : ''), onclick: onToggle, title: label }, label);
}
function renderHeader() {
  const el = $('#chathead'); if (!el) return;
  const models = S.info?.models || [];
  const sel = h('select', { onchange: e => { S.model = e.target.value; if (S.sid) api(`/api/sessions/${S.sid}`, { method: 'PATCH', body: { model: S.model } }).catch(fail); } },
    h('option', { value: '' }, 'auto model'), ...models.map(m => h('option', { value: m, selected: m === S.model }, shortModel(m))));
  const p = S.prefs;
  const flip = async (k, msg) => { p[k] = !p[k]; savePrefs(); toast(msg(p[k])); renderHeader(); };
  el.replaceChildren(h('div', { class: 'ttl' }, h('div', { class: 'title', dir: 'auto' }, S.title), sel),
    h('div', { class: 'toggles' },
      thinkingSelect(p),
      ocrSelect(p),
      toggleChip('🌐 Web', 'web', p.web, () => flip('web', v => 'Web search ' + (v ? 'ON' : 'OFF'))),
      toggleChip('✉ Email', 'email', p.email, () => flip('email', v => v ? 'Email access ON: the AI can read mail and write drafts (sending asks you)' : 'Email access OFF')),
      toggleChip('📅 Tasks', 'organizer', p.organizer, () => flip('organizer', v => 'Tasks & calendar access ' + (v ? 'ON' : 'OFF'))),
      toggleChip('🔊 Read', 'autoRead', p.autoRead, () => { flip('autoRead', v => 'Read replies aloud ' + (v ? 'ON' : 'OFF')); if (p.autoRead) Speech.stop(); }),
      toggleChip('⚡ Auto-approve', 'autoApprove', p.autoApprove, async () => {
        if (!p.autoApprove && !await confirmBox('Turn on auto-approve?', 'The AI will run code and write files on your PC without asking. A malicious web page, PDF or file the AI reads could trick it into running harmful commands. Sending email and Google events still ask.', 'Turn on', true)) return;
        flip('autoApprove', v => 'Auto-approve ' + (v ? 'ON' : 'OFF'));
      }),
      h('button', { class: 'toggle', title: 'Summarize older messages to free context', onclick: compressNow }, '⇊ Compress')));
}

function renderChat(main) {
  main.replaceChildren(
    h('div', { class: 'chat' },
      h('header', { id: 'chathead', class: 'chathead' }),
      h('div', { class: 'chatbody' },
        h('div', { class: 'chatcol' },
          h('div', { id: 'msgs', class: 'msgs' }),
          h('div', { id: 'question', class: 'question hidden' }),
          h('div', { id: 'live', class: 'live hidden' }),
          h('div', { class: 'composer-wrap' },
            h('div', { id: 'attchips', class: 'attchips' }),
            h('div', { class: 'composer' },
              h('button', { class: 'icon', title: 'Attach files (or drop / paste them)', onclick: () => $('#filepick').click() }, '📎'),
              h('button', { class: 'icon', title: 'Screenshot of the PC', onclick: attachScreenshot }, '🖥'),
              h('input', { id: 'filepick', type: 'file', multiple: true, class: 'hidden', onchange: e => { uploadFiles([...e.target.files]); e.target.value = ''; } }),
              h('textarea', { id: 'composer', rows: 2, dir: 'auto', placeholder: 'Message…  (Enter to send · Shift+Enter for a new line · paste or drop images)',
                onkeydown: e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } },
                onpaste: e => { const f = [...e.clipboardData.files]; if (f.length) { e.preventDefault(); uploadFiles(f); } } }),
              h('button', { id: 'sendbtn', class: 'primary send', onclick: () => S.streaming ? stopReply() : send() }, 'Send ➤')))),
        h('aside', { id: 'chatside', class: 'chatside' }))));
  const col = $('.chatcol', main);
  col.addEventListener('dragover', e => { e.preventDefault(); col.classList.add('drop'); });
  col.addEventListener('dragleave', () => col.classList.remove('drop'));
  col.addEventListener('drop', e => { e.preventDefault(); col.classList.remove('drop'); uploadFiles([...e.dataTransfer.files]); });
  renderChatParts(); scrollDown(true);
  $('#composer').focus();
}
window.addEventListener('speech', () => { if (S.view === 'chat') renderMessages(); });
