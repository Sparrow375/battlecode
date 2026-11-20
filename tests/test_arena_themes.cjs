// Run with: node --test tests/test_arena_themes.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');

function setup() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { value: 'medieval', attrs: {},
      setAttribute(k,v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } });
    return elements.get(id);
  };
  const context = vm.createContext({ console, performance, setTimeout, clearTimeout, THREE: require('../web/vendor/three.min.js'),
    window: { addEventListener() {} },
    document: { createElement: () => ({ width: 256, height: 256, getContext: () => ctx }), getElementById: element, body: { dataset: {} }, documentElement: { style: { setProperty() {} } } },
    Image: class {
      set src(value) { this.source = value; this.width = this.height = 100; queueMicrotask(() => this.onload()); }
    }
  });
  for (const file of ['arena_themes.js', 'arena_3d_art.js', 'td_visualizer.js', 'three_visualizer.js', 'visualizer.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, 'web', file), 'utf8'), context);
  }
  const app = vm.runInContext('Object.create(NodeWarVisualizer.prototype)', context);
  const td = vm.runInContext('Object.create(NodeWarTDVisualizer.prototype)', context);
  const replayFile = fs.readdirSync(path.join(root, 'replays')).find(f => f.endsWith('.json'));
  const replay = JSON.parse(fs.readFileSync(path.join(root, 'replays', replayFile), 'utf8'));
  const freeze = obj => { Object.values(obj).forEach(v => { if (v && typeof v === 'object') freeze(v); }); return Object.freeze(obj); };
  freeze(replay);
  // Exercise real rendering code on actual replay frames; reject invalid draw coordinates.
  const ctx = new Proxy({}, { get(_, key) {
    if (key === 'createRadialGradient' || key === 'createLinearGradient') return () => ({ addColorStop() {} });
    if (key === 'getImageData') return () => ({data: new Uint8ClampedArray(256*256*4)});
    return (...args) => args.forEach(arg => { if (typeof arg === 'number') assert.ok(Number.isFinite(arg), `Invalid ${String(key)} coordinate`); });
  }, set() { return true; } });
  Object.assign(td, { ctx, replayData: replay, currentFrameIdx: 10, displayWidth: 1200, displayHeight: 750,
    assetsLoaded: true, decorations: [], combatParticles: [], floatingTexts: [], viewMode: 'spectator',
    themeId: 'medieval', theme: context.window.ArenaThemes.themes.medieval,
    zoomLevel: 1.35, panOffsetX: 18, panOffsetY: -9, selectedNodeId: 3, currentTurnStartTime: 123,
    assetsReady: Promise.resolve({}) });
  Object.assign(app, { tdViz: td, replayData: replay, currentFrameIdx: 10, isPlaying: true,
    speedMs: 500, playbackInterval: 42, arenaThemeId: 'medieval', themeRequest: 0,
    render() {}, logEvent() {} });
  return { app, td, replay, context };
}

test('all themes render the same replay without changing battle, playback, selection or camera', async () => {
  const { app, td, replay, context } = setup();
  const before = JSON.stringify(replay);
  for (const id of ['cyber', 'galactic', 'wasteland', 'championship', 'medieval']) {
    await app.setArenaTheme(id);
    assert.equal(app.arenaThemeId, id);
    assert.equal(td.themeId, id);
    assert.equal(app.currentFrameIdx, 10);
    assert.equal(td.currentFrameIdx, 10);
    assert.equal(app.isPlaying, true);
    assert.equal(app.playbackInterval, 42);
    assert.equal(td.currentTurnStartTime, 123);
    assert.equal(td.selectedNodeId, 3);
    assert.deepEqual([td.zoomLevel, td.panOffsetX, td.panOffsetY], [1.35, 18, -9]);
    assert.equal(JSON.stringify(replay), before);
    assert.equal(app.replayData, replay);
    assert.equal(td.replayData, replay);
    if (id !== 'medieval') {
      assert.equal(Object.keys(td.assets).length, 24);
      for (const image of Object.values(td.assets)) assert.equal(image.width,256);
    }
  }
  assert.equal(Object.keys(context.window.ArenaThemes.themes).length, 5);
});

test('rapid selections finish on the latest requested theme, including returning to medieval', async () => {
  const { app, td } = setup();
  await Promise.all(['cyber', 'galactic', 'wasteland', 'championship', 'medieval'].map(id => app.setArenaTheme(id)));
  assert.equal(app.arenaThemeId, 'medieval');
  assert.equal(td.themeId, 'medieval');
  assert.equal(app.currentFrameIdx, 10);
});

