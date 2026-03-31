import os
import sqlite3

def clean_js_files():
    learn_js = """
/* V9 Learning Page - Safe Buffer */
async function refresh() {
  try {
    const r = await fetch('/api/learning?t=' + Date.now());
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();

    const outcomes = document.getElementById('kpi-outcomes');
    if (outcomes) outcomes.textContent = (d.outcomes_total !== undefined) ? d.outcomes_total : 0;
    
    const wr = document.getElementById('kpi-winrate');
    if (wr) {
      const wval = parseFloat(d.winrate || 0);
      wr.textContent = wval + '%';
      wr.className = 'kpi-value ' + (wval >= 50 ? 'c-green' : 'c-red');
    }
    
    const pnl = document.getElementById('kpi-pnl');
    if (pnl) {
      const pval = parseFloat(d.total_pnl_pct || 0);
      pnl.textContent = (pval >= 0 ? '+' : '') + pval.toFixed(2) + '%';
      pnl.className = 'kpi-value ' + (pval >= 0 ? 'c-green' : 'c-red');
    }
    
    const skills = document.getElementById('kpi-skills');
    if (skills) skills.textContent = (d.skill_candidates !== undefined) ? d.skill_candidates : 0;

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
            <td class="${pnlCls}">${pval >= 0 ? '+' : ''}${pval.toFixed(2)}%</td>
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
    const outcomes = document.getElementById('kpi-outcomes');
    if (outcomes) outcomes.textContent = 'ERR';
  }
}
refresh();
setInterval(refresh, 5000);
"""

    logs_js = r"""
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
"""

    with open(r'h:\ai binance\dashboard\static\js\learning.js', 'w', encoding='utf-8') as f:
        f.write(learn_js.strip())
    with open(r'h:\ai binance\dashboard\static\js\logs.js', 'w', encoding='utf-8') as f:
        f.write(logs_js.strip())
    print("Javascript files fixed using UTF-8.")

if __name__ == '__main__':
    clean_js_files()
