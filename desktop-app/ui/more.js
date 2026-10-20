// LocalAI Bridge Desktop: the phone app's newer screens - deep research, voice notes, live meeting, projects and their
// knowledge, schedules & alerts, translator, language tutor, private vault, audit log - plus the personal profile and
// PC voices in Settings. Same server calls as the Android app.
'use strict';

const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
const enc = s => encodeURIComponent(s);
function poll(main, fn, ms) {             // re-run fn while this view is on screen
  const t = setInterval(() => { if (main._poll !== t) return clearInterval(t); fn(); }, ms);
  main._poll = t;
}
function deleteDialog(title, hasResult) {  // resolves to null (cancel), 'list' or 'chat'
  return new Promise(res => {
    const done = v => { closeModal(); res(v); };
    modal(h('div', {}, h('h3', {}, title),
      h('p', {}, hasResult ? 'Remove it from the list only, or also delete its chat and the saved .md file on the PC? That cannot be undone.' : 'It will be removed from the list.'),
      h('div', { class: 'row end' }, h('button', { onclick: () => done(null) }, 'Cancel'),
        hasResult ? h('button', { onclick: () => done('list') }, 'List only') : null,
        h('button', { class: 'danger', onclick: () => done(hasResult ? 'chat' : 'list') }, hasResult ? 'Delete with chat' : 'Delete'))));
  });
}
const openChat = id => { go('chat'); openSession(id); };

// ---------------------------------------------------------------- deep research
async function viewResearch(main) {
  const q = h('textarea', { rows: 3, placeholder: 'What should be researched?', dir: 'auto' });
  let depth = 'normal';
  const depthChips = h('div', { class: 'chips' });
  const drawDepth = () => depthChips.replaceChildren(...[['quick', 'Quick (~3 min)'], ['normal', 'Normal (~8 min)'], ['deep', 'Deep (~20 min)']].map(([k, l]) =>
    h('button', { class: 'chip' + (depth === k ? ' on' : ''), onclick: () => { depth = k; drawDepth(); } }, l)));
  drawDepth();
  const list = h('div', { class: 'list' });
  const load = async () => {
    let runs = [];
    try { runs = await api('/api/research'); } catch (e) { return fail(e); }
    list.replaceChildren(...runs.map(r => card(
      h('div', { class: 'row' }, h('b', { dir: 'auto', style: 'flex:1' }, r.question),
        r.status !== 'running' ? h('button', { class: 'mini', title: 'Delete', onclick: async () => {
          const how = await deleteDialog('Delete this research?', r.status === 'done'); if (!how) return;
          try { await api(`/api/research/${r.id}?with_chat=${how === 'chat'}`, { method: 'DELETE' }); if (how === 'chat') loadSessions(); load(); } catch (e) { fail(e); } } }, '🗑') : null),
      r.status === 'running' ? [bar(0.5), h('div', { class: 'small muted' }, r.progress)]
        : r.status === 'done' ? h('button', { class: 'link', onclick: () => openChat(r.session_id) }, `✓ Report ready · ${r.sources} sources · open`)
        : h('div', { class: 'small err' }, '✗ ' + r.error))));
  };
  main.replaceChildren(page('Deep research',
    h('p', { class: 'muted' }, 'The PC searches the web, reads the pages, cross-checks them and writes a report with numbered sources. It runs in the background; the report opens as a chat.'),
    card(q, depthChips, h('button', { class: 'primary', onclick: async () => {
      if (!q.value.trim()) return;
      try { await api('/api/research', { method: 'POST', body: { question: q.value.trim(), depth } }); q.value = ''; toast('Research started'); load(); } catch (e) { fail(e); }
    } }, 'Start research')), list));
  load(); poll(main, load, 5000);
}

// ---------------------------------------------------------------- voice notes (record here or upload a file)
const Rec = { rec: null, chunks: [], started: 0 };
async function viewNotes(main) {
  const p = S.prefs;
  const status = h('h2', {}, Rec.rec ? '● Recording' : 'Ready');
  const list = h('div', { class: 'list' });
  const upload = async (blob, name) => {
    const f = new FormData(); f.append('file', blob, name); f.append('device', p.notesGpu ? 'gpu' : 'cpu'); f.append('add_tasks', String(p.notesTasks !== false));
    try { await api('/api/notes/voice', { method: 'POST', form: f }); toast('Uploaded - the notes will be ready soon'); load(); } catch (e) { fail(e); }
  };
  const recBtn = h('button', { class: 'primary big', onclick: async () => {
    if (Rec.rec) { Rec.rec.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      Rec.chunks = []; Rec.started = Date.now();
      Rec.rec = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      Rec.rec.ondataavailable = e => e.data.size && Rec.chunks.push(e.data);
      Rec.rec.onstop = () => {   // fires after the last data: the file is complete before it is sent
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(Rec.chunks, { type: 'audio/webm' }); Rec.rec = null;
        if (blob.size > 2000) upload(blob, `note-${Date.now()}.webm`); else toast('The recording was too short');
        if (S.view === 'notes') viewNotes(main);
      };
      Rec.rec.start(1000); viewNotes(main);
    } catch (e) { fail(new Error('Microphone: ' + e.message)); }
  } }, Rec.rec ? '■ Stop and make notes' : '🎙 Start recording');
  const filePick = h('input', { type: 'file', accept: 'audio/*,video/*', class: 'hidden', onchange: e => { const f = e.target.files[0]; if (f) upload(f, f.name); e.target.value = ''; } });
  const sw = (label, desc, key, def) => h('label', { class: 'setting' }, h('input', { type: 'checkbox', checked: p[key] ?? def, onchange: e => { p[key] = e.target.checked; savePrefs(); } }),
    h('div', {}, h('b', {}, label), h('div', { class: 'muted small' }, desc)));
  const load = async () => {
    if (Rec.rec) status.textContent = '● Recording  ' + mmss((Date.now() - Rec.started) / 1000);
    let jobs = [];
    try { jobs = await api('/api/notes/voice'); } catch { return; }
    list.replaceChildren(...jobs.map(j => card(
      h('div', { class: 'row' }, h('b', { dir: 'auto', style: 'flex:1' }, j.title || 'Voice note'),
        j.status !== 'running' ? h('button', { class: 'mini', title: 'Delete', onclick: async () => {
          const how = await deleteDialog('Delete this voice note?', j.status === 'done'); if (!how) return;
          try { await api(`/api/notes/voice/${j.id}?with_chat=${how === 'chat'}`, { method: 'DELETE' }); if (how === 'chat') loadSessions(); load(); } catch (e) { fail(e); } } }, '🗑') : null),
      j.status === 'running' ? [bar(0.5), h('div', { class: 'small muted' }, j.progress)]
        : j.status === 'done' ? h('button', { class: 'link', onclick: () => openChat(j.session_id) }, '✓ Notes ready' + (j.tasks_added ? ` · ${j.tasks_added} tasks added` : '') + ' · open')
        : h('div', { class: 'small err' }, '✗ ' + j.error))));
  };
  main.replaceChildren(page('Voice notes',
    h('p', { class: 'muted' }, 'Record a meeting, lecture or idea (or upload an audio file). The PC writes the transcript (Arabic or English), a summary, decisions and action items.'),
    card(status, h('div', { class: 'row' }, recBtn, h('button', { onclick: () => filePick.click() }, '⬆ Upload an audio file'), filePick),
      sw('Transcribe on the GPU (faster)', 'Off: on the CPU, the chat model stays loaded. On: the chat model is unloaded for a moment.', 'notesGpu', false),
      sw('Add action items to my tasks', '', 'notesTasks', true)), list));
  load(); poll(main, load, 2000);
}

