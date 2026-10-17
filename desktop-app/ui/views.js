// LocalAI Bridge Desktop: every screen besides the chat.
'use strict';

function page(title, ...kids) { return h('div', { class: 'page' }, h('header', { class: 'pagehead' }, h('h2', {}, title)), h('div', { class: 'pagebody' }, ...kids)); }
function askAi(text, opts = {}) { newChat(); send(text, opts); }
const card = (...k) => h('div', { class: 'card' }, ...k);

// ---------------------------------------------------------------- Models (V100-LLM launcher)
async function viewModels(main) {
  const list = h('div', { class: 'grid' }, h('span', { class: 'spin' }));
  main.replaceChildren(page('Models', h('p', { class: 'muted' }, 'Load, switch or unload the model running on your PC (V100-LLM launcher). The chat and the OpenAI API use whatever is loaded.'), list));
  let models;
  try { models = await api('/api/v100/models'); } catch (e) { list.replaceChildren(h('p', { class: 'err' }, e.message)); return; }
  const chosen = {};
  const draw = () => {
    const s = S.pc || {};
    list.replaceChildren(...models.sort((a, b) => b.installed - a.installed).map(m => {
      const isThis = s.model === m.id && s.health !== 'stopped', other = s.health && s.health !== 'stopped' && s.health !== 'offline' && !isThis;
      const sel = h('select', { onchange: e => { chosen[m.id] = e.target.value; draw(); } },
        ...m.presets.map(p => h('option', { value: p.id, selected: (chosen[m.id] || m.presets[0]?.id) === p.id }, p.name)));
      const pr = m.presets.find(p => p.id === (chosen[m.id] || m.presets[0]?.id));
      return h('div', { class: 'card model' + (isThis ? ' active' : '') },
        h('h4', {}, m.name), h('div', { class: 'tags' }, m.size_gb ? h('span', { class: 'tag' }, m.size_gb + ' GB') : null,
          m.vision ? h('span', { class: 'tag' }, 'vision') : null, !m.installed ? h('span', { class: 'tag warn' }, 'not downloaded') : null,
          isThis ? h('span', { class: 'tag ok' }, s.health) : null),
        h('p', { class: 'muted small' }, m.desc), m.presets.length ? sel : null, pr?.bench ? h('p', { class: 'small' }, 'Measured: ' + pr.bench) : null,
        h('div', { class: 'row end' },
          isThis ? h('button', { onclick: () => unload() }, 'Unload') : null,
          h('button', { class: 'primary', disabled: !m.installed || (isThis && s.health === 'loading'), onclick: async () => {
            try { await api('/api/v100/load', { method: 'POST', body: { id: m.id, preset: chosen[m.id] || m.presets[0]?.id || '' } }); toast(`Loading ${m.name}…`); } catch (e) { fail(e); }
          } }, isThis ? 'Reload' : other ? 'Switch to this' : 'Load')));
    }));
  };
  draw();
  main._refresh = draw;
}
async function unload() { try { await api('/api/v100/unload', { method: 'POST', body: {} }); toast('Model unloaded, GPU memory freed'); } catch (e) { fail(e); } }

// ---------------------------------------------------------------- PC status (sidebar)
async function pollPc() {
  try { S.pc = await api('/api/v100/status'); } catch { S.pc = null; }
  renderPcBar();
  if (S.pc?.health === 'ready' && !pollPc.ready) refreshInfo();
  pollPc.ready = S.pc?.health === 'ready';
  if (S.view === 'models' && $('#main')._refresh) $('#main')._refresh();
}
function renderPcBar() {
  const el = $('#pcbar'), s = S.pc;
  if (!s || !s.launcher) { el.replaceChildren(h('div', { class: 'muted small' }, s ? 'V100-LLM launcher not running' : 'PC status unavailable')); return; }
  const dot = { ready: 'ok', loading: 'warn' }[s.health] || 'off';
  el.replaceChildren(
    h('div', { class: 'pcname' }, h('span', { class: 'dot ' + dot }), h('span', { dir: 'auto' }, s.health === 'stopped' ? 'No model loaded' : (s.model_name || s.model) + (s.health === 'loading' ? ` (loading ${s.uptime}s)` : ''))),
    h('div', { class: 'pcgrid' },
      s.vram_total_mb ? h('div', {}, h('span', {}, `VRAM ${(s.vram_used_mb / 1024).toFixed(1)}/${(s.vram_total_mb / 1024).toFixed(0)}G`), bar(s.vram_used_mb / s.vram_total_mb)) : null,
      h('div', {}, h('span', {}, `GPU ${s.gpu_util}%`), bar(s.gpu_util / 100)),
      h('div', {}, h('span', {}, `CPU ${Math.round(s.cpu)}%`), bar(s.cpu / 100)),
      s.ram_total ? h('div', {}, h('span', {}, `RAM ${gib(s.ram_used)}/${Math.round(s.ram_total / 1073741824)}G`), bar(s.ram_used / s.ram_total)) : null));
}

