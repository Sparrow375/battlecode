// =============================================================================
// Node War - 2D Cartoon Tower Defense Visualizer (Kingdom Rush / TD Style)
// =============================================================================

class NodeWarTDVisualizer {
  constructor(canvasId = 'td-canvas') {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error("TD Canvas not found:", canvasId);
      return;
    }
    this.ctx = this.canvas.getContext('2d');

    this.replayData = null;
    this.currentFrameIdx = 0;
    this.viewMode = 'spectator'; // 'spectator' | 'p1' | 'p2'
    this.selectedNodeId = null;

    this.displayWidth = 800;
    this.displayHeight = 600;

    // Sprite Asset Cache
    this.assets = {};
    this.assetsLoaded = false;

    // Combat & Environmental FX
    this.combatParticles = [];
    this.floatingTexts = [];

    // Static Decor Placement (Trees, Rocks, Huts, Fences)
    this.decorations = [];

    this.initCanvasResize();
    this.loadAssets();
    this.bindEvents();
    this.startAnimationLoop();
  }

  // ---------------------------------------------------------------------------
  // 1. Asset Preloading
  // ---------------------------------------------------------------------------
  loadAssets() {
    const assetManifest = {
      // Buildings
      castle_p1: 'assets/td/buildings/castle_p1.svg',
      castle_p2: 'assets/td/buildings/castle_p2.svg',
      castle_neutral: 'assets/td/buildings/castle_neutral.svg',
      tower_stone: 'assets/td/buildings/tower_stone.svg',
      barracks: 'assets/td/buildings/barracks.svg',
      relic_shrine: 'assets/td/buildings/relic_shrine.svg',

      // Units
      knight_p1: 'assets/td/units/knight_guard_p1.svg',
      knight_p2: 'assets/td/units/knight_guard_p2.svg',
      rogue_p1: 'assets/td/units/rogue_raider_p1.svg',
      rogue_p2: 'assets/td/units/rogue_raider_p2.svg',
      cannon_p1: 'assets/td/units/cannon_siege_p1.svg',
      cannon_p2: 'assets/td/units/cannon_siege_p2.svg',
      eagle_p1: 'assets/td/units/eagle_scout_p1.svg',
      eagle_p2: 'assets/td/units/eagle_scout_p2.svg',

      // Environment
      tree: 'assets/td/env/tree_large.svg',
      rock: 'assets/td/env/rock.svg',
      hut: 'assets/td/env/hut.svg',
      fence: 'assets/td/env/fence.svg'
    };

    let loadedCount = 0;
    const totalCount = Object.keys(assetManifest).length;

    for (const [key, src] of Object.entries(assetManifest)) {
      const img = new Image();
      img.src = src;
      img.onload = () => {
        loadedCount++;
        if (loadedCount >= totalCount) {
          this.assetsLoaded = true;
          this.generateDecorations();
        }
      };
      img.onerror = () => {
        console.warn(`Could not load TD asset: ${src}`);
        loadedCount++;
        if (loadedCount >= totalCount) this.assetsLoaded = true;
      };
      this.assets[key] = img;
    }
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

  // ---------------------------------------------------------------------------
  // 2. Map Screen Coordinate Transform & Road Geometry
  // ---------------------------------------------------------------------------
  getNodeScreenPos(nodeId) {
    if (!this.replayData) return null;
    const node = this.replayData.map.nodes.find(n => n.id === nodeId);
    if (!node) return null;

    const padX = 100;
    const padY = 70;
    const w = this.displayWidth - padX * 2;
    const h = this.displayHeight - padY * 2;

    return {
      x: padX + (node.x / 100) * w,
      y: padY + (node.y / 100) * h
    };
  }

  generateDecorations() {
    this.decorations = [];
    const count = 35;
    const seedPrng = (s) => () => (s = Math.sin(s) * 10000, s - Math.floor(s));
    const random = seedPrng(42);

    for (let i = 0; i < count; i++) {
      const type = random() > 0.4 ? 'tree' : (random() > 0.4 ? 'rock' : (random() > 0.5 ? 'fence' : 'hut'));
      this.decorations.push({
        type,
        xRel: random() * 0.94 + 0.03,
        yRel: random() * 0.94 + 0.03,
        scale: 0.7 + random() * 0.4
      });
    }
  }

  // ---------------------------------------------------------------------------
  // 3. Rendering Pipeline (Layered Drawing)
  // ---------------------------------------------------------------------------
  startAnimationLoop() {
    const loop = () => {
      this.render();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  render() {
    this.ctx.clearRect(0, 0, this.displayWidth, this.displayHeight);

    // Layer 1: Cartoon Grass Meadow
    this.drawMeadowBackground();

    if (!this.replayData) {
      this.drawLoadingScreen();
      return;
    }

    const frame = this.replayData.frames[this.currentFrameIdx];

    // Layer 2: Winding Sand/Dirt Roads (Lanes)
    this.drawWindingRoads();

    // Layer 3: Environment Decor (Trees, Rocks, Fences)
    this.drawEnvironmentDecor();

    // Layer 4: Nodes as Illustrated Castles & Towers
    this.drawCastleNodes(frame);

    // Layer 5: Animated Soldier Squads on Paths
    this.drawSoldierSquads(frame);

    // Layer 6: Combat Clashes, Sparks, Cannon Smoke
    this.drawCombatFX();

    // Layer 7: Fog of War (Player Perspective)
    this.drawCartoonFogOfWar(frame);
  }

  drawMeadowBackground() {
    // Vibrant cartoon green meadow
    const grad = this.ctx.createRadialGradient(
      this.displayWidth / 2, this.displayHeight / 2, 50,
      this.displayWidth / 2, this.displayHeight / 2, this.displayWidth * 0.8
    );
    grad.addColorStop(0, '#9ad03b');
    grad.addColorStop(1, '#7bb828');
    this.ctx.fillStyle = grad;
    this.ctx.fillRect(0, 0, this.displayWidth, this.displayHeight);

    // Subtle cartoon grass blade clumps
    this.ctx.fillStyle = '#6ca320';
    const step = 60;
    for (let x = 30; x < this.displayWidth; x += step) {
      for (let y = 30; y < this.displayHeight; y += step) {
        const ox = ((x * 13) % 20) - 10;
        const oy = ((y * 17) % 20) - 10;
        this.ctx.fillRect(x + ox, y + oy, 3, 4);
        this.ctx.fillRect(x + ox + 3, y + oy - 2, 3, 6);
      }
    }
  }

  drawWindingRoads() {
    const lanes = this.replayData.map.lanes;

    // Draw road underbed shadow
    lanes.forEach(lane => {
      const pA = this.getNodeScreenPos(lane.node_a);
      const pB = this.getNodeScreenPos(lane.node_b);
      if (!pA || !pB) return;

      this.ctx.beginPath();
      this.ctx.moveTo(pA.x, pA.y);
      this.ctx.lineTo(pB.x, pB.y);
      this.ctx.strokeStyle = '#997b53'; // Dark earth border
      this.ctx.lineWidth = 42;
      this.ctx.lineCap = 'round';
      this.ctx.lineJoin = 'round';
      this.ctx.stroke();
    });

    // Draw sand/dirt main path
    lanes.forEach(lane => {
      const pA = this.getNodeScreenPos(lane.node_a);
      const pB = this.getNodeScreenPos(lane.node_b);
      if (!pA || !pB) return;

      this.ctx.beginPath();
      this.ctx.moveTo(pA.x, pA.y);
      this.ctx.lineTo(pB.x, pB.y);
      this.ctx.strokeStyle = '#e9d8a6'; // Warm sandy dirt road
      this.ctx.lineWidth = 32;
      this.ctx.lineCap = 'round';
      this.ctx.lineJoin = 'round';
      this.ctx.stroke();

      // Road pebbles / cobblestone dots
      const midX = (pA.x + pB.x) / 2;
      const midY = (pA.y + pB.y) / 2;

      // Wooden Milestone Turn Signpost
      this.ctx.fillStyle = '#583115';
      this.ctx.strokeStyle = '#2b2d42';
      this.ctx.lineWidth = 2;
      this.ctx.beginPath();
      this.ctx.arc(midX, midY, 13, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();

      this.ctx.fillStyle = '#ffd166';
      this.ctx.font = 'bold 11px "Orbitron", monospace';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText(`${lane.travel_turns}T`, midX, midY);
    });
  }

  drawEnvironmentDecor() {
    if (!this.assetsLoaded) return;

    this.decorations.forEach(dec => {
      const img = this.assets[dec.type];
      if (!img) return;

      const x = dec.xRel * this.displayWidth;
      const y = dec.yRel * this.displayHeight;

      // Avoid placing decor right on top of nodes
      let tooClose = false;
      if (this.replayData) {
        for (const n of this.replayData.map.nodes) {
          const np = this.getNodeScreenPos(n.id);
          if (np && Math.hypot(np.x - x, np.y - y) < 65) {
            tooClose = true;
            break;
          }
        }
      }
      if (tooClose) return;

      const w = (img.width || 60) * dec.scale * 0.7;
      const h = (img.height || 60) * dec.scale * 0.7;

      this.ctx.drawImage(img, x - w / 2, y - h / 2, w, h);
    });
  }

  drawCastleNodes(frame) {
    const nodes = this.replayData.map.nodes;

    nodes.forEach(staticNode => {
      const p = this.getNodeScreenPos(staticNode.id);
      if (!p) return;

      const dynamicNode = frame.nodes[String(staticNode.id)] || staticNode;
      const owner = dynamicNode.owner;
      const isRelic = (staticNode.id === 7);
      const isHomeP1 = (staticNode.id === 0);
      const isHomeP2 = (staticNode.id === 14);

      // Node Selection Highlight Ring
      if (this.selectedNodeId === staticNode.id) {
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y + 4, 48, 0, Math.PI * 2);
        this.ctx.strokeStyle = '#ffd166';
        this.ctx.lineWidth = 4;
        this.ctx.setLineDash([8, 6]);
        this.ctx.stroke();
        this.ctx.restore();
      }

      // 1. Pick Castle / Tower Asset
      let img = null;
      let drawW = 80;
      let drawH = 80;

      if (isHomeP1) {
        img = this.assets.castle_p1;
        drawW = 120;
        drawH = 120;
      } else if (isHomeP2) {
        img = this.assets.castle_p2;
        drawW = 120;
        drawH = 120;
      } else if (isRelic) {
        img = this.assets.relic_shrine;
        drawW = 110;
        drawH = 115;
      } else if (staticNode.id === 5 || staticNode.id === 6 || staticNode.id === 8 || staticNode.id === 9) {
        // Chokepoints -> Stone Guard Tower
        img = this.assets.tower_stone;
        drawW = 85;
        drawH = 105;
      } else {
        // Economy Outposts -> Barracks
        img = this.assets.barracks;
        drawW = 95;
        drawH = 82;
      }

      // Relic Turn 95 Golden Awakening Pulse
      if (isRelic && frame.relic_active) {
        const pulse = 1.0 + Math.sin(Date.now() * 0.006) * 0.08;
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, 60 * pulse, 0, Math.PI * 2);
        this.ctx.fillStyle = 'rgba(255, 215, 0, 0.25)';
        this.ctx.fill();
        this.ctx.restore();
      }

      // Draw Structure Image
      if (img && this.assetsLoaded) {
        this.ctx.drawImage(img, p.x - drawW / 2, p.y - drawH / 2, drawW, drawH);
      }

      // 2. 2-Turn Capture Progress Arc (over castle gate)
      if (dynamicNode.capture_progress > 0) {
        this.ctx.save();
        this.ctx.beginPath();
        const capAngle = (dynamicNode.capture_progress / 2) * Math.PI * 2;
        this.ctx.arc(p.x, p.y, drawW * 0.45, -Math.PI / 2, -Math.PI / 2 + capAngle);
        this.ctx.strokeStyle = dynamicNode.capturing_player === 1 ? '#3a86ff' : '#e63946';
        this.ctx.lineWidth = 5;
        this.ctx.stroke();
        this.ctx.restore();
      }

      // 3. Cartoon Wooden Nameplate & Income Tag Below Structure
      this.drawWoodenNameplate(p.x, p.y + drawH / 2 - 4, staticNode, dynamicNode);

      // 4. Stationed Garrison Soldiers Badge
      const totalUnits = dynamicNode.total_units || 0;
      if (totalUnits > 0) {
        const badgeX = p.x + drawW * 0.38;
        const badgeY = p.y - drawH * 0.36;
        const color = dynamicNode.resident_player === 1 ? '#3a86ff' : (dynamicNode.resident_player === 2 ? '#e63946' : '#6c757d');

        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(badgeX, badgeY, 14, 0, Math.PI * 2);
        this.ctx.fillStyle = color;
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2.5;
        this.ctx.fill();
        this.ctx.stroke();

        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 12px "Orbitron", sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(totalUnits, badgeX, badgeY);
        this.ctx.restore();
      }
    });
  }

  drawWoodenNameplate(x, y, staticNode, dynamicNode) {
    const isRelic = (staticNode.id === 7);
    const isHome = (staticNode.id === 0 || staticNode.id === 14);

    const title = isRelic ? `RELIC [7]` : (isHome ? `P${staticNode.id === 0 ? 1 : 2} CASTLE` : `NODE ${staticNode.id}`);
    const sub = `+${staticNode.production}`;

    // Wooden Plank
    this.ctx.save();
    this.ctx.fillStyle = '#583115';
    this.ctx.strokeStyle = '#2b2d42';
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    this.ctx.roundRect(x - 34, y, 68, 20, 4);
    this.ctx.fill();
    this.ctx.stroke();

    // Text
    this.ctx.fillStyle = '#ffd166';
    this.ctx.font = 'bold 9px "Orbitron", monospace';
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'middle';
    this.ctx.fillText(title, x, y + 6);

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = 'bold 8px "Rajdhani", sans-serif';
    this.ctx.fillText(`${sub} Credits`, x, y + 14);
    this.ctx.restore();
  }

  drawSoldierSquads(frame) {
    if (!frame.fleets || !this.assetsLoaded) return;

    frame.fleets.forEach(fleet => {
      const pA = this.getNodeScreenPos(fleet.origin_node);
      const pB = this.getNodeScreenPos(fleet.dest_node);
      if (!pA || !pB) return;

      const progress = 1.0 - (fleet.turns_remaining / fleet.total_turns);
      const fx = pA.x + (pB.x - pA.x) * progress;
      const fy = pA.y + (pB.y - pA.y) * progress;

      // Natural walking bobbing animation
      const walkBob = Math.sin(Date.now() * 0.015 + fleet.fleet_id) * 3;

      const isP1 = (fleet.owner === 1);
      const isMasked = (this.viewMode === 'p1' && !isP1) || (this.viewMode === 'p2' && isP1);

      if (isMasked) {
        // --- Shrouded Unknown Rogue Silhouette [?] ---
        const rogueImg = isP1 ? this.assets.rogue_p1 : this.assets.rogue_p2;
        if (rogueImg) {
          this.ctx.save();
          this.ctx.filter = 'brightness(0.2) opacity(0.7)';
          this.ctx.drawImage(rogueImg, fx - 20, fy - 22 + walkBob, 40, 40);
          this.ctx.restore();
        }

        // Question mark tag
        this.ctx.fillStyle = '#ffd166';
        this.ctx.font = 'bold 14px "Orbitron", monospace';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('?', fx, fy - 26);

      } else {
        // --- Actual Animated Cartoon Soldiers (Guards, Raiders, Siege, Scouts) ---
        const units = fleet.units || {};
        const models = [];

        // Pick distinct representative unit sprite
        let leadSprite = null;
        if ((units.siege || 0) > 0) {
          leadSprite = isP1 ? this.assets.cannon_p1 : this.assets.cannon_p2;
        } else if ((units.guard || 0) > 0) {
          leadSprite = isP1 ? this.assets.knight_p1 : this.assets.knight_p2;
        } else if ((units.raider || 0) > 0) {
          leadSprite = isP1 ? this.assets.rogue_p1 : this.assets.rogue_p2;
        } else {
          leadSprite = isP1 ? this.assets.eagle_p1 : this.assets.eagle_p2;
        }

        if (leadSprite) {
          this.ctx.drawImage(leadSprite, fx - 22, fy - 24 + walkBob, 44, 44);
        }

        // Flying scout companion overhead if scout present
        if ((units.scout || 0) > 0) {
          const eagle = isP1 ? this.assets.eagle_p1 : this.assets.eagle_p2;
          if (eagle) {
            const eagleFly = Math.sin(Date.now() * 0.008) * 4;
            this.ctx.drawImage(eagle, fx - 16, fy - 48 + eagleFly, 32, 32);
          }
        }

        // Wooden Banner with Total Unit Count
        const bannerColor = isP1 ? '#3a86ff' : '#e63946';
        this.ctx.save();
        this.ctx.fillStyle = '#583115';
        this.ctx.strokeStyle = bannerColor;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.roundRect(fx - 18, fy - 36, 36, 16, 4);
        this.ctx.fill();
        this.ctx.stroke();

        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 10px "Orbitron", monospace';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(fleet.total_count, fx, fy - 28);
        this.ctx.restore();
      }
    });
  }

  drawCombatFX() {
    for (let i = this.combatParticles.length - 1; i >= 0; i--) {
      const p = this.combatParticles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.15; // Gravity
      p.life -= 0.04;

      if (p.life <= 0) {
        this.combatParticles.splice(i, 1);
        continue;
      }

      this.ctx.save();
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
      this.ctx.fillStyle = p.color;
      this.ctx.globalAlpha = p.life;
      this.ctx.fill();
      this.ctx.restore();
    }
  }

  drawCartoonFogOfWar(frame) {
    if (this.viewMode === 'spectator') return;

    // Dark Twilight Shroud Canvas Mask
    const player = this.viewMode === 'p1' ? 1 : 2;

    this.ctx.save();
    // Create an offscreen darkness layer with transparent cutouts
    this.ctx.fillStyle = 'rgba(12, 16, 28, 0.78)';
    this.ctx.fillRect(0, 0, this.displayWidth, this.displayHeight);

    // Cut out warm lantern light circles around player's castles and towers
    this.ctx.globalCompositeOperation = 'destination-out';

    this.replayData.map.nodes.forEach(node => {
      const dynamicNode = frame.nodes[String(node.id)] || node;
      if (dynamicNode.owner === player || dynamicNode.resident_player === player) {
        const p = this.getNodeScreenPos(node.id);
        if (p) {
          const grad = this.ctx.createRadialGradient(p.x, p.y, 20, p.x, p.y, 110);
          grad.addColorStop(0, 'rgba(0,0,0,1)');
          grad.addColorStop(1, 'rgba(0,0,0,0)');
          this.ctx.fillStyle = grad;
          this.ctx.beginPath();
          this.ctx.arc(p.x, p.y, 110, 0, Math.PI * 2);
          this.ctx.fill();
        }
      }
    });

    // Cut out light circles around flying player scouts
    if (frame.fleets) {
      frame.fleets.forEach(fleet => {
        if (fleet.owner === player) {
          const pA = this.getNodeScreenPos(fleet.origin_node);
          const pB = this.getNodeScreenPos(fleet.dest_node);
          if (pA && pB) {
            const progress = 1.0 - (fleet.turns_remaining / fleet.total_turns);
            const fx = pA.x + (pB.x - pA.x) * progress;
            const fy = pA.y + (pB.y - pA.y) * progress;

            const radius = (fleet.units && fleet.units.scout > 0) ? 90 : 50;
            const grad = this.ctx.createRadialGradient(fx, fy, 15, fx, fy, radius);
            grad.addColorStop(0, 'rgba(0,0,0,1)');
            grad.addColorStop(1, 'rgba(0,0,0,0)');
            this.ctx.fillStyle = grad;
            this.ctx.beginPath();
            this.ctx.arc(fx, fy, radius, 0, Math.PI * 2);
            this.ctx.fill();
          }
        }
      });
    }

    this.ctx.restore();
  }

  drawLoadingScreen() {
    this.ctx.fillStyle = '#583115';
    this.ctx.font = 'bold 20px "Orbitron", monospace';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('PREPARING TOWER DEFENSE BATTLEFIELD...', this.displayWidth / 2, this.displayHeight / 2);
  }

  // ---------------------------------------------------------------------------
  // 4. Synchronization & Interaction
  // ---------------------------------------------------------------------------
  loadReplay(data) {
    this.replayData = data;
    this.currentFrameIdx = 0;
  }

  syncFrame(frame) {
    if (!this.replayData) return;
    this.currentFrameIdx = Math.max(0, Math.min(this.replayData.frames.length - 1, frame.turn - 1));

    // Spawn sparks if combat occurred on this frame
    if (frame.combat_events && frame.combat_events.length > 0) {
      frame.combat_events.forEach(cb => {
        const p = this.getNodeScreenPos(cb.node_id);
        if (!p) return;
        for (let i = 0; i < 22; i++) {
          this.combatParticles.push({
            x: p.x,
            y: p.y,
            vx: (Math.random() - 0.5) * 6,
            vy: (Math.random() - 0.5) * 6 - 2,
            life: 1.0,
            size: Math.random() * 4 + 2,
            color: Math.random() > 0.5 ? '#ffd166' : '#ff4d6d'
          });
        }
      });
    }
  }

  setViewMode(mode) {
    this.viewMode = mode;
  }

  bindEvents() {
    this.canvas.addEventListener('click', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      if (!this.replayData) return;
      for (const node of this.replayData.map.nodes) {
        const p = this.getNodeScreenPos(node.id);
        if (p && Math.hypot(p.x - clickX, p.y - clickY) < 45) {
          this.selectedNodeId = node.id;
          if (window.nodeWarApp) {
            window.nodeWarApp.selectNode(node.id);
          }
          return;
        }
      }
    });
  }
}

// Attach globally
window.NodeWarTDVisualizer = NodeWarTDVisualizer;
