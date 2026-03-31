import os

logs_js = """/* V9 Logs Page — Polling JSON, No SSE */
const terminal = document.getElementById('log-terminal');
const sourceSelect = document.getElementById('log-source');
const btnPause = document.getElementById('btn-pause');
const btnCopy = document.getElementById('btn-copy');
const btnClear = document.getElementById('btn-clear');

let paused = false;
let intervalId = null;

function colorize(line) {
  if (line.includes('[ERROR]') || line.includes('Error') || line.includes('Traceback'))
    return `<span style="color:#f5365c">${esc(line)}</span>`;
  if (line.includes('[WARNING]') || line.includes('WARN'))
    return `<span style="color:#f0b429">${esc(line)}</span>`;
  if (line.includes('[INFO]'))
    return `<span style="color:#aaffaa">${esc(line)}</span>`;
  return `<span style="color:#888">${esc(line)}</span>`;
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

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
        terminal.innerHTML = `<span style="color:#f0b429">Log Stream Error: ${data.error}</span>`;
      } else {
        terminal.innerHTML = '<span style="color:#555">Log attualmente vuoto. (Polling attivo...)</span>';
      }
    }
  } catch (e) {
    if (terminal) terminal.innerHTML = `<span style="color:#f5365c">Errore di rete: ${e.message}. (Cloudflare block o timeout?) Riprovo tra 3s...</span>`;
  }
}

async function checkStatus() {
  try {
    const r = await fetch('/api/state?t=' + Date.now());
    if (!r.ok) throw new Error(r.status);
    const d = await r.json();
    const el = document.getElementById('sys-status');
    if (el) {
      el.textContent = d.status || '---';
      el.className = 'badge ' + (d.status === 'ONLINE' ? 'badge-green' : 'badge-red');
    }
  } catch(e) {
    const el = document.getElementById('sys-status');
    if (el) { el.textContent = 'OFFLINE'; el.className = 'badge badge-red'; }
  }
}

if (btnPause) {
  btnPause.addEventListener('click', () => {
    paused = !paused;
    btnPause.textContent = paused ? '▶ Riprendi' : '⏸ Pausa';
    btnPause.classList.toggle('active-btn', paused);
  });
}

if (btnCopy) {
  btnCopy.addEventListener('click', () => {
    if(terminal) navigator.clipboard.writeText(terminal.innerText).then(() => {
      btnCopy.textContent = '✓ Copiato!';
      setTimeout(() => { btnCopy.textContent = '📋 Copia'; }, 1500);
    });
  });
}

if (btnClear) {
  btnClear.addEventListener('click', () => {
    if(terminal) terminal.innerHTML = '<span style="color:#555">Log pulito. In attesa di nuove linee...</span>';
  });
}

if (sourceSelect) {
  sourceSelect.addEventListener('change', () => {
    if(terminal) terminal.innerHTML = '<span style="color:#555">Cambio log in corso...</span>';
    fetchLogs();
  });
}

fetchLogs();
checkStatus();
intervalId = setInterval(fetchLogs, 3000);
setInterval(checkStatus, 15000);
"""

learn_js = """/* V9 Learning Page */
async function refresh() {
  try {
    const r = await fetch('/api/learning?t=' + Date.now());
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();

    if (document.getElementById('kpi-outcomes')) document.getElementById('kpi-outcomes').textContent = (d.outcomes_total !== undefined) ? d.outcomes_total : 0;
    
    const wr = document.getElementById('kpi-winrate');
    if (wr) {
      const wval = parseFloat(d.winrate || 0);
      wr.textContent = wval + '%';
      wr.className = 'kpi-value ' + (wval >= 50 ? 'c-green' : 'c-red');
    }
    
    const pnl = document.getElementById('kpi-pnl');
    if (pnl) {
      const pval = parseFloat(d.total_pnl_pct || 0);
      pnl.textContent = (pval >= 0 ? '+' : '') + pval + '%';
      pnl.className = 'kpi-value ' + (pval >= 0 ? 'c-green' : 'c-red');
    }
    
    if (document.getElementById('kpi-skills')) document.getElementById('kpi-skills').textContent = (d.skill_candidates !== undefined) ? d.skill_candidates : 0;

    const ap = document.getElementById('asset-perf-body');
    if (ap) {
      if (d.asset_performance && d.asset_performance.length > 0) {
        ap.innerHTML = d.asset_performance.map(a => {
          const pval = parseFloat(a.total_pnl_pct || 0);
          const pnlCls = pval >= 0 ? 'c-green' : 'c-red';
          return `<tr>
            <td><strong>${a.asset || 'N/A'}</strong></td>
            <td>${a.cnt || 0}</td>
            <td>${a.wins || 0}</td>
            <td class="${pnlCls}">${pval >= 0 ? '+' : ''}${pval}%</td>
          </tr>`;
        }).join('');
      } else {
        ap.innerHTML = '<tr class="empty-row"><td colspan="4">Nessun dato di performance registrato in Lab.</td></tr>';
      }
    }

    const sb = document.getElementById('skills-body');
    if (sb) {
      if (d.skills && d.skills.length > 0) {
        sb.innerHTML = d.skills.map(s => {
          let cls = 'badge-muted';
          if (s.status === 'approved') cls = 'badge-green';
          else if (s.status === 'rejected') cls = 'badge-red';
          else if (s.status === 'promoted') cls = 'badge-blue';
          return `<tr>
            <td>${s.id || 'N/A'}</td>
            <td>${s.name || 'Sconosciuto'}</td>
            <td><span class="badge ${cls}">${(s.status || 'unknown').toUpperCase()}</span></td>
          </tr>`;
        }).join('');
      } else {
        sb.innerHTML = '<tr class="empty-row"><td colspan="3">Nessuna skill attualmente processata.</td></tr>';
      }
    }
  } catch (e) {
    console.error('Learning refresh error:', e);
    // Error state fallback
    if (document.getElementById('kpi-outcomes')) document.getElementById('kpi-outcomes').textContent = 'ERR';
    if (document.getElementById('asset-perf-body')) document.getElementById('asset-perf-body').innerHTML = `<tr><td colspan="4" class="c-red">Errore Rete API: ${e.message}</td></tr>`;
  }
}

refresh();
setInterval(refresh, 5000);
"""

with open(r"h:\ai binance\dashboard\static\js\logs.js", "w", encoding="utf-8") as f:
    f.write(logs_js)
    
with open(r"h:\ai binance\dashboard\static\js\learning.js", "w", encoding="utf-8") as f:
    f.write(learn_js)
    
print("Clean writes completed via Python.")