// ---------------------------------------------------------------- OpenAI API
async function viewApi(main) {
  const body = h('div', {}, h('span', { class: 'spin' }));
  main.replaceChildren(page('API (OpenAI format)', h('p', { class: 'muted' }, 'Use the model running on your PC from any app or script that speaks the OpenAI API. Switch models from Models: the same URL and key keep working.'), body));
  const draw = i => {
    const url = i.base_url || '(the tunnel URL appears when the server is online)';
    const show = h('code', { class: 'key' }, i.key ? i.key.slice(0, 10) + '•'.repeat(18) : '');
    const curl = `curl ${i.base_url}/chat/completions \\\n  -H "Authorization: Bearer ${i.key}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"model":"local","messages":[{"role":"user","content":"Hi"}]}'`;
    const py = `from openai import OpenAI\nclient = OpenAI(base_url="${i.base_url}", api_key="${i.key}")\nr = client.chat.completions.create(model="local", messages=[{"role": "user", "content": "Hi"}])\nprint(r.choices[0].message.content)`;
    const copy = (t, l) => { navigator.clipboard.writeText(t); toast(l + ' copied'); };
    body.replaceChildren(card(
      h('label', {}, 'Base URL'), h('div', { class: 'row' }, h('code', { class: 'grow' }, url), h('button', { onclick: () => copy(i.base_url, 'URL') }, 'Copy')),
      i.enabled ? [h('label', {}, 'API key'), h('div', { class: 'row' }, show, h('button', { onclick: () => { show.textContent = show.textContent.includes('•') ? i.key : i.key.slice(0, 10) + '•'.repeat(18); } }, 'Show'),
        h('button', { onclick: () => copy(i.key, 'Key') }, 'Copy'))] : h('p', { class: 'err' }, 'API is off: no key yet.'),
      h('p', { class: 'muted small' }, `Model: ${shortModel((i.models || [])[0]) || 'no model loaded'} · any model name works in requests · on the PC itself: ${i.local_url}`),
      h('div', { class: 'row' },
        !i.enabled ? h('button', { class: 'primary', onclick: async () => draw(await api('/api/openai/regenerate', { method: 'POST', body: {} })) }, 'Generate key')
          : [h('button', { class: 'primary', onclick: async () => { if (await confirmBox('Refresh the API key?', 'Apps using the old key stop working until you give them the new one.', 'Refresh')) draw(await api('/api/openai/regenerate', { method: 'POST', body: {} })); } }, '↻ Refresh key'),
             h('button', { class: 'danger', onclick: async () => { if (await confirmBox('Turn the API off?', 'The key is deleted and the URL stops answering.', 'Turn off', true)) draw(await api('/api/openai/disable', { method: 'POST', body: {} })); } }, 'Turn off')])),
      i.enabled ? [card(h('div', { class: 'row' }, h('b', { class: 'grow' }, 'curl'), h('button', { onclick: () => copy(curl, 'curl example') }, 'Copy')), h('pre', {}, curl)),
                   card(h('div', { class: 'row' }, h('b', { class: 'grow' }, 'Python (openai package)'), h('button', { onclick: () => copy(py, 'Python example') }, 'Copy')), h('pre', {}, py))] : null,
      h('p', { class: 'muted small' }, i.fixed_url ? 'Your tunnel has a fixed address.' : 'With the free quick tunnel the URL changes when the PC server restarts; come back here to copy the new one.'));
  };
  try { draw(await api('/api/openai')); } catch (e) { body.replaceChildren(h('p', { class: 'err' }, e.message)); }
}

