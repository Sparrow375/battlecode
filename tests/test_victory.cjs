const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const THREE=require('../web/vendor/three.min.js');
function setup(){
 const elements=new Map(),listeners=new Map();
 const el=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,disabled:false,textContent:'',dataset:{},style:{setProperty(){}},classList:{toggle(){},add(){},remove(){}},addEventListener(type,fn){listeners.set(id+':'+type,fn);},replaceChildren(){},add(){},focus(){},scrollIntoView(){},click(){}});return elements.get(id);};
 let clock=1000;
 const window={THREE,matchMedia:()=>({matches:false}),Arena3DArt:{dispose(root){root.traverse(o=>{o.geometry?.dispose();if(o.material)o.material.dispose();});}}};
 const context=vm.createContext({window,THREE,AbortController,Option:class{},performance:{now:()=>clock},document:{hidden:false,getElementById:el,addEventListener(){},querySelector:()=>el('tab')},console});
 vm.runInContext(fs.readFileSync('web/victory.js','utf8'),context);
 const data={metadata:{p1_name:'Team Cyan',p2_name:'Team Crimson',winner:2,win_reason:'score',final_scores:{p1:20,p2:30},p2_college:'Test College'},map:{nodes:[{id:0,x:0,y:50},{id:7,x:50,y:50},{id:14,x:100,y:50}],lanes:[{node_a:0,node_b:7}]},frames:[{nodes:{0:{owner:1,units:{}},7:{owner:2,units:{guard:1}},14:{owner:2,units:{guard:2}}}},{nodes:{0:{owner:1,units:{}},7:{owner:2,units:{guard:1}},14:{owner:2,units:{guard:2}}}}]};
 const app={replayData:data,currentFrameIdx:0,arenaThemeId:'championship',engineMode:'td',tacticalZoom:1.5,tacticalPan:{x:20,y:0},tdViz:{zoomLevel:1.5,panOffsetX:20,panOffsetY:0,combatParticles:[1]},pause(){this.paused=true;},notify(){}};
 const c=new window.ChampionshipVictory(app);c.load(data);
 return {c,app,data,el,listeners,window,time:n=>clock=n};
}
test('only a designated Ultimate Arena final at the final frame with an official winner can celebrate',()=>{
 const {c,app,data}=setup();const before=JSON.stringify(data);
 app.currentFrameIdx=1;c.evaluate();assert.equal(c.active,false);
 c.isFinal=true;c.enabled=true;app.currentFrameIdx=0;c.evaluate();assert.equal(c.active,false);
 app.currentFrameIdx=1;app.arenaThemeId='medieval';c.evaluate();assert.equal(c.active,false);
 app.arenaThemeId='championship';c.enabled=false;c.evaluate();assert.equal(c.active,false);
 c.enabled=true;data.metadata.winner=0;c.evaluate();assert.equal(c.active,false);
 data.metadata.winner=2;c.evaluate();assert.equal(c.active,true);assert.equal(c.resultData.name,'Team Crimson');assert.equal(c.resultData.college,'Test College');assert.equal(app.engineMode,'td');assert.equal(app.threeViz,undefined);assert.equal(JSON.stringify(data),before);
});
test('shared stages advance in order, skip is immediate, replay restarts without changing match state',()=>{
 const {c,app,data,time,el}=setup();c.isFinal=true;c.enabled=true;app.currentFrameIdx=1;const before=JSON.stringify(data);c.evaluate();
 const stages=['VICTORY_CONFIRMED','ARENA_ILLUMINATION','TEAM_CELEBRATION','TROPHY_REVEAL','CHAMPION_ANNOUNCEMENT','COMPLETE'];
 [0,1800,4200,6500,8700,11500].forEach((ms,i)=>{time(1000+ms);c.tick(1000+ms);assert.equal(c.state,stages[i]);});
 c.replay();assert.equal(c.state,'VICTORY_CONFIRMED');c.skip();assert.equal(c.state,'COMPLETE');assert.equal(el('victory-team').textContent,'Team Crimson');assert.equal(app.currentFrameIdx,1);assert.equal(JSON.stringify(data),before);
});
test('leaving final frame, disabling, and loading another match remove celebration and restore viewport',()=>{
 const {c,app,data}=setup();c.isFinal=true;c.enabled=true;app.currentFrameIdx=1;c.evaluate();assert.equal(app.tacticalZoom,1);
 app.currentFrameIdx=0;c.evaluate();assert.equal(c.state,'IDLE');assert.equal(app.tacticalZoom,1.5);assert.equal(app.tdViz.panOffsetX,20);
 app.currentFrameIdx=1;c.evaluate();c.load(data);assert.equal(c.active,false);assert.equal(c.isFinal,false);assert.equal(c.enabled,false);
});
test('3D effects restore original materials and survivor poses and dispose owned geometry',()=>{
 const {c,app,data,window}=setup();c.isFinal=true;c.enabled=true;app.currentFrameIdx=1;c.evaluate();app.engineMode='3d';
 const scene=new THREE.Scene(),nodeObjects=new Map(),garrisonGroups=new Map();
 for(const node of data.map.nodes){const group=new THREE.Group(),buildingMesh=new THREE.Mesh(new THREE.BoxGeometry(5,10,5),new THREE.MeshStandardMaterial({color:0xffffff}));group.add(buildingMesh);scene.add(group);nodeObjects.set(node.id,{group,buildingMesh});const units=new THREE.Group();units.add(new THREE.Group());group.add(units);garrisonGroups.set(node.id,units);}
 const camera=new THREE.PerspectiveCamera();camera.position.set(0,200,400);const viz={scene,nodeObjects,garrisonGroups,camera,controls:{target:new THREE.Vector3(),update(){}},defaultCameraPosition:camera.position.clone(),mapToWorld:(x,y)=>({x:x-50,z:y-50}),particles:[]};
 const original=nodeObjects.get(14).buildingMesh.material;c.render3D(viz);assert.ok(c.fx);assert.notEqual(nodeObjects.get(14).buildingMesh.material,original);
 let disposed=0;c.fx.root.traverse(o=>o.geometry?.addEventListener('dispose',()=>disposed++));c.skip();c.render3D(viz);assert.equal(c.fx.trophy.visible,true);c.viewBattlefield();assert.equal(c.fx,null);assert.equal(nodeObjects.get(14).buildingMesh.material,original);assert.equal(garrisonGroups.get(14).children[0].position.y,0);assert.ok(disposed>0);assert.equal(c.active,true);assert.equal(c.hidden,true);
});
test('reduced motion goes straight to the official result and never opens audio by default',()=>{
 const {c,app}=setup();c.reduced=true;c.isFinal=true;c.enabled=true;app.currentFrameIdx=1;c.evaluate();assert.equal(c.state,'COMPLETE');assert.equal(c.audio,undefined);assert.equal(c.resultData.winner,2);
});
