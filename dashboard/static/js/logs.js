/* V9 Logs Page — Polling JSON, No SSE */
const terminal = document.getElementById('log-terminal');
const sourceSelect = document.getElementById('log-source');

let paused = false;

function colorize(line) {
  if (line.includes('[ERROR]') || line.includes('Error')) return `<span style="color:#f5365c">${esc(line)}</span>`;
  if (line.includes('[WARNING]')) return `<span style="color:#f0b429">${esc(line)}</span>`;
  if (line.includes('[INFO]')) return `<span style="color:#aaffaa">${esc(line)}</span>`;
  return `<span style="color:#888">${esc(line)}</span>`;
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

async function fetchLogs() {
  if (paused) return;
  try {
    const source = sourceSelect ? sourceSelect.value : 'daemon';
    const r = await fetch(`/api/logs?source=${source}&lines=60&t=${Date.now()}`);
    if (!r.ok) throw new Error("API Error " + r.status);
    const data = await r.json();
    if (terminal) {
      if (data.lines && data.lines.length > 0) {
        terminal.innerHTML = data.lines.map(l => colorize(l)).join('<br>');
        terminal.scrollTop = terminal.scrollHeight;
      } else if (data.error) {
        terminal.innerHTML = `<span style="color:#f0b429">Log Error: ${data.error}</span>`;
      } else {
        terminal.innerHTML = '<span style="color:#555">Log vuoto.</span>';
      }
    }
  } catch (e) {
    if (terminal) terminal.innerHTML = `<span style="color:#f5365c">Errore Rete: ${e.message}</span>`;
  }
}

fetchLogs();
if (sourceSelect) sourceSelect.addEventListener('change', fetchLogs);
setInterval(fetchLogs, 3000);