// ---------------------------------------------------------------- Memory
const CATS = { personal: 'Personal', family: 'Family', work: 'Work', preferences: 'Likes', health: 'Health', places: 'Places', plans: 'Plans', other: 'Other' };
async function viewMemory(main) {
  let q = '', cat = '';
  const status = h('div', { class: 'muted small' }), list = h('div', { class: 'list' });
  const auto = h('input', { type: 'checkbox', onchange: async e => { try { await api('/api/memory/settings', { method: 'POST', body: { auto_memory: e.target.checked } }); } catch (er) { fail(er); } } });
  const search = h('input', { type: 'search', placeholder: 'Search memories (any language, by meaning)' });
  const add = h('input', { placeholder: 'Add: e.g. I prefer answers in Arabic' });
  const cats = h('div', { class: 'chips' });
  const load = async () => {
    try {
      const [l, st] = await Promise.all([api('/api/memory?' + qs({ q, category: cat })), api('/api/memory/status')]);
      auto.checked = st.auto_memory;
      status.textContent = st.ready ? `${st.count} memories · smart recall by meaning (Arabic + English) is on` : st.loading ? `${st.count} memories · preparing smart recall on the PC…` : `${st.count} memories`;
      list.replaceChildren(...(l.length ? l.map(m => h('div', { class: 'card clickable', onclick: () => editMem(m) },
        h('div', { dir: 'auto' }, m.content), h('div', { class: 'muted small' }, `${CATS[m.category] || m.category} · ${m.source === 'manual' ? 'added by you' : 'remembered by AI'} · ${dateStr(m.updated || m.created)}`)))
        : [h('p', { class: 'muted' }, q ? 'Nothing matches.' : 'Nothing remembered yet. Just chat: the AI keeps what matters.')]));
    } catch (e) { fail(e); }
  };
  const drawCats = () => cats.replaceChildren(h('button', { class: 'chip' + (cat === '' ? ' on' : ''), onclick: () => { cat = ''; drawCats(); load(); } }, 'All'),
    ...Object.entries(CATS).map(([k, v]) => h('button', { class: 'chip' + (cat === k ? ' on' : ''), onclick: () => { cat = cat === k ? '' : k; drawCats(); load(); } }, v)));
  const editMem = m => {
    const t = h('textarea', { rows: 4, dir: 'auto' }); t.value = m.content;
    let c = m.category || 'other';
    const cc = h('div', { class: 'chips' });
    const dc = () => cc.replaceChildren(...Object.entries(CATS).map(([k, v]) => h('button', { class: 'chip' + (c === k ? ' on' : ''), onclick: () => { c = k; dc(); } }, v)));
    dc();
    modal(h('div', {}, h('h3', {}, 'Memory'), t, cc, h('div', { class: 'row end' },
      h('button', { class: 'danger', onclick: async () => { await api(`/api/memory/${m.id}`, { method: 'DELETE' }).catch(fail); closeModal(); load(); } }, 'Forget'),
      h('button', { onclick: closeModal }, 'Cancel'),
      h('button', { class: 'primary', onclick: async () => { await api(`/api/memory/${m.id}`, { method: 'PUT', body: { content: t.value, category: c } }).catch(fail); closeModal(); load(); } }, 'Save'))));
  };
  let tm;
  search.oninput = () => { clearTimeout(tm); tm = setTimeout(() => { q = search.value; load(); }, 350); };
  add.onkeydown = async e => { if (e.key === 'Enter' && add.value.trim()) { await api('/api/memory', { method: 'POST', body: { content: add.value, category: cat || 'other' } }).catch(fail); add.value = ''; load(); } };
  main.replaceChildren(page('Memory',
    card(h('label', { class: 'row' }, auto, h('div', {}, h('b', {}, 'Remember automatically'),
      h('div', { class: 'muted small' }, 'After each reply the AI keeps lasting facts about you (family, work, likes, plans) and updates or removes ones that changed.'))), status),
    search, cats, h('div', { class: 'row' }, add, h('button', { class: 'primary', onclick: () => add.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' })) }, 'Add')), list));
  drawCats(); load();
}

// ---------------------------------------------------------------- Notes, tasks, calendar, email
async function viewOrganizer(main, tab = S.orgTab || 'tasks') {
  S.orgTab = tab;
  const tabs = [['tasks', 'Tasks'], ['notes', 'Notes'], ['calendar', 'Calendar'], ['email', 'Email'], ['fromemail', 'From email']];
  const body = h('div', { class: 'orgbody' });
  main.replaceChildren(h('div', { class: 'page' }, h('header', { class: 'pagehead' }, h('h2', {}, 'Notes, tasks & calendar'),
    h('div', { class: 'tabs' }, ...tabs.map(([k, v]) => h('button', { class: 'tab' + (k === tab ? ' on' : ''), onclick: () => viewOrganizer(main, k) }, v)))),
    h('div', { class: 'pagebody' }, body)));
  ({ tasks: tabTasks, notes: tabNotes, calendar: tabCalendar, email: tabEmail, fromemail: tabFromEmail })[tab](body);
}
function dateInput(withTime = true, value = '') {
  const i = h('input', { type: withTime ? 'datetime-local' : 'date' });
  if (value) i.value = withTime ? value.replace(' ', 'T').slice(0, 16) : value.slice(0, 10);
  i.serverValue = () => i.value ? i.value.replace('T', ' ') : '';
  return i;
}
const draftReply = (id, about) => askAi(`Read the email with id=${id} ("${about}") and draft a reply for me. Save it as a draft, show it to me, and don't send it until I approve.`, { email: true });

async function tabTasks(body) {
  const title = h('input', { placeholder: 'New task' }), desc = h('textarea', { rows: 2, placeholder: 'Description (optional)' });
  const due = dateInput(true), high = h('input', { type: 'checkbox' });
  let showDone = false;
  const list = h('div', { class: 'list' });
  const load = async () => {
    let l; try { l = await api('/api/tasks_list?status=all'); } catch (e) { return fail(e); }
    l = l.filter(t => showDone || !t.done);
    list.replaceChildren(...(l.length ? l.map(t => {
      const fromEmail = !!t.email_id;
      return h('div', { class: 'card task' + (t.done ? ' done' : '') },
        h('input', { type: 'checkbox', checked: t.done, onchange: async e => { await api(`/api/tasks_list/${t.id}`, { method: 'PATCH', body: { done: e.target.checked } }).catch(fail); load(); } }),
        h('div', { class: 'grow' }, h('div', { class: 'ttitle' + (t.priority === 'high' && !t.done ? ' hi' : ''), dir: 'auto' }, t.title),
          h('div', { class: 'muted small', dir: 'auto' }, [t.due && 'due ' + t.due, t.priority !== 'normal' && t.priority, t.notes].filter(Boolean).join(' · ')),
          fromEmail && !t.done ? h('button', { class: 'link', onclick: () => draftReply(t.email_id, t.title) }, '✉ Draft reply with AI') : null),
        h('button', { class: 'icon', title: 'Delete', onclick: async () => { await api(`/api/organizer/tasks/${t.id}`, { method: 'DELETE' }).catch(fail); load(); } }, '🗑'));
    }) : [h('p', { class: 'muted' }, 'No tasks. Add one above, or tell the AI "remind me to …".')]));
  };
  body.replaceChildren(
    h('div', { class: 'row' }, h('button', { onclick: () => askAi('What tasks do I have? Sort them by due date and tell me what is most urgent.', { organizer: true }) }, 'Ask the AI: what tasks do I have?')),
    card(title, desc, h('div', { class: 'row' }, h('label', {}, 'Due '), due, h('label', { class: 'row' }, high, ' High priority'), h('span', { class: 'grow' }),
      h('button', { class: 'primary', onclick: async () => {
        if (!title.value.trim()) return;
        await api('/api/tasks_list', { method: 'POST', body: { title: title.value.trim(), due: due.serverValue(), priority: high.checked ? 'high' : 'normal', notes: desc.value.trim() } }).catch(fail);
        title.value = ''; desc.value = ''; due.value = ''; high.checked = false; load();
      } }, '＋ Add task'))),
    h('div', { class: 'row' }, h('h3', { class: 'grow' }, 'Tasks'), h('label', {}, h('input', { type: 'checkbox', onchange: e => { showDone = e.target.checked; load(); } }), ' Show done')),
    list);
  load();
}

async function tabNotes(body) {
  const q = h('input', { type: 'search', placeholder: 'Search notes' }), list = h('div', { class: 'grid' });
  const edit = n => {
    const t = h('input', { value: n?.title || '', placeholder: 'Title' }), b = h('textarea', { rows: 12, dir: 'auto' }); b.value = n?.body || '';
    modal(h('div', {}, h('h3', {}, n ? 'Edit note' : 'New note'), t, b, h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Cancel'),
      h('button', { class: 'primary', onclick: async () => {
        await api('/api/notes' + (n ? '/' + n.id : ''), { method: n ? 'PUT' : 'POST', body: { title: t.value || 'Note', body: b.value } }).catch(fail); closeModal(); load();
      } }, 'Save'))), { wide: true });
  };
  const load = async () => {
    let l; try { l = await api('/api/notes?' + qs({ q: q.value })); } catch (e) { return fail(e); }
    list.replaceChildren(...(l.length ? l.map(n => h('div', { class: 'card clickable note', onclick: () => edit(n) },
      h('div', { class: 'row' }, h('b', { class: 'grow', dir: 'auto' }, n.title),
        h('button', { class: 'icon', onclick: async e => { e.stopPropagation(); await api(`/api/organizer/notes/${n.id}`, { method: 'DELETE' }).catch(fail); load(); } }, '🗑')),
      h('div', { class: 'muted small clamp', dir: 'auto' }, n.body || ''))) : [h('p', { class: 'muted' }, 'No notes yet. Add one, or tell the AI "save a note …".')]));
  };
  q.oninput = load;
  body.replaceChildren(h('div', { class: 'row' }, q, h('button', { class: 'primary', onclick: () => edit(null) }, '＋ New note')), list);
  load();
}

async function tabCalendar(body) {
  const list = h('div', { class: 'list' });
  const add = () => {
    const t = h('input', { placeholder: 'Title' }), st = dateInput(true, new Date().toISOString().slice(0, 10) + ' 09:00'), en = dateInput(true), loc = h('input', { placeholder: 'Location (optional)' });
    modal(h('div', {}, h('h3', {}, 'New event'), t, h('label', {}, 'Starts'), st, h('label', {}, 'Ends (optional)'), en, loc,
      h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Cancel'), h('button', { class: 'primary', onclick: async () => {
        if (!t.value.trim() || !st.value) return toast('Add a title and a start');
        await api('/api/events', { method: 'POST', body: { title: t.value, start: st.serverValue(), end: en.serverValue(), location: loc.value } }).catch(fail); closeModal(); load();
      } }, 'Add'))));
  };
  const load = async () => {
    let l; try { l = await api('/api/events'); } catch (e) { return fail(e); }
    const byDay = {};
    for (const e of l) (byDay[(e.start || '').slice(0, 10) || 'No date'] ||= []).push(e);
    list.replaceChildren(...(l.length ? Object.entries(byDay).map(([d, evs]) => h('div', {}, h('h4', {}, d),
      ...evs.map(e => h('div', { class: 'card row' }, h('div', { class: 'grow' }, h('div', { dir: 'auto' }, ((e.start || '').slice(11, 16) + '  ' + e.title).trim()),
        h('div', { class: 'muted small' }, [e.location, e.source === 'google' && 'Google'].filter(Boolean).join(' · '))),
        e.source === 'local' ? h('button', { class: 'icon', onclick: async () => { await api(`/api/organizer/events/${e.id}`, { method: 'DELETE' }).catch(fail); load(); } }, '🗑') : null))))
      : [h('p', { class: 'muted' }, 'Nothing planned in the next 30 days.')]));
  };
  body.replaceChildren(h('div', { class: 'row' }, h('button', { class: 'primary', onclick: add }, '＋ Add event'),
    h('button', { onclick: () => askAi('What do I have on my calendar this week?', { organizer: true }) }, 'Ask the AI')),
    h('p', { class: 'muted small' }, 'Next 30 days: your calendar on the PC, plus Google Calendar when connected (Email tab).'), list);
  load();
}