// ---------------------------------------------------------------- live meeting (20-second WAV pieces while it runs)
const Live = { id: '', ctx: null, stream: null, node: null, buf: [], idx: 0, lines: [], status: '', sending: 0 };
function wavOf(samples, rate = 16000) {
  const b = new ArrayBuffer(44 + samples.length * 2), v = new DataView(b);
  const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); w(8, 'WAVEfmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, 'data'); v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, s)) * 0x7fff, true));
  return new Blob([b], { type: 'audio/wav' });
}
async function liveFlush(final = false) {
  const n = Live.buf.reduce((a, x) => a + x.length, 0);
  if (!n || (!final && n < 16000 * 20)) return;
  const all = new Float32Array(n); let o = 0; for (const x of Live.buf) { all.set(x, o); o += x.length; }
  Live.buf = [];
  if (n < 16000) return;
  const idx = Live.idx++, f = new FormData();
  f.append('file', wavOf(all), `piece_${idx}.wav`); f.append('idx', String(idx)); f.append('offset', String(idx * 20));
  Live.sending++;
  for (let i = 0; i < 5; i++) { try { await api(`/api/live/${Live.id}/chunk`, { method: 'POST', form: f }); break; } catch { await new Promise(r => setTimeout(r, 3000)); } }
  Live.sending--;
}
async function viewLive(main) {
  const p = S.prefs;
  const lines = h('div', { class: 'list' }), state = h('div', { class: 'row' });
  const q = h('input', { placeholder: 'Ask about the meeting', dir: 'auto', style: 'flex:1' }), ans = h('div', { class: 'pre', dir: 'auto' });
  const draw = () => {
    lines.replaceChildren(...Live.lines.slice(-120).map(l => h('div', { dir: 'auto' }, h('span', { class: 'muted small' }, mmss(l.t) + '  '), l.text)));
  };
  const start = async () => {
    try {
      Live.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const { id } = await api('/api/live/start', { method: 'POST', body: { lang: p.liveLang || '' } });
      Object.assign(Live, { id, idx: 0, buf: [], lines: [], status: 'live' });
      Live.ctx = new AudioContext({ sampleRate: 16000 });
      const src = Live.ctx.createMediaStreamSource(Live.stream);
      Live.node = Live.ctx.createScriptProcessor(4096, 1, 1);
      Live.node.onaudioprocess = e => { Live.buf.push(new Float32Array(e.inputBuffer.getChannelData(0))); liveFlush(); };
      src.connect(Live.node); Live.node.connect(Live.ctx.destination);
      viewLive(main);
    } catch (e) { fail(new Error('Could not start: ' + e.message)); }
  };
  const stop = async () => {
    try { Live.node?.disconnect(); Live.stream?.getTracks().forEach(t => t.stop()); await Live.ctx?.close(); } catch {}
    await liveFlush(true);
    Live.status = 'finishing';
    try { await api(`/api/live/${Live.id}/stop`, { method: 'POST', body: { add_tasks: p.liveTasks !== false } }); } catch (e) { fail(e); }
    viewLive(main);
  };
  const refresh = async () => {
    if (!Live.id) return;
    try {
      const s = await api(`/api/live/${Live.id}?after=${Live.lines.length}`);
      Live.lines.push(...s.lines); if (Live.status !== 'live' || s.status !== 'live') Live.status = s.status;
      Live.result = s.result; draw();
      state.replaceChildren(h('b', { class: Live.status === 'live' ? 'err' : '' }, Live.status === 'live' ? '● Live' : Live.status === 'done' ? '✓ Done' : Live.status === 'error' ? '✗ ' + (s.result?.error || 'failed') : 'Writing the meeting notes…'),
        s.behind ? h('span', { class: 'muted small' }, ` transcribing ${s.behind} piece(s)…`) : null,
        Live.result?.session_id ? h('button', { class: 'link', onclick: () => openChat(Live.result.session_id) }, 'Open the meeting notes') : null);
    } catch {}
  };
  const idle = !Live.id || Live.status === 'done' || Live.status === 'error';
  main.replaceChildren(page('Live meeting',
    h('p', { class: 'muted' }, 'The transcript appears while the meeting runs (Arabic or English, 20-40 s behind; Whisper on the PC CPU, so the GPU stays with the chat model). Ask about it at any time; when you stop you get the summary, decisions and action items.'),
    idle ? card(h('div', { class: 'chips' }, ...[['', 'Auto language'], ['ar', 'العربية'], ['en', 'English']].map(([k, l]) =>
        h('button', { class: 'chip' + ((p.liveLang || '') === k ? ' on' : ''), onclick: () => { p.liveLang = k; savePrefs(); viewLive(main); } }, l))),
      h('label', { class: 'setting' }, h('input', { type: 'checkbox', checked: p.liveTasks !== false, onchange: e => { p.liveTasks = e.target.checked; savePrefs(); } }), h('b', {}, 'Add action items to my tasks')),
      h('button', { class: 'primary big', onclick: start }, '🎙 Start live meeting'))
      : card(state, Live.status === 'live' ? h('button', { class: 'danger', onclick: stop }, '■ Stop and make notes') : bar(0.5),
        h('div', { class: 'row' }, q, h('button', { onclick: async () => {
          if (!q.value.trim()) return; ans.textContent = 'Thinking…';
          try { ans.textContent = (await api(`/api/live/${Live.id}/ask`, { method: 'POST', body: { question: q.value.trim() } })).answer; } catch (e) { ans.textContent = ''; fail(e); }
        } }, 'Ask')), ans),
    idle && Live.result?.session_id ? h('button', { class: 'link', onclick: () => openChat(Live.result.session_id) }, 'Open the last meeting notes') : null,
    state, lines));
  draw(); refresh(); poll(main, refresh, 3000);
}

