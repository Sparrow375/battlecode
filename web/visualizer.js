// Node War - Web Canvas Spectator & Visualizer

class NodeWarVisualizer {
  constructor() {
    this.canvas = document.getElementById('game-canvas');
    this.ctx = this.canvas.getContext('2d');

    this.replayData = null;
    this.currentFrameIdx = 0;
    this.isPlaying = false;
    this.playbackInterval = null;
    this.speedMs = 250;
    this.viewMode = 'spectator'; // 'spectator' | 'p1' | 'p2'
    this.selectedNodeId = null;

    this.particles = [];

    this.initCanvasResize();
    this.bindEvents();
    this.loadReplayList();
    this.startAnimationLoop();
  }

  initCanvasResize() {
    const resize = () => {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      this.canvas.width = rect.width * dpr;
      this.canvas.height = rect.height * dpr;
      this.ctx.scale(dpr, dpr);
      this.displayWidth = rect.width;
      this.displayHeight = rect.height;
    };
    window.addEventListener('resize', resize);
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
      });
    });

    // Run Battle button
    document.getElementById('btn-run-match').addEventListener('click', () => this.runNewMatch());

    // Load replay button
    document.getElementById('btn-load-replay').addEventListener('click', () => {
      const sel = document.getElementById('replay-dropdown');
      if (sel.value) this.fetchReplay(sel.value);
    });

    // Keyboard shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space') {
        e.preventDefault();
        this.togglePlay();
      } else if (e.code === 'ArrowRight') {
        this.stepFrame(1);
      } else if (e.code === 'ArrowLeft') {
        this.stepFrame(-1);
      }
    });

    // Node click/hover detection
    this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
    this.canvas.addEventListener('mousemove', (e) => this.handleCanvasHover(e));
  }

  async loadReplayList() {
    try {
      const res = await fetch('/api/replays');
      const data = await res.json();
      const sel = document.getElementById('replay-dropdown');
      sel.innerHTML = '';
      if (data.replays && data.replays.length > 0) {
        data.replays.forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.textContent = name;
          sel.appendChild(opt);
        });
        // Auto-load latest replay
        this.fetchReplay(data.replays[0]);
      } else {
        sel.innerHTML = '<option value="">No replays found</option>';
        // Auto-run a demo match
        this.runNewMatch();
      }
    } catch (err) {
      console.warn("Could not fetch replay list:", err);
    }
  }

  async fetchReplay(filename) {
    try {
      const res = await fetch(`/api/replay/${filename}`);
      const data = await res.json();
      this.loadReplayData(data);
    } catch (err) {
      console.error("Failed to load replay:", err);
    }
  }

  async runNewMatch() {
    const btn = document.getElementById('btn-run-match');
    btn.disabled = true;
    btn.textContent = 'SIMULATING...';

    const p1 = document.getElementById('select-p1').value;
    const p2 = document.getElementById('select-p2').value;
    const turns = parseInt(document.getElementById('input-turns').value) || 120;

    try {
      const res = await fetch('/api/run-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ p1, p2, turns })
      });
      const data = await res.json();
      this.loadReplayData(data);
      this.loadReplayList();
      this.play();
    } catch (err) {
      console.error("Match simulation failed:", err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'SIMULATE BATTLE';
    }
  }

  loadReplayData(data) {
    this.replayData = data;
    this.currentFrameIdx = 0;
    this.pause();

    const scrubber = document.getElementById('timeline-scrubber');
    scrubber.max = data.frames.length;
    scrubber.value = 1;
    document.getElementById('max-turn').textContent = data.frames.length;

    // Header metadata
    document.getElementById('p1-name').textContent = data.metadata.p1_name;
    document.getElementById('p2-name').textContent = data.metadata.p2_name;

    this.logEvent(`Loaded Match: ${data.metadata.p1_name} vs ${data.metadata.p2_name}`, 'system');
    this.updateHUD();
  }

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
    this.currentFrameIdx = idx;
    document.getElementById('timeline-scrubber').value = idx + 1;
    this.updateHUD();
    this.checkFrameEvents();
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
      relicBadge.textContent = 'RELIC ACTIVE - 2X POINTS & +15/SEC';
    } else {
      relicBadge.className = 'relic-badge';
      relicBadge.textContent = `RELIC DORMANT (ACTIVATES TURN 95)`;
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
      this.render();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  render() {
    this.ctx.clearRect(0, 0, this.displayWidth, this.displayHeight);
    this.drawTacticalGrid();

    if (!this.replayData) {
      this.drawLoadingMessage();
      return;
    }

    const frame = this.replayData.frames[this.currentFrameIdx];
    this.drawLanes();
    this.drawFleets(frame);
    this.drawNodes(frame);
    this.drawParticles();
  }

  drawTacticalGrid() {
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
      this.ctx.strokeStyle = 'rgba(60, 80, 120, 0.4)';
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

      // Calculate transit position interpolation
      // fleet.turns_remaining: from total_turns down to 1
      const progress = 1.0 - (fleet.turns_remaining / fleet.total_turns);
      const fx = pA.x + (pB.x - pA.x) * progress;
      const fy = pA.y + (pB.y - pA.y) * progress;

      const isP1 = (fleet.owner === 1);
      const fleetColor = isP1 ? '#00f3ff' : '#ff0055';

      // Check fog of war mask
      let isMasked = false;
      if (this.viewMode === 'p1' && !isP1) isMasked = true;
      if (this.viewMode === 'p2' && isP1) isMasked = true;

      // Draw fleet icon
      this.ctx.beginPath();
      this.ctx.arc(fx, fy, 14, 0, Math.PI * 2);
      this.ctx.fillStyle = 'rgba(10, 14, 24, 0.9)';
      this.ctx.fill();
      this.ctx.strokeStyle = fleetColor;
      this.ctx.lineWidth = 2;
      this.ctx.stroke();

      // Fleet text
      this.ctx.fillStyle = fleetColor;
      this.ctx.font = 'bold 10px Orbitron';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';

      if (isMasked) {
        this.ctx.fillText(`?`, fx, fy - 2);
      } else {
        this.ctx.fillText(fleet.total_count, fx, fy - 2);
      }

      // Small ETA tag
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
    const rect = this.canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

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
    const rect = this.canvas.getBoundingClientRect();
    const hoverX = e.clientX - rect.left;
    const hoverY = e.clientY - rect.top;

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
    const content = `
      <div class="inspector-item"><strong>Node ${node.id}:</strong> ${node.name}</div>
      <div class="inspector-item"><strong>Owner:</strong> ${ownerLabel}</div>
      <div class="inspector-item"><strong>Production:</strong> +${node.production} Credits/T</div>
      <div class="inspector-item"><strong>Defense Bonus:</strong> +25%</div>
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