const MailCache = { pages: {}, full: {} };
async function tabEmail(body) {
  let st;
  try { st = await api('/api/google/status'); } catch (e) { body.replaceChildren(h('p', { class: 'err' }, e.message)); return; }
  if (!st.connected) return googleSetup(body, st);
  let q = S.mailQ || 'in:inbox', mails = MailCache.pages[q]?.[0] || null, next = MailCache.pages[q]?.[1] || '', loading = false;
  const list = h('div', { class: 'list' }), more = h('div', {}), prog = h('div', { class: 'progress hidden' });
  const search = h('input', { type: 'search', placeholder: 'Search mail (e.g. from:sara invoice)', onkeydown: e => { if (e.key === 'Enter' && search.value.trim()) show(search.value.trim()); } });
  const chips = h('div', { class: 'chips' });
  const folders = [['in:inbox', 'Inbox'], ['is:unread', 'Unread'], ['in:sent', 'Sent'], ['in:drafts', 'Drafts'], ['is:starred', 'Starred'], ['-in:spam -in:trash', 'All mail']];
  const drawChips = () => chips.replaceChildren(...folders.map(([k, v]) => h('button', { class: 'chip' + (q === k ? ' on' : ''), onclick: () => { search.value = ''; show(k); } }, v)));
  const draw = () => {
    const sent = q === 'in:sent' || q === 'in:drafts';
    list.replaceChildren(...(mails || []).map(e => h('div', { class: 'card clickable mail' + (e.unread ? ' unread' : ''), onclick: () => openMail(e) },
      h('div', { class: 'row' }, h('b', { class: 'grow ell', dir: 'auto' }, sent ? 'To: ' + (e.to || '').split('<')[0] : (e.from || '').split('<')[0]),
        h('span', { class: 'muted small' }, (e.date.match(/\d{1,2} \w{3} \d{4} \d{2}:\d{2}/) || [e.date.slice(0, 16)])[0])),
      h('div', { class: 'ell', dir: 'auto' }, e.subject || '(no subject)'), h('div', { class: 'muted small ell', dir: 'auto' }, e.snippet))));
    if (mails && !mails.length) list.replaceChildren(h('p', { class: 'muted' }, 'No emails here.'));
    more.replaceChildren(next ? h('button', { class: 'wide', disabled: loading, onclick: () => load(true) }, loading ? 'Loading…' : `Load more (${(mails || []).length} shown)`)
      : mails?.length ? h('p', { class: 'muted small' }, `${mails.length} email(s), that's all.`) : '');
  };
  const load = async (append = false) => {
    if (loading) return; loading = true; prog.classList.remove('hidden'); draw();
    const query = q;
    try {
      const p = await api('/api/google/mail?' + qs({ n: 25, q: query, page: append ? next : '' }));
      const pageData = Array.isArray(p) ? { messages: p, next: '' } : p;
      if (query === q) { mails = append ? [...(mails || []), ...pageData.messages] : pageData.messages; next = pageData.next || ''; MailCache.pages[query] = [mails, next]; }
    } catch (e) { fail(e); }
    loading = false; prog.classList.add('hidden'); draw();
  };
  const show = k => { q = S.mailQ = k; mails = MailCache.pages[k]?.[0] || null; next = MailCache.pages[k]?.[1] || ''; drawChips(); draw(); load(); };
  const openMail = async e => {
    let mf = MailCache.full[e.id];
    if (!mf) { try { mf = MailCache.full[e.id] = await api(`/api/google/mail/${e.id}`); } catch (er) { return fail(er); } }
    if (q === 'in:drafts') return draftWindow(mf, () => { delete MailCache.full[e.id]; delete MailCache.pages['in:drafts']; load(); });
    modal(h('div', {}, h('h3', { dir: 'auto' }, mf.subject), h('div', { class: 'muted small' }, `From: ${mf.from}\nTo: ${mf.to}\n${mf.date}`),
      h('div', { class: 'mailbody pre', dir: 'auto' }, mf.body),
      h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Close'),
        h('button', { onclick: () => { closeModal(); askAi(`Read the email with id=${mf.id} ("${mf.subject}") and explain it to me simply: who sent it, what they want or tell me, any dates, deadlines or amounts, and whether I need to do or reply anything.`, { email: true }); } }, 'Explain this email'),
        h('button', { class: 'primary', onclick: () => { closeModal(); draftReply(mf.id, mf.subject); } }, 'Draft a reply with AI'))), { wide: true });
  };
  body.replaceChildren(h('div', { class: 'row' }, h('b', { class: 'grow' }, 'Gmail: ' + st.email),
    h('button', { onclick: () => askAi('Check my unread emails and summarize what needs a reply.', { email: true }) }, 'Ask the AI to summarize my unread email'),
    h('button', { onclick: async () => { if (await confirmBox('Disconnect Google?', 'The AI can no longer read your mail or calendar until you connect again.', 'Disconnect', true)) { await api('/api/google/disconnect', { method: 'POST', body: {} }).catch(fail); tabEmail(body); } } }, 'Disconnect')),
    chips, search, prog, list, more);
  drawChips(); draw(); load();
}
async function draftWindow(mf, onChanged) {
  let draftId = '';
  try { draftId = (await api(`/api/google/draft_of/${mf.id}`)).draft_id; } catch (e) { fail(e); }
  const to = h('input', { value: mf.to, placeholder: 'To' }), sub = h('input', { value: mf.subject, placeholder: 'Subject' });
  const txt = h('textarea', { rows: 14, dir: 'auto' }); txt.value = mf.body;
  const ask = h('input', { placeholder: 'Ask AI to change it: e.g. shorter, more formal, add the date' });
  modal(h('div', {}, h('h3', {}, 'Draft: ' + (mf.subject || '(no subject)')), to, sub, txt,
    h('div', { class: 'row' }, ask, h('button', { disabled: !draftId, onclick: () => { if (!ask.value.trim()) return; closeModal();
      askAi(`Edit my Gmail draft (draft_id=${draftId}, message id=${mf.id}, subject "${mf.subject}"). Read it with gmail_read id=${mf.id}, then rewrite it: ${ask.value.trim()}. Save the new version with gmail_update_draft (draft_id=${draftId}) and show me the new text. Do not send it.`, { email: true }); } }, 'Ask AI to edit')),
    h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Close'),
      h('button', { disabled: !draftId, onclick: async () => { try { await api(`/api/google/draft/${draftId}`, { method: 'PUT', body: { body: txt.value, subject: sub.value, to: to.value } }); toast('Draft saved'); closeModal(); onChanged(); } catch (e) { fail(e); } } }, 'Save changes'),
      h('button', { class: 'primary', disabled: !draftId, onclick: async () => {
        if (!await confirmBox('Send this email?', `To: ${to.value}\nSubject: ${sub.value}\n\nIt is sent from your Gmail right away (save your changes first).`, 'Send')) return;
        try { await api(`/api/google/draft/${draftId}/send`, { method: 'POST', body: {} }); toast('Email sent'); onChanged(); } catch (e) { fail(e); }
      } }, 'Send'))), { wide: true });
}
function googleSetup(body, st) {
  const cid = h('input', { placeholder: 'Client ID (…apps.googleusercontent.com)' }), sec = h('input', { placeholder: 'Client secret' });
  body.replaceChildren(card(h('h3', {}, 'Connect Google (Gmail + Calendar)'),
    h('p', {}, 'The AI can then read your email, write draft replies, list and add Google Calendar events. Sending an email or adding a Google event always asks you first. Your login stays on your PC.'),
    !st.configured ? [h('ol', { class: 'small' }, h('li', {}, 'Open console.cloud.google.com and create a project.'), h('li', {}, 'APIs & Services → Library: enable Gmail API and Google Calendar API.'),
      h('li', {}, 'OAuth consent screen (Google Auth Platform): External, add your Gmail as a test user.'), h('li', {}, 'Clients → Create client → type Desktop app. Copy the ID and secret here:')),
      cid, sec, h('button', { class: 'primary', onclick: async () => { try { await api('/api/google/client', { method: 'POST', body: { client_id: cid.value, client_secret: sec.value } }); tabEmail(body); } catch (e) { fail(e); } } }, 'Save')]
      : [h('p', {}, 'Click Connect: Google\'s sign-in page opens in the browser on the PC that runs the server. Sign in, allow access, then click "I signed in".'),
        h('div', { class: 'row' }, h('button', { class: 'primary', onclick: async () => { try { const r = await api('/api/google/connect', { method: 'POST', body: {} }); toast(r.opened_on_pc ? 'Sign-in page opened on the PC' : 'Open the sign-in page on the PC'); } catch (e) { fail(e); } } }, 'Connect'),
          h('button', { onclick: () => tabEmail(body) }, 'I signed in'))]));
}

