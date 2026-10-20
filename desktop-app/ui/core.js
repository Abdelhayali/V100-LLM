// LocalAI Bridge Desktop: shared helpers (server calls, state, markdown, read-aloud).
'use strict';
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'class') el.className = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k instanceof Node ? k : document.createTextNode(k));
  return el;
};

// replaceChildren / append print null and arrays as text: skip empty parts and flatten lists (used everywhere here)
for (const fn of ['replaceChildren', 'append']) {
  const orig = Element.prototype[fn];
  Element.prototype[fn] = function (...kids) { return orig.apply(this, kids.flat(Infinity).filter(k => k != null && k !== false)); };
}

// ---------------------------------------------------------------- server (through the local proxy)
class ApiError extends Error { constructor(code, msg) { super(msg); this.code = code; } }
async function api(path, { method = 'GET', body, form, raw } = {}) {
  const opt = { method, headers: {} };
  if (S.vaultKey) opt.headers['X-Vault-Key'] = S.vaultKey;
  if (form) opt.body = form;
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, opt);
  if (raw) return r;
  const txt = await r.text();
  let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = txt; }
  if (!r.ok) {
    const d = data && (data.detail || data.error);
    throw new ApiError(r.status, r.status === 401 ? 'Invalid token: connect again in Settings'
      : (typeof d === 'string' ? d : (d ? JSON.stringify(d) : `HTTP ${r.status}`)));
  }
  return data;
}
const qs = o => Object.entries(o).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

/** Server-Sent Events from a POST/GET: calls onEvent(obj) per event; resolves when the stream ends. */
async function sse(path, { method = 'GET', body, signal } = {}, onEvent) {
  const headers = body ? { 'Content-Type': 'application/json' } : {};
  if (S.vaultKey) headers['X-Vault-Key'] = S.vaultKey;
  const r = await fetch(path, { method, signal, headers, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { const j = await r.json(); msg = j.detail || msg; } catch {}
    throw new ApiError(r.status, msg);
  }
  const rd = r.body.getReader(), dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await rd.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
      if (!line.startsWith('data:')) continue;
      try { onEvent(JSON.parse(line.slice(5))); } catch (e) { if (!(e instanceof SyntaxError)) throw e; }
    }
  }
}

// ---------------------------------------------------------------- app state + preferences (kept by the desktop program)
const S = {
  view: 'chat', sessions: [], sid: null, title: 'New chat', model: '', info: null, items: [], streaming: false,
  approvals: [], questions: [], plan: [], stats: null, phase: '', phaseTool: '', liveTokens: 0, liveTps: null,
  streamStart: 0, pending: [], pc: null, abort: null, editId: null, vaultKey: null, vaultChat: false, tempChat: false,
  prefs: { theme: 'system', web: false, autoApprove: false, email: false, organizer: false, autoRead: false, rate: 1,
           autoCompress: true, compressAt: 75, thinking: 'auto', ocr: 'off' },
};
async function savePrefs() { try { await fetch('/local/prefs', { method: 'POST', body: JSON.stringify(S.prefs) }); } catch {} }

let toastTimer;
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 3800);
}
function fail(e) { console.error(e); toast(e.message || String(e)); }

// ---------------------------------------------------------------- dialogs
function modal(content, { wide } = {}) {
  const m = $('#modal'), box = $('#modalbox');
  box.className = 'modal-box' + (wide ? ' wide' : '');
  box.replaceChildren(content); m.classList.remove('hidden');
  return () => m.classList.add('hidden');
}
function closeModal() { $('#modal').classList.add('hidden'); }
function confirmBox(title, text, okLabel = 'OK', danger = false) {
  return new Promise(res => {
    const done = v => { closeModal(); res(v); };
    modal(h('div', {}, h('h3', {}, title), h('p', { class: 'pre' }, text),
      h('div', { class: 'row end' }, h('button', { onclick: () => done(false) }, 'Cancel'),
        h('button', { class: danger ? 'danger' : 'primary', onclick: () => done(true) }, okLabel))));
  });
}
function promptBox(title, value = '', { multiline, label = '' } = {}) {
  return new Promise(res => {
    const inp = multiline ? h('textarea', { rows: 8 }) : h('input', { type: 'text' });
    inp.value = value;
    const done = v => { closeModal(); res(v); };
    modal(h('div', {}, h('h3', {}, title), label ? h('label', {}, label) : null, inp,
      h('div', { class: 'row end' }, h('button', { onclick: () => done(null) }, 'Cancel'),
        h('button', { class: 'primary', onclick: () => done(inp.value) }, 'OK'))));
    setTimeout(() => inp.focus(), 30);
  });
}