// ---------------------------------------------------------------- projects (+ knowledge files, named chats)
async function viewProjects(main) {
  let list = [];
  try { list = await api('/api/projects'); } catch (e) { return fail(e); }
  const edit = async p => {
    const name = h('input', { value: p.name || '', placeholder: 'Name' }), goal = h('textarea', { rows: 3, placeholder: 'Goal: what should be achieved?' }), notes = h('textarea', { rows: 5, placeholder: 'Notes (the AI adds progress here)' });
    goal.value = p.goal || ''; notes.value = p.notes || '';
    modal(h('div', {}, h('h3', {}, p.id ? 'Edit project' : 'New project'), name, goal, notes,
      h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Cancel'), h('button', { class: 'primary', onclick: async () => {
        if (!name.value.trim()) return;
        const body = { name: name.value.trim(), goal: goal.value, notes: notes.value };
        try { await api(p.id ? `/api/projects/${p.id}` : '/api/projects', { method: p.id ? 'PUT' : 'POST', body }); closeModal(); viewProjects(main); } catch (e) { fail(e); }
      } }, 'Save'))));
  };
  const addKnowledge = (p, files) => {
    const run = async () => {
      let ok = 0;
      for (const f of files) {
        const fd = new FormData(); fd.append('file', f, f.name); fd.append('description', '');
        toast(`Adding ${f.name}…`);
        try { await api(`/api/projects/${p.id}/knowledge`, { method: 'POST', form: fd }); ok++; } catch (e) { fail(e); }
      }
      if (ok) toast(`${ok} file(s) added to the project knowledge`);
      viewProjects(main);
    };
    run();
  };
  main.replaceChildren(page('Projects',
    h('div', { class: 'row' }, h('p', { class: 'muted', style: 'flex:1' }, 'A project has a goal, notes, knowledge files and a folder that all its chats share; the AI records progress so every new chat or scheduled run continues where the last one stopped.'),
      h('button', { class: 'primary', onclick: () => edit({}) }, '＋ New project')),
    ...list.map(p => {
      const pick = h('input', { type: 'file', multiple: true, class: 'hidden', onchange: e => { addKnowledge(p, [...e.target.files]); e.target.value = ''; } });
      const c = card(
        h('h3', { dir: 'auto' }, '📁 ' + p.name), h('div', { dir: 'auto' }, p.goal || '(no goal yet)'),
        h('details', {}, h('summary', {}, 'Notes'), h('div', { class: 'pre small', dir: 'auto' }, p.notes || '(none yet)')),
        h('div', { class: 'row' }, h('b', { style: 'flex:1' }, `Knowledge (${p.knowledge?.length || 0})`), pick, h('button', { onclick: () => pick.click() }, '＋ Add files')),
        !(p.knowledge || []).length ? h('div', { class: 'muted small' }, 'PDFs, Word, PowerPoint, Excel, text or code files and figures the AI should use in every chat of this project. You can also drop files here.') : null,
        ...(p.knowledge || []).map(k => h('div', { class: 'row' },
          h('span', {}, k.kind === 'figure' ? '🖼' : k.kind === 'text' ? '📄' : '📎'),
          h('div', { style: 'flex:1' }, h('div', {}, k.name), h('div', { class: 'muted small', dir: 'auto' },
            k.kind === 'figure' ? (k.description || 'figure · add a description so the AI knows what it shows')
              : k.kind === 'text' ? `${k.chars.toLocaleString()} characters` + (k.description ? ' · ' + k.description : '') : 'no readable text (e.g. scanned PDF)')),
          h('button', { class: 'mini', title: 'Describe', onclick: async () => {
            const d = await promptBox(k.name, k.description, { multiline: true, label: k.kind === 'figure' ? 'What the figure shows (the AI cannot see figures here; this is what it knows)' : 'What the file is for (optional)' });
            if (d == null) return;
            try { await api(`/api/projects/${p.id}/knowledge/${enc(k.name)}`, { method: 'PUT', body: { title: d.trim() } }); viewProjects(main); } catch (e) { fail(e); }
          } }, '✎'),
          h('button', { class: 'mini', title: 'Remove', onclick: async () => {
            if (!await confirmBox('Remove this file?', k.name, 'Remove', true)) return;
            try { await api(`/api/projects/${p.id}/knowledge/${enc(k.name)}`, { method: 'DELETE' }); viewProjects(main); } catch (e) { fail(e); }
          } }, '🗑'))),
        h('b', {}, `Chats (${p.chats.length})`),
        ...p.chats.slice(0, 20).map(ch => h('div', { class: 'row' },
          h('button', { class: 'link', style: 'flex:1;text-align:left', dir: 'auto', onclick: () => openChat(ch.id) }, '• ' + ch.title),
          h('button', { class: 'mini', title: 'Rename', onclick: async () => {
            const t = await promptBox('Rename chat', ch.title.replace(/^📁 /, '')); if (!t?.trim()) return;
            try { await api(`/api/sessions/${ch.id}`, { method: 'PATCH', body: { title: '📁 ' + t.trim() } }); loadSessions(); viewProjects(main); } catch (e) { fail(e); }
          } }, '✎'))),
        h('div', { class: 'row' },
          h('button', { class: 'primary', onclick: async () => {
            const t = await promptBox(`New chat in "${p.name}"`, '', { label: 'Chat name (e.g. Literature review, Methods, Figures)' }); if (t == null) return;
            try { const s = await api(`/api/projects/${p.id}/chat`, { method: 'POST', body: { title: t.trim() } }); loadSessions(); openChat(s.id); } catch (e) { fail(e); }
          } }, 'New chat'),
          h('button', { onclick: async () => {
            const at = await promptBox(`Work on "${p.name}" every day`, '21:00', { label: 'Time (HH:MM)' }); if (!at) return;
            const prompt = 'Continue working on this project: read the goal and the notes, do the next useful step, save results in the project folder, and record progress and the next steps with project_note.';
            try {
              await api('/api/schedules', { method: 'POST', body: { name: 'Project: ' + p.name, prompt, kind: 'daily', at, every_min: 60, web: true,
                email: false, organizer: true, enabled: true, project_id: p.id } });
              toast('Scheduled daily at ' + at + ' (Schedules & alerts)');
            } catch (e) { fail(e); }
          } }, 'Daily work'),
          h('button', { onclick: () => edit(p) }, 'Edit'),
          h('button', { class: 'danger', onclick: async () => {
            if (!await confirmBox('Delete project?', 'Its chats and files stay.', 'Delete', true)) return;
            try { await api(`/api/projects/${p.id}`, { method: 'DELETE' }); viewProjects(main); } catch (e) { fail(e); }
          } }, 'Delete project')));
      c.addEventListener('dragover', e => e.preventDefault());
      c.addEventListener('drop', e => { e.preventDefault(); addKnowledge(p, [...e.dataTransfer.files]); });
      return c;
    })));
}

