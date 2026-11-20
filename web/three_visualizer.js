// =============================================================================
// Node War - 3D Isometric Battlefield & Esports Spectator Engine (Three.js)
// =============================================================================

class NodeWarThreeVisualizer {
  constructor(containerId = 'three-container') {
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
    this.isActive = false;

    this.initScene();
    this.bindEvents();
    this.startRenderLoop();
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
    this.scene.fog = new THREE.FogExp2(0x060812, 0.0016);

    // Camera: High-angle isometric perspective
    this.camera = new THREE.PerspectiveCamera(38, width / height, 1, 4000);
    this.setCameraPresetPosition('iso');

    // WebGL Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.container.appendChild(this.renderer.domElement);

    // OrbitControls
    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.08; // Prevent camera sinking under ground
    this.controls.minDistance = 80;
    this.controls.maxDistance = 1400;
    this.controls.target.set(0, 0, 0);

    // Lighting Rig
    this.setupLighting();

    // Ground Arena Platform
    this.setupGroundPlatform();

    // Resize Handler
    window.addEventListener('resize', () => this.onResize());
  }

  setupLighting() {
    // Ambient cyberpunk glow
    const ambientLight = new THREE.AmbientLight(0x1a243a, 1.1);
    this.scene.add(ambientLight);

    // Main Key Sunlight
    const keySun = new THREE.DirectionalLight(0xffffff, 1.3);
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

    // Hexagonal boundary border ring
    const ringGeo = new THREE.TorusGeometry(462, 3, 16, 64);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x1f2e4d, wireframe: false });
    const borderRing = new THREE.Mesh(ringGeo, ringMat);
    borderRing.rotation.x = Math.PI / 2;
    borderRing.position.y = 0.5;
    this.scene.add(borderRing);

    // Subtle tactical coordinate grid
    const gridHelper = new THREE.GridHelper(900, 36, 0x18243c, 0x0c1322);
    gridHelper.position.y = 0.2;
    this.scene.add(gridHelper);

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
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
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
    // Clear previous architecture if any
    this.nodeObjects.forEach(obj => this.scene.remove(obj.group));
    this.nodeObjects.clear();
    this.laneObjects.forEach(lane => this.scene.remove(lane.group));
    this.laneObjects = [];

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
      const tubeGeo = new THREE.TubeGeometry(curve, 12, 2.2, 6, false);
      const tubeMat = new THREE.MeshStandardMaterial({
        color: 0x101726,
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
        const citadel = this.createCitadelModel(node.id === 0 ? 1 : 2);
        citadel.position.y = 4.5;
        nodeGroup.add(citadel);
        buildingMesh = citadel;

        beaconLight = new THREE.PointLight(this.getOwnerColor(node.owner), 2.2, 120);
        beaconLight.position.set(0, 24, 0);
        nodeGroup.add(beaconLight);

      } else if (isRelic) {
        // --- The Ancient Relic Sanctuary ---
        const relicStructure = this.createRelicSanctuary();
        relicStructure.position.y = 4.5;
        nodeGroup.add(relicStructure);
        buildingMesh = relicStructure;

      } else if (node.id === 5 || node.id === 6 || node.id === 8 || node.id === 9) {
        // --- Heavy Chokepoint Pillbox Fort ---
        const chokepoint = this.createChokepointModel(node.owner);
        chokepoint.position.y = 4.5;
        nodeGroup.add(chokepoint);
        buildingMesh = chokepoint;

      } else {
        // --- Industrial Quantum Refinery / Outpost ---
        const outpost = this.createOutpostModel(node.production, node.owner);
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
        fontSize: 20
      });
      labelSprite.position.y = isRelic ? 38 : (isHome ? 32 : 24);
      labelSprite.scale.set(24, 12, 1);
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
    const group = new THREE.Group();
    const color = isShadow ? 0x444455 : this.getOwnerColor(owner);
    const metalness = isShadow ? 0.2 : 0.8;
    const roughness = isShadow ? 0.8 : 0.3;

    if (unitType === 'raider') {
      // --- RAIDER (Swift Combat Speeder) ---
      // Fuselage
      const fuselageGeo = new THREE.ConeGeometry(1.6, 5.5, 4);
      fuselageGeo.rotateX(Math.PI / 2);
      const fuselage = new THREE.Mesh(
        fuselageGeo,
        new THREE.MeshStandardMaterial({ color: color, metalness, roughness })
      );
      fuselage.position.y = 2.8;
      group.add(fuselage);

      // Swept Wings
      const wing = new THREE.Mesh(
        new THREE.BoxGeometry(4.8, 0.3, 2.2),
        new THREE.MeshStandardMaterial({ color: 0x121826, metalness: 0.9 })
      );
      wing.position.set(0, 2.8, -0.6);
      group.add(wing);

      // Plasma Blasters
      for (const side of [-1.8, 1.8]) {
        const gun = new THREE.Mesh(
          new THREE.CylinderGeometry(0.2, 0.2, 2.5, 6),
          new THREE.MeshStandardMaterial({ color: 0x334466, metalness: 0.9 })
        );
        gun.rotation.x = Math.PI / 2;
        gun.position.set(side, 2.7, 1.0);
        group.add(gun);
      }

      // Thruster engine glow
      if (!isShadow) {
        const glow = new THREE.Mesh(
          new THREE.ConeGeometry(0.8, 2.0, 6),
          new THREE.MeshBasicMaterial({ color: color, blending: THREE.AdditiveBlending })
        );
        glow.rotation.x = -Math.PI / 2;
        glow.position.set(0, 2.8, -3.2);
        group.add(glow);
      }

    } else if (unitType === 'guard') {
      // --- GUARD (Armored Phalanx Sentinel Mech) ---
      // Torso
      const torso = new THREE.Mesh(
        new THREE.BoxGeometry(2.4, 3.2, 1.8),
        new THREE.MeshStandardMaterial({ color: 0x182236, metalness, roughness })
      );
      torso.position.y = 3.4;
      group.add(torso);

      // Glowing Helmet Visor
      const visor = new THREE.Mesh(
        new THREE.BoxGeometry(1.6, 0.4, 0.5),
        new THREE.MeshStandardMaterial({
          color: color,
          emissive: color,
          emissiveIntensity: isShadow ? 0.2 : 0.9
        })
      );
      visor.position.set(0, 4.4, 0.85);
      group.add(visor);

      // Biped Legs
      for (const side of [-0.7, 0.7]) {
        const leg = new THREE.Mesh(
          new THREE.CylinderGeometry(0.4, 0.5, 2.2, 6),
          new THREE.MeshStandardMaterial({ color: 0x0f1522, metalness: 0.9 })
        );
        leg.position.set(side, 1.1, 0);
        group.add(leg);
      }

      // Translucent Hexagonal Tower Shield (Left Arm)
      const shieldGeo = new THREE.CylinderGeometry(2.2, 2.2, 0.4, 6);
      shieldGeo.rotateZ(Math.PI / 2);
      const shieldMat = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: isShadow ? 0.1 : 0.6,
        transparent: true,
        opacity: isShadow ? 0.4 : 0.75,
        metalness: 0.4
      });
      const shield = new THREE.Mesh(shieldGeo, shieldMat);
      shield.position.set(-1.9, 3.2, 1.0);
      group.add(shield);

      // Energy Lance (Right Arm)
      const lance = new THREE.Mesh(
        new THREE.CylinderGeometry(0.18, 0.22, 6.0, 6),
        new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.5 })
      );
      lance.rotation.x = Math.PI / 6;
      lance.position.set(1.8, 3.5, 0.6);
      group.add(lance);

    } else if (unitType === 'siege') {
      // --- SIEGE (Heavy Quad-Track Crawler Artillery Tank) ---
      // Heavy Tank Chassis
      const chassis = new THREE.Mesh(
        new THREE.BoxGeometry(4.2, 1.8, 5.0),
        new THREE.MeshStandardMaterial({ color: 0x141a29, metalness: 0.85, roughness: 0.4 })
      );
      chassis.position.y = 1.6;
      group.add(chassis);

      // Dual Armored Treads
      for (const side of [-2.0, 2.0]) {
        const tread = new THREE.Mesh(
          new THREE.BoxGeometry(0.9, 1.5, 5.4),
          new THREE.MeshStandardMaterial({ color: 0x0a0e17, metalness: 0.9 })
        );
        tread.position.set(side, 1.0, 0);
        group.add(tread);
      }

      // Sloped Turret
      const turret = new THREE.Mesh(
        new THREE.BoxGeometry(2.6, 1.6, 3.0),
        new THREE.MeshStandardMaterial({ color: 0x1e273d, metalness: 0.8 })
      );
      turret.position.set(0, 3.1, -0.4);
      group.add(turret);

      // Elongated Heavy Plasma Railgun Cannon
      const cannon = new THREE.Mesh(
        new THREE.CylinderGeometry(0.45, 0.6, 6.8, 8),
        new THREE.MeshStandardMaterial({ color: 0x2d3a56, metalness: 0.9 })
      );
      cannon.rotation.x = Math.PI / 2;
      cannon.position.set(0, 3.3, 3.2);
      group.add(cannon);

      // Glowing Plasma Coils
      for (let c = 0; c < 3; c++) {
        const coil = new THREE.Mesh(
          new THREE.TorusGeometry(0.7, 0.12, 6, 12),
          new THREE.MeshBasicMaterial({ color: color })
        );
        coil.position.set(0, 3.3, 1.8 + c * 1.4);
        group.add(coil);
      }

    } else if (unitType === 'scout') {
      // --- SCOUT (Floating Recon Probe Drone) ---
      // Central Chrome Eye Sphere
      const eye = new THREE.Mesh(
        new THREE.SphereGeometry(1.4, 12, 12),
        new THREE.MeshStandardMaterial({
          color: 0x111625,
          emissive: color,
          emissiveIntensity: 0.7,
          metalness: 0.9
        })
      );
      eye.position.y = 3.6;
      group.add(eye);

      // Counter-Rotating Horizontal Sensor Rings
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(2.2, 0.18, 6, 16),
        new THREE.MeshBasicMaterial({ color: color, wireframe: false })
      );
      ring.rotation.x = Math.PI / 2;
      ring.position.y = 3.6;
      group.add(ring);
      group.userData.sensorRing = ring;

      // Downward Scanning Spotlight Cone
      if (!isShadow) {
        const cone = new THREE.Mesh(
          new THREE.ConeGeometry(3.5, 6.0, 12, 1, true),
          new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.25,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending,
            depthWrite: false
          })
        );
        cone.position.set(0, 1.0, 0);
        group.add(cone);
      }
    }

    group.userData.unitType = unitType;
    group.userData.owner = owner;
    return group;
  }

  // ---------------------------------------------------------------------------
  // 5. Squad Layouts & Marching Synchronization
  // ---------------------------------------------------------------------------
  syncFrame(frame, prevFrame = null) {
    if (!this.replayData) return;
    this.currentFrame = frame;
    this.prevFrame = prevFrame || frame;

    // 1. Update Nodes (Owners, Rings, Garrison Units, Capture)
    this.updateNodes3D(frame);

    // 2. Update Traveling Fleets (Squads marching along lanes)
    this.updateFleets3D(frame);

    // 3. Update Relic State (Turn 95 Awakening)
    this.updateRelic3D(frame);

    // 4. Trigger Combat Clashes & Particle FX
    if (frame.combat_events && frame.combat_events.length > 0) {
      this.triggerCombatFX(frame.combat_events);
    }
  }

  updateNodes3D(frame) {
    this.nodeObjects.forEach((nodeObj, nodeId) => {
      const dynamicNode = frame.nodes[String(nodeId)] || frame.nodes[nodeId];
      if (!dynamicNode) return;

      const owner = dynamicNode.owner;
      const ownerColor = this.getOwnerColor(owner);

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

    // Clear previous garrison soldiers
    while (squadGroup.children.length > 0) {
      squadGroup.remove(squadGroup.children[0]);
    }

    // Check Fog of War mask for Node
    const isMasked = this.isNodeMasked(nodeId, nodeData);

    const units = nodeData.units || {};
    const unitList = [];
    if (!isMasked) {
      // Build list of units to render
      for (const [uType, count] of Object.entries(units)) {
        const c = Math.min(count, 4); // Max 4 per unit type to avoid clutter
        for (let i = 0; i < c; i++) unitList.push(uType);
      }
    }

    if (unitList.length === 0) return;

    // Arrange garrisoned soldiers in defensive ring around the fortress platform
    const ringRadius = 15.5;
    const count = unitList.length;
    unitList.forEach((uType, idx) => {
      const angle = (idx / count) * Math.PI * 2;
      const model = this.createSoldierModel(uType, nodeData.resident_player || nodeData.owner, false);
      model.position.set(Math.cos(angle) * ringRadius, 4.5, Math.sin(angle) * ringRadius);
      model.rotation.y = angle + Math.PI / 2;
      model.scale.setScalar(0.72);
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

    // Determine Fog of War masking
    const isMasked = this.isFleetMasked(fleet);

    // Rebuild soldiers if fleet composition changed
    const fleetSignature = `${fleet.owner}_${isMasked}_${JSON.stringify(fleet.units)}`;
    if (squadGroup.userData.signature !== fleetSignature) {
      squadGroup.userData.signature = fleetSignature;

      // Clear children
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
        const guards = Math.min(units.guard || 0, 3);
        const raiders = Math.min(units.raider || 0, 4);
        const sieges = Math.min(units.siege || 0, 2);
        const scouts = Math.min(units.scout || 0, 2);

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
        badge.position.y = 12;
        badge.scale.set(22, 11, 1);
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
    return false; // Fog masking allows node structure to show, masks garrison composition
  }

  isFleetMasked(fleet) {
    if (this.viewMode === 'spectator') return false;
    const player = this.viewMode === 'p1' ? 1 : 2;
    // Player's own fleets are always revealed
    if (fleet.owner === player) return false;
    // Enemy fleet is masked unless scouted
    return !fleet.is_revealed;
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
      for (let i = 0; i < 28; i++) {
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

  setActive(active) {
    this.isActive = !!active;
    if (this.isActive && this.renderer && this.container && this.camera) {
      const width = this.container.clientWidth || window.innerWidth;
      const height = this.container.clientHeight || window.innerHeight;
      if (width && height) {
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 8. Animation & Render Loop
  // ---------------------------------------------------------------------------
  startRenderLoop() {
    const animate = () => {
      requestAnimationFrame(animate);
      if (this.isActive === false) return;

      // Update Controls
      if (this.controls) this.controls.update();

      // Camera Lerp
      this.updateCameraLerp();

      // Cinematic Auto-Orbit
      if (this.isCinematicOrbit && this.controls) {
        this.controls.autoRotate = true;
        this.controls.autoRotateSpeed = 0.8;
      } else if (this.controls) {
        this.controls.autoRotate = false;
      }

      // Continuous Model Animations (Spins, hover bobs)
      this.animateSceneIdle();

      // Render
      if (this.renderer && this.scene && this.camera) {
        this.renderer.render(this.scene, this.camera);
      }
    };
    requestAnimationFrame(animate);
  }

  animateSceneIdle() {
    const time = Date.now() * 0.002;

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
  }

  // ---------------------------------------------------------------------------
  // 9. Camera Presets & Smooth Lerping
  // ---------------------------------------------------------------------------
  setCameraPreset(preset) {
    document.querySelectorAll('.cam-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.cam-btn[data-cam="${preset}"]`);
    if (btn) btn.classList.add('active');

    this.isCinematicOrbit = (preset === 'cinematic');

    let targetPos = new THREE.Vector3();
    let targetLook = new THREE.Vector3(0, 0, 0);

    switch (preset) {
      case 'iso':
        targetPos.set(0, 420, 460);
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
        targetPos.set(0, 420, 460);
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
      });
    });

    // Pointer move for 3D Raycasting & Tooltip
    this.renderer.domElement.addEventListener('mousemove', (e) => this.onPointerMove(e));
    this.renderer.domElement.addEventListener('click', (e) => this.onPointerClick(e));
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
    this.replayData = replayData;
    this.buildMapArchitecture(replayData.map);
  }

  setViewMode(mode) {
    this.viewMode = mode;
    if (this.currentFrame) {
      this.syncFrame(this.currentFrame);
    }
  }

  getOwnerColor(owner) {
    if (owner === 1) return 0x00f3ff;
    if (owner === 2) return 0xff0055;
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
