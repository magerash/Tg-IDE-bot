/* Shared client code for the TG-IDE-Bot web surfaces.
   Loaded by BOTH web/index.html (full dashboard) and web/refine.html (text
   workbench) as a plain <script src> at the end of <body> — no modules, no
   build step, no CDN. Same origin, same tunnel, version-stamped with the HTML.

   THE RULE: anything that types, clicks, scrolls, shells out, focuses a window,
   builds, restarts or schedules stays in index.html. This file may only reach
   the four refinement endpoints (status, stt, improve, scope) — the test
   test_refine_page_has_no_system_endpoints scans this file for the others and
   fails on a literal match, so do not name them here either.

   These blocks live here because each one is scar tissue from a real bug and a
   second copy would silently miss the next fix: the WAV re-encode (Whisper
   hallucinated "Thank you." on duration-less webm), the markdown escape-before-
   inject, api()'s abort deadline (a dead upstream wedged the capture queue), and
   the loud humanize-failure toast (Groq retired a model mid-day). */

let TOKEN = localStorage.getItem('tg_bot_token') || '';
let BASE = location.origin;

/* ===== Theme (night/day) ===== */
function applyTheme(t){
  if(t==='dark') document.documentElement.dataset.theme='dark';
  else document.documentElement.removeAttribute('data-theme');
  const b=document.getElementById('theme-toggle');
  if(b) b.textContent = t==='dark' ? '☀' : '🌙';
}
function toggleTheme(){
  const next = document.documentElement.dataset.theme==='dark' ? 'light' : 'dark';
  try{ localStorage.setItem('tg_theme', next); }catch(e){}
  applyTheme(next);
}
applyTheme(localStorage.getItem('tg_theme')||'light');

// Telegram Mini App mode: auth via initData, no token needed
const _twa = (window.Telegram && Telegram.WebApp) || null;
if (_twa) {
  _twa.ready();
  _twa.expand();
  // Android/iOS Telegram close the Mini App on a vertical drag inside the webview.
  // Panning a zoomed screenshot is exactly that gesture, so the viewer used to
  // "close itself" mid-pan with no back press. Bot API 7.7+; older clients ignore it.
  try { _twa.disableVerticalSwipes(); } catch (e) {}
  // macOS Telegram: hex colors here break webview rendering (solid red screen) — skip
  if (_twa.platform !== 'macos') {
    try { _twa.setBackgroundColor('#faf9f7'); _twa.setHeaderColor('#ffffff'); } catch (e) {}
  }
}

/* A page may refuse the ambient Telegram credential (window.NO_AMBIENT_AUTH).
   The refine view does: it mints a scope-limited token instead, and holding
   initData in a page-lifetime global would hand any later code a full one. */
const TG = (!window.NO_AMBIENT_AUTH && _twa && _twa.initData) ? _twa : null;

/* Must equal config.VERSION — tests enforce it. The Telegram webview caches the
   Mini App page hard (no-cache headers are advisory there), so a stale UI can
   run against a new server for days. Detect it and reload past the cache once. */
const CLIENT_VERSION = '0.19.1';

function _checkStaleClient(serverVersion) {
  if (!serverVersion || serverVersion === CLIENT_VERSION) return false;
  const msg = `Stale dashboard (UI ${CLIENT_VERSION}, bot ${serverVersion})`;
  // Namespaced per page: with one shared key, whichever surface loads second
  // after a version bump sees the flag already set and dead-ends on
  // "reload failed" without ever getting its own attempt.
  const _rk = 'tg_reloaded_for_' + location.pathname;
  if (sessionStorage.getItem(_rk) === serverVersion) {
    setStatus(msg + ' — reload failed, clear the app cache', true);
    return false;                 // already tried; don't loop
  }
  sessionStorage.setItem(_rk, serverVersion);
  setStatus(msg + ' — reloading…', true);
  // Query string differs → the webview cannot serve the cached entry
  location.replace(location.pathname + '?v=' + encodeURIComponent(serverVersion));
  return true;
}

function doAuth() {
  const v = document.getElementById('token-input').value.trim();
  if (!v) return;                 // empty input must not wipe a working token
  TOKEN = v;
  localStorage.setItem('tg_bot_token', TOKEN);
  checkAuth();
}

/* fetch() has NO timeout of its own. Through the reverse-SSH tunnel a request
   whose upstream died mid-flight hangs on the proxy indefinitely — and with the
   single-flight capture queue one such request wedges the live view forever
   (the symptom: "web updates, Telegram never does"). Every call gets an abort
   deadline; long jobs pass their own (0 = wait as long as it takes). */