// ---------------------------------------------------------------- schedules & temperature alerts
async function viewSchedules(main) {
  let list = [], al = { gpu_c: 0, cpu_c: 0 };
  try { [list, al] = await Promise.all([api('/api/schedules'), api('/api/alerts')]); } catch (e) { return fail(e); }
  const edit = async s => {
    const name = h('input', { value: s.name || '', placeholder: 'Name' }), prompt = h('textarea', { rows: 4, placeholder: 'What the PC should do, e.g. "Summarize my unread email"', dir: 'auto' });
    prompt.value = s.prompt || '';
    const kind = h('select', {}, h('option', { value: 'daily', selected: s.kind !== 'every' }, 'Daily at'), h('option', { value: 'every', selected: s.kind === 'every' }, 'Every N minutes'));
    const at = h('input', { value: s.at || '08:00', style: 'width:80px' }), every = h('input', { type: 'number', value: s.every_min || 60, style: 'width:80px' });
    const box = (label, k) => { const i = h('input', { type: 'checkbox', checked: !!s[k] }); i.dataset.k = k; return h('label', { class: 'row' }, i, label); };
    const checks = [box('Web search', 'web'), box('Email', 'email'), box('Tasks & calendar', 'organizer'), box('Enabled', 'enabled')];
    if (s.enabled === undefined) checks[3].querySelector('input').checked = true;
    modal(h('div', {}, h('h3', {}, s.id ? 'Edit schedule' : 'New schedule'), name, prompt, h('div', { class: 'row' }, kind, at, every, h('span', { class: 'muted small' }, '(time for daily, minutes for every)')), ...checks,
      h('div', { class: 'row end' }, h('button', { onclick: closeModal }, 'Cancel'), h('button', { class: 'primary', onclick: async () => {
        const body = { name: name.value.trim() || 'Schedule', prompt: prompt.value.trim(), kind: kind.value, at: at.value, every_min: +every.value || 60 };
        checks.forEach(c => { const i = c.querySelector('input'); body[i.dataset.k] = i.checked; });
        if (!body.prompt) return;
        try { await api(s.id ? `/api/schedules/${s.id}` : '/api/schedules', { method: s.id ? 'PUT' : 'POST', body }); closeModal(); viewSchedules(main); } catch (e) { fail(e); }
      } }, 'Save'))));
  };
  const g = h('input', { type: 'number', value: al.gpu_c || '', placeholder: 'off', style: 'width:80px' }), c = h('input', { type: 'number', value: al.cpu_c || '', placeholder: 'off', style: 'width:80px' });
  main.replaceChildren(page('Schedules & alerts',
    h('div', { class: 'row' }, h('p', { class: 'muted', style: 'flex:1' }, 'A prompt the PC runs by itself (daily at a time, or every N minutes) in its own chat, with the access you give it.'),
      h('button', { class: 'primary', onclick: () => edit({}) }, '＋ New schedule')),
    ...list.map(s => card(h('div', { class: 'row' }, h('b', { style: 'flex:1' }, (s.enabled ? '' : '⏸ ') + s.name),
        h('button', { class: 'mini', title: 'Run now', onclick: async () => { try { await api(`/api/schedules/${s.id}/run`, { method: 'POST', body: {} }); toast('Started'); } catch (e) { fail(e); } } }, '▶'),
        h('button', { class: 'mini', title: 'Edit', onclick: () => edit(s) }, '✎'),
        h('button', { class: 'mini', title: 'Delete', onclick: async () => { if (await confirmBox('Delete this schedule?', s.name, 'Delete', true)) { await api(`/api/schedules/${s.id}`, { method: 'DELETE' }).catch(fail); viewSchedules(main); } } }, '🗑')),
      h('div', { class: 'small', dir: 'auto' }, s.prompt),
      h('div', { class: 'muted small' }, (s.kind === 'every' ? `every ${s.every_min} min` : `daily at ${s.at}`) + (s.next_run ? ' · next ' + fmtTime(s.next_run) : '') + (s.last_status ? ' · last: ' + s.last_status : '')),
      s.session_id ? h('button', { class: 'link', onclick: () => openChat(s.session_id) }, 'Open its chat') : null)),
    card(h('h3', {}, '🌡 Temperature alerts'), h('p', { class: 'muted small' }, 'A notification when the GPU or CPU passes your limit (checked every 30 s on the PC). Empty = off.'),
      h('div', { class: 'row' }, 'GPU °C', g, 'CPU °C', c, h('button', { onclick: async () => {
        try { await api('/api/alerts', { method: 'POST', body: { gpu_c: +g.value || 0, cpu_c: +c.value || 0 } }); toast('Saved'); } catch (e) { fail(e); } } }, 'Save')))));
}