async function tabFromEmail(body) {
  let days = 30, skip = true, st = null, timer = null;
  const list = h('div', { class: 'list' }), status = h('div', {});
  const daysChips = h('div', { class: 'chips' });
  const drawDays = () => daysChips.replaceChildren(...[3, 7, 14, 30, 90].map(d => h('button', { class: 'chip' + (d === days ? ' on' : ''), onclick: () => { days = d; drawDays(); } }, `Last ${d} days`)));
  const load = async () => {
    let l; try { l = await api('/api/email_tasks'); } catch (e) { return fail(e); }
    l.sort((a, b) => (b.kind === 'reply') - (a.kind === 'reply'));
    const replies = l.filter(s => s.kind === 'reply').length;
    list.replaceChildren(h('h3', {}, `Suggested (${l.length})` + (replies ? ` · ${replies} need a reply` : '')),
      ...(l.length ? l.map(s => h('div', { class: 'card' }, s.kind === 'reply' ? h('div', { class: 'tag ok' }, '✉ NEEDS YOUR REPLY') : null,
        h('b', { class: s.priority === 'high' ? 'hi' : '', dir: 'auto' }, s.title), h('div', { class: 'small' }, [s.due && 'due ' + s.due, s.priority !== 'normal' && s.priority].filter(Boolean).join(' · ')),
        s.notes ? h('div', { class: 'small', dir: 'auto' }, s.notes) : null,
        h('div', { class: 'muted small ell', dir: 'auto' }, `From: ${(s.email_from || '').split('<')[0]} · "${s.email_subject}"`),
        h('div', { class: 'row' }, h('button', { class: 'primary', onclick: async () => { try { await api(`/api/email_tasks/${s.id}/accept`, { method: 'POST', body: {} }); toast('Added to your tasks'); } catch (e) { fail(e); } load(); } }, 'Add to my tasks'),
          h('button', { onclick: async () => { await api(`/api/email_tasks/${s.id}/dismiss`, { method: 'POST', body: {} }).catch(fail); load(); } }, 'Dismiss'),
          s.kind === 'reply' ? h('button', { class: 'link', onclick: () => draftReply(s.email_id, s.email_subject) }, '✉ Draft the reply with AI now') : null)))
        : [h('p', { class: 'muted' }, 'No suggestions. Scan your email to find tasks and emails waiting for your reply.')]));
  };
  const drawStatus = () => {
    const r = st?.running;
    status.replaceChildren(
      h('div', { class: 'row' }, h('button', { class: 'primary', disabled: r, onclick: async () => {
        try { st = await api('/api/email_tasks/scan', { method: 'POST', body: { query: `in:inbox newer_than:${days}d`, skip_promotions: skip } }); poll(); } catch (e) { fail(e); }
      } }, r ? `Reading email… ${st.done}/${st.total}` : 'Scan all my email for tasks'),
        r ? h('button', { onclick: async () => { st = await api('/api/email_tasks/cancel', { method: 'POST', body: {} }).catch(() => st); } }, 'Stop scanning') : null),
      r ? [bar(st.total ? st.done / st.total : 0), h('p', { class: 'muted small' }, `Every email in the period is read once (${st.matched} found, ${st.total} new). About ${Math.round((st.total - st.done) * 3.3 / 60)} min left; you can leave this screen.`)]
        : st && (st.total || st.found) ? h('p', { class: 'muted small' }, `Last scan: ${st.total} new email(s) read, ${st.found} suggestion(s).` + (st.error ? ' ' + st.error : '')) : null);
  };
  const poll = () => { clearInterval(timer); timer = setInterval(async () => {
    if (!document.body.contains(status)) return clearInterval(timer);
    try { st = await api('/api/email_tasks/status'); } catch {}
    drawStatus(); load();
    if (!st?.running) clearInterval(timer);
  }, 2500); };
  body.replaceChildren(card(h('p', {}, 'The AI on your PC reads your recent email and suggests tasks (deadlines, payments, things to submit) and emails waiting for your reply. Nothing is added until you click Add.'),
    daysChips, h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: true, onchange: e => skip = e.target.checked }), ' Skip Promotions & Social (faster)'), status,
    h('button', { class: 'link', onclick: async () => { await api('/api/email_tasks/forget', { method: 'POST', body: {} }).catch(fail); toast('Next scan reads all emails again'); load(); } }, 'Rescan everything next time')), list);
  drawDays();
  try { st = await api('/api/email_tasks/status'); } catch {}
  drawStatus(); load(); if (st?.running) poll();
}