const API_TIMEOUT = 20000;

/* The credential every request carries. A page may narrow its own by setting
   window.AUTH_HEADERS — the refine view returns a scope-limited bearer here, so
   its requests are refused by the server on any system route. Without this hook
   initData would always win in Telegram mode and the narrowing would be fiction. */
function _authHeaders() {
  if (window.AUTH_HEADERS) return window.AUTH_HEADERS();
  return TG ? {'X-Telegram-Init-Data': TG.initData} : {'Authorization': 'Bearer ' + TOKEN};
}

async function api(method, path, body, timeoutMs) {
  const headers = Object.assign({'Content-Type': 'application/json'}, _authHeaders());
  const opts = {method, headers, cache: 'no-store'};
  if (body) opts.body = JSON.stringify(body);
  const ms = timeoutMs === undefined ? API_TIMEOUT : timeoutMs;
  const ctl = new AbortController();
  const timer = ms ? setTimeout(() => ctl.abort(), ms) : null;
  opts.signal = ctl.signal;
  try {
    const r = await fetch(BASE + path, opts);
    const text = await r.text();
    if (r.status === 401 && TG) {
      // Mini App initData expires after 24h — a reopened cached webview 401s
      return {ok: false, error: 'Session expired — close and reopen the Mini App'};
    }
    try {
      return JSON.parse(text);
    } catch(e) {
      // Non-JSON reply (404 page, proxy error) — surface readable error
      return {ok: false, error: 'HTTP ' + r.status + ': ' + text.slice(0, 120)};
    }
  } catch(e) {
    if (e.name === 'AbortError') return {ok: false, error: `Timed out after ${ms / 1000}s — tunnel stalled?`};
    return {ok: false, error: e.message};
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function toast(msg, isErr) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = isErr ? 'error' : 'ok';
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
  setStatus(msg, isErr);
}

/* Persistent status field in Actions rail (+ mobile) — last action result with time */
function setStatus(msg, isErr) {
  const time = new Date().toLocaleTimeString();
  document.querySelectorAll('[data-status]').forEach(el => {
    el.className = 'action-status ' + (isErr ? 'err' : 'ok');
    el.innerHTML = '';
    const b = document.createElement('b');
    b.textContent = msg;
    el.appendChild(b);
    el.appendChild(document.createTextNode(time));
  });
}

/* ===== Auto-grow inputs to fit content (long humanized prompts) ===== */
function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight + 2, 400) + 'px';
}

/* ===== History (localStorage, newest first, cap 100) ===== */
function _history() {
  try { return JSON.parse(localStorage.getItem('tg_history') || '[]'); }
  catch(e) { return []; }
}

function addHistory(kind, text) {
  const h = _history();
  h.unshift({t: new Date().toISOString(), kind, text});
  localStorage.setItem('tg_history', JSON.stringify(h.slice(0, 100)));
  renderHistory();
}

function clearHistory() {
  localStorage.removeItem('tg_history');
  renderHistory();
}

function renderHistory() {
  const box = document.getElementById('history-list');
  const h = _history();
  box.innerHTML = '';
  if (!h.length) {
    box.innerHTML = '<span class="hint">Sent messages appear here — click one to refill its input</span>';
    return;
  }
  // A page that has no #sh-input/#claude-input overrides this (refine routes
  // every kind to its one field); the null guard below is what stops a click
  // on a shell row from throwing there.
  const targets = window.HISTORY_TARGETS ||
    {type: 'type-input', draft: 'type-input', shell: 'sh-input', claude: 'claude-input'};
  h.forEach(item => {
    const row = document.createElement('div');
    row.className = 'hist-row';
    const time = document.createElement('span');
    time.className = 'hist-time';
    time.textContent = new Date(item.t).toLocaleTimeString().slice(0, 5);
    const kind = document.createElement('span');
    kind.className = 'hist-kind ' + item.kind;
    kind.textContent = item.kind;
    const text = document.createElement('span');
    text.className = 'hist-text';
    text.textContent = item.text;
    text.title = item.text;
    row.append(time, kind, text);
    row.onclick = () => {
      const el = targets[item.kind] && document.getElementById(targets[item.kind]);
      if (!el) return;
      el.value = item.text; autoGrow(el); el.focus();
      _mdAuto(item.text);          // programmatic write — the input event won't fire
    };
    box.appendChild(row);
  });
}
renderHistory();

