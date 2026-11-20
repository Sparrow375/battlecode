// Node War - Web Canvas & 3D Isometric Spectator Arena

class NodeWarVisualizer {
  constructor() {
    this.canvas = document.getElementById('game-canvas');
    this.ctx = this.canvas.getContext('2d');

    this.replayData = null;
    this.currentFrameIdx = 0;
    this.isPlaying = false;
    this.playbackInterval = null;
    this.speedMs = 1000;
    this.viewMode = 'spectator'; // 'spectator' | 'p1' | 'p2'
    this.selectedNodeId = null;
    this.engineMode = 'td'; // Tower Defense is the default view.
    this.arenaThemeId = 'medieval';
    this.themeRequest = 0;
    this.tacticalZoom = 1;
    this.tacticalPan = { x: 0, y: 0 };

    this.particles = [];

    // Initialize 2D Cartoon Tower Defense Visualizer
    try {
      if (window.NodeWarTDVisualizer) {
        this.tdViz = new window.NodeWarTDVisualizer('td-canvas');
      }
    } catch (e) {
      console.warn("Could not initialize TD visualizer:", e);
    }

    // No WebGL renderer or cinematic controller is created in the default view.
    this.threeViz = null;
    this.cinematic = null;

    window.nodeWarApp = this;
    this.victory = window.ChampionshipVictory ? new window.ChampionshipVictory(this) : null;

    this.initCanvasResize();
    this.bindEvents();
    this.bindEngineModeEvents();
    document.getElementById('select-arena-theme').addEventListener('change', e => this.setArenaTheme(e.target.value));
    this.bindControlCenterEvents();
    this.loadBotList();
    this.loadReplayList();
    this.startAnimationLoop();

    // Migrate any saved '2d' preference — 2D Tactical is restored and valid.
    // No migration needed; all modes are available.

    // Set the stable initial view, initialising WebGL upfront for 3D Arena.
    this.setEngineMode(this.engineMode);
  }

  initCanvasResize() {
    const resize = () => {
      if (!this.canvas || !this.canvas.parentElement) return;
      const rect = this.canvas.parentElement.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const dpr = window.devicePixelRatio || 1;
      this.canvas.width = rect.width * dpr;
      this.canvas.height = rect.height * dpr;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.displayWidth = rect.width;
      this.displayHeight = rect.height;
    };
    if (!this._resizeBound) {
      window.addEventListener('resize', resize);
      this.resizeObserver = new ResizeObserver(resize);
      this.resizeObserver.observe(this.canvas.parentElement);
      this._resizeBound = true;
    }
    resize();
  }

