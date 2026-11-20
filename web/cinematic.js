// Loaded only after an explicit Cinematic Battle selection. Camera/replay observers only.
(() => {
  class BattleEventAdapter {
    constructor(replay) { this.replay=replay; }
    read(index,nodeId) {
      const frame=this.replay.frames[index], previous=this.replay.frames[Math.max(0,index-1)];
      const node=frame.nodes[String(nodeId)], before=previous.nodes[String(nodeId)];
      if(!node) return null;
      const combats=(frame.combat_events || []).filter(event=>event.node_id===nodeId);
      const captures=(frame.capture_events || []).filter(event=>event.node_id===nodeId);
      const incoming=(frame.fleets || []).filter(fleet=>fleet.dest_node===nodeId).slice().sort((a,b)=>a.turns_remaining-b.turns_remaining);
      const arrivals=(previous.fleets || []).filter(fleet=>fleet.dest_node===nodeId && fleet.turns_remaining<=1);
      const defender=[1,2].includes(before.resident_player)?before.resident_player:([1,2].includes(before.owner)?before.owner:null);
      const participants=[...new Set(arrivals.map(f=>f.owner).filter(id=>id===1 || id===2))];
      let attacker=participants.find(id=>id!==defender) || null;
      if(combats.length && defender) attacker=3-defender;
      if(!attacker && node.capturing_player) attacker=node.capturing_player;
      // A neutral meeting engagement has no assigned attacker or defender.
      if(!defender && participants.length===2) attacker=null;
      const recentCombat=(previous.combat_events || []).some(event=>event.node_id===nodeId);
      const phase=combats.length?'combat':captures.some(e=>e.type==='flipped') || recentCombat?'result':incoming.length?'approach':'inspection';
      return {nodeId,node,before,frame,combats,captures,incoming,arrivals,attacker,defender,phase};
    }
    active(index) {
      const frame=this.replay.frames[index];
      return [...new Set((frame.combat_events || []).map(e=>e.node_id))];
    }
    approaching(index) {
      return [...new Set((this.replay.frames[index].fleets || []).filter(f=>f.turns_remaining<=2).map(f=>f.dest_node))];
    }
  }

  class ArenaCinematic {
    constructor(app,viz) {
      this.app=app;this.viz=viz;this.active=false;this.mode='free';this.pov='neutral';
      this.focusId=null;this.transitions=true;this.transition=null;this.phase='Manual camera';
      this.minimumShotMs=4000;this.lastShot=-Infinity;this.sequence=0;this.events=new AbortController();
      this.bindControls();
    }
    element(id) { return document.getElementById('cinematic-'+id); }
    bindControls() {
      const listen=(id,event,handler)=>this.element(id).addEventListener(event,handler,{signal:this.events.signal});
      listen('pov','change',event=>{this.pov=event.target.value;if(this.active) this.focus(this.focusId ?? this.app.selectedNodeId ?? 7);});
      listen('camera','change',event=>{
        this.mode=event.target.value;this.viz.controls.enabled=this.mode==='free';
        if(!this.active) return;
        if(this.mode==='automatic') {this.lastShot=-Infinity;this.direct(performance.now(),true);}
        else if(this.mode!=='free') this.focus(this.focusId ?? this.app.selectedNodeId ?? 7);
        else {this.transition=null;this.phase='Free camera';this.renderStatus();}
      });
      listen('transitions','change',event=>{this.transitions=event.target.checked;if(!this.transitions) this.skipTransition();});
      listen('adaptive','change',event=>{this.viz.adaptive=event.target.checked;});
      listen('quality','change',event=>{if(this.active) {this.viz.applyQuality(event.target.value);this.refreshCombat();this.setFocusedLabels(this.focusId);this.renderPerformance();}});
      listen('focus','click',()=>{if(this.app.selectedNodeId!==null) this.focus(this.app.selectedNodeId);else this.app.notify('Select a battlefield node first.');});
      listen('next','click',()=>this.nextBattle());
      listen('reset','click',()=>this.reset());
      listen('skip','click',()=>{this.skipTransition();if(this.combatReplay){this.combatReplay.progress=1;this.updateCombat(0);}this.renderStatus();});
      listen('latest','click',()=>{if(this.app.replayData) {this.app.pause();this.app.setFrame(this.app.replayData.frames.length-1);this.renderStatus();}});
      listen('return','click',()=>this.app.setEngineMode('3d'));
    }
    activate() {
      if(this.active) return;
      this.active=true;
      this.normalPose={position:this.viz.camera.position.clone(),target:this.viz.controls.target.clone(),fov:this.viz.camera.fov};
      this.viz.cameraLerp=null;this.viz.controls.autoRotate=false;this.viz.controls.enabled=true;
      // Automatic directing must be explicitly selected on every entry, even after a previous session.
      this.mode='free';this.element('camera').value='free';this.phase='Manual camera';
      this.focusId=this.app.selectedNodeId;this.lastShot=-Infinity;this.sequence=0;
      this.lastTick=undefined;
      this.viz.adaptive=this.element('adaptive').checked;
      const quality=this.element('quality').value;
      if(this.viz.quality!==quality) this.viz.applyQuality(quality);
      this.viz.onBeforeRender=timestamp=>this.tick(timestamp);
      this.viz.onMetrics=()=>this.renderPerformance();
      this.viz.onQualityChange=id=>{this.element('quality').value=id;this.refreshCombat();this.setFocusedLabels(this.focusId);this.app.notify('Graphics quality reduced to '+id+' to keep playback smooth.');this.renderPerformance();};
      this.onFrame(true);this.renderPerformance();
    }
    deactivate() {
      if(!this.active) return;
      this.active=false;this.transition=null;this.mode='free';this.element('camera').value='free';
      this.clearCombat();this.setFocusedLabels(null);
      this.viz.onBeforeRender=null;this.viz.onMetrics=null;this.viz.onQualityChange=null;
      this.viz.cameraLerp=null;this.viz.controls.enabled=true;this.viz.controls.autoRotate=false;
      if(this.normalPose) {
        this.viz.camera.position.copy(this.normalPose.position);this.viz.controls.target.copy(this.normalPose.target);
        this.viz.camera.fov=this.normalPose.fov;this.viz.camera.updateProjectionMatrix();this.viz.camera.lookAt(this.normalPose.target);
      }
      this.adapter=null;this.sample=null;this.normalPose=null;
    }
    dispose() { this.deactivate();this.events.abort(); }
    onFrame(reset=false) {
      if(this.app.victory?.active) {this.clearCombat();return;}
      if(!this.active || !this.app.replayData) return;
      if(reset || !this.adapter || this.adapter.replay!==this.app.replayData) {
        this.clearCombat();
        this.adapter=new BattleEventAdapter(this.app.replayData);this.lastShot=-Infinity;this.sequence=0;
        if(this.focusId!==null && !this.app.replayData.map.nodes.some(n=>n.id===this.focusId)) this.focusId=null;
      }
      this.sample=this.focusId===null?null:this.adapter.read(this.app.currentFrameIdx,this.focusId);
      if(this.sample) this.phase=this.sample.phase==='combat'?'Active combat':this.sample.phase==='result'?'Recorded result':this.sample.phase==='approach'?'Incoming forces':'Inspection · no active combat';
      this.refreshCombat();
      this.renderStatus();
    }
    focus(id) {
      if(!this.active || !this.adapter || !Number.isInteger(id)) return;
      const sample=this.adapter.read(this.app.currentFrameIdx,id);if(!sample) return;
      this.focusId=id;this.sample=sample;this.app.selectedNodeId=id;this.app.renderNodeInspector(id);
      this.refreshCombat();this.setFocusedLabels(id);
      this.manualFocusUntil=performance.now()+8000;
      const style=this.mode==='free'?'inspection':this.mode==='automatic'?'side':this.mode;
      this.phase=sample.phase==='inspection'?'Inspection · no active combat':sample.phase==='combat'?'Active combat':sample.phase==='result'?'Capture result':'Incoming forces';
      this.applyPose(this.pose(style,id),performance.now());this.renderStatus();
    }
    nextBattle() {
      if(!this.active || !this.adapter) return;
      const ids=this.adapter.active(this.app.currentFrameIdx);
      if(!ids.length) {this.app.notify('No active battles in this replay frame. Select any node to inspect it.');return;}
      const index=ids.indexOf(this.focusId);this.focus(ids[(index+1)%ids.length]);
    }
    pose(style,id) {
      const T=THREE, camera=this.viz.camera;
      if(id===null || style==='wide') return {position:this.viz.defaultCameraPosition.clone(),target:new T.Vector3(0,0,0),fov:38};
      const staticNode=this.adapter.replay.map.nodes.find(n=>n.id===id);if(!staticNode) return null;
      const p=this.viz.mapToWorld(staticNode.x,staticNode.y), center=new T.Vector3(p.x,16,p.z);
      const sample=this.adapter.read(this.app.currentFrameIdx,id);
      let player=this.pov==='p1'?1:this.pov==='p2'?2:style==='attacker'?sample.attacker:style==='defender'?sample.defender:null;
      let direction=new T.Vector3(1,0,0);
      if(player) {
        const home=this.adapter.replay.map.nodes.find(n=>n.id===(player===1?0:14));
        const world=this.viz.mapToWorld(home.x,home.y);
        direction.set(p.x-world.x,0,p.z-world.z);
        if(direction.lengthSq()<1) direction.set(player===1?1:-1,0,0);
        direction.normalize();
      } else {
        const origin=sample.arrivals[0] || sample.incoming[0];
        if(origin) {const node=this.adapter.replay.map.nodes.find(n=>n.id===origin.origin_node);const w=this.viz.mapToWorld(node.x,node.y);direction.set(p.x-w.x,0,p.z-w.z).normalize();}
      }
      if(style==='top') return {position:center.clone().add(new T.Vector3(0,245,.1)),target:center,fov:45};
      const radius=id===0 || id===14?70:48;
      let anchor=center.clone(), distance=radius+150, height=100;
      if(style==='attacker' && player) {
        const fleet=sample.incoming.find(f=>f.owner===player);
        const group=fleet && this.viz.fleetSquadGroups.get(fleet.id ?? fleet.fleet_id);
        if(sample.phase==='approach' && group && group.position.distanceTo(center)<120) anchor.copy(group.position).setY(16);
        distance=radius+140;height=100;
      } else if(style==='defender') {distance=radius+140;height=105;}
      let offset;
      if(style==='side' && !player) offset=new T.Vector3(-direction.z,.5,direction.x).normalize().multiplyScalar(distance);
      else if(!player) offset=new T.Vector3(.75,.7,1).normalize().multiplyScalar(distance);
      else offset=direction.clone().multiplyScalar(-distance);
      offset.y=height;
      const target=center.clone();
      if(style==='attacker' || style==='defender' || style==='side') target.addScaledVector(direction,-20);
      return {position:anchor.add(offset),target,fov:48};
    }
    applyPose(pose,now) {
      if(!this.active || !pose) return;
      this.viz.cameraLerp=null;
      if(this.transitions) this.transition={from:this.viz.camera.position.clone(),to:pose.position.clone(),fromTarget:this.viz.controls.target.clone(),toTarget:pose.target.clone(),start:now,duration:1100,fov:pose.fov};
      else {this.transition=null;this.commitPose(pose);}
    }
    commitPose(pose) {
      this.viz.camera.position.copy(pose.position);this.viz.controls.target.copy(pose.target);
      if(this.viz.camera.fov!==pose.fov) {this.viz.camera.fov=pose.fov;this.viz.camera.updateProjectionMatrix();}
      this.viz.camera.lookAt(pose.target);
    }
    skipTransition() {
      if(this.transition) {const t=this.transition;this.commitPose({position:t.to,target:t.toTarget,fov:t.fov});this.transition=null;}
    }
    reset() {
      if(!this.active) return;
      this.mode='free';this.element('camera').value='free';this.focusId=null;this.sample=null;
      this.clearCombat();this.setFocusedLabels(null);
      this.viz.controls.enabled=true;this.phase='Manual wide view';
      this.applyPose(this.pose('wide',null),performance.now());this.renderStatus();
    }
    direct(now,explicit=false) {
      if(!this.active || this.mode!=='automatic' || !this.adapter || (!explicit && !this.app.isPlaying)) return;
      if(!explicit && now-this.lastShot<this.minimumShotMs) return;
      const active=this.adapter.active(this.app.currentFrameIdx), approaching=this.adapter.approaching(this.app.currentFrameIdx);
      let id=this.focusId;
      const captures=(this.adapter.replay.frames[this.app.currentFrameIdx].capture_events || []).filter(e=>e.type==='flipped').map(e=>e.node_id);
      if(id===null || now>(this.manualFocusUntil || 0)) id=active.includes(id)?id:active[0] ?? captures[0] ?? approaching[0] ?? null;
      const sample=id===null?null:this.adapter.read(this.app.currentFrameIdx,id);
      let style='wide';
      if(sample && sample.phase==='combat') {style=['attacker','defender','side'][this.sequence%3];this.sequence++;this.phase=style==='attacker'?'Attack begins':style==='defender'?'Defensive response':'Both forces · side angle';}
      else if(sample && sample.phase==='approach') {style='side';this.phase='Battle approaching';}
      else if(sample && sample.phase==='result') {style='side';this.phase='Result · current survivors and ownership';}
      else this.phase='Wide view · no active combat';
      if(this.focusId!==id) {this.focusId=id;this.sample=sample;this.refreshCombat();}
      else this.sample=sample;
      this.setFocusedLabels(style==='wide'?null:id);this.lastShot=now;
      this.applyPose(this.pose(style,id),now);this.renderStatus();
    }
    tick(now) {
      if(this.app.victory?.active) return;
      if(!this.active || this.app.engineMode!=='cinematic') return;
      if(this.mode==='automatic') this.direct(now);
      const delta=this.lastTick===undefined?0:Math.min(100,Math.max(0,now-this.lastTick));this.lastTick=now;
      this.updateCombat(delta);
      if(this.transition) {
        const t=this.transition,u=Math.min(1,Math.max(0,(now-t.start)/t.duration)),smooth=u*u*(3-2*u);
        const position=new THREE.Vector3().lerpVectors(t.from,t.to,smooth),target=new THREE.Vector3().lerpVectors(t.fromTarget,t.toTarget,smooth);
        this.commitPose({position,target,fov:t.fov});if(u===1) this.transition=null;
      } else if((this.mode==='attacker' || this.mode==='defender') && this.app.isPlaying && this.focusId!==null) {
        const pose=this.pose(this.mode,this.focusId);if(pose) {
          this.viz.camera.position.lerp(pose.position,.08);this.viz.controls.target.lerp(pose.target,.08);this.viz.camera.lookAt(this.viz.controls.target);
        }
      }
      if(now-(this.lastStatusAt || 0)>500) {this.lastStatusAt=now;this.renderStatus();}
    }
    renderStatus() {
      if(!this.active) return;
      const frame=this.app.replayData && this.app.replayData.frames[this.app.currentFrameIdx];
      const node=this.focusId===null?'Select a node':`Node ${this.focusId}`;
      this.element('status').textContent=`${this.mode==='automatic'?'Automatic director':'Manual selection'} · ${this.pov==='p1'?'Player 1 POV':this.pov==='p2'?'Player 2 POV':'Neutral POV'} · ${node} · ${this.phase}`;
      const latest=this.app.replayData && this.app.replayData.frames.at(-1);
      const reconstruction=this.combatReplay?` · Combat reconstruction: ${this.combatReplay.progress<1?'before recorded casualties':'recorded result'}`:'';
      this.element('replay-status').textContent=frame?`Recorded replay · Turn ${frame.turn} / ${latest.turn} · ${this.app.isPlaying?'playing':'paused'}${reconstruction} · Match results are unchanged.`:'No replay loaded · load a saved match or simulate one.';
    }
    setFocusedLabels(id) {
      if(!this.viz.nodeObjects) return;
      this.viz.nodeObjects.forEach(node=>{node.labelSprite.visible=id===null;});
      this.viz.fleetSquadGroups.forEach(group=>group.children.forEach(child=>{if(child.isSprite) child.visible=id===null;}));
    }
    clearCombat() {
      if(!this.combatReplay) return;
      const replay=this.combatReplay;
      if(this.viz.scene) this.viz.scene.remove(replay.group);
      window.Arena3DArt.dispose(replay.group);
      const squad=this.viz.garrisonGroups.get(replay.nodeId);if(squad) squad.visible=true;
      this.combatReplay=null;
    }
    refreshCombat() {
      const progress=this.combatReplay && this.combatReplay.nodeId===this.focusId && this.combatReplay.frameIndex===this.app.currentFrameIdx?this.combatReplay.progress:0;
      this.clearCombat();
      if(this.app.victory?.active) return;
      if(!this.active || !this.adapter || this.focusId===null || !this.viz.scene) return;
      const sample=this.adapter.read(this.app.currentFrameIdx,this.focusId);
      if(!sample || !sample.combats.length) return;
      const event=sample.combats[0],node=this.adapter.replay.map.nodes.find(n=>n.id===this.focusId);
      const p=this.viz.mapToWorld(node.x,node.y),direction=new THREE.Vector3(1,0,0);
      const arrival=sample.arrivals.find(f=>!sample.attacker || f.owner===sample.attacker) || sample.incoming[0];
      if(arrival) {const origin=this.adapter.replay.map.nodes.find(n=>n.id===arrival.origin_node);const from=this.viz.mapToWorld(origin.x,origin.y);direction.set(p.x-from.x,0,p.z-from.z).normalize();}
      else if(sample.attacker===2) direction.x=-1;
      const lateral=new THREE.Vector3(-direction.z,0,direction.x),group=new THREE.Group(),units=[];
      const radius=this.focusId===0 || this.focusId===14?32:21;
      const cap=this.viz.qualitySettings?this.viz.qualitySettings.units:3;
      for(const side of ['attackers','defenders']) {
        const owner=side==='attackers'?sample.attacker || 1:sample.defender || 0;
        const before=event[side+'_before'] || {},after=event[side+'_after'] || {};
        let index=0;
        for(const [role,count] of Object.entries(before)) for(let i=0;i<Math.min(count,cap);i++) {
          const model=this.viz.createSoldierModel(role,owner,false),offset=side==='attackers'?radius+55:radius+14;
          model.position.set(p.x-direction.x*(offset+Math.floor(index/3)*10)+lateral.x*((index%3)-1)*9,4,p.z-direction.z*(offset+Math.floor(index/3)*10)+lateral.z*((index%3)-1)*9);
          model.rotation.y=Math.atan2(direction.x,direction.z)+(side==='defenders'?Math.PI:0);model.scale.setScalar(1.6);
          const base=model.position.clone();group.add(model);units.push({model,base,survives:i<Math.min(after[role] || 0,cap),sign:side==='attackers'?1:-1,index});index++;
        }
      }
      this.viz.scene.add(group);
      const squad=this.viz.garrisonGroups.get(this.focusId);if(squad) squad.visible=false;
      this.combatReplay={group,units,nodeId:this.focusId,frameIndex:this.app.currentFrameIdx,direction,progress,duration:Math.min(1800,Math.max(600,this.app.speedMs*.85 || 850))};
      this.updateCombat(0);
    }
    updateCombat(delta) {
      const replay=this.combatReplay;if(!replay) return;
      if(this.app.isPlaying) replay.progress=Math.min(1,replay.progress+delta/replay.duration);
      for(const unit of replay.units) {
        unit.model.visible=replay.progress<1 || unit.survives;
        const lunge=Math.sin(replay.progress*Math.PI*4)*2*unit.sign;
        unit.model.position.copy(unit.base).addScaledVector(replay.direction,lunge);
      }
    }
    renderPerformance() {
      if(!this.active) return;
      const m=this.viz.metrics;
      this.element('performance').textContent=m.samples?`${this.viz.quality} · ${m.fps.toFixed(1)} FPS · ${m.renderMs.toFixed(1)} ms · ${m.drawCalls} draws · ${m.geometries} geometries / ${m.textures} textures`:`${this.viz.quality} · measuring FPS`;
      this.element('performance').dataset.fps=String(m.fps);
      this.element('performance').dataset.quality=this.viz.quality;
    }
  }
  window.BattleEventAdapter=BattleEventAdapter;
  window.ArenaCinematic=ArenaCinematic;
})();