// ---------------------------------------------------------------- Files on PC
async function viewFiles(main, path = S.filesPath) {
  const crumbs = h('div', { class: 'row' }), list = h('div', { class: 'list' });
  main.replaceChildren(page('Files on PC', crumbs, list));
  let roots;
  try { roots = await api('/api/fs/roots'); } catch (e) { return list.replaceChildren(h('p', { class: 'err' }, e.message)); }
  if (!path) {
    S.filesPath = '';
    return list.replaceChildren(...roots.roots.map(r => h('div', { class: 'card clickable row', onclick: () => viewFiles(main, r) }, '📁 ', h('span', {}, r))));
  }
  S.filesPath = path;
  let l; try { l = await api('/api/fs/list?' + qs({ path })); } catch (e) { return list.replaceChildren(h('p', { class: 'err' }, e.message)); }
  const parent = l.path.replace(/[\\/][^\\/]+[\\/]?$/, '');
  const up = h('input', { type: 'file', multiple: true, class: 'hidden', onchange: async e => {
    for (const f of e.target.files) { const fd = new FormData(); fd.append('file', f); await api('/api/fs/upload?' + qs({ dir: l.path }), { method: 'POST', form: fd }).catch(fail); }
    viewFiles(main, l.path);
  } });
  crumbs.replaceChildren(h('button', { onclick: () => viewFiles(main, roots.roots.some(r => r.toLowerCase() === l.path.toLowerCase()) ? '' : parent) }, '⬑ Up'),
    h('code', { class: 'grow' }, l.path), up, h('button', { onclick: () => up.click() }, '⬆ Upload here'),
    h('button', { onclick: async () => { const n = await promptBox('New folder name'); if (n) { await api('/api/fs/mkdir', { method: 'POST', body: { parent: l.path, name: n } }).catch(fail); viewFiles(main, l.path); } } }, '＋ Folder'));
  list.replaceChildren(...l.entries.map(e => h('div', { class: 'card row file' },
    h('span', { class: 'grow clickable', onclick: () => e.is_dir ? viewFiles(main, l.path.replace(/[\\/]$/, '') + '\\' + e.name) : null }, (e.is_dir ? '📁 ' : '📄 ') + e.name),
    !e.is_dir ? h('span', { class: 'muted small' }, kfmt(e.size) + 'B') : null,
    !e.is_dir ? h('a', { class: 'button', href: '/api/fs/download?' + qs({ path: l.path.replace(/[\\/]$/, '') + '\\' + e.name }), download: e.name }, 'Download') : null,
    !e.is_dir ? h('button', { onclick: () => askAi(`Read the file ${l.path.replace(/[\\/]$/, '')}\\${e.name} and tell me what it contains.`) }, 'Ask AI') : null)));
}

