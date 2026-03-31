/* V9 Trading Page — Ultra Resilient */
async function fetchJSON(url) {
  try {
    const r = await fetch(url + (url.includes('?') ? '&' : '?') + 't=' + Date.now());
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  } catch (e) {
    throw e;
  }
}

function colorPnl(val) { return val >= 0 ? 'c-green' : 'c-red'; }
function formatTime(iso) { return (!iso || iso === 'N/A') ? 'N/A' : String(iso).replace('T', ' ').split('.')[0]; }

async function refresh() {
  let stateErr = null, assetsErr = null, posErr = null, histErr = null;
  const state = await fetchJSON('/api/state').catch(e => { stateErr = e.message; return null; });
  const assets = await fetchJSON('/api/assets').catch(e => { assetsErr = e.message; return null; });
  const positions = await fetchJSON('/api/positions').catch(e => { posErr = e.message; return null; });
  const history = await fetchJSON('/api/history').catch(e => { histErr = e.message; return null; });

  // --- Top Bar ---
  try {
    if (state) {
      if (document.getElementById('sys-status')) {
        document.getElementById('sys-status').textContent = state.status || '---';
        document.getElementById('sys-status').className = 'badge ' + (state.status === 'ONLINE' ? 'badge-green' : 'badge-red');
      }
      if (document.getElementById('sys-mode')) document.getElementById('sys-mode').textContent = state.mode || '---';
      const wInit = parseFloat(state.wallet_initial || 0);
      const wNow = parseFloat(state.wallet_current || 0);
      const pEur = parseFloat(state.pnl_eur || 0);
      const pPct = parseFloat(state.pnl_pct || 0);
      const exMode = state.exchange_mode || 'SIMULATION';
      const currency = exMode === 'TESTNET' ? '$' : '€';
      
      // Update Mode Badge
      if (document.getElementById('exchange-mode-badge')) {
          const emb = document.getElementById('exchange-mode-badge');
          emb.textContent = exMode;
          emb.className = 'badge ' + (exMode === 'TESTNET' ? 'badge-green' : 'badge-amber');
      }

      // Update Init Wallet
      if (document.getElementById('wallet-init')) {
          document.getElementById('wallet-init').textContent = currency + ' ' + wInit.toLocaleString();
      }

      // Update Current Wallet
      if (document.getElementById('wallet-now')) {
          document.getElementById('wallet-now').textContent = currency + ' ' + wNow.toLocaleString();
          document.getElementById('wallet-now').className = 'stat-value ' + colorPnl(pEur);
      }

      // Update Testnet Box
      if (document.getElementById('testnet-balance-box')) {
          if (state.testnet_balance_usdt !== null && state.testnet_balance_usdt !== undefined) {
              document.getElementById('testnet-balance-box').style.display = 'flex';
              document.getElementById('testnet-balance-val').textContent = state.testnet_balance_usdt.toLocaleString() + ' USDT';
          } else {
              document.getElementById('testnet-balance-box').style.display = 'none';
          }
      }

      if (document.getElementById('pnl-eur')) {
          document.getElementById('pnl-eur').textContent = (pEur >= 0 ? '+' : '') + currency + ' ' + pEur.toFixed(2);
          document.getElementById('pnl-eur').className = 'stat-value ' + colorPnl(pEur);
      }
      if (document.getElementById('pnl-pct')) {
          document.getElementById('pnl-pct').textContent = (pPct >= 0 ? '+' : '') + pPct.toFixed(2) + '%';
          document.getElementById('pnl-pct').className = 'stat-value ' + colorPnl(pPct);
      }
      if (document.getElementById('open-cnt')) document.getElementById('open-cnt').textContent = (positions && !posErr) ? positions.length : 0;
      if (document.getElementById('closed-cnt')) document.getElementById('closed-cnt').textContent = state.closed_trades || 0;

    } else {
      // Error state
      if (document.getElementById('sys-status')) {
        document.getElementById('sys-status').textContent = 'ERR: ' + stateErr;
        document.getElementById('sys-status').className = 'badge badge-red';
      }
    }
  } catch(e) { console.error("Error top bar", e); }

  // --- Asset Grid ---
  try {
    const grid = document.getElementById('asset-grid');
    if (grid) {
      if (assetsErr) {
        grid.innerHTML = `<div class="asset-card"><span class="c-red">Errore Rete AI Decision: ${assetsErr}</span></div>`;
      } else if (!assets || assets.length === 0) {
        grid.innerHTML = '<div class="asset-card"><span class="c-muted">Nessun dato di mercato disponibile. Il bot analizza asset.</span></div>';
      } else {
        grid.innerHTML = assets.map(a => {
          const decisionStr = String(a.decision || 'hold');
          const dec = decisionStr.toUpperCase();
          const regimeStr = String(a.regime || 'N/A');
          let decClass = 'c-amber';
          if (dec === 'BUY') decClass = 'c-green';
          else if (regimeStr.includes('CHAOS') || regimeStr.includes('DOWN')) decClass = 'c-red';
          return `<div class="asset-card">
            <div class="asset-name">${a.asset || 'N/A'}</div>
            <div class="asset-price">$${parseFloat(a.price || 0).toFixed(2)}</div>
            <div class="asset-decision ${decClass}">${dec} · ${a.confidence || 0}%</div>
            <div class="asset-meta">
              Regime: ${regimeStr}<br>
              Score: ${((a.consensus_score || 0) * 100).toFixed(1)}%<br>
              RSI: ${parseFloat(a.rsi_5m || 0).toFixed(1)} · MACD: ${parseFloat(a.macd_5m || 0).toFixed(4)}
            </div>
            <div class="asset-thesis">"${a.why_not_trade || 'Conditions optimal'}"</div>
          </div>`;
        }).join('');
      }
    }
  } catch(e) { console.error("Error assets", e); }

  // --- Positions ---
  try {
    const tbody = document.getElementById('positions-body');
    const badge = document.getElementById('pos-badge');
    if (badge) badge.textContent = (posErr ? 'ERR' : (positions ? positions.length : 0)) + ' attive';
    
    if (tbody) {
      if (posErr) {
        tbody.innerHTML = `<tr><td colspan="7" class="c-red">Errore Rete Posizioni: ${posErr}</td></tr>`;
      } else if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">Nessuna posizione aperta. Il bot è in attesa di segnali validi.</td></tr>';
      } else {
        tbody.innerHTML = positions.map(p => {
          const arrow = p.direction === 'up' ? '▲' : '▼';
          const cls = p.direction === 'up' ? 'c-green' : 'c-red';
          return `<tr>
            <td><strong>${p.asset || 'N/A'}</strong></td>
            <td>$${parseFloat(p.entry_price || 0).toFixed(2)}</td>
            <td>$${parseFloat(p.current_price || 0).toFixed(2)}</td>
            <td>${((p.size_pct || 0) * 100).toFixed(1)}%</td>
            <td class="${cls}">${p.pnl_pct >= 0 ? '+' : ''}${parseFloat(p.pnl_pct || 0).toFixed(2)}%</td>
            <td class="${cls}">${arrow}</td>
            <td>${formatTime(p.opened_at)}</td>
          </tr>`;
        }).join('');
      }
    }
  } catch(e) { console.error("Error positions", e); }

  // --- History ---
  try {
    const hbody = document.getElementById('history-body');
    if (hbody) {
      if (histErr) {
        hbody.innerHTML = `<tr><td colspan="5" class="c-red">Errore Rete Storico: ${histErr}</td></tr>`;
      } else if (!history || history.length === 0) {
        hbody.innerHTML = '<tr class="empty-row"><td colspan="5">Nessun trade storico registrato.</td></tr>';
      } else {
        hbody.innerHTML = history.map(h => {
          const pnl = parseFloat(h.realized_pnl_pct || 0) * 100;
          const win = h.was_profitable;
          return `<tr>
            <td><strong>${h.asset || 'N/A'}</strong></td>
            <td>$${parseFloat(h.entry_price || 0).toFixed(2)}</td>
            <td class="${win ? 'c-green' : 'c-red'}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%</td>
            <td><span class="badge ${win ? 'badge-green' : 'badge-red'}">${win ? 'WIN' : 'LOSS'}</span></td>
            <td>${formatTime(h.closed_at)}</td>
          </tr>`;
        }).join('');
      }
    }
  } catch(e) { console.error("Error history", e); }
}