// ---------------------------------------------------------------- translator
function viewTranslate(main) {
  let to = S.prefs.trTo || 'en';
  const src = h('textarea', { rows: 6, dir: 'auto', placeholder: 'Text to translate' }), out = h('div', { class: 'pre card', dir: 'auto' });
  const go2 = async () => {
    if (!src.value.trim()) return; out.textContent = 'Translating…';
    try { const r = await api('/api/translate', { method: 'POST', body: { text: src.value, to } }); out.textContent = r.text; } catch (e) { out.textContent = ''; fail(e); }
  };
  const chips = h('div', { class: 'chips' });
  const draw = () => chips.replaceChildren(...[['en', 'To English'], ['ar', 'إلى العربية']].map(([k, l]) =>
    h('button', { class: 'chip' + (to === k ? ' on' : ''), onclick: () => { to = k; S.prefs.trTo = k; savePrefs(); draw(); } }, l)));
  draw();
  main.replaceChildren(page('Translator', card(chips, src, h('div', { class: 'row' }, h('button', { class: 'primary', onclick: go2 }, 'Translate'),
    h('button', { onclick: () => out.textContent && Speech.speak(out.textContent) }, '🔊 Read'), h('button', { onclick: () => navigator.clipboard.writeText(out.textContent) }, 'Copy'))), out));
}