// ---------------------------------------------------------------- Terminal
function viewTerminal(main) {
  const lang = h('select', {}, ...['powershell', 'python', 'cmd'].map(l => h('option', { value: l }, l)));
  const code = h('textarea', { rows: 8, class: 'mono', placeholder: 'Code to run on the PC (Ctrl+Enter)' });
  const out = h('pre', { class: 'termout' });
  const run = async () => {
    if (!code.value.trim()) return;
    out.textContent = 'Running…';
    try { const r = await api('/api/exec', { method: 'POST', body: { language: lang.value, code: code.value } });
      out.textContent = (r.stdout || '') + (r.stderr ? '\n[stderr]\n' + r.stderr : '') + `\n[exit ${r.exit_code}${r.timed_out ? ', timed out' : ''}]`; }
    catch (e) { out.textContent = e.message; }
  };
  code.onkeydown = e => { if (e.key === 'Enter' && e.ctrlKey) run(); };
  main.replaceChildren(page('Terminal', h('p', { class: 'muted' }, 'Runs directly on the PC, in the workspace folder.'), h('div', { class: 'row' }, lang, h('button', { class: 'primary', onclick: run }, '▶ Run')), code, out));
}

// ---------------------------------------------------------------- Running tasks
async function viewRunning(main) {
  const body = h('div', {});
  main.replaceChildren(page('Running tasks', body));
  const draw = async () => {
    if (!document.body.contains(body)) return;
    let t; try { t = await api('/api/tasks'); } catch (e) { return body.replaceChildren(h('p', { class: 'err' }, e.message)); }
    body.replaceChildren(card(h('b', {}, 'LLM server: ' + (t.llm_busy === true ? 'busy generating' : t.llm_busy === false ? 'idle' : 'unknown')),
      t.llm_busy && !t.runs.length ? h('div', {}, h('p', { class: 'small' }, 'The model is finishing an earlier request nobody waits for.'), h('button', { onclick: () => api('/api/llm/abort', { method: 'POST', body: {} }).then(r => toast(`LLM stopped (${r.cancelled})`)).catch(fail) }, 'Stop it')) : null),
      h('h3', {}, `Chats (${t.runs.length})`),
      ...(t.runs.length ? t.runs.map(r => card(h('div', { class: 'row' }, h('div', { class: 'grow' }, h('b', { dir: 'auto' }, r.title),
        h('div', { class: 'muted small' }, `${r.step || r.phase}${r.tokens ? ' · ' + r.tokens + ' tokens' : ''}${r.tps ? ' · ' + r.tps + ' t/s' : ''} · ${mmss(r.elapsed)}${r.waiting_approval ? ' · waiting for approval' : ''}${r.waiting_question ? ' · waiting for your choice' : ''}`)),
        h('button', { onclick: () => openSession(r.session_id) }, 'Open'), h('button', { class: 'danger', onclick: () => api(`/api/tasks/${r.session_id}/stop`, { method: 'POST', body: {} }).catch(fail) }, 'Stop'))))
        : [h('p', { class: 'muted' }, 'No chat is generating.')]),
      h('h3', {}, `Processes (${t.processes.length})`),
      ...t.processes.map(p => card(h('div', { class: 'row' }, h('code', { class: 'grow ell' }, `${p.language}: ${p.preview}`), h('span', { class: 'muted small' }, mmss(p.elapsed)),
        h('button', { class: 'danger', onclick: () => api(`/api/processes/${p.pid}/kill`, { method: 'POST', body: {} }).catch(fail) }, 'Kill')))),
      h('button', { class: 'danger', onclick: async () => { if (await confirmBox('Stop everything?', 'Stops every chat, kills all code started from the app and denies pending approvals.', 'Stop all', true)) { const r = await api('/api/tasks/kill_all', { method: 'POST', body: {} }).catch(fail); r && toast(`Stopped ${r.runs} chat(s), ${r.processes} process(es)`); } } }, '⛔ Stop all'));
  };
  await draw();
  const tm = setInterval(() => document.body.contains(body) ? draw() : clearInterval(tm), 2000);
}