async function refreshSupervisor() {
  try {
    const r = await fetch('/api/supervisor?t=' + Date.now());
    if (!r.ok) return;
    const d = await r.json();
    const ctrl = d.controls;

    if (document.getElementById('sup-stop')) {
      const stop = ctrl.emergency_stop;
      document.getElementById('sup-stop').textContent = stop ? '🚨 STOP' : '✅ OK';
      document.getElementById('sup-stop').className = 'badge ' + (stop ? 'badge-red' : 'badge-green');
      document.getElementById('supervisor-card').style.borderLeftColor = stop ? 'var(--red)' : 'var(--amber)';
    }
    if (document.getElementById('sup-max-trades')) document.getElementById('sup-max-trades').textContent = ctrl.max_open_trades;
    if (document.getElementById('sup-min-conf')) document.getElementById('sup-min-conf').textContent = ctrl.min_confidence + '%';
    if (document.getElementById('sup-close-threshold')) document.getElementById('sup-close-threshold').textContent = ctrl.close_losers_threshold + '%';
    if (document.getElementById('sup-reasoning')) document.getElementById('sup-reasoning').textContent = ctrl.ai_reasoning || "No reasoning provided.";
    if (document.getElementById('sup-last-check')) {
        const ts = ctrl.last_update ? ctrl.last_update.split('T')[1].split('.')[0] : '---';
        document.getElementById('sup-last-check').textContent = 'Last: ' + ts;
    }
  } catch (e) {
    console.error('Supervisor refresh error:', e);
  }
}

refresh();
refreshSupervisor();
setInterval(refresh, 3000);
setInterval(refreshSupervisor, 20000); // 20s poller for supervisor