// ---------------------------------------------------------------- markdown (safe: everything is escaped first)
function md(src) {
  const blocks = [];
  let t = String(src ?? '').replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    blocks.push(`<div class="code"><div class="code-bar"><span>${esc(lang || 'code')}</span><button class="copycode">Copy</button></div><pre><code>${esc(code.replace(/\n$/, ''))}</code></pre></div>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  t = esc(t);
  const inline = s => s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/__([^_]+)__/g, '<b>$1</b>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/(^|\s)(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  const out = []; const lines = t.split('\n'); let list = null, para = [];
  const flushP = () => { if (para.length) { out.push('<p>' + inline(para.join('<br>')) + '</p>'); para = []; } };
  const flushL = () => { if (list) { out.push(`<${list.t}>` + list.items.map(i => `<li>${inline(i)}</li>`).join('') + `</${list.t}>`); list = null; } };
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    let m;
    if (/^\u0000\d+\u0000$/.test(l.trim())) { flushP(); flushL(); out.push(l.trim()); continue; }
    if (/^\s*\|.*\|\s*$/.test(l) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushP(); flushL();
      const row = s => s.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()));
      const head = row(l); i += 2; const body = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) body.push(row(lines[i++]));
      i--;
      out.push('<table><thead><tr>' + head.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>' +
        body.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody></table>');
      continue;
    }
    if ((m = l.match(/^(#{1,4})\s+(.*)$/))) { flushP(); flushL(); out.push(`<h${m[1].length + 2}>${inline(m[2])}</h${m[1].length + 2}>`); continue; }
    if ((m = l.match(/^\s*[-*•]\s+(.*)$/))) { flushP(); if (!list || list.t !== 'ul') { flushL(); list = { t: 'ul', items: [] }; } list.items.push(m[1]); continue; }
    if ((m = l.match(/^\s*\d+[.)]\s+(.*)$/))) { flushP(); if (!list || list.t !== 'ol') { flushL(); list = { t: 'ol', items: [] }; } list.items.push(m[1]); continue; }
    if (/^\s*(---|\*\*\*)\s*$/.test(l)) { flushP(); flushL(); out.push('<hr>'); continue; }
    if (!l.trim()) { flushP(); flushL(); continue; }
    if (list) flushL();
    para.push(l);
  }
  flushP(); flushL();
  return out.join('').replace(/\u0000(\d+)\u0000/g, (_, n) => blocks[+n]);
}
document.addEventListener('click', e => {
  const b = e.target.closest('.copycode');
  if (b) { navigator.clipboard.writeText(b.closest('.code').querySelector('code').innerText); toast('Copied'); }
});
const splitThink = t => {
  const m = String(t || '').match(/<think>([\s\S]*?)(<\/think>|$)/);
  return m ? [m[1], t.replace(m[0], '').trim()] : ['', t || ''];
};

// ---------------------------------------------------------------- read aloud (Arabic + English, per sentence)
const Speech = {
  key: null,
  clean(t) {
    return String(t).replace(/<think>[\s\S]*?<\/think>/g, ' ').replace(/```[\s\S]*?```/g, '\n(code)\n')
      .replace(/`([^`]*)`/g, '$1').replace(/!?\[([^\]]*)]\([^)]*\)/g, '$1').replace(/https?:\/\/\S+/g, '')
      .replace(/^\s*[#>|]+\s*/gm, '').replace(/[*_~]{1,3}/g, '').replace(/^\s*[-•]\s+/gm, '').replace(/\|/g, ' ');
  },
  segments(t) {
    const out = [];
    for (const s of t.split(/(?<=[.!?؟\n])\s+/).map(x => x.trim()).filter(Boolean)) {
      const ar = (s.match(/[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/g) || []).length;
      const la = (s.match(/[A-Za-z]/g) || []).length;
      const isAr = ar === 0 && la === 0 ? (out.at(-1)?.[0] ?? false) : ar >= la;
      if (out.length && out.at(-1)[0] === isAr) out.at(-1)[1] += ' ' + s; else out.push([isAr, s]);
    }
    return out;
  },
  voice(ar) {
    const vs = speechSynthesis.getVoices();
    const want = ar ? 'ar' : 'en';
    return vs.find(v => v.lang.toLowerCase().startsWith(want) && /natural|online/i.test(v.name)) || vs.find(v => v.lang.toLowerCase().startsWith(want));
  },
  speak(text, key = null) {
    speechSynthesis.cancel();
    this.key = key;
    const parts = this.segments(this.clean(text));
    let warned = false;
    parts.forEach(([ar, s], i) => {
      const u = new SpeechSynthesisUtterance(s);
      u.lang = ar ? 'ar-SA' : 'en-US'; u.rate = S.prefs.rate || 1;
      const v = this.voice(ar);
      if (v) u.voice = v; else if (ar && !warned) { warned = true; toast('No Arabic voice on this PC: add Arabic in Windows Settings > Time & language > Speech'); }
      if (i === parts.length - 1) u.onend = () => { this.key = null; window.dispatchEvent(new Event('speech')); };
      speechSynthesis.speak(u);
    });
    window.dispatchEvent(new Event('speech'));
  },
  stop() { speechSynthesis.cancel(); this.key = null; window.dispatchEvent(new Event('speech')); },
};
speechSynthesis.onvoiceschanged = () => {};

// ---------------------------------------------------------------- small formatting helpers
const kfmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e4 ? Math.round(n / 1e3) + 'k' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(n);
const gib = b => (b / 1073741824).toFixed(1);
const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const shortModel = m => String(m || '').split(/[\\/]/).pop().replace(/\.gguf$/i, '');
const dateStr = ts => ts ? new Date(ts * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '';
function bar(frac) {
  const f = Math.max(0, Math.min(1, frac || 0));
  return h('div', { class: 'meter ' + (f > .97 ? 'full' : f > .85 ? 'hot' : '') }, h('div', { style: `width:${(f * 100).toFixed(1)}%` }));
}
