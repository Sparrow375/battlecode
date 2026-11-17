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
      tower_p1: 'assets/td/buildings/tower_p1.svg',
      tower_p2: 'assets/td/buildings/tower_p2.svg',
      tower_neutral: 'assets/td/buildings/tower_neutral.svg',
      tower_stone: 'assets/td/buildings/tower_stone.svg',
      barracks_p1: 'assets/td/buildings/barracks_p1.svg',
      barracks_p2: 'assets/td/buildings/barracks_p2.svg',
      barracks_neutral: 'assets/td/buildings/barracks_neutral.svg',
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
      this._resizeBound = true;
    }
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

    // Continuous Sub-Turn Lerp Progress for Smooth Motion Interpolation
    if (window.nodeWarApp && window.nodeWarApp.isPlaying) {
      const elapsed = performance.now() - (this.currentTurnStartTime || performance.now());
      const duration = Math.max(50, window.nodeWarApp.speedMs || 1000);
      this.subTurnProgress = Math.min(1.0, Math.max(0.0, elapsed / duration));
    } else {
      this.subTurnProgress = 1.0;
    }

    // Layer 1: Cartoon Grass Meadow
    this.drawMeadowBackground();

    if (!this.replayData) {
      this.drawLoadingScreen();
      return;
    }

    const frame = this.replayData.frames[this.currentFrameIdx];
    if (!frame) return;

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
      const units = dynamicNode.units || { raider: 0, siege: 0, guard: 0, scout: 0 };
      const totalUnits = dynamicNode.total_units || (units.raider + units.siege + units.guard + units.scout) || 0;
      const residentPlayer = dynamicNode.resident_player || owner;

      // Check if battle is active at this node
      const activeBattle = frame.combat_events && frame.combat_events.find(cb => cb.node_id === staticNode.id);

      // Node Selection Highlight Ring
      if (this.selectedNodeId === staticNode.id) {
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y + 4, 52, 0, Math.PI * 2);
        this.ctx.strokeStyle = '#ffd166';
        this.ctx.lineWidth = 4;
        this.ctx.setLineDash([8, 6]);
        this.ctx.stroke();
        this.ctx.restore();
      }

      // 1. Pick Castle / Tower / Barracks Asset with full team coloration
      let img = null;
      let drawW = 80;
      let drawH = 80;
      const ownerSuffix = (owner === 1) ? '_p1' : (owner === 2 ? '_p2' : '_neutral');

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
      } else if (staticNode.id === 5 || staticNode.id === 6 || staticNode.id === 8 || staticNode.id === 9 || staticNode.id === 3 || staticNode.id === 11) {
        // Chokepoint Watchtowers (Full Team Tinting)
        img = this.assets['tower' + ownerSuffix] || this.assets.tower_stone;
        drawW = 85;
        drawH = 105;
      } else {
        // Economy Bastions / Refineries (Full Team Tinting)
        img = this.assets['barracks' + ownerSuffix] || this.assets.barracks;
        drawW = 95;
        drawH = 82;
      }

      // Ground Faction Base Ring
      this.ctx.save();
      this.ctx.beginPath();
      this.ctx.ellipse(p.x, p.y + drawH * 0.36, drawW * 0.44, drawH * 0.16, 0, 0, Math.PI * 2);
      if (owner === 1) {
        this.ctx.fillStyle = 'rgba(0, 210, 255, 0.25)';
        this.ctx.strokeStyle = '#00f0ff';
        this.ctx.lineWidth = 2.5;
      } else if (owner === 2) {
        this.ctx.fillStyle = 'rgba(255, 0, 85, 0.25)';
        this.ctx.strokeStyle = '#ff0055';
        this.ctx.lineWidth = 2.5;
      } else {
        this.ctx.fillStyle = 'rgba(100, 116, 139, 0.18)';
        this.ctx.strokeStyle = '#64748b';
        this.ctx.lineWidth = 1.8;
      }
      this.ctx.fill();
      this.ctx.stroke();
      this.ctx.restore();

      // 2. Battle Active Shockwaves & Warning Rings
      if (activeBattle) {
        const ringTime = (Date.now() * 0.04) % 45;
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, drawW * 0.42 + ringTime, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(255, 0, 85, ${1.0 - ringTime / 45})`;
        this.ctx.lineWidth = 3.5;
        this.ctx.stroke();
        this.ctx.restore();
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

      // Draw Main Structure Image
      if (img && this.assetsLoaded) {
        this.ctx.drawImage(img, p.x - drawW / 2, p.y - drawH / 2, drawW, drawH);
      }

      // 3. Stationed Garrison Soldiers Drawn Directly on the Castle!
      if (totalUnits > 0 && this.assetsLoaded) {
        const isP1 = (residentPlayer === 1);
        const knightSprite = isP1 ? this.assets.knight_p1 : this.assets.knight_p2;
        const rogueSprite = isP1 ? this.assets.rogue_p1 : this.assets.rogue_p2;
        const cannonSprite = isP1 ? this.assets.cannon_p1 : this.assets.cannon_p2;
        const eagleSprite = isP1 ? this.assets.eagle_p1 : this.assets.eagle_p2;

        const breathe = Math.sin(Date.now() * 0.004 + staticNode.id) * 1.5;

        // Draw Knight Guard stationed at left gate
        if ((units.guard || 0) > 0 && knightSprite) {
          this.ctx.drawImage(knightSprite, p.x - drawW * 0.38, p.y + drawH * 0.08 + breathe, 34, 34);
        }

        // Draw Rogue Raider stationed at right gate
        if ((units.raider || 0) > 0 && rogueSprite) {
          this.ctx.drawImage(rogueSprite, p.x + drawW * 0.12, p.y + drawH * 0.08 + breathe, 34, 34);
        }

        // Draw Cannon Siege parked beside wall
        if ((units.siege || 0) > 0 && cannonSprite) {
          this.ctx.drawImage(cannonSprite, p.x - drawW * 0.48, p.y - drawH * 0.12, 36, 32);
        }

        // Draw Eagle Scout perched on tower spire
        if ((units.scout || 0) > 0 && eagleSprite) {
          const wingBob = Math.sin(Date.now() * 0.006) * 3;
          this.ctx.drawImage(eagleSprite, p.x + drawW * 0.22, p.y - drawH * 0.44 + wingBob, 32, 32);
        }
      }

      // 4. 2-Turn Capture Progress Arc (over castle gate)
      if (dynamicNode.capture_progress > 0) {
        this.ctx.save();
        this.ctx.beginPath();
        const capAngle = (dynamicNode.capture_progress / 2) * Math.PI * 2;
        this.ctx.arc(p.x, p.y, drawW * 0.48, -Math.PI / 2, -Math.PI / 2 + capAngle);
        this.ctx.strokeStyle = dynamicNode.capturing_player === 1 ? '#00f3ff' : '#ff0055';
        this.ctx.lineWidth = 5;
        this.ctx.stroke();
        this.ctx.restore();
      }

      // 5. Streamlined Nameplate & Income Badge Below Structure
      this.drawStreamlinedBadge(p.x, p.y + drawH / 2 - 2, staticNode, dynamicNode);

      // 6. Clean Troop Breakdown Pill (only active unit types)
      this.drawTroopInventoryPill(p.x, p.y + drawH / 2 + 19, units, residentPlayer, totalUnits);

      // 7. Active Battle Alert Badge: Crossed Swords (⚔️ BATTLE! ⚔️)
      if (activeBattle) {
        const wobble = Math.sin(Date.now() * 0.02) * 5;
        this.ctx.save();
        this.ctx.translate(p.x, p.y - drawH * 0.58);
        this.ctx.rotate(wobble * Math.PI / 180);

        // Glowing Red/Gold Battle Pill
        this.ctx.fillStyle = '#ff0055';
        this.ctx.strokeStyle = '#ffd166';
        this.ctx.lineWidth = 3;
        this.ctx.shadowColor = '#ff0055';
        this.ctx.shadowBlur = 14;
        this.ctx.beginPath();
        if (typeof this.ctx.roundRect === 'function') {
          this.ctx.roundRect(-58, -15, 116, 30, 8);
        } else {
          this.ctx.rect(-58, -15, 116, 30);
        }
        this.ctx.fill();
        this.ctx.stroke();
        this.ctx.shadowBlur = 0;

        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 11px "Orbitron", monospace';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('⚔️ BATTLE! ⚔️', 0, 0);
        this.ctx.restore();
      }
    });
  }

  drawStreamlinedBadge(x, y, staticNode, dynamicNode) {
    const isRelic = (staticNode.id === 7);
    const owner = dynamicNode.owner;

    let title = `NODE ${staticNode.id}`;
    if (isRelic) title = `RELIC [7]`;
    else if (staticNode.id === 0) title = `P1 CORE`;
    else if (staticNode.id === 14) title = `P2 CORE`;
    else if (owner === 1) title = `P1 BASTION`;
    else if (owner === 2) title = `P2 BASTION`;

    const label = `${title} | +${staticNode.production}`;

    this.ctx.save();
    this.ctx.fillStyle = 'rgba(10, 14, 26, 0.92)';
    this.ctx.strokeStyle = owner === 1 ? '#00f3ff' : (owner === 2 ? '#ff0055' : '#718096');
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    const bw = 96;
    const bh = 18;
    if (typeof this.ctx.roundRect === 'function') {
      this.ctx.roundRect(x - bw / 2, y, bw, bh, 5);
    } else {
      this.ctx.rect(x - bw / 2, y, bw, bh);
    }
    this.ctx.fill();
    this.ctx.stroke();

    this.ctx.fillStyle = owner === 1 ? '#00f3ff' : (owner === 2 ? '#ff7096' : '#ffd166');
    this.ctx.font = 'bold 9px "Orbitron", monospace';
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'middle';
    this.ctx.fillText(label, x, y + bh / 2);
    this.ctx.restore();
  }

  drawTroopInventoryPill(x, y, units, residentPlayer, totalUnits) {
    if (totalUnits <= 0) {
      // De-clutter: don't render empty pills
      return;
    }

    const isP1 = (residentPlayer === 1);
    const isP2 = (residentPlayer === 2);
    const borderColor = isP1 ? '#00f3ff' : (isP2 ? '#ff0055' : '#7b88a8');

    // Only collect non-zero unit types
    const activeItems = [];
    if ((units.guard || 0) > 0) activeItems.push({ icon: '🛡️', count: units.guard, color: '#4caf50' });
    if ((units.raider || 0) > 0) activeItems.push({ icon: '🗡️', count: units.raider, color: '#00f3ff' });
    if ((units.siege || 0) > 0) activeItems.push({ icon: '💣', count: units.siege, color: '#ff9900' });
    if ((units.scout || 0) > 0) activeItems.push({ icon: '🦅', count: units.scout, color: '#ba68c8' });

    if (activeItems.length === 0) return;

    const itemWidth = 24;
    const w = Math.max(32, activeItems.length * itemWidth + 8);
    const h = 18;

    this.ctx.save();
    this.ctx.fillStyle = 'rgba(10, 14, 26, 0.92)';
    this.ctx.strokeStyle = borderColor;
    this.ctx.lineWidth = 1.8;
    this.ctx.beginPath();
    if (typeof this.ctx.roundRect === 'function') {
      this.ctx.roundRect(x - w / 2, y, w, h, 5);
    } else {
      this.ctx.rect(x - w / 2, y, w, h);
    }
    this.ctx.fill();
    this.ctx.stroke();

    this.ctx.font = 'bold 9px "Orbitron", monospace';
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'middle';

    activeItems.forEach((item, idx) => {
      const ix = (x - w / 2) + 4 + idx * itemWidth + itemWidth / 2;
      this.ctx.fillStyle = item.color;
      this.ctx.fillText(`${item.icon}${item.count}`, ix, y + h / 2);
    });

    this.ctx.restore();
  }

  drawSoldierSquads(frame) {
    if (!frame.fleets || !this.assetsLoaded) return;

    frame.fleets.forEach(fleet => {
      const pA = this.getNodeScreenPos(fleet.origin_node);
      const pB = this.getNodeScreenPos(fleet.dest_node);
      if (!pA || !pB) return;

      const turnsRemaining = fleet.turns_remaining;
      const totalTurns = fleet.total_turns;
      const turnStep = 1.0 / totalTurns;
      const baseProgress = 1.0 - (turnsRemaining / totalTurns);
      const subProg = (this.subTurnProgress !== undefined) ? this.subTurnProgress : 1.0;
      const progress = Math.max(0.0, Math.min(1.0, baseProgress + subProg * turnStep));
      const fx = pA.x + (pB.x - pA.x) * progress;
      const fy = pA.y + (pB.y - pA.y) * progress;

      // Road vector & orientation
      const dirX = pB.x - pA.x;
      const dirY = pB.y - pA.y;
      const dist = Math.hypot(dirX, dirY) || 1;
      const fwdX = dirX / dist;
      const fwdY = dirY / dist;
      const normX = -fwdY;
      const normY = fwdX;

      const isP1 = (fleet.owner === 1);
      const teamColor = isP1 ? '#00f3ff' : '#ff0055';
      const isMasked = (this.viewMode === 'p1' && !isP1) || (this.viewMode === 'p2' && isP1);

      // 1. Draw Animated Road Direction Chevrons (>> pointing to destination)
      this.drawMarchDirectionChevrons(fx, fy, fwdX, fwdY, teamColor);

      // 2. Draw Destination Target Warning at Destination Node
      this.drawDestinationTarget(pB.x, pB.y, fleet);

      if (isMasked) {
        // --- Shrouded Unknown Silhouette ---
        const rogueImg = isP1 ? this.assets.rogue_p1 : this.assets.rogue_p2;
        const walkBob = Math.sin(Date.now() * 0.015 + fleet.fleet_id) * 3;
        if (rogueImg) {
          this.ctx.save();
          this.ctx.filter = 'brightness(0.15) opacity(0.7)';
          this.ctx.drawImage(rogueImg, fx - 18, fy - 20 + walkBob, 36, 36);
          this.ctx.restore();
        }

        // Unknown fleet banner
        this.ctx.save();
        this.ctx.fillStyle = '#583115';
        this.ctx.strokeStyle = '#ffd166';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.roundRect(fx - 45, fy - 36, 90, 18, 4);
        this.ctx.fill();
        this.ctx.stroke();

        this.ctx.fillStyle = '#ffd166';
        this.ctx.font = 'bold 9px "Orbitron", monospace';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(`? UNKNOWN FLEET`, fx, fy - 27);
        this.ctx.restore();

      } else {
        // --- Render EVERY Individual Soldier Sprite in Tactical Formation! ---
        const units = fleet.units || {};
        const squadUnits = [];

        // Add Guards
        for (let i = 0; i < (units.guard || 0); i++) {
          squadUnits.push({ type: 'guard', img: isP1 ? this.assets.knight_p1 : this.assets.knight_p2, rank: 0 });
        }
        // Add Raiders
        for (let i = 0; i < (units.raider || 0); i++) {
          squadUnits.push({ type: 'raider', img: isP1 ? this.assets.rogue_p1 : this.assets.rogue_p2, rank: 1 });
        }
        // Add Siege Cannons
        for (let i = 0; i < (units.siege || 0); i++) {
          squadUnits.push({ type: 'siege', img: isP1 ? this.assets.cannon_p1 : this.assets.cannon_p2, rank: 2 });
        }
        // Add Scouts
        for (let i = 0; i < (units.scout || 0); i++) {
          squadUnits.push({ type: 'scout', img: isP1 ? this.assets.eagle_p1 : this.assets.eagle_p2, rank: 3 });
        }

        // Draw each individual soldier sprite in formation
        const maxDraw = Math.min(squadUnits.length, 8);
        for (let i = 0; i < maxDraw; i++) {
          const u = squadUnits[i];
          const walkBob = Math.sin(Date.now() * 0.016 + i * 0.9 + fleet.fleet_id) * 3;

          // Spread laterally across road and forward/backward
          const colOffset = ((i % 3) - 1) * 14;
          const rowOffset = - Math.floor(i / 3) * 16;

          const ux = fx + normX * colOffset + fwdX * rowOffset;
          const uy = fy + normY * colOffset + fwdY * rowOffset;

          if (u.type === 'scout') {
            // Eagle flying overhead
            this.ctx.drawImage(u.img, ux - 15, uy - 34 + walkBob, 30, 30);
          } else {
            // Ground soldier marching
            this.ctx.drawImage(u.img, ux - 15, uy - 18 + walkBob, 30, 30);
          }
        }

        // Tactical Esports Squad Banner with Destination & Composition
        this.drawSquadEsportsBanner(fx, fy - 38, fleet, units, isP1);
      }
    });
  }

  drawMarchDirectionChevrons(fx, fy, fwdX, fwdY, teamColor) {
    this.ctx.save();
    this.ctx.strokeStyle = teamColor;
    this.ctx.lineWidth = 2.5;
    this.ctx.lineCap = 'round';

    const timePhase = (Date.now() * 0.005) % 1.0;
    for (let c = 0; c < 3; c++) {
      const distFwd = 24 + ((c + timePhase) * 12);
      const cx = fx + fwdX * distFwd;
      const cy = fy + fwdY * distFwd;

      // Draw chevron V pointing forward
      const tipX = cx + fwdX * 6;
      const tipY = cy + fwdY * 6;
      const wing1X = cx - fwdX * 4 + (-fwdY) * 6;
      const wing1Y = cy - fwdY * 4 + (fwdX) * 6;
      const wing2X = cx - fwdX * 4 - (-fwdY) * 6;
      const wing2Y = cy - fwdY * 4 - (fwdX) * 6;

      this.ctx.beginPath();
      this.ctx.moveTo(wing1X, wing1Y);
      this.ctx.lineTo(tipX, tipY);
      this.ctx.lineTo(wing2X, wing2Y);
      this.ctx.globalAlpha = 1.0 - (c / 3);
      this.ctx.stroke();
    }
    this.ctx.restore();
  }

  drawDestinationTarget(tx, ty, fleet) {
    const isP1 = (fleet.owner === 1);
    const color = isP1 ? '#00f3ff' : '#ff0055';
    const pulse = 1.0 + Math.sin(Date.now() * 0.008 + fleet.fleet_id) * 0.15;

    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.arc(tx, ty, 38 * pulse, 0, Math.PI * 2);
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 2;
    this.ctx.setLineDash([6, 6]);
    this.ctx.stroke();
    this.ctx.restore();
  }

  drawSquadEsportsBanner(x, y, fleet, units, isP1) {
    const teamName = isP1 ? 'P1 CYAN' : 'P2 CRIMSON';
    const borderColor = isP1 ? '#00f3ff' : '#ff0055';

    const w = 120;
    const h = 28;

    this.ctx.save();
    // Banner box
    this.ctx.fillStyle = '#583115';
    this.ctx.strokeStyle = borderColor;
    this.ctx.lineWidth = 2.5;
    this.ctx.shadowColor = borderColor;
    this.ctx.shadowBlur = 8;
    this.ctx.beginPath();
    this.ctx.roundRect(x - w / 2, y, w, h, 6);
    this.ctx.fill();
    this.ctx.stroke();
    this.ctx.shadowBlur = 0;

    // Line 1: Team & Destination
    this.ctx.fillStyle = borderColor;
    this.ctx.font = 'bold 9px "Orbitron", monospace';
    this.ctx.textAlign = 'center';
    this.ctx.fillText(`${teamName} ➔ NODE ${fleet.dest_node} (${fleet.turns_remaining}T)`, x, y + 10);

    // Line 2: Troop Composition Strip: 🛡️2 🗡️3 💣1 🦅1
    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = 'bold 8px "Orbitron", monospace';
    const troopStr = `🛡️${units.guard || 0} 🗡️${units.raider || 0} 💣${units.siege || 0} 🦅${units.scout || 0}`;
    this.ctx.fillText(troopStr, x, y + 21);
    this.ctx.restore();
  }

  drawCombatFX() {
    // 1. Draw Particle Sparks
    for (let i = this.combatParticles.length - 1; i >= 0; i--) {
      const p = this.combatParticles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.14; // Gravity
      p.life -= 0.035;

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

    // 2. Draw Floating Battle Casualties Text (e.g. -2 GUARDS, CRIT!)
    for (let i = this.floatingTexts.length - 1; i >= 0; i--) {
      const ft = this.floatingTexts[i];
      ft.y += ft.vy;
      ft.life -= 0.02;

      if (ft.life <= 0) {
        this.floatingTexts.splice(i, 1);
        continue;
      }

      this.ctx.save();
      this.ctx.fillStyle = ft.color;
      this.ctx.globalAlpha = Math.max(0, ft.life);
      this.ctx.font = ft.font;
      this.ctx.textAlign = 'center';
      this.ctx.shadowColor = '#000000';
      this.ctx.shadowBlur = 4;
      this.ctx.fillText(ft.text, ft.x, ft.y);
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
    this.currentTurnStartTime = performance.now();
    this.currentFrameIdx = Math.max(0, Math.min(this.replayData.frames.length - 1, frame.turn - 1));

    // High-Visibility Battle Alerts & Floating Casualties
    if (frame.combat_events && frame.combat_events.length > 0) {
      const banner = document.getElementById('combat-banner');
      if (banner) {
        const firstCb = frame.combat_events[0];
        banner.textContent = `⚔️ TURN ${frame.turn}: BATTLE AT NODE ${firstCb.node_id}!`;
        banner.classList.remove('hidden');
        clearTimeout(this.bannerTimer);
        this.bannerTimer = setTimeout(() => banner.classList.add('hidden'), 2800);
      }

      frame.combat_events.forEach(cb => {
        const p = this.getNodeScreenPos(cb.node_id);
        if (!p) return;

        // Floating Clash Text
        this.floatingTexts.push({
          text: '⚔️ CLASH!',
          x: p.x,
          y: p.y - 48,
          vy: -1.3,
          life: 1.0,
          color: '#ffd166',
          font: 'bold 15px "Orbitron", monospace'
        });

        // Compute casualties if any
        let defCasualties = 0;
        let attCasualties = 0;
        for (const [ut, count] of Object.entries(cb.defenders_before || {})) {
          const rem = (cb.defenders_after && cb.defenders_after[ut]) || 0;
          defCasualties += (count - rem);
        }
        for (const [ut, count] of Object.entries(cb.attackers_before || {})) {
          const rem = (cb.attackers_after && cb.attackers_after[ut]) || 0;
          attCasualties += (count - rem);
        }

        if (defCasualties > 0 || attCasualties > 0) {
          this.floatingTexts.push({
            text: `💥 -${defCasualties + attCasualties} CASUALTIES`,
            x: p.x,
            y: p.y - 28,
            vy: -0.9,
            life: 1.2,
            color: '#ff4d6d',
            font: 'bold 12px "Rajdhani", sans-serif'
          });
        }

        if (cb.defender_bonus_applied) {
          this.floatingTexts.push({
            text: `🛡️ +25% DEFENSE BONUS`,
            x: p.x,
            y: p.y - 12,
            vy: -0.8,
            life: 1.3,
            color: '#4caf50',
            font: 'bold 11px "Rajdhani", sans-serif'
          });
        }

        // Particle sparks
        for (let i = 0; i < 30; i++) {
          this.combatParticles.push({
            x: p.x,
            y: p.y,
            vx: (Math.random() - 0.5) * 8,
            vy: (Math.random() - 0.5) * 8 - 2,
            life: 1.0,
            size: Math.random() * 5 + 2,
            color: Math.random() > 0.5 ? '#ffd166' : '#ff0055'
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