  bindEvents() {
    // Playback buttons
    document.getElementById('btn-play').addEventListener('click', () => this.togglePlay());
    document.getElementById('btn-prev').addEventListener('click', () => this.stepFrame(-1));
    document.getElementById('btn-next').addEventListener('click', () => this.stepFrame(1));
    document.getElementById('btn-restart').addEventListener('click', () => this.setFrame(0));

    // Scrubber
    const scrubber = document.getElementById('timeline-scrubber');
    scrubber.addEventListener('input', (e) => {
      this.pause();
      this.setFrame(parseInt(e.target.value) - 1);
    });

    // Speed buttons
    document.querySelectorAll('.speed-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.speedMs = parseInt(e.target.dataset.speed);
        if (this.isPlaying) {
          this.pause();
          this.play();
        }
      });
    });

    // View mode buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.viewMode = e.target.dataset.mode;
        this.updateHUD();
        if (this.tdViz) {
          this.tdViz.setViewMode(this.viewMode);
        }
        if (this.threeViz) {
          this.threeViz.setViewMode(this.viewMode);
        }
      });
    });

    // Quick Navigation buttons on Canvas
    document.getElementById('btn-jump-relic').addEventListener('click', () => this.jumpToRelic());
    document.getElementById('btn-jump-clash').addEventListener('click', () => this.jumpToNextClash());
    document.getElementById('btn-jump-end').addEventListener('click', () => this.jumpToEnd());

    // Keyboard shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.code === 'Space') {
        e.preventDefault();
        this.togglePlay();
      } else if (e.code === 'ArrowRight') {
        this.stepFrame(1);
      } else if (e.code === 'ArrowLeft') {
        this.stepFrame(-1);
      }
    });

    // Canvas click & hover
    this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
    this.canvas.addEventListener('mousemove', (e) => this.handleCanvasHover(e));
    this.canvas.addEventListener('wheel', e => {
      e.preventDefault(); this.zoomTactical(e.deltaY < 0 ? 1.15 : 1/1.15);
    }, { passive: false });
    this.canvas.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      this.tacticalDrag = { x: e.clientX, y: e.clientY, pan: { ...this.tacticalPan } };
      this.tacticalDragged = false; this.canvas.setPointerCapture(e.pointerId);
    });
    this.canvas.addEventListener('pointermove', e => {
      if (!this.tacticalDrag) return;
      const dx=e.clientX-this.tacticalDrag.x,dy=e.clientY-this.tacticalDrag.y;
      if (Math.hypot(dx,dy)>4) this.tacticalDragged=true;
      this.tacticalPan = { x:this.tacticalDrag.pan.x+dx, y:this.tacticalDrag.pan.y+dy };
    });
    this.canvas.addEventListener('pointerup', () => { this.tacticalDrag=null; });
    this.canvas.addEventListener('pointercancel', () => { this.tacticalDrag=null; });
  }

  bindEngineModeEvents() {
    const btnTD = document.getElementById('btn-mode-td');
    const btn3D = document.getElementById('btn-mode-3d');
    const btn2D = document.getElementById('btn-mode-2d');
    document.getElementById('btn-mode-cinematic').addEventListener('click', () => this.setEngineMode('cinematic'));

    if (btnTD) {
      btnTD.addEventListener('click', () => this.setEngineMode('td'));
    }
    if (btn3D) {
      btn3D.addEventListener('click', () => this.setEngineMode('3d'));
    }
    if (btn2D) {
      btn2D.addEventListener('click', () => this.setEngineMode('2d'));
    }
  }

  async setArenaTheme(id) {
    if (!window.ArenaThemes.themes[id]) return;
    const request = ++this.themeRequest;
    const select = document.getElementById('select-arena-theme');
    select.setAttribute('aria-busy', 'true');
    try {
      // Prepare an entire pack before swapping it, so no half-loaded frame is drawn.
      const assets = id === 'medieval'
        ? await this.tdViz.assetsReady
        : await window.ArenaThemes.loadAssets(id);
      if (request !== this.themeRequest) return;
      this.tdViz.setTheme(id, assets);
      this.arenaThemeId = id;
      if(this.victory) this.victory.evaluate();
      document.body.dataset.arenaTheme = id;
      document.documentElement.style.setProperty('--arena-accent', window.ArenaThemes.themes[id].accent);
      if (this.threeViz) this.threeViz.setTheme(id);
      if(this.engineMode==='cinematic' && this.cinematic) {this.cinematic.refreshCombat();this.cinematic.setFocusedLabels(this.cinematic.focusId);}
      select.value = id;
      this.render();
    } catch (error) {
      if (request !== this.themeRequest) return;
      select.value = this.arenaThemeId;
      console.error('Arena theme could not load:', error);
      this.logEvent('Theme could not load. Please try again.', 'system');
    } finally {
      if (request === this.themeRequest) select.removeAttribute('aria-busy');
    }
  }

  notify(message) {
    const notice=document.getElementById('arena-notification');
    notice.textContent=message;notice.classList.remove('hidden');
    clearTimeout(this.noticeTimer);this.noticeTimer=setTimeout(()=>notice.classList.add('hidden'),7000);
  }

  ensureThree() {
    if (this.threeViz) return this.threeViz;
    try {
      this.threeViz=new window.NodeWarThreeVisualizer('three-container', { onFailure: error => this.graphicsFallback(error) });
      this.threeViz.setTheme(this.arenaThemeId);
      if (this.replayData) {
        this.threeViz.loadReplay(this.replayData);
        this.threeViz.syncFrame(this.replayData.frames[this.currentFrameIdx]);
      }
      return this.threeViz;
    } catch (error) { this.graphicsFallback(error); return null; }
  }

  async ensureCinematic(request) {
    if (!window.ArenaCinematic) {
      if (!this.cinematicLoading) this.cinematicLoading=new Promise((resolve,reject)=>{
        const script=document.createElement('script');script.src='cinematic.js';script.id='cinematic-module';
        script.onload=resolve;script.onerror=()=>{script.remove();this.cinematicLoading=null;reject(new Error('Cinematic controls could not load'));};
        document.head.appendChild(script);
      });
      await this.cinematicLoading;
    }
    if(request!==this.modeRequest) return null;
    if (!this.cinematic) this.cinematic=new window.ArenaCinematic(this,this.threeViz);
    return this.cinematic;
  }

  graphicsFallback(error) {
    if(this.victory) this.victory.cleanup3D();
    console.warn('3D view stopped:', error.message || error);
    if (this.cinematic) { this.cinematic.dispose(); this.cinematic=null; }
    if (this.threeViz) { this.threeViz.dispose(); this.threeViz=null; }
    this.setEngineMode('td');
    this.notify('3D stopped safely. Tower Defense view is ready; your match and playback position are preserved.');
  }

  async setEngineMode(mode) {
    if (!['td','2d','3d','cinematic'].includes(mode)) return;
    const request=this.modeRequest=(this.modeRequest || 0)+1;
    if (mode==='3d' || mode==='cinematic') {
      if (!this.ensureThree()) return;
      if (mode==='cinematic') {
        try { await this.ensureCinematic(request); }
        catch (error) { if(request===this.modeRequest) { this.setEngineMode('3d');this.notify(error.message); } return; }
      }
      if(request!==this.modeRequest) return;
    }
    if (this.engineMode==='cinematic' && mode!=='cinematic' && this.cinematic) this.cinematic.deactivate();
    this.engineMode = mode;
    if(this.victory) this.victory.cleanup3D();
    document.body.dataset.arenaView=mode;
    document.getElementById('cinematic-controls').classList.toggle('hidden',mode!=='cinematic');
    const btnCinematic=document.getElementById('btn-mode-cinematic');
    btnCinematic.classList.toggle('active',mode==='cinematic');
    document.getElementById('zoom-level-badge').textContent = `${Math.round((mode === '2d' ? this.tacticalZoom : (this.tdViz ? this.tdViz.zoomLevel : 1))*100)}%`;
    const canvasTD = document.getElementById('td-canvas');
    const container3D = document.getElementById('three-container');
    const canvas2D = document.getElementById('game-canvas');
    const camPresets = document.getElementById('camera-presets-bar');
    const zoomBar = document.getElementById('zoom-controls-bar');
    const btnTD = document.getElementById('btn-mode-td');
    const btn3D = document.getElementById('btn-mode-3d');
    const btn2D = document.getElementById('btn-mode-2d');

    // Reset buttons
    if (btnTD) btnTD.classList.remove('active');
    if (btn3D) btn3D.classList.remove('active');
    if (btn2D) btn2D.classList.remove('active');

    if (zoomBar) {
      if (mode === '3d' || mode === 'cinematic') zoomBar.classList.add('hidden');
      else zoomBar.classList.remove('hidden');
    }

    if (mode === 'td') {
      if (canvasTD) canvasTD.classList.remove('hidden');
      if (container3D) container3D.classList.add('hidden');
      if (canvas2D) canvas2D.classList.add('hidden');
      if (camPresets) camPresets.classList.add('hidden');
      if (btnTD) btnTD.classList.add('active');
      if (this.tdViz) {
        this.tdViz.initCanvasResize();
        if (this.replayData && this.replayData.frames) {
          const currentFrame = this.replayData.frames[this.currentFrameIdx];
          this.tdViz.syncFrame(currentFrame);
        }
      }
    } else if (mode === '2d') {
      if (canvasTD) canvasTD.classList.add('hidden');
      if (container3D) container3D.classList.add('hidden');
      if (canvas2D) canvas2D.classList.remove('hidden');
      if (camPresets) camPresets.classList.add('hidden');
      if (btn2D) btn2D.classList.add('active');
      this.initCanvasResize();
      if (this.replayData && this.replayData.frames) {
        this.render();
      }
    } else {
      if (canvasTD) canvasTD.classList.add('hidden');
      if (container3D) container3D.classList.remove('hidden');
      if (canvas2D) canvas2D.classList.add('hidden');
      if (camPresets) camPresets.classList.toggle('hidden',mode==='cinematic');
      if (btn3D && mode==='3d') btn3D.classList.add('active');
      if (this.threeViz) {
        this.threeViz.onResize();
        if (this.replayData && this.replayData.frames) {
          const currentFrame = this.replayData.frames[this.currentFrameIdx];
          this.threeViz.syncFrame(currentFrame);
        }
      }
      if(mode==='cinematic') this.cinematic.activate();
    }
  }

  selectNode(nodeId) {
    this.selectedNodeId = nodeId;
    this.renderNodeInspector(nodeId);
    if(this.engineMode==='cinematic' && this.cinematic) this.cinematic.focus(nodeId);
  }

  bindControlCenterEvents() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        e.target.classList.add('active');
        const targetTab = document.getElementById(e.target.dataset.tab);
        if (targetTab) targetTab.classList.add('active');
      });
    });

    // Preset selector
    const presetSelect = document.getElementById('select-preset');
    const customFields = document.getElementById('custom-config-fields');
    presetSelect.addEventListener('change', (e) => {
      const mode = e.target.value;
      if (mode === 'custom') {
        customFields.classList.remove('hidden');
      } else {
        customFields.classList.add('hidden');
        if (mode === 'standard') {
          document.getElementById('input-turns').value = 120;
          document.getElementById('input-credits').value = 30;
          document.getElementById('input-relic-turn').value = "";
          document.getElementById('input-relic-pts').value = 10;
        } else if (mode === 'blitz') {
          document.getElementById('input-turns').value = 60;
          document.getElementById('input-credits').value = 40;
          document.getElementById('input-relic-turn').value = 40;
          document.getElementById('input-relic-pts').value = 10;
        } else if (mode === 'marathon') {
          document.getElementById('input-turns').value = 160;
          document.getElementById('input-credits').value = 20;
          document.getElementById('input-relic-turn').value = 120;
          document.getElementById('input-relic-pts').value = 10;
        }
      }
    });

    // Run 1v1 match button
    document.getElementById('btn-run-match').addEventListener('click', () => {
      const p1 = document.getElementById('select-p1').value;
      const p2 = document.getElementById('select-p2').value;
      this.runMatch(p1, p2);
    });

    // Run Tournament Matrix button
    document.getElementById('btn-run-tournament').addEventListener('click', () => this.runTournamentMatrix());

    // Bot lab quick test buttons
    document.querySelectorAll('.lab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const opponent = e.target.dataset.opponent;
        this.runMatch('custom', opponent);
      });
    });

    // Replay vault refresh button
    document.getElementById('btn-refresh-replays').addEventListener('click', () => this.loadReplayList());

    // Bot list refresh button
    const refreshBotsBtn = document.getElementById('btn-refresh-bots');
    if (refreshBotsBtn) {
      refreshBotsBtn.addEventListener('click', () => {
        this.loadBotList();
        this.logEvent("Refreshed bots directory.", "system");
      });
    }

    // Viewport Zoom controls
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnZoomReset = document.getElementById('btn-zoom-reset');
    if (btnZoomIn) btnZoomIn.addEventListener('click', () => { if (this.engineMode === '2d') this.zoomTactical(1.25); else if (this.tdViz) this.tdViz.zoomIn(); });
    if (btnZoomOut) btnZoomOut.addEventListener('click', () => { if (this.engineMode === '2d') this.zoomTactical(.8); else if (this.tdViz) this.tdViz.zoomOut(); });
    if (btnZoomReset) btnZoomReset.addEventListener('click', () => { if (this.engineMode === '2d') { this.tacticalPan={x:0,y:0}; this.tacticalZoom=1; this.zoomTactical(1); } else if (this.tdViz) this.tdViz.resetZoom(); });

    // Load custom script into editor button
    const loadScriptBtn = document.getElementById('btn-load-script-into-editor');
    if (loadScriptBtn) {
      loadScriptBtn.addEventListener('click', () => {
        const scriptSel = document.getElementById('select-load-script');
        if (scriptSel && scriptSel.value) {
          this.loadScriptIntoEditor(scriptSel.value);
        }
      });
    }
  }

  async loadBotList() {
    try {
      const res = await fetch('/api/bots');
      const data = await res.json();
      this.populateBotSelects(data);
    } catch (err) {
      console.warn("Could not load bot list:", err);
    }
  }

  populateBotSelects(data) {
    const p1Sel = document.getElementById('select-p1');
    const p2Sel = document.getElementById('select-p2');
    const scriptSel = document.getElementById('select-load-script');
    if (!p1Sel || !p2Sel) return;

    const prevP1 = p1Sel.value || 'rusher';
    const prevP2 = p2Sel.value || 'turtle';

    const generateOptionsHtml = () => {
      let html = '';

      // 1. Custom scripts in bots/
      let customFiles = (data && data.custom_files && data.custom_files.length > 0) ? data.custom_files : null;
      if (customFiles) {
        html += '<optgroup label="Custom Scripts (bots/)">';
        customFiles.forEach(b => {
          html += `<option value="${b.id}">${b.display_name || b.filename}</option>`;
        });
        html += '</optgroup>';
      } else {
        html += '<optgroup label="Custom Scripts (bots/)">';
        html += '<option value="bot1.py">bot1.py (ApexNodeBot)</option>';
        html += '</optgroup>';
      }

      // 2. Builtin baseline bots
      let builtins = (data && data.builtins) ? data.builtins : null;
      if (!builtins && data && Array.isArray(data.bots)) {
        builtins = data.bots
          .filter(b => b !== 'custom' && !b.endsWith('.py'))
          .map(b => ({
            id: b,
            name: b.charAt(0).toUpperCase() + b.slice(1) + ' Bot'
          }));
      }
      if (!builtins || builtins.length === 0) {
        builtins = [
          { id: 'rusher', name: 'Rusher Bot' },
          { id: 'turtle', name: 'Turtle Bot' },
          { id: 'balanced', name: 'Balanced (Scout) Bot' },
          { id: 'starter', name: 'Starter Bot' }
        ];
      }

      html += '<optgroup label="Built-in Baseline Bots">';
      builtins.forEach(b => {
        html += `<option value="${b.id}">${b.name}</option>`;
      });
      html += '</optgroup>';

      // 3. Browser Lab
      html += '<optgroup label="Browser Lab">';
      html += '<option value="custom">Custom Lab Bot (from Code Editor)</option>';
      html += '</optgroup>';

      return html;
    };

    const optionsHtml = generateOptionsHtml();
    if (optionsHtml.trim().length > 0) {
      p1Sel.innerHTML = optionsHtml;
      p2Sel.innerHTML = optionsHtml;
    }

    if ([...p1Sel.options].some(o => o.value === prevP1)) {
      p1Sel.value = prevP1;
    } else {
      p1Sel.value = 'rusher';
    }

    if ([...p2Sel.options].some(o => o.value === prevP2)) {
      p2Sel.value = prevP2;
    } else if ([...p2Sel.options].some(o => o.value === 'bot1.py')) {
      p2Sel.value = 'bot1.py';
    } else {
      p2Sel.value = 'turtle';
    }

    if (scriptSel) {
      scriptSel.innerHTML = '<option value="">Load from bots/ ...</option>';
      let customFiles = (data && data.custom_files && data.custom_files.length > 0) ? data.custom_files : [{ filename: 'bot1.py', class_name: 'ApexNodeBot' }];
      customFiles.forEach(b => {
        scriptSel.innerHTML += `<option value="${b.filename}">${b.filename} (${b.class_name || 'Bot'})</option>`;
      });
      let builtins = [
        { id: 'rusher', name: 'Rusher' },
        { id: 'turtle', name: 'Turtle' },
        { id: 'balanced', name: 'Balanced' },
        { id: 'starter_bot', name: 'Starter' }
      ];
      builtins.forEach(b => {
        scriptSel.innerHTML += `<option value="${b.id}.py">${b.id}.py (${b.name})</option>`;
      });
    }
  }

  async loadScriptIntoEditor(filename) {
    try {
      const res = await fetch(`/api/bot-source/${filename}`);
      const data = await res.json();
      if (data.source) {
        document.getElementById('custom-bot-editor').value = data.source;
        this.logEvent(`Loaded ${filename} into code editor.`, 'system');
      } else if (data.error) {
        alert(data.error);
      }
    } catch (err) {
      console.error("Failed to load script into editor:", err);
    }
  }

  // =========================================
  // API Calls & Match Execution
  // =========================================

  async runMatch(p1, p2) {
    const btn = document.getElementById('btn-run-match');
    btn.disabled = true;
    btn.textContent = 'SIMULATING...';

    const turns = parseInt(document.getElementById('input-turns').value) || 120;
    const credits = parseInt(document.getElementById('input-credits').value) || 30;
    const presetMode = document.getElementById('select-preset').value;
    let relicTurn = null;
    if (presetMode !== 'standard') {
      const val = parseInt(document.getElementById('input-relic-turn').value);
      if (!isNaN(val)) relicTurn = val;
    }
    const relicPts = parseInt(document.getElementById('input-relic-pts').value) || 10;
    const customCode = document.getElementById('custom-bot-editor').value;

    try {
      const res = await fetch('/api/run-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          p1: p1,
          p2: p2,
          turns: turns,
          initial_credits: credits,
          relic_spawn_turn: relicTurn,
          relic_points: relicPts,
          custom_code: customCode
        })
      });
      const data = await res.json();
      if (data.error) {
        alert("Match Simulation Error: " + data.error);
        return;
      }
      this.loadReplayData(data);
      this.loadReplayList();
      this.play();
    } catch (err) {
      console.error("Match simulation failed:", err);
      alert("Failed to communicate with simulation server: " + err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'SIMULATE & PLAY';
    }
  }

  async runTournamentMatrix() {
    const btn = document.getElementById('btn-run-tournament');
    btn.disabled = true;
    btn.textContent = 'EVALUATING MATRIX...';

    const rounds = parseInt(document.getElementById('select-tournament-rounds').value) || 10;
    const turns = parseInt(document.getElementById('input-turns').value) || 120;

    try {
      const res = await fetch('/api/run-tournament', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rounds: rounds, turns: turns })
      });
      const data = await res.json();
      if (data.tournament) {
        this.renderTournamentResults(data.tournament);
      }
    } catch (err) {
      console.error("Tournament failed:", err);
      alert("Tournament execution failed: " + err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'RUN BALANCE MATRIX';
    }
  }

  renderTournamentResults(matrix) {
    const card = document.getElementById('tournament-results-card');
    const container = document.getElementById('tournament-matrix-view');
    card.classList.remove('hidden');
    container.innerHTML = '';

    for (const [key, item] of Object.entries(matrix)) {
      const row = document.createElement('div');
      row.className = 'matrix-matchup';
      const aName = item.bot_a.toUpperCase();
      const bName = item.bot_b.toUpperCase();
      row.innerHTML = `
        <div class="matchup-title">
          <span style="color:#00f3ff">${aName} (${item.rate_a.toFixed(1)}%)</span>
          <span style="color:#ff0055">${bName} (${item.rate_b.toFixed(1)}%)</span>
        </div>
        <div class="matchup-bar-container">
          <div class="matchup-bar-fill" style="width: ${item.rate_a}%;"></div>
        </div>
        <div style="font-size:0.75rem; color:#8c9bbd; margin-top:3px; display:flex; justify-content:space-between;">
          <span>Wins: ${item.wins_a} vs ${item.wins_b}</span>
          <span>Avg: ${item.avg_turns.toFixed(1)} Turns</span>
        </div>
      `;
      container.appendChild(row);
    }

    const cyclePill = document.createElement('div');
    cyclePill.className = 'cycle-pill';
    cyclePill.textContent = 'CYCLE VALID: RUSHER > BALANCED > TURTLE > RUSHER';
    container.appendChild(cyclePill);
  }

  async loadReplayList() {
    try {
      const res = await fetch('/api/replays');
      const data = await res.json();
      const vault = document.getElementById('replay-vault-list');
      vault.innerHTML = '';

      if (data.replays && data.replays.length > 0) {
        data.replays.forEach(r => {
          const item = document.createElement('div');
          item.className = 'replay-item';
          const winnerColor = r.winner === 1 ? '#00f3ff' : (r.winner === 2 ? '#ff0055' : '#888');
          item.innerHTML = `
            <div>
              <div class="replay-item-title">${r.p1_name} vs ${r.p2_name}</div>
              <div class="replay-item-meta">${r.total_turns} Turns // Winner: <span style="color:${winnerColor}; font-weight:700;">P${r.winner}</span></div>
            </div>
            <button class="secondary-btn" style="width:auto; margin:0; padding:3px 8px; font-size:0.75rem;">Load</button>
          `;
          item.addEventListener('click', () => this.fetchReplay(r.filename));
          vault.appendChild(item);
        });

        // Load first replay if nothing loaded yet
        if (!this.replayData) {
          for(const replay of data.replays) {
            if(await this.fetchReplay(replay.filename,true)) break;
          }
        }
      } else {
        vault.innerHTML = '<div class="muted">No replays found. Simulate a match!</div>';
      }
    } catch (err) {
      console.warn("Could not fetch replay list:", err);
    }
  }

  async fetchReplay(filename, silent=false) {
    try {
      const res = await fetch(`/api/replay/${encodeURIComponent(filename)}`);
      if(!res.ok) throw new Error('Replay could not be loaded');
      const data = await res.json();
      this.loadReplayData(data);
      return true;
    } catch (err) {
      if(!silent) this.notify('This replay could not load. Choose another saved match or simulate a new one.');
      return false;
    }
  }

  loadReplayData(data) {
    if(this.victory) this.victory.reset();
    this.replayData = data;
    this.currentFrameIdx = 0;
    this.pause();

    const scrubber = document.getElementById('timeline-scrubber');
    const totalFrames = data.frames.length;
    scrubber.max = totalFrames;
    scrubber.value = 1;
    document.getElementById('max-turn').textContent = totalFrames;
    document.getElementById('scrubber-end-marker').textContent = `Turn ${totalFrames}`;

    // Header metadata
    document.getElementById('p1-name').textContent = data.metadata.p1_name;
    document.getElementById('p2-name').textContent = data.metadata.p2_name;

    // Dynamic Relic Activation Turn
    let relicTurn = (data.metadata && data.metadata.relic_spawn_turn) ? data.metadata.relic_spawn_turn : null;
    if (!relicTurn && data.frames) {
      const activeIdx = data.frames.findIndex(f => f.relic_active);
      if (activeIdx !== -1) {
        relicTurn = data.frames[activeIdx].turn;
      }
    }
    this.relicSpawnTurn = relicTurn;

    const relicBtn = document.getElementById('btn-jump-relic');
    if (relicBtn) {
      relicBtn.innerHTML = relicTurn ? `&#9889; Relic (T${relicTurn})` : `&#9889; Relic`;
      relicBtn.title = relicTurn ? `Jump to Relic Phase (Turn ${relicTurn})` : `Jump to Relic Phase`;
    }

    const relicMarker = document.getElementById('scrubber-relic-marker');
    if (relicMarker) {
      if (relicTurn) {
        const relicPct = Math.max(0, Math.min(100, ((relicTurn - 1) / Math.max(1, totalFrames - 1)) * 100));
        relicMarker.textContent = `Turn ${relicTurn} (Relic)`;
        relicMarker.style.left = `${relicPct}%`;
      } else {
        relicMarker.textContent = `Relic Phase`;
        relicMarker.style.left = `75%`;
      }
    }

    this.logEvent(`Match Loaded: ${data.metadata.p1_name} vs ${data.metadata.p2_name} (${totalFrames} Turns)`, 'system');
    this.updateHUD();

    if (this.tdViz) {
      this.tdViz.loadReplay(data);
      if (data.frames && data.frames.length > 0) {
        this.tdViz.syncFrame(data.frames[0]);
      }
    }

    if (this.threeViz) {
      this.threeViz.loadReplay(data);
      if (data.frames && data.frames.length > 0) {
        this.threeViz.syncFrame(data.frames[0]);
      }
    }
    if(this.engineMode==='cinematic' && this.cinematic) this.cinematic.onFrame(true);
    if(this.victory) this.victory.load(data);
  }

  // =========================================
  // Playback Navigation
  // =========================================

  togglePlay() {
    if (this.isPlaying) this.pause();
    else this.play();
  }

  play() {
    if (!this.replayData) return;
    this.isPlaying = true;
    document.getElementById('btn-play').innerHTML = '&#10074;&#10074;';
    clearInterval(this.playbackInterval);
    this.playbackInterval = setInterval(() => {
      if (this.currentFrameIdx < this.replayData.frames.length - 1) {
        this.stepFrame(1);
      } else {
        this.pause();
      }
    }, this.speedMs);
  }

  pause() {
    this.isPlaying = false;
    document.getElementById('btn-play').innerHTML = '&#9654;';
    clearInterval(this.playbackInterval);
  }

  stepFrame(delta) {
    if (!this.replayData) return;
    const newIdx = Math.max(0, Math.min(this.replayData.frames.length - 1, this.currentFrameIdx + delta));
    this.setFrame(newIdx);
  }

  setFrame(idx) {
    const prevIdx = this.currentFrameIdx;
    this.currentFrameIdx = idx;
    document.getElementById('timeline-scrubber').value = idx + 1;
    this.updateHUD();
    this.checkFrameEvents();

    if (this.replayData && this.replayData.frames) {
      const currentFrame = this.replayData.frames[idx];
      const prevFrame = this.replayData.frames[prevIdx];
      if (this.tdViz) {
        this.tdViz.syncFrame(currentFrame);
      }
      if (this.threeViz) {
        this.threeViz.syncFrame(currentFrame, prevFrame);
      }
      if(this.engineMode==='cinematic' && this.cinematic) this.cinematic.onFrame();
      if(this.victory) this.victory.evaluate();
    }
  }

  jumpToRelic() {
    if (!this.replayData) return;
    // Find first frame where relic is active
    const relicIdx = this.replayData.frames.findIndex(f => f.relic_active);
    if (relicIdx !== -1) {
      this.pause();
      this.setFrame(relicIdx);
    } else if (this.relicSpawnTurn) {
      const idx = this.replayData.frames.findIndex(f => f.turn >= this.relicSpawnTurn);
      if (idx !== -1) {
        this.pause();
        this.setFrame(idx);
      }
    }
  }

  jumpToNextClash() {
    if (!this.replayData) return;
    for (let i = this.currentFrameIdx + 1; i < this.replayData.frames.length; i++) {
      if (this.replayData.frames[i].combat_events && this.replayData.frames[i].combat_events.length > 0) {
        this.pause();
        this.setFrame(i);
        return;
      }
    }
    // If no future clashes, loop to first
    for (let i = 0; i <= this.currentFrameIdx; i++) {
      if (this.replayData.frames[i].combat_events && this.replayData.frames[i].combat_events.length > 0) {
        this.pause();
        this.setFrame(i);
        return;
      }
    }
  }

  jumpToEnd() {
    if (!this.replayData) return;
    this.pause();
    this.setFrame(this.replayData.frames.length - 1);
  }

  checkFrameEvents() {
    if (!this.replayData) return;
    const frame = this.replayData.frames[this.currentFrameIdx];
    if (frame.combat_events && frame.combat_events.length > 0) {
      frame.combat_events.forEach(cb => {
        this.logEvent(`Turn ${frame.turn}: Combat at Node ${cb.node_id}!`, 'combat');
        this.spawnCombatSparks(cb.node_id);
      });
    }
    if (frame.capture_events && frame.capture_events.length > 0) {
      frame.capture_events.forEach(cap => {
        if (cap.type === 'flipped') {
          this.logEvent(`Turn ${frame.turn}: Node ${cap.node_id} flipped to Player ${cap.new_owner}!`, 'capture');
        }
      });
    }
  }

  spawnCombatSparks(nodeId) {
    const coords = this.getNodeScreenPos(nodeId);
    if (!coords) return;
    for (let i = 0; i < 20; i++) {
      this.particles.push({
        x: coords.x,
        y: coords.y,
        vx: (Math.random() - 0.5) * 6,
        vy: (Math.random() - 0.5) * 6,
        life: 1.0,
        color: Math.random() > 0.5 ? '#ff0055' : '#00f3ff'
      });
    }
  }

  logEvent(msg, type = 'system') {
    const feed = document.getElementById('event-feed');
    const item = document.createElement('div');
    item.className = `feed-item ${type}`;
    item.textContent = msg;
    feed.prepend(item);
    if (feed.children.length > 30) feed.removeChild(feed.lastChild);
  }

  updateHUD() {
    if (!this.replayData) return;
    const frame = this.replayData.frames[this.currentFrameIdx];
    document.getElementById('current-turn').textContent = frame.turn;
    document.getElementById('p1-score').textContent = frame.scores.p1;
    document.getElementById('p2-score').textContent = frame.scores.p2;

    document.getElementById('p1-credits').textContent = frame.credits.p1;
    document.getElementById('p2-credits').textContent = frame.credits.p2;

    document.getElementById('p1-income').textContent = `+${frame.income.p1}`;
    document.getElementById('p2-income').textContent = `+${frame.income.p2}`;

    document.getElementById('p1-upkeep').textContent = frame.upkeep.p1;
    document.getElementById('p2-upkeep').textContent = frame.upkeep.p2;

    const relicBadge = document.getElementById('relic-status');
    if (frame.relic_active) {
      relicBadge.className = 'relic-badge active';
      relicBadge.textContent = 'RELIC ACTIVE // 2X POINTS & +10/TURN';
    } else if (frame.relic_charging) {
      relicBadge.className = 'relic-badge charging';
      relicBadge.textContent = '⚡ RELIC CHARGING // AWAKENING IMMINENT';
    } else {
      relicBadge.className = 'relic-badge';
      if (this.relicSpawnTurn) {
        relicBadge.textContent = `RELIC DORMANT (ACTIVATES TURN ${this.relicSpawnTurn})`;
      } else {
        relicBadge.textContent = `RELIC DORMANT (ACTIVATES TURN 80-100)`;
      }
    }

    if (this.selectedNodeId !== null) {
      this.renderNodeInspector(this.selectedNodeId);
    }
  }

  getNodeScreenPos(nodeId) {
    if (!this.replayData) return null;
    const node = this.replayData.map.nodes.find(n => n.id === nodeId);
    if (!node) return null;
    const padX = 80;
    const padY = 60;
    const w = this.displayWidth - padX * 2;
    const h = this.displayHeight - padY * 2;
    return {
      x: padX + (node.x / 100) * w,
      y: padY + (node.y / 100) * h
    };
  }

  // =========================================
  // Canvas Rendering Loop
  // =========================================
  startAnimationLoop() {
    const loop = () => {
      if(this.victory) this.victory.tick(performance.now());
      this.render();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  render() {
    if (this.engineMode !== '2d') return;
    this.ctx.clearRect(0, 0, this.displayWidth, this.displayHeight);
    this.ctx.save();
    this.ctx.translate(this.displayWidth/2+this.tacticalPan.x,this.displayHeight/2+this.tacticalPan.y);
    this.ctx.scale(this.tacticalZoom,this.tacticalZoom);
    this.ctx.translate(-this.displayWidth/2,-this.displayHeight/2);
    this.drawTacticalGrid();

    if (!this.replayData) {
      this.drawLoadingMessage();
      this.ctx.restore();
      return;
    }

    const frame = this.replayData.frames[this.currentFrameIdx];
    this.drawLanes();
    this.drawFleets(frame);
    this.drawNodes(frame);
    this.drawParticles();
    if(this.victory) this.victory.draw2D(this.ctx,id=>this.getNodeScreenPos(id),frame);
    this.ctx.restore();
  }

  zoomTactical(factor) {
    this.tacticalZoom=Math.max(.75,Math.min(3,this.tacticalZoom*factor));
    document.getElementById('zoom-level-badge').textContent=`${Math.round(this.tacticalZoom*100)}%`;
    this.render();
  }

  tacticalPointer(e) {
    const rect=this.canvas.getBoundingClientRect();
    return {x:(e.clientX-rect.left-this.displayWidth/2-this.tacticalPan.x)/this.tacticalZoom+this.displayWidth/2,
      y:(e.clientY-rect.top-this.displayHeight/2-this.tacticalPan.y)/this.tacticalZoom+this.displayHeight/2};
  }

  drawTacticalGrid() {
    if (this.arenaThemeId !== 'medieval') {
      window.ArenaThemes.drawTerrain(this.ctx, this.displayWidth, this.displayHeight, this.arenaThemeId);
    }
    this.ctx.strokeStyle = 'rgba(35, 44, 69, 0.25)';
    this.ctx.lineWidth = 1;
    const step = 40;
    for (let x = 0; x < this.displayWidth; x += step) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, this.displayHeight);
      this.ctx.stroke();
    }
    for (let y = 0; y < this.displayHeight; y += step) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(this.displayWidth, y);
      this.ctx.stroke();
    }
  }

  drawLanes() {
    const lanes = this.replayData.map.lanes;
    lanes.forEach(lane => {
      const pA = this.getNodeScreenPos(lane.node_a);
      const pB = this.getNodeScreenPos(lane.node_b);
      if (!pA || !pB) return;

      this.ctx.beginPath();
      this.ctx.moveTo(pA.x, pA.y);
      this.ctx.lineTo(pB.x, pB.y);
      this.ctx.strokeStyle = this.arenaThemeId === 'medieval' ? 'rgba(60, 80, 120, 0.4)' : window.ArenaThemes.themes[this.arenaThemeId].path;
      this.ctx.lineWidth = 3;
      this.ctx.stroke();

      // Travel turns tag
      const midX = (pA.x + pB.x) / 2;
      const midY = (pA.y + pB.y) / 2;
      this.ctx.fillStyle = 'rgba(12, 16, 28, 0.85)';
      this.ctx.strokeStyle = '#232c45';
      this.ctx.lineWidth = 1;
      this.ctx.beginPath();
      this.ctx.arc(midX, midY, 11, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();

      this.ctx.fillStyle = '#8c9bbd';
      this.ctx.font = '10px Rajdhani';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText(`${lane.travel_turns}T`, midX, midY);
    });
  }

  drawNodes(frame) {
    const nodes = this.replayData.map.nodes;
    nodes.forEach(staticNode => {
      const p = this.getNodeScreenPos(staticNode.id);
      if (!p) return;

      const dynamicNode = frame.nodes[String(staticNode.id)] || staticNode;
      const owner = dynamicNode.owner;
      const isRelic = (staticNode.id === 7);
      const radius = isRelic ? 28 : (staticNode.id === 0 || staticNode.id === 14 ? 26 : 22);

      // Relic glow
      if (isRelic && frame.relic_active) {
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, radius + 10, 0, Math.PI * 2);
        this.ctx.fillStyle = 'rgba(255, 215, 0, 0.2)';
        this.ctx.fill();
      }

      // Base circle
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      this.ctx.fillStyle = '#0f1424';
      this.ctx.fill();

      // Owner colored border
      let strokeColor = '#7b88a8';
      if (owner === 1) strokeColor = '#00f3ff';
      else if (owner === 2) strokeColor = '#ff0055';
      else if (isRelic) strokeColor = '#ffd700';

      this.ctx.strokeStyle = strokeColor;
      this.ctx.lineWidth = (this.selectedNodeId === staticNode.id) ? 4 : 2.5;
      this.ctx.stroke();

      // Capture progress radial arc
      if (dynamicNode.capture_progress > 0) {
        this.ctx.beginPath();
        const capAngle = (dynamicNode.capture_progress / 2) * Math.PI * 2;
        this.ctx.arc(p.x, p.y, radius + 5, -Math.PI / 2, -Math.PI / 2 + capAngle);
        this.ctx.strokeStyle = dynamicNode.capturing_player === 1 ? '#00f3ff' : '#ff0055';
        this.ctx.lineWidth = 4;
        this.ctx.stroke();
      }

      // Node Name & ID
      this.ctx.fillStyle = '#ffffff';
      this.ctx.font = 'bold 11px Orbitron';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText(staticNode.id, p.x, p.y - 4);

      // Income tag below node
      this.ctx.font = '10px Rajdhani';
      this.ctx.fillStyle = '#8c9bbd';
      this.ctx.fillText(`+${staticNode.production}`, p.x, p.y + 10);

      // Units stationed badge
      const totalUnits = dynamicNode.total_units || 0;
      if (totalUnits > 0) {
        const badgeX = p.x + radius - 4;
        const badgeY = p.y - radius + 4;
        this.ctx.beginPath();
        this.ctx.arc(badgeX, badgeY, 10, 0, Math.PI * 2);
        this.ctx.fillStyle = dynamicNode.resident_player === 1 ? '#00f3ff' : (dynamicNode.resident_player === 2 ? '#ff0055' : '#555');
        this.ctx.fill();

        this.ctx.fillStyle = '#000';
        this.ctx.font = 'bold 10px Rajdhani';
        this.ctx.fillText(totalUnits, badgeX, badgeY);
      }
    });
  }

  drawFleets(frame) {
    if (!frame.fleets) return;

    frame.fleets.forEach(fleet => {
      const pA = this.getNodeScreenPos(fleet.origin_node);
      const pB = this.getNodeScreenPos(fleet.dest_node);
      if (!pA || !pB) return;

      const progress = 1.0 - (fleet.turns_remaining / fleet.total_turns);
      const fx = pA.x + (pB.x - pA.x) * progress;
      const fy = pA.y + (pB.y - pA.y) * progress;

      const isP1 = (fleet.owner === 1);
      const fleetColor = isP1 ? '#00f3ff' : '#ff0055';

      let isMasked = false;
      if (this.viewMode === 'p1' && !isP1) isMasked = true;
      if (this.viewMode === 'p2' && isP1) isMasked = true;

      this.ctx.beginPath();
      this.ctx.arc(fx, fy, 14, 0, Math.PI * 2);
      this.ctx.fillStyle = 'rgba(10, 14, 24, 0.9)';
      this.ctx.fill();
      this.ctx.strokeStyle = fleetColor;
      this.ctx.lineWidth = 2;
      this.ctx.stroke();

      this.ctx.fillStyle = fleetColor;
      this.ctx.font = 'bold 10px Orbitron';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';

      if (isMasked) {
        this.ctx.fillText(`?`, fx, fy - 2);
      } else {
        this.ctx.fillText(fleet.total_count, fx, fy - 2);
      }

      this.ctx.font = '8px Rajdhani';
      this.ctx.fillStyle = '#8c9bbd';
      this.ctx.fillText(`${fleet.turns_remaining}T`, fx, fy + 8);
    });
  }

  drawParticles() {
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.life -= 0.03;

      if (p.life <= 0) {
        this.particles.splice(i, 1);
        continue;
      }

      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, 3 * p.life, 0, Math.PI * 2);
      this.ctx.fillStyle = p.color;
      this.ctx.globalAlpha = p.life;
      this.ctx.fill();
      this.ctx.globalAlpha = 1.0;
    }
  }

  drawLoadingMessage() {
    this.ctx.fillStyle = '#8c9bbd';
    this.ctx.font = '18px Orbitron';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('LOADING ESPORTS ARENA SIMULATION...', this.displayWidth / 2, this.displayHeight / 2);
  }

  handleCanvasClick(e) {
    if (this.tacticalDragged) return;
    const {x:clickX,y:clickY}=this.tacticalPointer(e);

    if (!this.replayData) return;
    const nodes = this.replayData.map.nodes;
    for (const node of nodes) {
      const p = this.getNodeScreenPos(node.id);
      if (p) {
        const dist = Math.hypot(p.x - clickX, p.y - clickY);
        if (dist <= 30) {
          this.selectedNodeId = node.id;
          this.renderNodeInspector(node.id);
          return;
        }
      }
    }
    this.selectedNodeId = null;
    document.getElementById('inspector-content').innerHTML = '<p class="muted">Hover or click any node to inspect telemetry.</p>';
  }

  handleCanvasHover(e) {
    if (this.tacticalDrag) return;
    const {x:hoverX,y:hoverY}=this.tacticalPointer(e);

    if (!this.replayData) return;
    const nodes = this.replayData.map.nodes;
    let hovered = false;
    for (const node of nodes) {
      const p = this.getNodeScreenPos(node.id);
      if (p && Math.hypot(p.x - hoverX, p.y - hoverY) <= 30) {
        this.canvas.style.cursor = 'pointer';
        hovered = true;
        break;
      }
    }
    if (!hovered) this.canvas.style.cursor = 'default';
  }

  renderNodeInspector(nodeId) {
    if (!this.replayData) return;
    const frame = this.replayData.frames[this.currentFrameIdx];
    const node = this.replayData.map.nodes.find(n => n.id === nodeId);
    const dynamicNode = frame.nodes[String(nodeId)] || node;

    let ownerLabel = '<span style="color:#7b88a8">Neutral</span>';
    if (dynamicNode.owner === 1) ownerLabel = '<span style="color:#00f3ff">Player 1</span>';
    else if (dynamicNode.owner === 2) ownerLabel = '<span style="color:#ff0055">Player 2</span>';

    const units = dynamicNode.units || { raider: 0, siege: 0, guard: 0, scout: 0 };
    const defBonus = (node.id === 0 || node.id === 14) ? '+50% (Fortified Core)' : '+25%';
    const content = `
      <div class="inspector-item"><strong>Node ${node.id}:</strong> ${node.name}</div>
      <div class="inspector-item"><strong>Owner:</strong> ${ownerLabel}</div>
      <div class="inspector-item"><strong>Production:</strong> +${node.production} Gold/T 🪙</div>
      <div class="inspector-item"><strong>Defense Bonus:</strong> ${defBonus}</div>
      <div class="inspector-item"><strong>Capture Progress:</strong> ${dynamicNode.capture_progress}/2</div>
      <hr style="border-color:#232c45; margin: 8px 0;">
      <div class="inspector-item"><strong>Garrison:</strong></div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.85rem; margin-top:4px;">
        <div>Raiders: <strong style="color:#00f3ff">${units.raider || 0}</strong></div>
        <div>Siege: <strong style="color:#ff9900">${units.siege || 0}</strong></div>
        <div>Guards: <strong style="color:#4caf50">${units.guard || 0}</strong></div>
        <div>Scouts: <strong style="color:#ba68c8">${units.scout || 0}</strong></div>
      </div>
    `;
    document.getElementById('inspector-content').innerHTML = content;
  }
}

// Instantiate visualizer when page loads
window.addEventListener('DOMContentLoaded', () => {
  window.visualizer = new NodeWarVisualizer();
});
