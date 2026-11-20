const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const T=require('../web/vendor/three.min.js');
const root=path.resolve(__dirname,'../web');

function setup() {
  const elements=new Map();
  const element=id=>{
    if(!elements.has(id)) elements.set(id,{value:id==='cinematic-quality'?'medium':'free',checked:true,dataset:{},textContent:'',
      addEventListener(){},classList:{add(){},remove(){},toggle(){}},setAttribute(){}});
    return elements.get(id);
  };
  let clock=1000;
  const context=vm.createContext({THREE:T,AbortController,performance:{now:()=>clock},console,
    window:{addEventListener(){},devicePixelRatio:1},document:{getElementById:element,body:{dataset:{}},hidden:false},setTimeout,clearTimeout});
  for(const file of ['cinematic.js','visualizer.js','three_visualizer.js']) vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),context);
  const nodes={0:{id:0,owner:1,resident_player:1,units:{guard:2},capturing_player:0},7:{id:7,owner:2,resident_player:2,units:{guard:3},capturing_player:0},14:{id:14,owner:2,resident_player:2,units:{guard:2},capturing_player:0}};
  const incoming={id:1,owner:1,origin_node:0,dest_node:7,turns_remaining:1,total_turns:3,units:{raider:4},total_count:4};
  const frames=[{turn:1,nodes,fleets:[incoming],combat_events:[],capture_events:[]},
    {turn:2,nodes,fleets:[],combat_events:[{node_id:7,defender_bonus_applied:true,attackers_before:{raider:4},defenders_before:{guard:3}}],capture_events:[]},
    {turn:3,nodes,fleets:[],combat_events:[],capture_events:[]}];
  const replay={map:{nodes:[{id:0,x:10,y:50},{id:7,x:50,y:50},{id:14,x:90,y:50}]},frames};
  function freeze(obj){Object.values(obj).forEach(v=>{if(v && typeof v==='object')freeze(v);});return Object.freeze(obj);}freeze(replay);
  const viz={camera:new T.PerspectiveCamera(38,1.6,1,4000),controls:{target:new T.Vector3(),enabled:true,autoRotate:false},
    defaultCameraPosition:new T.Vector3(0,600,700),quality:'medium',metrics:{samples:0,fps:0},fleetSquadGroups:new Map(),
    mapToWorld(x,y){return{x:(x-50)*7.8,z:(y-50)*5.2};},applyQuality(id){this.quality=id;}};
  viz.camera.position.set(0,600,700);
  const app={engineMode:'cinematic',selectedNodeId:null,currentFrameIdx:1,replayData:replay,isPlaying:false,
    renderNodeInspector(){},notify(message){this.notice=message;},pause(){this.isPlaying=false;},
    setEngineMode(mode){this.engineMode=mode;},setFrame(index){this.currentFrameIdx=index;}};
  const controller=new context.window.ArenaCinematic(app,viz);
  return{context,app,viz,controller,replay,element,time:value=>{clock=value;}};
}

test('cinematic activation is manual, starts free, and never directs while disabled',()=>{
  const {controller:c,app,viz,time}=setup(),start=viz.camera.position.clone();
  c.tick(50000);assert.ok(viz.camera.position.equals(start));
  c.activate();app.isPlaying=true;time(20000);c.tick(20000);
  assert.equal(c.mode,'free');assert.ok(viz.camera.position.equals(start));
  c.mode='automatic';c.deactivate();assert.equal(c.mode,'free');assert.equal(viz.onBeforeRender,null);
  c.tick(60000);assert.ok(viz.camera.position.equals(start));
  c.activate();assert.equal(c.mode,'free');
});

test('P1 and P2 camera positions oppose each other without changing replay data',()=>{
  const {controller:c,app,viz,replay}=setup(),before=JSON.stringify(replay);
  c.activate();c.transitions=false;c.mode='side';
  c.pov='p1';c.focus(7);const p1=viz.camera.position.clone();
  c.pov='p2';c.focus(7);const p2=viz.camera.position.clone();
  c.pov='neutral';c.focus(7);const neutral=viz.camera.position.clone();
  assert.ok(p1.x<0);assert.ok(p2.x>0);assert.ok(Math.abs(neutral.z)>50);
  assert.equal(app.currentFrameIdx,1);assert.equal(JSON.stringify(replay),before);
});

test('camera transitions interpolate smoothly and can be skipped or disabled',()=>{
  const {controller:c,viz,time}=setup();c.activate();const start=viz.camera.position.clone();
  time(1000);c.focus(7);assert.ok(viz.camera.position.equals(start));
  const target=c.transition.to.clone();c.tick(1550);
  assert.ok(viz.camera.position.distanceTo(start)>0);assert.ok(viz.camera.position.distanceTo(target)>0);
  c.skipTransition();assert.equal(c.transition,null);assert.ok(viz.camera.position.equals(target));
  c.transitions=false;c.pov='p2';c.focus(7);assert.equal(c.transition,null);
});

test('automatic director requires opt-in, respects shot hold times, and stops on pause or exit',()=>{
  const {controller:c,app}=setup();c.activate();app.isPlaying=true;
  c.tick(10000);assert.equal(c.sequence,0);
  c.mode='automatic';c.direct(10000,true);assert.equal(c.sequence,1);
  c.tick(11000);assert.equal(c.sequence,1);
  c.tick(14100);assert.equal(c.sequence,2);
  app.isPlaying=false;c.tick(20000);assert.equal(c.sequence,2);
  c.deactivate();c.tick(30000);assert.equal(c.sequence,2);
});

