// =============================================================================
// Node War - 3D Isometric Battlefield & Esports Spectator Engine (Three.js)
// =============================================================================

class NodeWarThreeVisualizer {
  static QUALITY = {
    low: { fps:30, pixelRatio:.75, shadow:0, particles:24, units:2, scenery:10 },
    medium: { fps:30, pixelRatio:1.25, shadow:1024, particles:96, units:3, scenery:16 },
    high: { fps:60, pixelRatio:2, shadow:2048, particles:256, units:4, scenery:22 }
  };

  constructor(containerId = 'three-container', options = {}) {
    this.options=options;
    this.events=new AbortController();
    this.quality='medium';this.qualitySettings=NodeWarThreeVisualizer.QUALITY.medium;
    this.metrics={fps:0,renderMs:0,drawCalls:0,triangles:0,geometries:0,textures:0,samples:0};
    this.adaptive=true;this.slowWindows=0;this.unstableWindows=0;
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.error("Three.js container not found:", containerId);
      return;
    }

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.replayData = null;
    this.currentFrameIdx = 0;
    this.viewMode = 'spectator'; // 'spectator' | 'p1' | 'p2'
    this.selectedNodeId = null;
    this.themeId = 'medieval';

    // Node & Lane 3D Object Registries
    this.nodeObjects = new Map(); // id -> { group, baseMesh, buildingMesh, beaconLight, ringMesh, labelSprite }
    this.laneObjects = [];        // list of lane visual objects
    this.fleetSquadGroups = new Map(); // fleetId -> THREE.Group
    this.garrisonGroups = new Map();   // nodeId -> THREE.Group

    // Combat & Environmental FX
    this.particles = [];
    this.combatBeams = [];
    this.relicAnimation = {
      active: false,
      obelisk: null,
      skybeam: null,
      rings: [],
      pulseLight: null
    };

    // Camera preset states & lerping
    this.cameraLerp = null; // { startPos, endPos, startTarget, endTarget, t: 0 }
    this.isCinematicOrbit = false;

    // Fog of war 3D shrouds
    this.fogShrouds = new Map(); // nodeId/laneKey -> Mesh

    this.tooltipEl = document.getElementById('three-tooltip');
    this.hoveredEntity = null;