// ---------------------------------------------------------------- language tutor (speech recognition in Edge)
const Tutor = { lang: 'en', level: 'intermediate', mode: 'talk', chat: [], sentence: '', result: null, heard: '', reading: false };
function recognizer(lang, onPartial, onFinal) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) { toast('Speech recognition is not available in this window'); return null; }
  const r = new R(); r.lang = lang === 'ar' ? 'ar-EG' : 'en-US'; r.interimResults = true; r.continuous = false;
  let last = '';
  r.onresult = e => { last = [...e.results].map(x => x[0].transcript).join(' '); onPartial && onPartial(last); };
  r.onend = () => onFinal(last); r.onerror = () => {};
  r.start(); return r;
}
const normWord = w => w.toLowerCase().replace(/[ً-ْٰـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/[^\p{L}\p{N}]/gu, '');
function followWords(words, heard) {
  const t = words.map(normWord); let pos = 0;
  for (const hw of heard.split(/\s+/).map(normWord).filter(Boolean)) {
    for (let j = pos; j < Math.min(pos + 3, t.length); j++) if (t[j] === hw || (hw.length > 3 && t[j].length > 3 && t[j].startsWith(hw.slice(0, 3)) && Math.abs(t[j].length - hw.length) <= 2)) { pos = j + 1; break; }
  }
  return pos;
}
function viewTutor(main) {
  const T = Tutor, isAr = s => /[؀-ۿ]/.test(s);
  const chips = (opts, cur, set) => h('div', { class: 'chips' }, ...opts.map(([k, l]) => h('button', { class: 'chip' + (cur === k ? ' on' : ''), onclick: () => { set(k); viewTutor(main); } }, l)));
  const body = h('div', { class: 'list' });
  const newSentence = async () => {
    T.result = null; T.heard = ''; T.sentence = '…'; viewTutor(main);
    try { T.sentence = (await api('/api/tutor/sentence', { method: 'POST', body: { lang: T.lang, level: T.level } })).sentence; } catch (e) { T.sentence = ''; fail(e); }
    viewTutor(main);
  };
  const readIt = () => {
    const sl = isAr(T.sentence) ? 'ar' : 'en';
    Speech.stop(); T.result = null; T.heard = ''; T.reading = true; viewTutor(main);
    recognizer(sl, txt => { T.heard = txt; viewTutor(main); }, async txt => {
      T.reading = false; T.heard = txt;
      if (!txt) { toast('I did not hear anything - try again'); return viewTutor(main); }
      try { T.result = await api('/api/tutor/pronounce', { method: 'POST', body: { lang: sl, target: T.sentence, heard: txt } }); } catch (e) { fail(e); }
      viewTutor(main);
    });
  };
  if (T.mode === 'talk') {
    body.append(...T.chat.map(m => card(h('div', { dir: 'auto' }, (m.mine ? '🗣 ' : '🎓 ') + m.text),
      m.turn ? [...(m.turn.corrections || []).map(c => h('div', {}, h('b', { class: 'err' }, `✗ ${c.wrong}  →  ✓ ${c.right}`), c.why ? h('div', { class: 'muted small' }, c.why) : null)),
        m.turn.better ? h('div', { class: 'small', style: 'color:#2E9D57' }, 'Better: ' + m.turn.better) : null,
        m.turn.score != null ? h('div', { class: 'muted small' }, `Score: ${m.turn.score}/10`) : null,
        h('button', { class: 'link', onclick: () => Speech.speak(m.text) }, '▶ Hear again')] : null)));
    const say = async text => {
      if (!text.trim()) return;
      T.chat.push({ mine: true, text }); viewTutor(main);
      try {
        const t = await api('/api/tutor/turn', { method: 'POST', body: { lang: T.lang, level: T.level, text, history: T.chat.slice(0, -1).map(m => ({ role: m.mine ? 'user' : 'assistant', content: m.text })) } });
        T.chat.push({ mine: false, text: t.reply, turn: t }); Speech.speak(t.reply);
      } catch (e) { fail(e); }
      viewTutor(main);
    };
    const typed = h('input', { placeholder: 'Or type your answer', dir: 'auto', style: 'flex:1', onkeydown: e => { if (e.key === 'Enter') say(e.target.value); } });
    body.append(h('div', { class: 'row' }, h('button', { class: 'primary big', onclick: () => { Speech.stop(); recognizer(T.lang, null, say); } }, T.chat.length ? '🎤 Answer' : '🎤 Start talking'), typed,
      T.chat.length ? h('button', { onclick: () => { T.chat = []; viewTutor(main); } }, 'New conversation') : null));
  } else {
    const own = h('input', { placeholder: 'Or type your own word or sentence', dir: 'auto', style: 'flex:1' });
    body.append(h('div', { class: 'row' }, own, h('button', { onclick: () => {
      if (!own.value.trim()) return; T.sentence = own.value.trim(); T.result = null; T.heard = '';
      Speech.speak(T.sentence);
      const wait = setInterval(() => { if (!speechSynthesis.speaking) { clearInterval(wait); readIt(); } }, 300);   // read it to me, then listen
    } }, '▶ Say it')));
    if (T.sentence) {
      const words = T.sentence.split(/\s+/).filter(Boolean), done = T.result ? 0 : followWords(words, T.heard);
      const marks = T.result?.words?.length === words.length ? T.result.words : null;
      body.append(card(h('div', { class: 'row', dir: 'auto', style: 'font-size:26px;gap:12px' }, ...words.map((w, i) => h('span', {
        style: 'cursor:pointer;color:' + (marks ? (marks[i].ok ? '#2E9D57' : 'var(--bad)') : i < done ? '#2E9D57' : T.reading && i === done ? 'var(--accent)' : 'inherit') + (T.reading && i === done ? ';font-weight:700' : ''),
        onclick: () => Speech.speak(w) }, w)))),
        T.reading ? h('div', { style: 'color:var(--accent)' }, '🎤 Listening… ' + T.heard) : null,
        h('div', { class: 'row' }, h('button', { onclick: () => Speech.speak(T.sentence) }, '▶ Hear it'), h('button', { class: 'primary', onclick: readIt, disabled: T.reading }, '🎤 Read it'), h('button', { onclick: newSentence }, 'Next')));
    }
    if (T.result) body.append(card(h('h3', { style: `color:${T.result.score >= 85 ? '#2E9D57' : T.result.score >= 60 ? '#C27C0E' : 'var(--bad)'}` }, `Score: ${T.result.score}%`),
      h('div', { class: 'muted small' }, 'Click a word to hear it.'), T.result.tips ? h('div', { class: 'pre', dir: 'auto' }, T.result.tips) : null));
  }
  main.replaceChildren(page('Language tutor',
    chips([['en', 'English'], ['ar', 'العربية']], T.lang, k => { T.lang = k; T.chat = []; T.sentence = ''; T.result = null; }),
    chips([['beginner', 'Beginner'], ['intermediate', 'Intermediate'], ['advanced', 'Advanced']], T.level, k => { T.level = k; }),
    chips([['talk', 'Conversation'], ['say', 'Pronunciation']], T.mode, k => { T.mode = k; if (k === 'say' && !T.sentence) setTimeout(newSentence); }),
    h('p', { class: 'muted small' }, T.mode === 'talk' ? 'Speak (or type), and the tutor answers, corrects your mistakes and suggests a more natural way to say it.' : 'Read the sentence aloud: it stays on screen and each word lights up as you say it.'),
    body));
}

// ---------------------------------------------------------------- private vault (the key is the phone's recovery code)
async function viewVault(main) {
  if (!S.vaultKey) {
    const code = h('input', { type: 'password', placeholder: 'Recovery code (xxxx-xxxx-…)', style: 'flex:1' });
    main.replaceChildren(page('Private vault',
      h('p', { class: 'muted' }, 'Private chats are encrypted on the PC with a key that the phone holds behind your fingerprint. To open them here, enter the vault\'s recovery code (shown on the phone when the vault was created). The key stays only in this window\'s memory and is forgotten when you lock it or close the app.'),
      card(h('div', { class: 'row' }, code, h('button', { class: 'primary', onclick: async () => {
        const hex = code.value.replace(/[^0-9a-fA-F]/g, '').toLowerCase();
        if (hex.length !== 64) return toast('That is not a valid recovery code');
        const key = btoa(String.fromCharCode(...hex.match(/../g).map(x => parseInt(x, 16))));
        S.vaultKey = key;
        try { await api('/api/vault/unlock', { method: 'POST', body: {} }); viewVault(main); }
        catch (e) { S.vaultKey = null; fail(new Error('The PC refused this key (it does not match the vault)')); }
      } }, '🔓 Unlock'))),
      h('p', { class: 'muted small' }, 'No vault yet? Create it in the phone app (Private vault): it needs the phone\'s fingerprint.')));
    return;
  }
  let list = [];
  try { list = await api('/api/vault/sessions'); } catch (e) { fail(e); }
  main.replaceChildren(page('Private vault',
    h('p', { class: 'muted' }, 'Unlocked in this window. Chats here are never used for memories. Files you attach are stored on the PC like other uploads (not encrypted).'),
    h('div', { class: 'row' }, h('button', { class: 'primary', onclick: async () => {
      try { const s = await api('/api/vault/sessions', { method: 'POST', body: {} }); go('chat'); await openSession(s.id); S.vaultChat = true; renderHeader(); } catch (e) { fail(e); }
    } }, 'New private chat'), h('button', { onclick: () => { S.vaultKey = null; S.vaultChat = false; viewVault(main); } }, '🔒 Lock')),
    ...list.map(s => card(h('button', { class: 'link', style: 'text-align:left', dir: 'auto', onclick: async () => { go('chat'); await openSession(s.id); S.vaultChat = true; renderHeader(); } }, s.title))),
    !list.length ? h('p', { class: 'muted' }, 'No private chats yet.') : null));
}
async function newTempChat() {
  try { const s = await api('/api/sessions/temp', { method: 'POST', body: {} }); go('chat'); await openSession(s.id); S.tempChat = true; renderHeader(); }
  catch (e) { fail(e); }
}

// ---------------------------------------------------------------- audit log
async function viewAudit(main, q = '') {
  let rows = [];
  try { rows = await api('/api/audit?limit=300' + (q ? '&q=' + enc(q) : '')); } catch (e) { return fail(e); }
  const search = h('input', { type: 'search', placeholder: 'Search the audit log', value: q, onkeydown: e => { if (e.key === 'Enter') viewAudit(main, e.target.value); } });
  main.replaceChildren(page('Audit log', h('p', { class: 'muted' }, 'Every tool action the AI took - code, files, email, OCR, images, schedules - with time, chat, approval and result.'), search,
    h('div', { class: 'list' }, ...rows.map(r => card(
      h('div', { class: 'row' }, h('b', {}, (r.ok ? '' : '✗ ') + r.tool), h('span', { class: 'muted small', style: 'flex:1' }, fmtTime(r.ts) + ' · ' + r.approval + (r.source === 'schedule' ? ' · scheduled' : '')),
        r.session_id ? h('button', { class: 'link small', onclick: () => openChat(r.session_id) }, r.chat || 'chat') : null),
      h('div', { class: 'small', dir: 'auto' }, r.summary),
      r.result ? h('details', {}, h('summary', { class: 'small muted' }, 'result'), h('div', { class: 'pre small' }, r.result)) : null)))));
}

// ---------------------------------------------------------------- Settings additions: personal profile, PC voices
async function profileCard() {
  const box = card(h('h3', {}, '👤 Personal profile'), h('p', { class: 'muted small' }, 'Loading…'));
  (async () => {
    let p;
    try { p = await api('/api/profile'); } catch { box.replaceChildren(h('h3', {}, '👤 Personal profile'), h('p', { class: 'muted small' }, 'Not available on this server.')); return; }
    const txt = h('textarea', { rows: 10, dir: 'auto' }); txt.value = p.text || '';
    const on = h('input', { type: 'checkbox', checked: p.enabled === 1, onchange: async e => { try { await api('/api/profile', { method: 'PUT', body: { enabled: e.target.checked } }); } catch (er) { fail(er); } } });
    box.replaceChildren(h('h3', {}, '👤 Personal profile'),
      h('p', { class: 'muted small' }, 'The AI learns how you write and what you work on from your chats, notes and memories (never private or temporary chats), refreshes it every night and adds it to every chat. You can read, edit or turn it off.'),
      h('label', { class: 'setting' }, on, h('b', {}, 'Use my profile in chats')), p.building ? h('p', { class: 'muted small' }, 'Building your profile…') : null, txt,
      h('div', { class: 'row' }, h('button', { onclick: async () => { try { await api('/api/profile', { method: 'PUT', body: { enabled: on.checked, text: txt.value } }); toast('Profile saved'); } catch (e) { fail(e); } } }, 'Save'),
        h('button', { onclick: async () => { try { await api('/api/profile/rebuild', { method: 'POST', body: {} }); toast('Rebuilding the profile on the PC…'); } catch (e) { fail(e); } } }, 'Rebuild now')));
  })();
  return box;
}
async function voicesCard() {
  const p = S.prefs, box = card(h('h3', {}, '🗣 PC voices'));
  let voices = [];
  try { voices = await api('/api/tts/voices'); } catch {}
  const sel = (lang, key) => h('select', { onchange: e => { p[key] = e.target.value; savePrefs(); } },
    h('option', { value: '' }, 'Windows / Edge voice'),
    ...voices.filter(v => (v.lang || v.id || '').toLowerCase().startsWith(lang)).map(v => h('option', { value: v.id, selected: p[key] === v.id }, 'PC: ' + (v.name || v.id))));
  box.append(h('p', { class: 'muted small' }, 'Natural offline neural voices made on the PC (Piper) instead of the Windows voices, per language.'),
    voices.length ? [h('div', { class: 'row' }, 'Arabic', sel('ar', 'pcArabic')), h('div', { class: 'row' }, 'English', sel('en', 'pcEnglish'))]
      : h('p', { class: 'muted small' }, 'No PC voices installed (ocr\\setup-ocr.bat installs them).'));
  return box;
}

// PC voice playback: replies are spoken by Piper on the PC when a PC voice is chosen for that language
(() => {
  const base = Speech.speak.bind(Speech), stop = Speech.stop.bind(Speech);
  let audio = null, gen = 0;
  Speech.stop = () => { gen++; if (audio) { audio.pause(); audio = null; } stop(); };
  Speech.speak = async function (text, key = null) {
    const p = S.prefs;
    if (!p.pcArabic && !p.pcEnglish) return base(text, key);
    Speech.stop(); const my = ++gen; this.key = key; window.dispatchEvent(new Event('speech'));
    for (const [ar, s] of this.segments(this.clean(text))) {
      if (my !== gen) return;
      const voice = ar ? p.pcArabic : p.pcEnglish;
      if (!voice) { await new Promise(res => { const u = new SpeechSynthesisUtterance(s); u.lang = ar ? 'ar-SA' : 'en-US'; u.rate = p.rate || 1; const v = this.voice(ar); if (v) u.voice = v; u.onend = u.onerror = res; speechSynthesis.speak(u); }); continue; }
      try {
        const r = await api('/api/tts', { method: 'POST', body: { text: s, voice }, raw: true });
        if (!r.ok || my !== gen) continue;
        audio = new Audio(URL.createObjectURL(await r.blob())); audio.playbackRate = p.rate || 1;
        await new Promise(res => { audio.onended = audio.onerror = res; audio.play().catch(res); });
      } catch {}
    }
    if (my === gen) { this.key = null; window.dispatchEvent(new Event('speech')); }
  };
})();

// ---------------------------------------------------------------- model shop (GGUF models from Hugging Face)
const Shop = { q: '', results: [], open: null, mmproj: null };
const gbs = b => (b / 1e9).toFixed(1) + ' GB';
const fitCol = f => f === 'gpu' ? '#2E9D57' : f === 'tight' ? '#C27C0E' : 'var(--bad)';
async function viewShop(main) {
  const S2 = Shop;
  const prog = h('div'), installedBox = h('div', { class: 'list' });
  const q = h('input', { type: 'search', placeholder: 'Search Hugging Face, e.g. Qwen3 8B, Gemma 3, Llama', value: S2.q, style: 'flex:1',
    onkeydown: e => { if (e.key === 'Enter') doSearch(); } });
  const body = h('div', { class: 'list' });
  async function doSearch() {
    S2.q = q.value.trim(); if (!S2.q) return;
    body.replaceChildren(h('span', { class: 'spin' })); S2.open = null;
    try { S2.results = await api('/api/v100/shop/search?q=' + enc(S2.q)); } catch (e) { S2.results = []; fail(e); }
    S2.searched = true;
    draw();
  }
  async function openRepo(repo) {
    body.replaceChildren(h('span', { class: 'spin' }));
    try { S2.open = await api('/api/v100/shop/files?repo=' + enc(repo)); S2.mmproj = null; } catch (e) { fail(e); }
    draw();
  }
  async function install(c) {
    const f = S2.open, mm = f.mmproj.find(x => x.name === S2.mmproj);
    const lines = c.parts.map(p => `• ${p.name} (${gbs(p.size)})`).concat(mm ? [`• ${mm.name} (${gbs(mm.size)}, vision)`] : []);
    if (!await confirmBox('Download this model?', `From huggingface.co/${f.repo}\n${lines.join('\n')}\n\nTotal ${gbs(c.size + (mm?.size || 0))} onto the PC (V100-LLM\models). Each file is checked against its SHA-256 from Hugging Face.\n${c.fit_text}` + (f.license ? `\nLicence: ${f.license}` : ''), 'Download')) return;
    try { const r = await api('/api/v100/shop/install', { method: 'POST', body: { repo: f.repo, key: c.key, mmproj: mm?.name || null } }); toast('Downloading ' + r.name + '…'); } catch (e) { fail(e); }
  }
  function draw() {
    if (S2.open) {
      const f = S2.open;
      body.replaceChildren(h('div', { class: 'row' }, h('button', { onclick: () => { S2.open = null; draw(); } }, '← Results'), h('h3', {}, f.repo)),
        f.gated ? h('p', { class: 'err small' }, '🔒 Gated: on the PC run `hf auth login` once and accept access on the model\'s Hugging Face page.') : null,
        f.mmproj.length ? h('div', { class: 'chips' }, h('span', { class: 'small' }, 'Vision:'),
          h('button', { class: 'chip' + (!S2.mmproj ? ' on' : ''), onclick: () => { S2.mmproj = null; draw(); } }, 'No vision'),
          ...f.mmproj.slice(0, 3).map(m => h('button', { class: 'chip' + (S2.mmproj === m.name ? ' on' : ''), onclick: () => { S2.mmproj = m.name; draw(); } }, `${m.name.replace(/\.gguf$/, '')} ${gbs(m.size)}`))) : null,
        !f.choices.length ? h('p', {}, 'No GGUF files in this repository.') : null,
        ...f.choices.map(c => card(h('div', { class: 'row' }, h('div', { style: 'flex:1' },
          h('b', {}, `${c.quant || c.key.split('/').pop()} · ${gbs(c.size)}` + (c.parts.length > 1 ? ` (${c.parts.length} parts)` : '')),
          h('div', { class: 'small', style: 'color:' + fitCol(c.fit) }, c.fit_text)), h('button', { onclick: () => install(c) }, 'Get')))));
    } else {
      if (S2.searched && !S2.results.length) return body.replaceChildren(h('p', { class: 'muted' }, `No GGUF models found for "${S2.q}". Try fewer words, e.g. just the model name.`));
      body.replaceChildren(...S2.results.map(r => card(h('button', { class: 'link', style: 'text-align:left', onclick: () => openRepo(r.repo) }, h('b', {}, r.repo)),
        h('div', { class: 'muted small' }, `⬇ ${r.downloads.toLocaleString()} · ♥ ${r.likes}` + (r.license ? ' · ' + r.license : '') + (r.gated ? ' · 🔒 gated (sign in on the PC)' : '')))));
    }
  }
  async function tick() {
    try {
      const p = await api('/api/v100/shop/progress');
      prog.replaceChildren(p.active ? card(h('div', {}, 'Downloading: ' + p.item), p.total ? [bar(p.done / p.total), h('div', { class: 'small muted' }, `${gbs(p.done)} of ${gbs(p.total)}`)] : bar(0.5))
        : p.error ? h('p', { class: 'err small' }, p.error) : null);
      if (tick.was && !p.active) loadInstalled();
      tick.was = p.active;
    } catch {}
  }
  async function loadInstalled() {
    let list = [];
    try { list = await api('/api/v100/shop/installed'); } catch {}
    installedBox.replaceChildren(list.length ? h('h3', {}, 'Installed from the shop') : null, ...list.map(m => h('div', { class: 'row' },
      h('div', { style: 'flex:1' }, h('div', {}, m.name), h('div', { class: 'muted small' }, gbs(m.size) + (m.installed ? ' · ready in Models' : ' · not fully downloaded'))),
      h('button', { class: 'danger', onclick: async () => {
        if (!await confirmBox('Remove ' + m.name + '?', `Deletes its files from the PC (${gbs(m.size)}) and removes it from Models. If it is loaded, it is unloaded first.`, 'Remove', true)) return;
        try { await api('/api/v100/shop/remove', { method: 'POST', body: { id: m.id } }); toast('Removed'); loadInstalled(); } catch (e) { fail(e); }
      } }, 'Remove'))));
  }
  main.replaceChildren(page('Model shop',
    h('p', { class: 'muted' }, 'Find GGUF models on Hugging Face and install them on the PC. They run on the standard llama.cpp engine with automatic fit (what does not fit in 16 GB runs on the CPU), not tuned like the catalog models.'),
    h('div', { class: 'row' }, h('button', { onclick: () => go('models') }, '← Models'), q, h('button', { class: 'primary', onclick: doSearch }, 'Search')),
    prog, body, installedBox));
  draw(); loadInstalled(); tick(); poll(main, tick, 2000);
}