test('event adapter uses recorded roles and does not invent combat at an idle node',()=>{
  const {context,replay,controller:c,app,viz,element}=setup();
  const adapter=new context.window.BattleEventAdapter(replay);
  const battle=adapter.read(1,7);assert.equal(battle.attacker,1);assert.equal(battle.defender,2);
  assert.equal(adapter.read(1,0).phase,'inspection');assert.deepEqual(Array.from(adapter.active(0)),[]);
  c.activate();c.transitions=false;c.focus(0);assert.match(element('cinematic-status').textContent,/no active combat/);
  app.currentFrameIdx=0;c.onFrame();const position=viz.camera.position.clone();c.nextBattle();
  assert.match(app.notice,/No active battles/);assert.ok(viz.camera.position.equals(position));
});

test('leaving cinematic restores the normal camera and releases callbacks',()=>{
  const {controller:c,viz}=setup();viz.controls.target.set(20,0,8);
  const position=viz.camera.position.clone(),target=viz.controls.target.clone();
  c.activate();c.transitions=false;c.pov='p1';c.focus(7);c.deactivate();
  assert.ok(viz.camera.position.equals(position));assert.ok(viz.controls.target.equals(target));assert.equal(viz.camera.fov,38);
  assert.equal(viz.onBeforeRender,null);assert.equal(viz.onMetrics,null);assert.equal(viz.controls.autoRotate,false);
});

test('graphics failures restore Tactical without resetting cursor, replay or playback',()=>{
  const {context,replay}=setup();const app=vm.runInContext('Object.create(NodeWarVisualizer.prototype)',context);
  let disposed=0;Object.assign(app,{currentFrameIdx:1,replayData:replay,isPlaying:true,
    cinematic:{dispose(){disposed++;}},threeViz:{dispose(){disposed++;}},setEngineMode(mode){this.engineMode=mode;},notify(){}});
  context.console={warn(){}};app.graphicsFallback(new Error('test context loss'));
  assert.equal(app.engineMode,'2d');assert.equal(app.currentFrameIdx,1);assert.equal(app.replayData,replay);
  assert.equal(app.isPlaying,true);assert.equal(disposed,2);assert.equal(app.threeViz,null);assert.equal(app.cinematic,null);
});

test('quality presets reduce real geometry detail and adaptive downgrades wait for sustained load',()=>{
  const {context}=setup();const viz=vm.runInContext('Object.create(NodeWarThreeVisualizer.prototype)',context);
  const calls=[];Object.assign(viz,{adaptive:true,quality:'high',qualitySettings:{fps:60},slowWindows:0,unstableWindows:0,
    metrics:{samples:0},renderer:{info:{render:{calls:40,triangles:1000},memory:{geometries:20,textures:10}}},
    applyQuality(id){calls.push(id);this.quality=id;this.slowWindows=0;this.unstableWindows=0;this.metricWindow=null;},fail(error){calls.push(error.message);}});
  for(let window=0;window<3;window++){viz.recordMetrics(window*3000,80);viz.recordMetrics(window*3000+2100,80);}
  assert.deepEqual(calls,['medium']);
  const presets=vm.runInContext('NodeWarThreeVisualizer.QUALITY',context);
  assert.ok(presets.low.particles<presets.medium.particles);assert.ok(presets.low.pixelRatio<presets.high.pixelRatio);
  assert.equal(presets.medium.fps,30);assert.equal(presets.high.fps,60);assert.equal(presets.low.shadow,0);
});

test('combat reconstruction uses recorded before/after counts and disposes its owned models on exit',()=>{
  const {controller:c,context,viz,replay,app}=setup();
  vm.runInContext(fs.readFileSync(path.join(root,'arena_3d_art.js'),'utf8'),context);
  viz.scene=new T.Scene();viz.garrisonGroups=new Map();viz.nodeObjects=new Map();viz.qualitySettings={units:3};
  viz.createSoldierModel=(role,owner)=>context.window.Arena3DArt.unit('medieval',role,owner,false);
  const before=JSON.stringify(replay);c.activate();c.transitions=false;c.focus(7);
  assert.equal(c.combatReplay.units.length,6); // Four raiders capped to three, plus three guards.
  assert.ok(c.combatReplay.units.every(unit=>unit.model.visible));
  c.combatReplay.progress=1;c.updateCombat(0);
  assert.ok(c.combatReplay.units.every(unit=>!unit.model.visible)); // Fixture records no after-survivors.
  c.refreshCombat();assert.equal(c.combatReplay.progress,1);
  c.deactivate();assert.equal(c.combatReplay,null);assert.equal(viz.scene.children.length,0);
  assert.equal(app.currentFrameIdx,1);assert.equal(JSON.stringify(replay),before);
});

test('a delayed cinematic load cannot override a newer Tactical selection',async()=>{
  const {context,replay}=setup();const app=vm.runInContext('Object.create(NodeWarVisualizer.prototype)',context);
  let finish,activations=0;
  const pending=new Promise(resolve=>{finish=resolve;});
  Object.assign(app,{engineMode:'2d',tacticalZoom:1,currentFrameIdx:1,replayData:replay,
    ensureThree:()=>true,ensureCinematic:()=>pending,cinematic:{activate(){activations++;}},initCanvasResize(){},render(){}});
  const entry=app.setEngineMode('cinematic');await app.setEngineMode('2d');finish();await entry;
  assert.equal(app.engineMode,'2d');assert.equal(activations,0);assert.equal(app.currentFrameIdx,1);
});
