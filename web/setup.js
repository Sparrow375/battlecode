// Node War - Tournament Control Deck & Live Caster Synchronization
// Handles bot selection, simulation, live remote streaming, matrix testing, and replay broadcasting.

function getApiUrl(path) {
  const origin = window.location.origin;
  if (!origin || origin === 'null' || window.location.protocol === 'file:' || (window.location.port !== '8000' && window.location.port !== '')) {
    return 'http://localhost:8000' + path;
  }
  return path;
}

class NodeWarSetupDeck {
  constructor() {
    this.broadcastChannel = null;
    this.initBroadcastChannel();
    this.bindTabs();
    this.bindMatchControls();
    this.bindRemoteControls();
    this.bindMatrixControls();
    this.bindBotLabControls();
    this.loadBotList();
    this.loadReplayList();
  }

  initBroadcastChannel() {
    try {
      this.broadcastChannel = new BroadcastChannel('node_war_stream');
    } catch (e) {
      console.warn("BroadcastChannel not supported in this environment:", e);
    }
  }

  broadcast(message) {
    if (this.broadcastChannel) {
      this.broadcastChannel.postMessage(message);
    }
  }

  bindTabs() {
    document.querySelectorAll('.deck-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.deck-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.deck-tab-pane').forEach(p => p.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const target = document.getElementById(e.currentTarget.dataset.tab);
        if (target) target.classList.add('active');
      });
    });
  }

  async loadBotList() {
    try {
      const res = await fetch(getApiUrl('/api/bots'));
      const data = await res.json();
      this.populateBotSelects(data);
    } catch (err) {
      console.warn("Could not load bot list:", err);
    }
  }

  populateBotSelects(data) {
    const selP1 = document.getElementById('select-p1');
    const selP2 = document.getElementById('select-p2');
    const scriptSel = document.getElementById('select-load-script');

    let html = '';
    if (data && data.custom_files && data.custom_files.length > 0) {
      html += '<optgroup label="Custom Scripts (bots/)">';
      data.custom_files.forEach(b => {
        const errMark = b.error ? ' ⚠️ [Error]' : '';
        html += `<option value="${b.filename}">${b.filename} (${b.class_name || 'Bot'})${errMark}</option>`;
      });
      html += '</optgroup>';
    }

    html += '<optgroup label="Built-in Baseline Bots">';
    if (data && data.builtins) {
      data.builtins.forEach(b => {
        html += `<option value="${b.id}">${b.name}</option>`;
      });
    } else {
      html += '<option value="rusher">Rusher Bot</option>';
      html += '<option value="turtle">Turtle Bot</option>';
      html += '<option value="balanced">Balanced (Scout) Bot</option>';
      html += '<option value="starter">Starter Bot</option>';
    }
    html += '</optgroup>';
    html += '<optgroup label="Browser Lab">';
    html += '<option value="custom">Custom Lab Bot (from Code Editor)</option>';
    html += '</optgroup>';

    if (selP1) {
      selP1.innerHTML = html;
      selP1.value = 'rusher';
    }
    if (selP2) {
      selP2.innerHTML = html;
      selP2.value = 'turtle';
    }

    if (scriptSel) {
      scriptSel.innerHTML = '<option value="">Load from bots/ ...</option>';
      let customFiles = (data && data.custom_files && data.custom_files.length > 0) ? data.custom_files : [{ filename: 'bot1.py', class_name: 'NemesisNodeBot' }];
      customFiles.forEach(b => {
        scriptSel.innerHTML += `<option value="${b.filename}">${b.filename} (${b.class_name || 'Bot'})</option>`;
      });
    }
  }

  bindMatchControls() {
    const btnRefresh = document.getElementById('btn-refresh-bots');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        btnRefresh.textContent = 'Scanning...';
        this.loadBotList().finally(() => {
          btnRefresh.textContent = '↻ Refresh Bots';
        });
      });
    }

    const selectPreset = document.getElementById('select-preset');
    const customFields = document.getElementById('custom-config-fields');
    if (selectPreset && customFields) {
      selectPreset.addEventListener('change', (e) => {
        if (e.target.value === 'custom') {
          customFields.classList.remove('hidden');
        } else {
          customFields.classList.add('hidden');
          if (e.target.value === 'standard') {
            document.getElementById('input-turns').value = 120;
            document.getElementById('input-credits').value = 30;
            document.getElementById('input-relic-turn').value = '';
            document.getElementById('input-relic-pts').value = 10;
          } else if (e.target.value === 'blitz') {
            document.getElementById('input-turns').value = 60;
            document.getElementById('input-credits').value = 40;
            document.getElementById('input-relic-turn').value = 40;
            document.getElementById('input-relic-pts').value = 15;
          } else if (e.target.value === 'marathon') {
            document.getElementById('input-turns').value = 160;
            document.getElementById('input-credits').value = 20;
            document.getElementById('input-relic-turn').value = 130;
            document.getElementById('input-relic-pts').value = 10;
          }
        }
      });
    }

    const btnRunMatch = document.getElementById('btn-run-match');
    if (btnRunMatch) {
      btnRunMatch.addEventListener('click', () => this.runAndBroadcastMatch());
    }
  }

  async runAndBroadcastMatch() {
    const btn = document.getElementById('btn-run-match');
    const statusCallout = document.getElementById('match-status-callout');
    btn.disabled = true;
    btn.textContent = 'SIMULATING MATCH...';
    if (statusCallout) statusCallout.textContent = 'Running full headless deterministic match on server...';

    const p1 = document.getElementById('select-p1').value;
    const p2 = document.getElementById('select-p2').value;
    const turns = parseInt(document.getElementById('input-turns').value) || 120;
    const credits = parseInt(document.getElementById('input-credits').value) || 30;
    const relicTurnVal = document.getElementById('input-relic-turn').value;
    const relicTurn = relicTurnVal ? parseInt(relicTurnVal) : null;
    const relicPts = parseInt(document.getElementById('input-relic-pts').value) || 10;
    const customCode = document.getElementById('custom-bot-editor') ? document.getElementById('custom-bot-editor').value : '';

    try {
      const res = await fetch(getApiUrl('/api/run-match'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          p1,
          p2,
          turns,
          initial_credits: credits,
          relic_spawn_turn: relicTurn,
          relic_points: relicPts,
          custom_code: customCode
        })
      });

      const data = await res.json();
      if (data.error) {
        alert("Match Simulation Error: " + data.error);
        if (statusCallout) statusCallout.textContent = "Error: " + data.error;
        return;
      }

      // 1. Sync with active-match endpoint for cross-tab and cross-device persistence
      if (data.filename) {
        try {
          await fetch(getApiUrl('/api/active-match'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: data.filename })
          });
        } catch (syncErr) {
          console.warn("Active match sync notice:", syncErr);
        }
      }

      // 2. Broadcast to any open stream tab/window in real-time
      this.broadcast({ type: 'LOAD_MATCH', data: data });

      const meta = data.metadata || {};
      const winnerName = meta.winner === 1 ? meta.p1_name : (meta.winner === 2 ? meta.p2_name : 'Draw');
      const turnsPlayed = meta.total_turns || data.frames.length;

      if (statusCallout) {
        statusCallout.innerHTML = `✅ <strong>Match Loaded &amp; Broadcasted!</strong> ${meta.p1_name} vs ${meta.p2_name} &bull; Winner: <strong style="color:#00f3ff;">${winnerName}</strong> (${turnsPlayed} Turns). Projector screen updated automatically!`;
      }

      this.loadReplayList();
    } catch (err) {
      console.error("Match simulation failed:", err);
      alert("Failed to communicate with simulation server: " + err + "\n\nMake sure the Node War server is running: python serve.py");
      if (statusCallout) statusCallout.textContent = "Connection failed. Is the server running on port 8000?";
    } finally {
      btn.disabled = false;
      btn.textContent = '▶ SIMULATE & BROADCAST TO PROJECTOR';
    }
  }

  bindRemoteControls() {
    let isPlaying = true;
    const btnPlay = document.getElementById('remote-btn-play');
    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        isPlaying = !isPlaying;
        if (isPlaying) {
          btnPlay.textContent = '❚❚ Pause';
          this.broadcast({ type: 'PLAY' });
        } else {
          btnPlay.textContent = '▶ Play';
          this.broadcast({ type: 'PAUSE' });
        }
      });
    }

    const btnPrev = document.getElementById('remote-btn-prev');
    if (btnPrev) {
      btnPrev.addEventListener('click', () => this.broadcast({ type: 'STEP', delta: -1 }));
    }

    const btnNext = document.getElementById('remote-btn-next');
    if (btnNext) {
      btnNext.addEventListener('click', () => this.broadcast({ type: 'STEP', delta: 1 }));
    }

    const btnRestart = document.getElementById('remote-btn-restart');
    if (btnRestart) {
      btnRestart.addEventListener('click', () => this.broadcast({ type: 'SET_FRAME', frameIdx: 0 }));
    }

    document.querySelectorAll('.remote-speed-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.remote-speed-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const ms = parseInt(e.currentTarget.dataset.speed);
        this.broadcast({ type: 'SET_SPEED', speedMs: ms });
      });
    });

    document.querySelectorAll('.remote-mode-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.remote-mode-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const mode = e.currentTarget.dataset.mode;
        this.broadcast({ type: 'SET_MODE', mode: mode });
      });
    });

    const jumpRelic = document.getElementById('remote-jump-relic');
    if (jumpRelic) jumpRelic.addEventListener('click', () => this.broadcast({ type: 'JUMP', target: 'relic' }));
    const jumpClash = document.getElementById('remote-jump-clash');
    if (jumpClash) jumpClash.addEventListener('click', () => this.broadcast({ type: 'JUMP', target: 'clash' }));
    const jumpFinish = document.getElementById('remote-jump-finish');
    if (jumpFinish) jumpFinish.addEventListener('click', () => this.broadcast({ type: 'JUMP', target: 'end' }));
  }

  bindMatrixControls() {
    const btn = document.getElementById('btn-run-tournament');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'EVALUATING MATRIX...';
      const rounds = parseInt(document.getElementById('select-tournament-rounds').value) || 10;
      const turns = parseInt(document.getElementById('input-turns').value) || 120;

      try {
        const res = await fetch(getApiUrl('/api/run-tournament'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rounds: rounds, turns: turns })
        });
        const data = await res.json();
        this.renderMatrixResults(data.tournament);
      } catch (err) {
        console.error("Tournament evaluation failed:", err);
        alert("Failed to run tournament: " + err);
      } finally {
        btn.disabled = false;
        btn.textContent = 'RUN BALANCE MATRIX';
      }
    });
  }

  renderMatrixResults(results) {
    const card = document.getElementById('tournament-results-card');
    const container = document.getElementById('tournament-matrix-view');
    if (!card || !container) return;

    card.classList.remove('hidden');
    container.innerHTML = '';

    if (!results || !results.matrix) {
      container.innerHTML = '<p class="muted">No tournament results received.</p>';
      return;
    }

    const bots = Object.keys(results.matrix);
    let tableHtml = '<table class="matrix-table"><thead><tr><th>Attacker \\ Defender</th>';
    bots.forEach(b => {
      tableHtml += `<th>${b.toUpperCase()}</th>`;
    });
    tableHtml += '</tr></thead><tbody>';

    bots.forEach(b1 => {
      tableHtml += `<tr><td class="matrix-bot-name">${b1.toUpperCase()}</td>`;
      bots.forEach(b2 => {
        if (b1 === b2) {
          tableHtml += '<td class="matrix-cell self">-</td>';
        } else {
          const stats = results.matrix[b1][b2];
          const wr = stats.win_rate;
          const wrPct = Math.round(wr * 100);
          let colorClass = 'even';
          if (wrPct > 55) colorClass = 'win';
          else if (wrPct < 45) colorClass = 'loss';

          tableHtml += `<td class="matrix-cell ${colorClass}">
            <div class="wr-pct">${wrPct}%</div>
            <div class="wr-record">${stats.wins}W - ${stats.losses}L</div>
          </td>`;
        }
      });
      tableHtml += '</tr>';
    });
    tableHtml += '</tbody></table>';

    if (results.rock_paper_scissors_valid) {
      tableHtml += '<div class="matrix-verdict success">✓ ROCK-PAPER-SCISSORS CYCLE VALIDATED: Rusher &gt; Siege/Balanced &gt; Turtle/Guard &gt; Rusher</div>';
    }

    container.innerHTML = tableHtml;
  }

  bindBotLabControls() {
    const btnLoad = document.getElementById('btn-load-script-into-editor');
    const sel = document.getElementById('select-load-script');
    if (btnLoad && sel) {
      btnLoad.addEventListener('click', async () => {
        const fname = sel.value;
        if (!fname) return;
        try {
          const res = await fetch(getApiUrl(`/api/bot-source/${fname}`));
          const data = await res.json();
          if (data.source) {
            document.getElementById('custom-bot-editor').value = data.source;
          }
        } catch (e) {
          alert("Could not load script source: " + e);
        }
      });
    }

    document.querySelectorAll('.lab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const opp = e.currentTarget.dataset.opponent;
        document.getElementById('select-p1').value = 'custom';
        document.getElementById('select-p2').value = opp;
        // Switch to match tab and run
        const matchTabBtn = document.querySelector('[data-tab="tab-match-setup"]');
        if (matchTabBtn) matchTabBtn.click();
        this.runAndBroadcastMatch();
      });
    });
  }

  async loadReplayList() {
    try {
      const res = await fetch(getApiUrl('/api/replays'));
      const data = await res.json();
      const vault = document.getElementById('replay-vault-list');
      if (!vault) return;
      vault.innerHTML = '';

      if (!data.replays || data.replays.length === 0) {
        vault.innerHTML = '<div class="muted">No saved replays found yet. Simulate a match to create one!</div>';
        return;
      }

      data.replays.forEach(r => {
        const item = document.createElement('div');
        item.className = 'replay-item';
        item.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:#121829; border:1px solid var(--border-color); padding:10px 14px; border-radius:6px; margin-bottom:8px;';
        
        const winLabel = r.winner === 1 ? `<span style="color:#00f3ff; font-weight:700;">${r.p1_name} Won</span>` : (r.winner === 2 ? `<span style="color:#ff0055; font-weight:700;">${r.p2_name} Won</span>` : '<span style="color:#ffd166;">Draw</span>');
        
        item.innerHTML = `
          <div>
            <div style="font-family:'Orbitron', sans-serif; font-size:0.9rem; font-weight:700; color:#fff;">${r.p1_name} vs ${r.p2_name}</div>
            <div style="font-size:0.8rem; color:#8c9bbd; margin-top:2px;">${winLabel} &bull; ${r.total_turns} Turns &bull; <code style="color:#64748b;">${r.filename}</code></div>
          </div>
          <button class="deck-btn-primary btn-broadcast-replay" style="padding:6px 14px; font-size:0.78rem; text-transform:uppercase;">&#x29c9; Broadcast</button>
        `;

        item.querySelector('.btn-broadcast-replay').addEventListener('click', async () => {
          try {
            const replayRes = await fetch(getApiUrl(`/api/replay/${r.filename}`));
            const replayData = await replayRes.json();
            
            // Set active match on server
            await fetch(getApiUrl('/api/active-match'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filename: r.filename })
            });

            // Broadcast to stream
            this.broadcast({ type: 'LOAD_MATCH', data: replayData });

            const statusCallout = document.getElementById('match-status-callout');
            if (statusCallout) {
              statusCallout.innerHTML = `✅ <strong>Broadcasted Replay:</strong> ${r.p1_name} vs ${r.p2_name} sent to projector screen!`;
            }
            alert(`Replay '${r.filename}' broadcasted live to the projector stream!`);
          } catch (err) {
            alert("Failed to broadcast replay: " + err);
          }
        });

        vault.appendChild(item);
      });
    } catch (err) {
      console.warn("Could not load replays:", err);
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.nodeWarSetupDeck = new NodeWarSetupDeck();
});