    try { this.initScene();this.bindEvents();this.applyQuality('medium');this.startRenderLoop(); }
    catch(error) { this.dispose(); throw error; }
  }

  // ---------------------------------------------------------------------------
  // 1. Initialization & Lighting Rig
  // ---------------------------------------------------------------------------
  initScene() {
    const width = this.container.clientWidth || window.innerWidth * 0.6;
    const height = this.container.clientHeight || window.innerHeight * 0.8;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x060812);
    this.scene.fog = new THREE.FogExp2(0x060812, 0.00012);

    // Camera: High-angle isometric perspective
    this.camera = new THREE.PerspectiveCamera(38, width / height, 1, 4000);
    this.setCameraPresetPosition('iso');

    // WebGL Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.95;
    this.renderer.outputEncoding = THREE.sRGBEncoding;
    this.container.appendChild(this.renderer.domElement);
    this.renderer.domElement.addEventListener('webglcontextlost',event=>{
      event.preventDefault();this.fail(new Error('Graphics context lost'));
    },{signal:this.events.signal});
    this.emptyNotice = document.createElement('div');
    this.emptyNotice.className = 'renderer-notice';
    this.emptyNotice.textContent = 'Load a replay or simulate a match to begin.';
    this.emptyNotice.setAttribute('role','status');
    this.container.appendChild(this.emptyNotice);

    // OrbitControls
    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.18;
    this.controls.minDistance = 80;
    this.controls.maxDistance = 2000;
    this.controls.target.set(0, 0, 0);

    // Lighting Rig
    this.setupLighting();

    // Ground Arena Platform
    this.setupGroundPlatform();
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(256*3),3));
    particleGeometry.setAttribute('color',new THREE.BufferAttribute(new Float32Array(256*3),3));
    particleGeometry.setDrawRange(0,0);
    this.combatCloud = new THREE.Points(particleGeometry,new THREE.PointsMaterial({size:4,vertexColors:true,transparent:true,opacity:.9,depthWrite:false,blending:THREE.AdditiveBlending}));
    this.combatCloud.frustumCulled = false;
    this.scene.add(this.combatCloud);
    this.setTheme(this.themeId);
    this.fitCamera();

    // Resize Handler
    this.resizeHandler=()=>this.onResize();
    window.addEventListener('resize',this.resizeHandler,{signal:this.events.signal});
    this.resizeObserver = new ResizeObserver(() => this.onResize());
    this.resizeObserver.observe(this.container);
  }

  setupLighting() {
    // Ambient cyberpunk glow
    const ambientLight = new THREE.HemisphereLight(0xeaf5ff, 0x626c83, 0.95);
    this.scene.add(ambientLight);

    // Main Key Sunlight
    const keySun = new THREE.DirectionalLight(0xffffff, 1.1);
    keySun.position.set(250, 480, 200);
    keySun.castShadow = true;
    keySun.shadow.mapSize.width = 2048;
    keySun.shadow.mapSize.height = 2048;
    keySun.shadow.camera.near = 50;
    keySun.shadow.camera.far = 1200;
    const d = 420;
    keySun.shadow.camera.left = -d;
    keySun.shadow.camera.right = d;
    keySun.shadow.camera.top = d;
    keySun.shadow.camera.bottom = -d;
    keySun.shadow.bias = -0.0005;
    this.scene.add(keySun);
    this.keySun=keySun;

    // Secondary Cool Blue Fill
    const fillLight = new THREE.DirectionalLight(0x00f3ff, 0.4);
    fillLight.position.set(-300, 250, -200);
    this.scene.add(fillLight);

    // Player 1 Cyan Accent Light (Home Citadel)
    this.p1BeaconLight = new THREE.PointLight(0x00f3ff, 2.5, 380, 1.5);
    this.p1BeaconLight.position.set(-360, 25, 0);
    this.scene.add(this.p1BeaconLight);

    // Player 2 Crimson Accent Light (Home Citadel)
    this.p2BeaconLight = new THREE.PointLight(0xff0055, 2.5, 380, 1.5);
    this.p2BeaconLight.position.set(360, 25, 0);
    this.scene.add(this.p2BeaconLight);

    // Relic Central Gold Accent Light
    this.relicLight = new THREE.PointLight(0xffd700, 1.8, 300, 1.4);
    this.relicLight.position.set(0, 35, 0);
    this.scene.add(this.relicLight);
  }

  setupGroundPlatform() {
    // Cyber arena battleground base slab
    const groundGeo = new THREE.CylinderGeometry(460, 480, 14, 32);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x070b16,
      roughness: 0.85,
      metalness: 0.45
    });
    const groundMesh = new THREE.Mesh(groundGeo, groundMat);
    groundMesh.position.y = -7;
    groundMesh.receiveShadow = true;
    this.scene.add(groundMesh);
    this.groundMesh = groundMesh;

    // Hexagonal boundary border ring
    const ringGeo = new THREE.TorusGeometry(462, 3, 16, 64);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x1f2e4d, wireframe: false });
    const borderRing = new THREE.Mesh(ringGeo, ringMat);
    borderRing.rotation.x = Math.PI / 2;
    borderRing.position.y = 0.5;
    this.scene.add(borderRing);
    this.borderRing = borderRing;

    // Subtle tactical coordinate grid
    const gridHelper = new THREE.GridHelper(900, 36, 0x18243c, 0x0c1322);
    gridHelper.position.y = 0.2;
    this.scene.add(gridHelper);
    this.gridHelper = gridHelper;
    gridHelper.material.transparent = true;
    gridHelper.material.opacity = .16;

    // Floating arena ambient dust particles
    const starGeo = new THREE.BufferGeometry();
    const starCount = 350;
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 1100;
      starPositions[i + 1] = Math.random() * 250 + 10;
      starPositions[i + 2] = (Math.random() - 0.5) * 800;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const starMat = new THREE.PointsMaterial({
      color: 0x3d5a80,
      size: 2.2,
      transparent: true,
      opacity: 0.6
    });
    this.ambientDust = new THREE.Points(starGeo, starMat);
    this.scene.add(this.ambientDust);
  }

  onResize() {
    if (!this.container || !this.camera || !this.renderer) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (!w || !h) return; // Hidden view must never create an invalid projection matrix.
    const refit = !this.hasOpened || (this.defaultCameraPosition && this.camera.position.distanceTo(this.defaultCameraPosition) < 1);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
    if (refit) { this.fitCamera(); this.hasOpened = true; }
  }

  applyQuality(id) {
    if (!NodeWarThreeVisualizer.QUALITY[id] || this.disposed) return;
    this.quality=id;this.qualitySettings=NodeWarThreeVisualizer.QUALITY[id];
    const q=this.qualitySettings;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,q.pixelRatio));
    this.renderer.shadowMap.enabled=!!q.shadow;
    if(this.keySun) {
      this.keySun.castShadow=!!q.shadow;
      if(this.keySun.shadow.map) { this.keySun.shadow.map.dispose();this.keySun.shadow.map=null; }
      this.keySun.shadow.mapSize.set(q.shadow || 512,q.shadow || 512);
    }
    this.scene.traverse(obj=>{if(obj.isPointLight) obj.visible=id!=='low';});
    if(this.ambientDust) this.ambientDust.geometry.setDrawRange(0,id==='low'?50:id==='medium'?160:350);
    this.slowWindows=0;this.unstableWindows=0;this.metricWindow=null;
    // Quality affects presentation detail only. Rebuild once, not on every render tick.
    if(this.replayData) {
      const frame=this.currentFrame;
      this.buildMapArchitecture(this.replayData.map);
      this.setTheme(this.themeId);
      if(frame) this.syncFrame(frame);
    }
    this.onResize();
  }

  recordMetrics(timestamp,cost) {
    if(document.hidden) {this.metricWindow=null;return;}
    if(!this.metricWindow) this.metricWindow={start:timestamp,frames:0,cost:0};
    const m=this.metricWindow;m.frames++;m.cost+=cost;
    const elapsed=timestamp-m.start;
    if(elapsed<2000) return;
    this.metrics={fps:m.frames*1000/elapsed,renderMs:m.cost/m.frames,
      drawCalls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles,
      geometries:this.renderer.info.memory.geometries,textures:this.renderer.info.memory.textures,samples:(this.metrics.samples || 0)+1};
    this.metricWindow=null;
    if(this.onMetrics) this.onMetrics(this.metrics);
    if(!this.adaptive) return;
    const slow=this.metrics.fps<this.qualitySettings.fps*.65 || this.metrics.renderMs>1000/this.qualitySettings.fps*.9;
    this.slowWindows=slow?this.slowWindows+1:0;
    this.unstableWindows=this.metrics.fps<8?this.unstableWindows+1:0;
    if(this.slowWindows>=3 && this.quality!=='low') {
      const next=this.quality==='high'?'medium':'low';this.applyQuality(next);
      if(this.onQualityChange) this.onQualityChange(next);
    } else if(this.quality==='low' && this.unstableWindows>=4) this.fail(new Error('Graphics frame rate became unstable'));
  }

  fail(error) {
    if(this.disposed || this.failed) return;
    this.failed=true;
    if(this.options.onFailure) this.options.onFailure(error);
    else this.dispose();
  }

  dispose() {
    if(this.disposed) return;
    this.disposed=true;this.onBeforeRender=null;this.onMetrics=null;this.onQualityChange=null;
    if(this.rafId!==undefined) cancelAnimationFrame(this.rafId);
    if(this.events) this.events.abort();
    if(this.resizeObserver) this.resizeObserver.disconnect();
    if(this.controls) this.controls.dispose();
    if(this.scene) {
      this.scene.traverse(obj=>{if(obj.isLight && obj.shadow && obj.shadow.map) obj.shadow.map.dispose();});
      window.Arena3DArt.dispose(this.scene);this.scene.clear();
    }
    if(this.renderer) {this.renderer.dispose();this.renderer.forceContextLoss();this.renderer.domElement.remove();}
    if(this.emptyNotice) this.emptyNotice.remove();
    if(this.tooltipEl) this.tooltipEl.classList.add('hidden');
    for(const key of ['nodeObjects','garrisonGroups','fleetSquadGroups','fogShrouds']) if(this[key]) this[key].clear();
    this.particles=[];this.laneObjects=[];
  }

  fitCamera() {
    const halfFov = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const distance = Math.max(390 / (Math.tan(halfFov) * this.camera.aspect), 285 / Math.tan(halfFov)) * 1.12;
    this.defaultCameraPosition = new THREE.Vector3(0, .85, 1).normalize().multiplyScalar(distance);
    this.camera.position.copy(this.defaultCameraPosition);
    this.camera.lookAt(0, 0, 0);
    if (this.controls) { this.controls.target.set(0, 0, 0); this.controls.update(); }
  }

  // ---------------------------------------------------------------------------
  // 2. Map Coordinates & Procedural 3D Fortresses
  // ---------------------------------------------------------------------------
  mapToWorld(xPercent, yPercent) {
    // Maps 0..100 map space to -360..360 X, -210..210 Z
    const scaleX = 7.8;
    const scaleZ = 5.2;
    return {
      x: (xPercent - 50) * scaleX,
      y: 0,
      z: (yPercent - 50) * scaleZ
    };
  }

  buildMapArchitecture(mapData) {
    this.particles = [];
    // Clear previous architecture if any
    this.nodeObjects.forEach(obj => { this.scene.remove(obj.group); window.Arena3DArt.dispose(obj.group); });
    this.nodeObjects.clear();
    this.laneObjects.forEach(lane => { this.scene.remove(lane.group); window.Arena3DArt.dispose(lane.group); });
    this.laneObjects = [];
    this.garrisonGroups.clear();
    this.fleetSquadGroups.forEach(group => { this.scene.remove(group); window.Arena3DArt.dispose(group); });
    this.fleetSquadGroups.clear();
    this.relicAnimation.rings = [];

    // 1. Build Lanes (Elevated Cyber-Rails)
    mapData.lanes.forEach(lane => {
      const nodeA = mapData.nodes.find(n => n.id === lane.node_a);
      const nodeB = mapData.nodes.find(n => n.id === lane.node_b);
      if (!nodeA || !nodeB) return;

      const pA = this.mapToWorld(nodeA.x, nodeA.y);
      const pB = this.mapToWorld(nodeB.x, nodeB.y);

      const laneGroup = new THREE.Group();

      // Rail path
      const vA = new THREE.Vector3(pA.x, 1.2, pA.z);
      const vB = new THREE.Vector3(pB.x, 1.2, pB.z);
      const curve = new THREE.LineCurve3(vA, vB);

      // Cyber-Highway track
      const tubeGeo = new THREE.TubeGeometry(curve, 12, 4, 6, false);
      const tubeMat = new THREE.MeshStandardMaterial({
        color: 0x728399,
        roughness: 0.6,
        metalness: 0.8
      });
      const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
      tubeMesh.receiveShadow = true;
      laneGroup.add(tubeMesh);

      // Glowing center energy rail
      const railGeo = new THREE.TubeGeometry(curve, 12, 0.7, 4, false);
      const railMat = new THREE.MeshBasicMaterial({
        color: 0x243b66,
        transparent: true,
        opacity: 0.8
      });
      const railMesh = new THREE.Mesh(railGeo, railMat);
      laneGroup.add(railMesh);

      // Travel Turns holographic badge at midpoint
      const mid = new THREE.Vector3().lerpVectors(vA, vB, 0.5);
      const badgePillar = new THREE.Mesh(
        new THREE.CylinderGeometry(1.2, 1.5, 3.5, 6),
        new THREE.MeshStandardMaterial({ color: 0x182438, metalness: 0.7 })
      );
      badgePillar.position.set(mid.x, 1.5, mid.z);
      laneGroup.add(badgePillar);

      const labelSprite = this.createTextSprite(`${lane.travel_turns}T`, {
        textColor: '#8c9bbd',
        bgColor: 'rgba(9, 13, 24, 0.85)',
        borderColor: '#232c45',
        fontSize: 22,
        padding: 4
      });
      labelSprite.position.set(mid.x, 5.5, mid.z);
      labelSprite.scale.set(16, 8, 1);
      laneGroup.add(labelSprite);

      this.scene.add(laneGroup);
      this.laneObjects.push({
        data: lane,
        group: laneGroup,
        pA,
        pB,
        railMesh
      });
    });

    // 2. Build Nodes (Fortresses, Refineries, Chokepoints, Relic Shrine)
    mapData.nodes.forEach(node => {
      const pos = this.mapToWorld(node.x, node.y);
      const nodeGroup = new THREE.Group();
      nodeGroup.position.set(pos.x, 0, pos.z);
      nodeGroup.userData = { type: 'node', id: node.id, nodeData: node };

      // Base Platform
      const isRelic = (node.id === 7);
      const isHome = (node.id === 0 || node.id === 14);
      const radius = isRelic ? 26 : (isHome ? 24 : 19);

      // Hexagonal Foundation Dais
      const baseGeo = new THREE.CylinderGeometry(radius, radius + 2, 4.5, 6);
      const baseMat = new THREE.MeshStandardMaterial({
        color: 0x0c1220,
        roughness: 0.7,
        metalness: 0.6
      });
      const baseMesh = new THREE.Mesh(baseGeo, baseMat);
      baseMesh.position.y = 2.25;
      baseMesh.receiveShadow = true;
      baseMesh.castShadow = true;
      nodeGroup.add(baseMesh);

      // Dynamic Holographic Capture Ring
      const ringGeo = new THREE.TorusGeometry(radius + 1.2, 0.8, 8, 32);
      const ringMat = new THREE.MeshStandardMaterial({
        color: this.getOwnerColor(node.owner),
        emissive: this.getOwnerColor(node.owner),
        emissiveIntensity: 0.8,
        metalness: 0.3
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.rotation.x = Math.PI / 2;
      ringMesh.position.y = 4.8;
      nodeGroup.add(ringMesh);

      // Specific Architectural Superstructures
      let buildingMesh = null;
      let beaconLight = null;

      if (isHome) {
        // --- Megastructure Command Bastion Citadel ---
        const citadel = window.Arena3DArt.building(this.themeId, 'core', node.owner, this.quality);
        citadel.position.y = 4.5;
        nodeGroup.add(citadel);
        buildingMesh = citadel;

        beaconLight = new THREE.PointLight(this.getOwnerColor(node.owner), 2.2, 120);
        beaconLight.visible=this.quality!=='low';
        beaconLight.position.set(0, 24, 0);
        nodeGroup.add(beaconLight);

      } else if (isRelic) {
        // --- The Ancient Relic Sanctuary ---
        const relicStructure = window.Arena3DArt.building(this.themeId, 'relic', node.owner, this.quality);
        this.relicAnimation.obelisk = relicStructure.userData.reactor;
        relicStructure.position.y = 4.5;
        nodeGroup.add(relicStructure);
        buildingMesh = relicStructure;

      } else if ([3,5,6,8,9,11].includes(node.id)) {
        // --- Heavy Chokepoint Pillbox Fort ---
        const chokepoint = window.Arena3DArt.building(this.themeId, 'tower', node.owner, this.quality);
        chokepoint.position.y = 4.5;
        nodeGroup.add(chokepoint);
        buildingMesh = chokepoint;

      } else {
        // --- Industrial Quantum Refinery / Outpost ---
        const outpost = window.Arena3DArt.building(this.themeId, 'bastion', node.owner, this.quality);
        outpost.position.y = 4.5;
        nodeGroup.add(outpost);
        buildingMesh = outpost;
      }

      // Floating Holographic Node Label Sprite
      const labelText = isRelic ? `RELIC [7]` : (isHome ? `P${node.id === 0 ? 1 : 2} CORE` : `N${node.id} (+${node.production})`);
      const labelSprite = this.createTextSprite(labelText, {
        textColor: '#ffffff',
        bgColor: 'rgba(10, 14, 25, 0.88)',
        borderColor: this.getOwnerHex(node.owner),
        fontSize: 30
      });
      labelSprite.position.set(0, isRelic ? 49 : (isHome ? 82 : 61), 0);
      labelSprite.scale.set(74, 37, 1);
      nodeGroup.add(labelSprite);

      this.scene.add(nodeGroup);
      this.nodeObjects.set(node.id, {
        id: node.id,
        group: nodeGroup,
        baseMesh,
        ringMesh,
        buildingMesh,
        beaconLight,
        labelSprite,
        isRelic,
        isHome
      });
      buildingMesh.userData.appearance = `${this.themeId}_${node.owner}`;
    });
  }

  // ---------------------------------------------------------------------------
  // 3. Procedural Superstructure Models (Citadels, Outposts, Relic)
  // ---------------------------------------------------------------------------
  createCitadelModel(playerId) {
    const group = new THREE.Group();
    const color = playerId === 1 ? 0x00f3ff : 0xff0055;

    // Citadel Lower Fortress Deck
    const lowerDeck = new THREE.Mesh(
      new THREE.CylinderGeometry(18, 20, 6, 6),
      new THREE.MeshStandardMaterial({ color: 0x12192a, metalness: 0.8, roughness: 0.3 })
    );
    lowerDeck.position.y = 3;
    lowerDeck.castShadow = true;
    group.add(lowerDeck);

    // 4 Corner Defense Turrets
    for (let i = 0; i < 4; i++) {
      const angle = (i * Math.PI) / 2;
      const tx = Math.cos(angle) * 14;
      const tz = Math.sin(angle) * 14;
      const turret = new THREE.Mesh(
        new THREE.CylinderGeometry(2, 2.5, 8, 8),
        new THREE.MeshStandardMaterial({ color: 0x1b243b, metalness: 0.9 })
      );
      turret.position.set(tx, 7, tz);
      group.add(turret);

      // Glowing Turret Cap
      const cap = new THREE.Mesh(
        new THREE.SphereGeometry(1.2, 8, 8),
        new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.9 })
      );
      cap.position.set(tx, 11, tz);
      group.add(cap);
    }

    // Command Tower Spire
    const tower = new THREE.Mesh(
      new THREE.CylinderGeometry(5, 7, 14, 6),
      new THREE.MeshStandardMaterial({ color: 0x182035, metalness: 0.7 })
    );
    tower.position.y = 13;
    tower.castShadow = true;
    group.add(tower);

    // Central Pulsing Power Reactor
    const reactor = new THREE.Mesh(
      new THREE.OctahedronGeometry(3.5, 0),
      new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 1.0,
        wireframe: false
      })
    );
    reactor.position.y = 22;
    group.add(reactor);
    group.userData.reactor = reactor;

    // Translucent Holographic Defense Dome (Garrison Shield)
    const domeMat = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.22,
      wireframe: true
    });
    const dome = new THREE.Mesh(new THREE.SphereGeometry(21, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2), domeMat);
    dome.position.y = 0;
    group.add(dome);
    group.userData.shieldDome = dome;

    return group;
  }

  createOutpostModel(production, owner) {
    const group = new THREE.Group();
    const color = this.getOwnerColor(owner);
    const height = production >= 15 ? 15 : 11;

    // Hexagonal Industrial Platform
    const deck = new THREE.Mesh(
      new THREE.CylinderGeometry(13, 15, 3.5, 6),
      new THREE.MeshStandardMaterial({ color: 0x141b2d, metalness: 0.75 })
    );
    deck.position.y = 1.75;
    group.add(deck);

    // Quantum Extractor Spire
    const spire = new THREE.Mesh(
      new THREE.CylinderGeometry(2.5, 4.5, height, 8),
      new THREE.MeshStandardMaterial({ color: 0x1f2a45, metalness: 0.85, roughness: 0.4 })
    );
    spire.position.y = 1.75 + height / 2;
    spire.castShadow = true;
    group.add(spire);

    // Spinning Magnetic Induction Rings
    const ring1 = new THREE.Mesh(
      new THREE.TorusGeometry(4.2, 0.4, 6, 16),
      new THREE.MeshBasicMaterial({ color: color, wireframe: false })
    );
    ring1.rotation.x = Math.PI / 2;
    ring1.position.y = 1.75 + height * 0.4;
    group.add(ring1);

    const ring2 = ring1.clone();
    ring2.position.y = 1.75 + height * 0.75;
    group.add(ring2);

    group.userData.rings = [ring1, ring2];

    // Beacon Top Light
    const beacon = new THREE.Mesh(
      new THREE.SphereGeometry(1.2, 8, 8),
      new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.9 })
    );
    beacon.position.y = 1.75 + height + 1;
    group.add(beacon);

    return group;
  }

  createChokepointModel(owner) {
    const group = new THREE.Group();
    const color = this.getOwnerColor(owner);

    // Armored Bunker
    const bunker = new THREE.Mesh(
      new THREE.BoxGeometry(20, 7, 16),
      new THREE.MeshStandardMaterial({ color: 0x172033, metalness: 0.85, roughness: 0.5 })
    );
    bunker.position.y = 3.5;
    bunker.castShadow = true;
    group.add(bunker);

    // Angled Blast Deflector Shields
    const shieldL = new THREE.Mesh(
      new THREE.BoxGeometry(2, 8, 14),
      new THREE.MeshStandardMaterial({ color: 0x222f4b, metalness: 0.9 })
    );
    shieldL.position.set(-9, 4, 0);
    shieldL.rotation.z = 0.2;
    group.add(shieldL);

    const shieldR = shieldL.clone();
    shieldR.position.set(9, 4, 0);
    shieldR.rotation.z = -0.2;
    group.add(shieldR);

    // Watchtower Pod
    const pod = new THREE.Mesh(
      new THREE.CylinderGeometry(4, 5, 5, 8),
      new THREE.MeshStandardMaterial({ color: 0x101624, metalness: 0.7 })
    );
    pod.position.y = 9;
    group.add(pod);

    // Searchlight
    const light = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 8, 8),
      new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.8 })
    );
    light.position.y = 12;
    group.add(light);

    return group;
  }

  createRelicSanctuary() {
    const group = new THREE.Group();

    // Ancient High-Tech Dais
    const dais = new THREE.Mesh(
      new THREE.CylinderGeometry(18, 22, 5, 8),
      new THREE.MeshStandardMaterial({ color: 0x151b29, metalness: 0.85, roughness: 0.3 })
    );
    dais.position.y = 2.5;
    group.add(dais);

    // Golden Rune Rings
    for (let r = 0; r < 2; r++) {
      const runeRing = new THREE.Mesh(
        new THREE.TorusGeometry(12 + r * 5, 0.4, 6, 32),
        new THREE.MeshBasicMaterial({ color: 0xffd700, transparent: true, opacity: 0.6 })
      );
      runeRing.rotation.x = Math.PI / 2;
      runeRing.position.y = 5.2;
      group.add(runeRing);
      this.relicAnimation.rings.push(runeRing);
    }

    // Levitating Multi-Faceted Golden Crystal Obelisk
    const obeliskGeo = new THREE.OctahedronGeometry(6.5, 0);
    obeliskGeo.scale(1, 2.4, 1); // Stretched crystal
    const obeliskMat = new THREE.MeshStandardMaterial({
      color: 0xffd700,
      emissive: 0xffaa00,
      emissiveIntensity: 0.6,
      metalness: 0.9,
      roughness: 0.15
    });
    const obelisk = new THREE.Mesh(obeliskGeo, obeliskMat);
    obelisk.position.y = 16;
    obelisk.castShadow = true;
    group.add(obelisk);
    this.relicAnimation.obelisk = obelisk;

    // Massive Golden Skybeam (Turn 95+ Activation)
    const beamGeo = new THREE.CylinderGeometry(3.5, 7, 360, 16, 1, true);
    const beamMat = new THREE.MeshBasicMaterial({
      color: 0xffd700,
      transparent: true,
      opacity: 0.0, // Invisible until activated
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const skybeam = new THREE.Mesh(beamGeo, beamMat);
    skybeam.position.y = 180;
    group.add(skybeam);
    this.relicAnimation.skybeam = skybeam;

    return group;
  }

  // ---------------------------------------------------------------------------
  // 4. Procedural 3D Soldier Models & Squads
  // ---------------------------------------------------------------------------
  createSoldierModel(unitType, owner, isShadow = false) {
    return window.Arena3DArt.unit(this.themeId, unitType, owner, isShadow, this.quality);

  }

  // ---------------------------------------------------------------------------
  // 5. Squad Layouts & Marching Synchronization
  // ---------------------------------------------------------------------------
  syncFrame(frame, prevFrame = null) {
    if (!this.replayData) return;
    const changed = this.currentFrame !== frame;
    this.currentFrame = frame;
    this.prevFrame = prevFrame || frame;
    this.frameStartTime = performance.now();
    if(this.container && this.container.classList.contains('hidden')) return;

    // 1. Update Nodes (Owners, Rings, Garrison Units, Capture)
    this.updateNodes3D(frame);

    // 2. Update Traveling Fleets (Squads marching along lanes)
    this.updateFleets3D(frame);

    // 3. Update Relic State (Turn 95 Awakening)
    this.updateRelic3D(frame);

    // 4. Trigger Combat Clashes & Particle FX
    if (changed && frame.combat_events && frame.combat_events.length > 0) {
      this.triggerCombatFX(frame.combat_events);
    }
  }

  updateNodes3D(frame) {
    this.nodeObjects.forEach((nodeObj, nodeId) => {
      const dynamicNode = frame.nodes[String(nodeId)] || frame.nodes[nodeId];
      if (!dynamicNode) return;

      const owner = dynamicNode.owner;
      const ownerColor = this.getOwnerColor(owner);
      const appearance = `${this.themeId}_${owner}`;
      if (nodeObj.buildingMesh.userData.appearance !== appearance) {
        nodeObj.group.remove(nodeObj.buildingMesh);
        window.Arena3DArt.dispose(nodeObj.buildingMesh);
        const kind = nodeObj.isRelic ? 'relic' : nodeObj.isHome ? 'core' : [3,5,6,8,9,11].includes(nodeId) ? 'tower' : 'bastion';
        const model = window.Arena3DArt.building(this.themeId, kind, owner, this.quality);
        model.position.y = 4.5; model.userData.appearance = appearance;
        nodeObj.group.add(model); nodeObj.buildingMesh = model;
        if (nodeObj.isRelic) this.relicAnimation.obelisk = model.userData.reactor;
      }

      // Update ring color
      nodeObj.ringMesh.material.color.setHex(ownerColor);
      nodeObj.ringMesh.material.emissive.setHex(ownerColor);

      // Capture progress effect (pulsing or scaling ring)
      if (dynamicNode.capture_progress > 0) {
        const capColor = this.getOwnerColor(dynamicNode.capturing_player);
        nodeObj.ringMesh.material.emissive.setHex(capColor);
        nodeObj.ringMesh.scale.setScalar(1.0 + dynamicNode.capture_progress * 0.15);
      } else {
        nodeObj.ringMesh.scale.setScalar(1.0);
      }

      // Update Beacon Light if present
      if (nodeObj.beaconLight) {
        nodeObj.beaconLight.color.setHex(ownerColor);
      }

      // Update Garrison 3D Soldiers stationed at Node
      this.renderGarrisonSquad(nodeId, dynamicNode, nodeObj.group);
    });
  }

  renderGarrisonSquad(nodeId, nodeData, parentGroup) {
    let squadGroup = this.garrisonGroups.get(nodeId);
    if (!squadGroup) {
      squadGroup = new THREE.Group();
      parentGroup.add(squadGroup);
      this.garrisonGroups.set(nodeId, squadGroup);
    }

    const isMasked = this.isNodeMasked(nodeId, nodeData);
    const signature = `${this.quality}_${this.themeId}_${isMasked}_${nodeData.owner}_${nodeData.resident_player}_${JSON.stringify(nodeData.units)}`;
    if (squadGroup.userData.signature === signature) return;
    squadGroup.userData.signature = signature;

    // Clear previous garrison soldiers
    window.Arena3DArt.dispose(squadGroup);
    while (squadGroup.children.length > 0) squadGroup.remove(squadGroup.children[0]);

    // Check Fog of War mask for Node
    const units = nodeData.units || {};
    const unitList = [];
    if (!isMasked) {
      // Build list of units to render
      for (const [uType, count] of Object.entries(units)) {
        const c = Math.min(count, this.qualitySettings ? this.qualitySettings.units : 3);
        for (let i = 0; i < c; i++) unitList.push(uType);
      }
    }

    if (unitList.length === 0) return;

    // Arrange garrisoned soldiers in defensive ring around the fortress platform
    const ringRadius = nodeId === 0 || nodeId === 14 ? 38 : 28;
    const count = unitList.length;
    unitList.forEach((uType, idx) => {
      const angle = (idx / count) * Math.PI * 2;
      const model = this.createSoldierModel(uType, nodeData.resident_player || nodeData.owner, false);
      model.position.set(Math.cos(angle) * ringRadius, 4.5, Math.sin(angle) * ringRadius);
      model.rotation.y = angle + Math.PI / 2;
      model.scale.setScalar(1.2);
      squadGroup.add(model);
    });
  }

  updateFleets3D(frame) {
    // Collect active fleet IDs to remove stale squads
    const activeFleetIds = new Set();

    if (frame.fleets) {
      frame.fleets.forEach(fleet => {
        const fid = (fleet.id !== undefined ? fleet.id : fleet.fleet_id);
        activeFleetIds.add(fid);
        this.renderFleetSquad(fleet);
      });
    }

    // Remove squads that reached destination or disbanded
    this.fleetSquadGroups.forEach((group, fleetId) => {
      if (!activeFleetIds.has(fleetId)) {
        this.scene.remove(group);
        window.Arena3DArt.dispose(group);
        this.fleetSquadGroups.delete(fleetId);
      }
    });
  }

  renderFleetSquad(fleet) {
    const nodeA = this.replayData.map.nodes.find(n => n.id === fleet.origin_node);
    const nodeB = this.replayData.map.nodes.find(n => n.id === fleet.dest_node);
    if (!nodeA || !nodeB) return;

    const pA = this.mapToWorld(nodeA.x, nodeA.y);
    const pB = this.mapToWorld(nodeB.x, nodeB.y);

    // Compute progress along lane: 0.0 (launch) -> 1.0 (arrival)
    const progress = Math.max(0.0, Math.min(1.0, 1.0 - (fleet.turns_remaining / fleet.total_turns)));

    // Current position
    const currentPos = new THREE.Vector3(
      pA.x + (pB.x - pA.x) * progress,
      3.2,
      pA.z + (pB.z - pA.z) * progress
    );

    // March direction angle
    const angle = Math.atan2(pB.x - pA.x, pB.z - pA.z);

    // Retrieve or create squad group
    const fid = (fleet.id !== undefined ? fleet.id : fleet.fleet_id);
    let squadGroup = this.fleetSquadGroups.get(fid);
    if (!squadGroup) {
      squadGroup = new THREE.Group();
      this.scene.add(squadGroup);
      this.fleetSquadGroups.set(fid, squadGroup);
    }

    // Reposition and orient squad
    squadGroup.position.copy(currentPos);
    squadGroup.rotation.y = angle;
    squadGroup.scale.setScalar(1.25);
    squadGroup.userData.motion = { fleet, pA, pB };

    // Determine Fog of War masking
    const isMasked = this.isFleetMasked(fleet);

    // Rebuild soldiers if fleet composition changed
    const fleetSignature = `${this.quality}_${this.themeId}_${fleet.owner}_${isMasked}_${JSON.stringify(fleet.units)}`;
    if (squadGroup.userData.signature !== fleetSignature) {
      squadGroup.userData.signature = fleetSignature;

      // Clear children
      window.Arena3DArt.dispose(squadGroup);
      while (squadGroup.children.length > 0) squadGroup.remove(squadGroup.children[0]);

      if (isMasked) {
        // --- Shrouded Phantom Silhouette ("Ghost Fleet [?]") ---
        const ghostDrone = this.createSoldierModel('scout', fleet.owner, true);
        ghostDrone.scale.setScalar(1.2);
        squadGroup.add(ghostDrone);

        const badge = this.createTextSprite(`? [MASKED]`, {
          textColor: '#ffaa00',
          bgColor: 'rgba(20, 15, 10, 0.9)',
          borderColor: '#ffaa00',
          fontSize: 18
        });
        badge.position.y = 10;
        badge.scale.set(18, 9, 1);
        squadGroup.add(badge);

      } else {
        // --- Full Tactical Squad Formation ---
        const units = fleet.units || {};
        const models = [];

        // Order: Guards (Rank 1 Front), Raiders (Flanks), Siege (Center Rear), Scouts (Overhead)
        const cap=this.qualitySettings ? this.qualitySettings.units : 3;
        const guards = Math.min(units.guard || 0, cap);
        const raiders = Math.min(units.raider || 0, cap);
        const sieges = Math.min(units.siege || 0, Math.min(2,cap));
        const scouts = Math.min(units.scout || 0, Math.min(2,cap));

        // Position Guards front row (z = 4)
        for (let i = 0; i < guards; i++) {
          const m = this.createSoldierModel('guard', fleet.owner);
          const x = (i - (guards - 1) / 2) * 4.2;
          m.position.set(x, 0, 3.5);
          m.scale.setScalar(0.85);
          squadGroup.add(m);
        }

        // Position Raiders mid row (z = 0)
        for (let i = 0; i < raiders; i++) {
          const m = this.createSoldierModel('raider', fleet.owner);
          const x = (i - (raiders - 1) / 2) * 4.0;
          m.position.set(x, 0, 0);
          m.scale.setScalar(0.85);
          squadGroup.add(m);
        }

        // Position Siege rear row (z = -4.5)
        for (let i = 0; i < sieges; i++) {
          const m = this.createSoldierModel('siege', fleet.owner);
          const x = (i - (sieges - 1) / 2) * 5.0;
          m.position.set(x, 0, -4.5);
          m.scale.setScalar(0.85);
          squadGroup.add(m);
        }

        // Position Scouts overhead (y = 8)
        for (let i = 0; i < scouts; i++) {
          const m = this.createSoldierModel('scout', fleet.owner);
          const x = (i - (scouts - 1) / 2) * 4.0;
          m.position.set(x, 5.0, -1.0);
          m.scale.setScalar(0.85);
          squadGroup.add(m);
        }

        // Floating Tactical Banner
        const ownerHex = this.getOwnerHex(fleet.owner);
        const badge = this.createTextSprite(`P${fleet.owner} SQUAD (${fleet.total_count})`, {
          textColor: ownerHex,
          bgColor: 'rgba(7, 10, 20, 0.92)',
          borderColor: ownerHex,
          fontSize: 18
        });
        badge.position.y = 18;
        badge.scale.set(32, 16, 1);
        squadGroup.add(badge);
      }
    }
  }

  updateRelic3D(frame) {
    if (!this.relicAnimation.obelisk) return;

    if (frame.relic_active) {
      this.relicAnimation.active = true;

      // Awaken: Lift obelisk, spin, radiate intense golden beam
      this.relicAnimation.obelisk.position.y = 28 + Math.sin(Date.now() * 0.003) * 2.5;
      this.relicAnimation.obelisk.rotation.y += 0.04;

      if (this.relicAnimation.skybeam) {
        this.relicAnimation.skybeam.material.opacity = 0.55 + Math.sin(Date.now() * 0.005) * 0.2;
      }
      if (this.relicLight) {
        this.relicLight.intensity = 4.8;
      }
    } else {
      this.relicAnimation.active = false;
      this.relicAnimation.obelisk.position.y = 14 + Math.sin(Date.now() * 0.0015) * 1.0;
      this.relicAnimation.obelisk.rotation.y += 0.008;

      if (this.relicAnimation.skybeam) {
        this.relicAnimation.skybeam.material.opacity = 0.0;
      }
      if (this.relicLight) {
        this.relicLight.intensity = 1.6;
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 6. Fog of War Intelligence Check
  // ---------------------------------------------------------------------------
  isNodeMasked(nodeId, nodeData) {
    if (this.viewMode === 'spectator') return false;
    const player = this.viewMode === 'p1' ? 1 : 2;
    // Visible if owned by player or scouted
    if (nodeData.owner === player || nodeData.resident_player === player) return false;
    return !this.replayData.map.lanes.some(lane => {
      const other=lane.node_a===nodeId?lane.node_b:lane.node_b===nodeId?lane.node_a:null;
      return other!==null && this.currentFrame.nodes[String(other)].owner===player;
    });
  }

  isFleetMasked(fleet) {
    if (this.viewMode === 'spectator') return false;
    const player = this.viewMode === 'p1' ? 1 : 2;
    // Player's own fleets are always revealed
    if (fleet.owner === player) return false;
    // Enemy fleet is masked unless scouted
    if (fleet.is_revealed) return false;
    const nodes=this.currentFrame.nodes;
    if ([fleet.origin_node,fleet.dest_node].some(id=>nodes[String(id)].owner===player && (nodes[String(id)].units.scout||0)>0)) return false;
    return !this.currentFrame.fleets.some(own=>own.owner===player && (own.units.scout||0)>0 &&
      ((own.origin_node===fleet.origin_node && own.dest_node===fleet.dest_node)||(own.origin_node===fleet.dest_node && own.dest_node===fleet.origin_node)));
  }

  // ---------------------------------------------------------------------------
  // 7. Combat Clashing FX (Lasers, Shells, Explosions, Voxels)
  // ---------------------------------------------------------------------------
  triggerCombatFX(combatEvents) {
    combatEvents.forEach(cb => {
      const node = this.replayData.map.nodes.find(n => n.id === cb.node_id);
      if (!node) return;
      const pos = this.mapToWorld(node.x, node.y);

      // Spawn burst of combat spark particles
      const limit=this.qualitySettings ? this.qualitySettings.particles : 96;
      for (let i = 0; i < Math.min(28,limit) && this.particles.length<limit; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3.5 + 1.5;
        this.particles.push({
          x: pos.x + (Math.random() - 0.5) * 8,
          y: 6.0 + Math.random() * 8,
          z: pos.z + (Math.random() - 0.5) * 8,
          vx: Math.cos(angle) * speed,
          vy: Math.random() * 4.0 + 2.0,
          vz: Math.sin(angle) * speed,
          life: 1.0,
          color: Math.random() > 0.5 ? 0x00f3ff : 0xff0055,
          size: Math.random() * 2.2 + 1.2
        });
      }
    });
  }

  // ---------------------------------------------------------------------------
  // 8. Animation & Render Loop
  // ---------------------------------------------------------------------------
  startRenderLoop() {
    let lastRender = 0;
    const animate = timestamp => {
      if(this.disposed) return;
      this.rafId=requestAnimationFrame(animate);
      if (!this.container.clientWidth || this.container.classList.contains('hidden') || timestamp-lastRender<1000/this.qualitySettings.fps-.5) return;
      lastRender = timestamp;
      const started=performance.now();
      try {
      // Update Controls
      if (this.controls) this.controls.update();
      if (this.controls) {
        this.controls.target.x=THREE.MathUtils.clamp(this.controls.target.x,-400,400);
        this.controls.target.z=THREE.MathUtils.clamp(this.controls.target.z,-270,270);
        this.controls.target.y=THREE.MathUtils.clamp(this.controls.target.y,0,70);
      }

      // Camera Lerp
      this.updateCameraLerp();

      if(this.controls) this.controls.autoRotate=false;

      // Continuous Model Animations (Spins, hover bobs)
      this.animateSceneIdle();
      if(this.onBeforeRender) this.onBeforeRender(timestamp);
      if(window.nodeWarApp?.victory) window.nodeWarApp.victory.render3D(this);

      // Render
      if (this.renderer && this.scene && this.camera) {
        this.renderer.render(this.scene, this.camera);
        this.recordMetrics(timestamp,performance.now()-started);
      }
      } catch(error) {this.fail(error);}
    };
    this.rafId=requestAnimationFrame(animate);
  }

  animateSceneIdle() {
    const time = Date.now() * 0.002;
    if (window.nodeWarApp && window.nodeWarApp.isPlaying) {
      const fraction = Math.min(1, (performance.now() - (this.frameStartTime || performance.now())) / window.nodeWarApp.speedMs);
      this.fleetSquadGroups.forEach(group => {
        const motion = group.userData.motion;
        if (!motion) return;
        const {fleet,pA,pB} = motion;
        const progress = Math.min(1, 1 - (fleet.turns_remaining - fraction) / fleet.total_turns);
        group.position.set(pA.x+(pB.x-pA.x)*progress,3.2,pA.z+(pB.z-pA.z)*progress);
      });
    }

    // Ambient dust drift
    if (this.ambientDust) {
      this.ambientDust.rotation.y += 0.0003;
    }

    // Animate Citadels & Outposts
    this.nodeObjects.forEach(obj => {
      if (obj.buildingMesh && obj.buildingMesh.userData.reactor) {
        obj.buildingMesh.userData.reactor.rotation.y += 0.03;
        obj.buildingMesh.userData.reactor.rotation.x += 0.015;
      }
      if (obj.buildingMesh && obj.buildingMesh.userData.rings) {
        obj.buildingMesh.userData.rings.forEach((r, idx) => {
          r.rotation.z += (idx === 0 ? 0.025 : -0.025);
        });
      }
    });

    // Animate Relic Rings
    this.relicAnimation.rings.forEach((r, idx) => {
      r.rotation.z += (idx === 0 ? 0.015 : -0.015);
    });

    // Animate Particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.z += p.vz;
      p.vy -= 0.12; // gravity
      p.life -= 0.028;
      if (p.life <= 0) {
        this.particles.splice(i, 1);
      }
    }
    if (this.combatCloud) {
      const count=Math.min(256,this.particles.length);
      const positions=this.combatCloud.geometry.attributes.position, colors=this.combatCloud.geometry.attributes.color;
      for(let i=0;i<count;i++) { const p=this.particles[i],c=new THREE.Color(p.color);positions.setXYZ(i,p.x,p.y,p.z);colors.setXYZ(i,c.r,c.g,c.b); }
      positions.needsUpdate=true;colors.needsUpdate=true;this.combatCloud.geometry.setDrawRange(0,count);
    }
  }

  // ---------------------------------------------------------------------------
  // 9. Camera Presets & Smooth Lerping
  // ---------------------------------------------------------------------------
  setCameraPreset(preset) {
    document.querySelectorAll('.cam-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.cam-btn[data-cam="${preset}"]`);
    if (btn) btn.classList.add('active');

    this.isCinematicOrbit = false;

    let targetPos = new THREE.Vector3();
    let targetLook = new THREE.Vector3(0, 0, 0);

    switch (preset) {
      case 'iso':
        targetPos.copy(this.defaultCameraPosition);
        targetLook.set(0, 0, 0);
        break;
      case 'p1':
        targetPos.set(-280, 160, 220);
        targetLook.set(-360, 10, 0);
        break;
      case 'relic':
        targetPos.set(0, 160, 200);
        targetLook.set(0, 15, 0);
        break;
      case 'p2':
        targetPos.set(280, 160, 220);
        targetLook.set(360, 10, 0);
        break;
      case 'cinematic':
        targetPos.set(0, 320, 400);
        targetLook.set(0, 0, 0);
        break;
      case 'reset':
      default:
        targetPos.copy(this.defaultCameraPosition);
        targetLook.set(0, 0, 0);
        break;
    }

    this.startCameraLerp(targetPos, targetLook);
  }

  setCameraPresetPosition(preset) {
    if (preset === 'iso') {
      this.camera.position.set(0, 420, 460);
      this.camera.lookAt(0, 0, 0);
    }
  }

  startCameraLerp(endPos, endTarget) {
    this.cameraLerp = {
      startPos: this.camera.position.clone(),
      endPos: endPos.clone(),
      startTarget: this.controls.target.clone(),
      endTarget: endTarget.clone(),
      t: 0
    };
  }

  updateCameraLerp() {
    if (!this.cameraLerp) return;
    this.cameraLerp.t += 0.04;
    const factor = this.easeOutCubic(Math.min(1.0, this.cameraLerp.t));

    this.camera.position.lerpVectors(this.cameraLerp.startPos, this.cameraLerp.endPos, factor);
    this.controls.target.lerpVectors(this.cameraLerp.startTarget, this.cameraLerp.endTarget, factor);

    if (this.cameraLerp.t >= 1.0) {
      this.cameraLerp = null;
    }
  }

  easeOutCubic(x) {
    return 1 - Math.pow(1 - x, 3);
  }

  // ---------------------------------------------------------------------------
  // 10. User Interaction, Raycasting & Tooltips
  // ---------------------------------------------------------------------------
  bindEvents() {
    // Camera Preset Buttons
    document.querySelectorAll('.cam-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const cam = e.target.dataset.cam;
        this.setCameraPreset(cam);
      },{signal:this.events.signal});
    });

    // Pointer move for 3D Raycasting & Tooltip
    this.renderer.domElement.addEventListener('pointerdown',event=>{this.pointerStart={x:event.clientX,y:event.clientY};},{signal:this.events.signal});
    this.renderer.domElement.addEventListener('mousemove', (e) => this.onPointerMove(e),{signal:this.events.signal});
    this.renderer.domElement.addEventListener('click', (e) => {
      if(this.pointerStart && Math.hypot(e.clientX-this.pointerStart.x,e.clientY-this.pointerStart.y)>5) return;
      this.onPointerClick(e);
    },{signal:this.events.signal});
  }

  onPointerMove(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.scene.children, true);

    let foundNode = null;
    for (const hit of intersects) {
      let cur = hit.object;
      while (cur && cur !== this.scene) {
        if (cur.userData && cur.userData.type === 'node') {
          foundNode = cur.userData.nodeData;
          break;
        }
        cur = cur.parent;
      }
      if (foundNode) break;
    }

    if (foundNode && this.tooltipEl) {
      const dynamicNode = this.currentFrame && this.currentFrame.nodes[String(foundNode.id)] ? this.currentFrame.nodes[String(foundNode.id)] : foundNode;
      const ownerName = dynamicNode.owner === 1 ? 'Player 1 (Cyan)' : (dynamicNode.owner === 2 ? 'Player 2 (Crimson)' : 'Neutral');
      const units = dynamicNode.units || {};
      const uStr = `R:${units.raider || 0} G:${units.guard || 0} S:${units.siege || 0} Sc:${units.scout || 0}`;

      this.tooltipEl.innerHTML = `
        <div style="font-weight:700; color:#00f3ff; margin-bottom:2px;">${foundNode.name} [Node ${foundNode.id}]</div>
        <div style="font-size:0.75rem; color:#8c9bbd;">Owner: <strong style="color:#fff">${ownerName}</strong></div>
        <div style="font-size:0.75rem; color:#8c9bbd;">Income: +${foundNode.production} / Turn</div>
        <div style="font-size:0.75rem; color:#fff; margin-top:2px;">Garrison: <strong>${uStr}</strong></div>
      `;
      this.tooltipEl.style.left = `${event.clientX - rect.left}px`;
      this.tooltipEl.style.top = `${event.clientY - rect.top}px`;
      this.tooltipEl.classList.remove('hidden');
    } else if (this.tooltipEl) {
      this.tooltipEl.classList.add('hidden');
    }
  }

  onPointerClick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.scene.children, true);

    for (const hit of intersects) {
      let cur = hit.object;
      while (cur && cur !== this.scene) {
        if (cur.userData && cur.userData.type === 'node') {
          const nodeId = cur.userData.id;
          if (window.nodeWarApp) {
            window.nodeWarApp.selectNode(nodeId);
          }
          return;
        }
        cur = cur.parent;
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 11. Helpers & Text Sprites
  // ---------------------------------------------------------------------------
  loadReplay(replayData) {
    if (this.emptyNotice) this.emptyNotice.classList.add('hidden');
    this.replayData = replayData;
    this.buildMapArchitecture(replayData.map);
    if (this.themeId) this.setTheme(this.themeId);
  }

  setTheme(id) {
    this.themeId = id;
    const t = window.ArenaThemes.themes[id];
    this.renderer.domElement.setAttribute('role', 'img');
    this.renderer.domElement.setAttribute('aria-label', `${t.name} interactive 3D battlefield`);
    this.scene.background.set(id === 'medieval' ? 0xa6c8cd : t.ground);
    this.scene.fog.color.copy(this.scene.background);
    this.groundMesh.material.color.set(id === 'medieval' ? 0x6c9849 : id === 'wasteland' ? 0xb58b5a : 0x293552);
    this.groundMesh.material.metalness = .05;
    if (this.groundMesh.material.map) this.groundMesh.material.map.dispose();
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1024;
    window.ArenaThemes.drawTerrain(canvas.getContext('2d'),1024,1024,id);
    const texture = new THREE.CanvasTexture(canvas); texture.encoding = THREE.sRGBEncoding;
    this.groundMesh.material.map = texture; this.groundMesh.material.needsUpdate = true;
    this.borderRing.material.color.set(t.accent);
    this.ambientDust.material.color.set(t.accent);
    this.ambientDust.visible = id === 'galactic' || id === 'cyber';
    if (this.gridHelper) this.gridHelper.visible = id === 'cyber' || id === 'championship';
    this.laneObjects.forEach(lane => {
      lane.railMesh.material.color.set(t.path);
      lane.group.children[0].material.color.set(id==='medieval'?0xa28d6c:id==='wasteland'?0x997248:0x4d567b);
    });
    if (this.environmentGroup) { this.scene.remove(this.environmentGroup); window.Arena3DArt.dispose(this.environmentGroup); }
    this.environmentGroup = window.Arena3DArt.environment(id, this.quality);
    this.scene.add(this.environmentGroup);
    if (this.currentFrame && this.replayData) {
      this.updateNodes3D(this.currentFrame);
      this.updateFleets3D(this.currentFrame);
      this.updateRelic3D(this.currentFrame);
    }
  }

  setViewMode(mode) {
    this.viewMode = mode;
    if (this.currentFrame) {
      this.syncFrame(this.currentFrame);
    }
  }

  getOwnerColor(owner) {
    if (owner === 1) return 0x238bff;
    if (owner === 2) return 0xf52d55;
    return 0x5a6a8c;
  }

  getOwnerHex(owner) {
    if (owner === 1) return '#00f3ff';
    if (owner === 2) return '#ff0055';
    return '#8c9bbd';
  }

  createTextSprite(text, options = {}) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 128;

    const fontSize = options.fontSize || 22;
    ctx.font = `bold ${fontSize}px "Orbitron", monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    if (options.bgColor) {
      ctx.fillStyle = options.bgColor;
      ctx.beginPath();
      if (typeof ctx.roundRect === 'function') {
        ctx.roundRect(16, 24, 224, 80, 10);
      } else {
        ctx.rect(16, 24, 224, 80);
      }
      ctx.fill();
    }

    if (options.borderColor) {
      ctx.strokeStyle = options.borderColor;
      ctx.lineWidth = 4;
      ctx.beginPath();
      if (typeof ctx.roundRect === 'function') {
        ctx.roundRect(16, 24, 224, 80, 10);
      } else {
        ctx.rect(16, 24, 224, 80);
      }
      ctx.stroke();
    }

    ctx.fillStyle = options.textColor || '#ffffff';
    ctx.fillText(text, 128, 64);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    return sprite;
  }
}

// Attach globally
window.NodeWarThreeVisualizer = NodeWarThreeVisualizer;