test('failed asset pack retains the current theme and battle', async () => {
  const { app, td, context, replay } = setup();
  context.Image = class { set src(_) { queueMicrotask(() => this.onerror()); } };
  const saved = context.console;
  context.console = { ...saved, error() {} };
  await app.setArenaTheme('cyber');
  assert.equal(app.arenaThemeId, 'medieval');
  assert.equal(td.themeId, 'medieval');
  assert.equal(app.replayData, replay);
  assert.equal(app.isPlaying, true);
});

test('all five 3D environments build real geometry and retain replay state across switches and reloads', () => {
  const { context, replay } = setup(), T=context.THREE;
  const viz=vm.runInContext('Object.create(NodeWarThreeVisualizer.prototype)',context);
  Object.assign(viz,{scene:new T.Scene(), themeId:'medieval', nodeObjects:new Map(),laneObjects:[],
    fleetSquadGroups:new Map(),garrisonGroups:new Map(),particles:[],viewMode:'spectator',
    camera:new T.PerspectiveCamera(38,1.6,1,4000),controls:{target:new T.Vector3(),update(){}},
    renderer:{domElement:{setAttribute(){}}},groundMesh:new T.Mesh(new T.PlaneGeometry(1,1),new T.MeshStandardMaterial()),
    borderRing:new T.Mesh(new T.TorusGeometry(1),new T.MeshBasicMaterial()),ambientDust:{material:new T.PointsMaterial()},
    relicAnimation:{rings:[]},relicLight:{intensity:1}});
  viz.scene.background=new T.Color();viz.scene.fog=new T.FogExp2();
  const before=JSON.stringify(replay);
  viz.loadReplay(replay);viz.syncFrame(replay.frames[10]);
  viz.fitCamera();const cameraBefore=viz.camera.position.clone();
  const meshes=[];
  for(const id of ['medieval','cyber','galactic','wasteland','championship']) {
    viz.setTheme(id);
    assert.equal(viz.nodeObjects.size,15);
    assert.equal(viz.laneObjects.length,replay.map.lanes.length);
    assert.equal(viz.currentFrame,replay.frames[10]);
    assert.equal(viz.replayData,replay);
    assert.ok(viz.camera.position.equals(cameraBefore));
    let count=0;viz.scene.traverse(obj=>{if(obj.isMesh){count++;assert.ok(Number.isFinite(obj.position.x));}});
    assert.ok(count>100,`${id} must contain structures and scenery`);meshes.push(count);
  }
  assert.ok(new Set(meshes).size>=3,'Theme silhouettes must differ');
  viz.loadReplay(replay);viz.syncFrame(replay.frames[10]);
  for(const [id,squad] of viz.garrisonGroups) assert.equal(squad.parent,viz.nodeObjects.get(id).group);
  for(const aspect of [.8,1.5,2.2]) {
    viz.camera.aspect=aspect;viz.camera.updateProjectionMatrix();viz.fitCamera();viz.camera.updateMatrixWorld();
    const frustum=new T.Frustum().setFromProjectionMatrix(new T.Matrix4().multiplyMatrices(viz.camera.projectionMatrix,viz.camera.matrixWorldInverse));
    for(const node of replay.map.nodes) {
      const p=viz.mapToWorld(node.x,node.y);
      for(const xOffset of [-30,30]) assert.ok(frustum.containsPoint(new T.Vector3(p.x+xOffset,70,p.z)),`Core/node ${node.id} clipped at aspect ${aspect}`);
    }
  }
  assert.equal(JSON.stringify(replay),before);
});

test('tactical camera hit-testing follows zoom and pan without touching match state', () => {
  const {app,replay}=setup();
  Object.assign(app,{canvas:{getBoundingClientRect:()=>({left:10,top:20})},displayWidth:1200,displayHeight:750,
    tacticalZoom:2,tacticalPan:{x:25,y:-15}});
  const point=app.tacticalPointer({clientX:10+600+25+(100-600)*2,clientY:20+375-15+(200-375)*2});
  assert.equal(point.x,100);assert.equal(point.y,200);
  app.zoomTactical(20);assert.equal(app.tacticalZoom,3);
  app.zoomTactical(.01);assert.equal(app.tacticalZoom,.75);
  assert.equal(app.replayData,replay);assert.equal(app.currentFrameIdx,10);
});