/* ===== Voice to text: mic button records, /api/stt transcribes into Type field ===== */
const MIC_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';
const STOP_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
let _rec = null, _recTimer = null, _recTick = null, _recT0 = 0;
const REC_MAX_S = 600;   // 10 min — WAV stays under Groq 25MB cap
document.getElementById('mic-btn').innerHTML = MIC_ICON;

/* Humanize toggle: clean transcript via LLM server-side (persisted) */
let _humanize = localStorage.getItem('tg_humanize') !== '0';
function toggleHumanize() {
  _humanize = !_humanize;
  localStorage.setItem('tg_humanize', _humanize ? '1' : '0');
  _syncHumanBtn();
  toast('Transcript cleanup: ' + (_humanize ? 'ON' : 'OFF (raw)'));
}
function _syncHumanBtn() {
  // Monochrome toggle: dark = ON, gray = OFF (palette: gray/white/black/red only)
  const b = document.getElementById('human-btn');
  b.textContent = 'AI: ' + (_humanize ? 'ON' : 'OFF');
  b.classList.toggle('btn-primary', _humanize);
  b.classList.toggle('btn-soft', !_humanize);
}
_syncHumanBtn();

/* ===== Improve text (AI rewrite of the Type field, never auto-sends) ===== */
let _twin = localStorage.getItem('tg_twin') === '1';
function toggleTwin() {
  _twin = !_twin;
  localStorage.setItem('tg_twin', _twin ? '1' : '0');
  _syncTwinBtn();
  toast('Twin persona: ' + (_twin ? 'ON' : 'OFF'));
}
function _syncTwinBtn() {
  const b = document.getElementById('twin-btn');
  b.textContent = 'Twin: ' + (_twin ? 'ON' : 'OFF');
  b.classList.toggle('btn-primary', _twin);
  b.classList.toggle('btn-soft', !_twin);
}
_syncTwinBtn();

function impStyleChanged() {
  localStorage.setItem('tg_imp_style', document.getElementById('imp-style').value);
}
document.getElementById('imp-style').value =
  localStorage.getItem('tg_imp_style') || 'structured';

async function doImprove() {
  const input = document.getElementById('type-input');
  const text = input.value.trim();
  if (!text) { toast('Nothing to improve — type something first', true); return; }
  // Original goes to History FIRST so it survives even if the request dies
  addHistory('draft', text);
  const btn = document.getElementById('imp-btn');
  const style = document.getElementById('imp-style').value;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    const r = await api('POST', '/api/improve', {text, style, twin: _twin}, 60000);
    if (!r.ok) { toast('Improve failed: ' + (r.error || '?'), true); return; }
    // Replace the field only — the user reads the result and sends it themselves
    input.value = r.improved;
    autoGrow(input);
    input.focus();
    _mdAuto(r.improved);           // detailed style returns markdown — show it rendered
    toast('Improved (' + r.style + ')'
          + (r.twin_used ? ' · twin' : '')
          + (r.twin_missing ? ' · twin profile not found' : ''));
  } finally {
    btn.disabled = false;
    btn.innerHTML = '&#10024; Improve';
  }
}

/* ===== Markdown preview of the Type field =====
   Textareas can't render, so a read-only preview pane below the field shows
   headers/tables/code the way a file view would. The raw text is what gets
   typed — the preview is for reading an Improved (detailed) result. */