// ---------------------------------------------------------------- Settings
async function viewSettings(main) {
  let local = {};
  try { local = await (await fetch('/local/settings')).json(); } catch {}
  const p = S.prefs;
  const sw = (label, desc, key, after) => h('label', { class: 'setting' }, h('input', { type: 'checkbox', checked: !!p[key], onchange: e => { p[key] = e.target.checked; savePrefs(); after && after(); } }),
    h('div', {}, h('b', {}, label), h('div', { class: 'muted small' }, desc)));
  const rate = h('input', { type: 'range', min: 0.6, max: 1.8, step: 0.1, value: p.rate || 1, oninput: e => { p.rate = +e.target.value; rl.textContent = `Speech speed ${p.rate.toFixed(1)}x`; }, onchange: savePrefs });
  const rl = h('span', {}, `Speech speed ${(p.rate || 1).toFixed(1)}x`);
  const comp = h('input', { type: 'range', min: 50, max: 95, step: 5, value: p.compressAt, oninput: e => { p.compressAt = +e.target.value; cl.textContent = `Compress at ${p.compressAt}% of the context`; }, onchange: savePrefs });
  const cl = h('span', {}, `Compress at ${p.compressAt}% of the context`);
  main.replaceChildren(page('Settings',
    card(h('h3', {}, 'Server'), h('p', {}, local.paired ? ['Connected to ', h('code', {}, local.url)] : 'Not connected'),
      h('div', { class: 'row' }, h('button', { onclick: () => pairScreen(true) }, 'Connect to another server'),
        h('button', { class: 'danger', onclick: async () => { await fetch('/local/unpair', { method: 'POST' }); pairScreen(); } }, 'Disconnect'))),
    card(h('h3', {}, 'Assistant'),
      sw('Web search', 'Let the AI search the internet and read web pages.', 'web'),
      sw('Email access', 'Let the AI use your Gmail in chats (read, drafts; sending always asks you).', 'email'),
      sw('Tasks & calendar access', 'Let the AI read and change your tasks, notes and calendar.', 'organizer'),
      sw('Auto-compress long chats', 'When the context fills up, older messages are summarized so the chat can go on.', 'autoCompress'), cl, comp),
    card(h('h3', {}, 'Read aloud'), sw('Read replies aloud', 'Every finished reply is spoken, in Arabic or English (detected per sentence).', 'autoRead'), rl, rate,
      h('div', { class: 'row' }, h('button', { onclick: () => Speech.speak('Hello, I will read the replies for you. مرحباً، سأقرأ لك الردود.') }, 'Test voice'), h('button', { onclick: () => Speech.stop() }, 'Stop')),
      h('p', { class: 'muted small' }, 'Voices come from Windows and Edge. For Arabic, add Arabic in Windows Settings > Time & language > Speech if no voice is found.')),
    card(h('h3', {}, 'Appearance'), h('div', { class: 'chips' }, ...[['system', 'System'], ['light', 'Light'], ['dark', 'Dark']].map(([k, v]) =>
      h('button', { class: 'chip' + (p.theme === k ? ' on' : ''), onclick: () => { p.theme = k; savePrefs(); applyTheme(); viewSettings(main); } }, v)))),
    card(h('h3', {}, 'About'), h('p', { class: 'small' }, 'LocalAI Bridge Desktop: the phone app\'s features for Windows. Part of V100-LLM.'))));
}