function _mdEsc(s) {
  // Quotes too: the link rule below drops the URL into an href="" attribute, and
  // an unescaped quote there would close it and start a new one.
  return s.replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* Only linkify schemes that cannot execute. `javascript:`/`data:`/`vbscript:` in a
   markdown link are a click away from running script with this origin's
   credentials, which would walk straight past the refine view's scoped token. */
function _mdSafeUrl(u) {
  return /^(?:https?:\/\/|mailto:|[.\/#?])/i.test(u) ? u : '';
}
function _mdInline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, url) => {
      const safe = _mdSafeUrl(url);
      return safe ? '<a href="' + safe + '" target="_blank" rel="noopener">' + text + '</a>' : m;
    });
}
function _mdRender(src) {
  const lines = _mdEsc(src).split('\n');
  const out = [];
  let i = 0, list = null;
  const closeList = () => { if (list) { out.push('</' + list + '>'); list = null; } };
  while (i < lines.length) {
    const L = lines[i];
    if (/^```/.test(L)) {                                   // fenced code block
      closeList();
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      out.push('<pre><code>' + code.join('\n') + '</code></pre>');
      continue;
    }
    if (/^\|.*\|/.test(L) && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {  // table
      closeList();
      const cells = r => r.replace(/^\s*\||\|\s*$/g, '').split('|').map(c => _mdInline(c.trim()));
      out.push('<table><tr>' + cells(L).map(c => '<th>' + c + '</th>').join('') + '</tr>');
      i += 2;
      while (i < lines.length && /^\|.*\|/.test(lines[i])) {
        out.push('<tr>' + cells(lines[i]).map(c => '<td>' + c + '</td>').join('') + '</tr>');
        i++;
      }
      out.push('</table>');
      continue;
    }
    const h = L.match(/^(#{1,6})\s+(.*)/);
    if (h) { closeList(); const n = h[1].length; out.push(`<h${n}>` + _mdInline(h[2]) + `</h${n}>`); i++; continue; }
    const ul = L.match(/^\s*[-*]\s+(.*)/), ol = L.match(/^\s*\d+[.)]\s+(.*)/);
    if (ul || ol) {
      const t = ul ? 'ul' : 'ol';
      if (list !== t) { closeList(); out.push('<' + t + '>'); list = t; }
      out.push('<li>' + _mdInline((ul || ol)[1]) + '</li>');
      i++; continue;
    }
    if (/^\s*&gt;\s?/.test(L)) { closeList(); out.push('<blockquote>' + _mdInline(L.replace(/^\s*&gt;\s?/, '')) + '</blockquote>'); i++; continue; }
    if (/^\s*$/.test(L)) { closeList(); i++; continue; }
    closeList(); out.push('<p>' + _mdInline(L) + '</p>'); i++;
  }
  closeList();
  return out.join('');
}
function _looksLikeMd(t) {
  return /(^|\n)#{1,6}\s|\*\*[^*]+\*\*|(^|\n)[-*]\s|\n\|.*\||```/.test(t);
}

/* Per-page key: the dashboard field is text about to be typed into a terminal
   (markdown is noise, default OFF); the refine field is a document being produced
   to paste elsewhere (rendered IS the point, default ON). One shared key would
   let a choice made on one page push the other's controls below the fold. */
const MD_KEY = window.MD_STORAGE_KEY || 'tg_md';
let _mdOn = localStorage.getItem(MD_KEY) === '1' ||
            (localStorage.getItem(MD_KEY) === null && window.MD_DEFAULT_ON === true);
let _mdManual = localStorage.getItem(MD_KEY) !== null;   // auto-on only until the user chooses
function toggleMd() {
  _mdOn = !_mdOn;
  _mdManual = true;
  localStorage.setItem(MD_KEY, _mdOn ? '1' : '0');
  _syncMd();
}
function _syncMd() {
  const b = document.getElementById('md-btn');
  b.textContent = 'MD: ' + (_mdOn ? 'ON' : 'OFF');
  b.classList.toggle('btn-primary', _mdOn);
  b.classList.toggle('btn-soft', !_mdOn);
  document.getElementById('md-preview').style.display = _mdOn ? '' : 'none';
  if (_mdOn) _mdRenderNow();
}
function _mdRenderNow() {
  const t = document.getElementById('type-input').value;
  document.getElementById('md-preview').innerHTML =
    t.trim() ? _mdRender(t) : '<span class="hint">markdown preview — empty field</span>';
}
function _mdAuto(text) {           // improve returned markdown -> show it rendered
  if (!_mdManual && !_mdOn && _looksLikeMd(text)) { _mdOn = true; _syncMd(); }
  else if (_mdOn) _mdRenderNow();
}
document.getElementById('type-input').addEventListener('input', () => { if (_mdOn) _mdRenderNow(); });
_syncMd();

async function toggleMic() {
  const btn = document.getElementById('mic-btn');
  if (_rec) { _rec.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    _micLabel = stream.getAudioTracks()[0]?.label || 'unknown device';
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus'
               : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';
    const chunks = [];
    _rec = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
    _rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    _rec.onstop = async () => {
      clearTimeout(_recTimer);
      clearInterval(_recTick);
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(chunks, {type: _rec.mimeType || 'audio/webm'});
      _rec = null;
      btn.classList.remove('btn-red');
      if (blob.size < 1000) { btn.innerHTML = MIC_ICON; toast('Recording too short', true); return; }
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
      // MediaRecorder webm lacks duration metadata — some decoders read it as 0s
      // silence ("Thank you." hallucination). Re-encode to WAV via Web Audio.
      let payload = blob;
      _lastPeak = -1;
      try { payload = await blobToWav(blob); } catch(e) { /* fall back to raw blob */ }
      if (_lastPeak >= 0 && _lastPeak < 0.005) {
        btn.disabled = false; btn.innerHTML = MIC_ICON;
        toast(`Mic "${_micLabel}" captured pure silence (peak ${_lastPeak.toFixed(4)}) — check mic permission / input device / OS mic privacy`, true);
        return;
      }
      setStatus(`Uploading audio (${(payload.size / 1024 / 1024).toFixed(1)}MB)...`, false);
      const r = await sttUpload(payload);
      btn.disabled = false; btn.innerHTML = MIC_ICON;
      if (r.ok && r.text) {
        const input = document.getElementById('type-input');
        input.value = input.value ? input.value.replace(/\s*$/, ' ') + r.text : r.text;
        autoGrow(input);
        input.focus();
        _mdAuto(input.value);      // programmatic write — the input event won't fire
        addHistory('type', r.text);
        // A failed cleanup must say so — silently handing back the raw transcript
        // is indistinguishable from "the AI button does nothing" (Groq retiring
        // llama-3.3-70b did exactly that for a day).
        if (r.humanize_error) toast('AI cleanup failed, raw text: ' + r.humanize_error, true);
        else toast(r.humanized
          ? `Transcribed + cleaned (raw ${r.raw.length} → ${r.text.length} chars)`
          : 'Transcribed (' + r.text.length + ' chars)');
      } else toast(r.error || 'STT: empty result', true);
    };
    _rec.start();
    btn.classList.add('btn-red');
    btn.innerHTML = STOP_ICON;
    // Ticking mm:ss on the button; ⚠ during the last minute
    _recT0 = Date.now();
    _recTick = setInterval(() => {
      const s = Math.floor((Date.now() - _recT0) / 1000);
      const mm = String(Math.floor(s / 60)), ss = String(s % 60).padStart(2, '0');
      btn.innerHTML = (s >= REC_MAX_S - 60 ? '⚠ ' : '') + mm + ':' + ss;
    }, 1000);
    _recTimer = setTimeout(() => {
      if (_rec) { toast('Max 10 min reached, transcribing...', true); _rec.stop(); }
    }, REC_MAX_S * 1000);
  } catch(e) { toast('Mic: ' + e.message + ' — Telegram webview may block mic, try browser', true); }
}

let _lastPeak = -1;   // max |sample| of last recording; -1 = unknown (decode failed)
let _micLabel = '';   // device label of last used mic (for diagnostics)

/* Decode any recorded blob -> mono 16kHz 16-bit WAV (small, decodes everywhere) */
async function blobToWav(blob) {
  const raw = await blob.arrayBuffer();
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const decoded = await ac.decodeAudioData(raw);
  ac.close();
  const rate = 16000;
  const frames = Math.ceil(decoded.duration * rate);
  const oc = new OfflineAudioContext(1, frames, rate);
  const src = oc.createBufferSource();
  src.buffer = decoded;
  src.connect(oc.destination);
  src.start();
  const rendered = await oc.startRendering();
  const pcm = rendered.getChannelData(0);
  _lastPeak = 0;
  for (let i = 0; i < pcm.length; i++) { const a = Math.abs(pcm[i]); if (a > _lastPeak) _lastPeak = a; }
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const v = new DataView(buf);
  const wstr = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  wstr(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); wstr(8, 'WAVE');
  wstr(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  wstr(36, 'data'); v.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return new Blob([buf], {type: 'audio/wav'});
}

async function sttUpload(blob) {
  const headers = Object.assign({'Content-Type': blob.type || 'audio/webm'}, _authHeaders());
  try {
    const url = BASE + '/api/stt' + (_humanize ? '?humanize=1' : '');
    // Abort guard: big WAV over mobile + tunnel can stall — fail loud, not spin forever
    const ctl = new AbortController();
    const kill = setTimeout(() => ctl.abort(), 180000);
    const r = await fetch(url, {method: 'POST', headers, body: blob, signal: ctl.signal});
    clearTimeout(kill);
    const text = await r.text();
    try { return JSON.parse(text); }
    catch(e) { return {ok: false, error: 'HTTP ' + r.status + ': ' + text.slice(0, 120)}; }
  } catch(e) {
    return {ok: false, error: e.name === 'AbortError' ? 'Upload timed out (3 min)' : e.message};
  }
}
