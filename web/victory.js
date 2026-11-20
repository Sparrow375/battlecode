// Post-match presentation only. Never computes a winner or writes to replay data.
(() => {
  const STAGES=['IDLE','VICTORY_CONFIRMED','ARENA_ILLUMINATION','TEAM_CELEBRATION','TROPHY_REVEAL','CHAMPION_ANNOUNCEMENT','COMPLETE'];
  const TIMES=[0,0,1800,4200,6500,8700,11500];
  const TITLES=['','Final victory confirmed','The arena awakens','A salute to the champions','The championship trophy','Your tournament champions','Official final result'];
  const QUALITY={low:{particles:18,segments:8},medium:{particles:42,segments:16},high:{particles:72,segments:24}};
  class ChampionshipVictory {
    constructor(app) {
      this.app=app;this.state='IDLE';this.active=false;this.quality='medium';this.enabled=false;this.isFinal=false;
      this.events=new AbortController();this.started=0;this.elapsed=0;this.hidden=false;this.reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.bind();
    }
    el(id){return document.getElementById('victory-'+id);}
    bind(){
      const on=(id,event,fn)=>this.el(id).addEventListener(event,fn,{signal:this.events.signal});
      on('final','change',e=>{this.isFinal=e.target.checked;this.enabled=this.isFinal;this.el('enabled').checked=this.enabled;this.el('enabled').disabled=!this.isFinal;this.reset();this.evaluate();});
      on('enabled','change',e=>{this.enabled=e.target.checked;this.reset();this.evaluate();});
      on('quality','change',e=>{this.quality=e.target.value;this.cleanup3D();if(this.app.threeViz){this.app.threeViz.applyQuality(this.quality);this.qualityViz=this.app.threeViz;}});
      on('replay','click',()=>this.replay());on('replay-setting','click',()=>this.replay());on('skip','click',()=>this.skip());
      on('battlefield','click',()=>this.viewBattlefield());on('bracket','click',()=>this.showBracket());
      on('audio','change',e=>{if(!e.target.checked)this.stopAudio();});
      on('commentary','change',e=>{if(!e.target.checked && window.speechSynthesis)window.speechSynthesis.cancel();});
      const voices=()=>{const select=this.el('voice'),value=select.value;select.replaceChildren(new Option('Browser default',''));if(window.speechSynthesis)for(const voice of speechSynthesis.getVoices())select.add(new Option(`${voice.name} (${voice.lang})`,voice.voiceURI));select.value=value;};
      if(window.speechSynthesis){speechSynthesis.addEventListener('voiceschanged',voices,{signal:this.events.signal});voices();}
      document.addEventListener('visibilitychange',()=>{if(document.hidden){this.suspendedAt=performance.now();this.stopAudio();}else if(this.suspendedAt){this.started+=performance.now()-this.suspendedAt;this.suspendedAt=null;}},{signal:this.events.signal});
    }
    load(data){
      this.reset();const m=data.metadata || {};
      // Explicit tournament metadata, or an organizer checkbox for legacy exports.
      this.isFinal=m.tournament?.is_final===true || m.is_tournament_final===true;
      this.enabled=this.isFinal;this.el('final').checked=this.isFinal;this.el('enabled').checked=this.enabled;this.el('enabled').disabled=!this.isFinal;
      document.getElementById('championship-bracket').classList.add('hidden');this.evaluate();
    }
    result(){
      const data=this.app.replayData,m=data?.metadata;
      if(!m || ![1,2].includes(m.winner) || typeof m.win_reason!=='string' || !m.win_reason.trim() || !data.frames?.length)return null;
      const winner=m.winner,prefix='p'+winner,scores=m.final_scores;
      return {winner,name:m[prefix+'_name'] || `Player ${winner}`,college:m[prefix+'_college'] || m.teams?.[prefix]?.college || '',
        detail:`${m.p1_name || 'Player 1'} vs ${m.p2_name || 'Player 2'}${scores && Number.isFinite(scores.p1) && Number.isFinite(scores.p2)?` · ${scores.p1} – ${scores.p2}`:''} · ${m.win_reason}`,metadata:m};
    }
    eligible(){return !!(this.isFinal && this.enabled && this.app.arenaThemeId==='championship' && this.result() && this.app.currentFrameIdx===this.app.replayData.frames.length-1);}
    evaluate(){
      const eligible=this.eligible();this.el('replay-setting').disabled=!eligible;
      this.el('setting-status').textContent=!this.isFinal?'Ordinary match · celebration inactive':!this.enabled?'Final · celebration off':this.app.arenaThemeId!=='championship'?'Final · select The Ultimate Arena':!this.result()?'Final · awaiting an official winning result':!eligible?'Final · waiting for final replay frame':'Final · official result confirmed';
      if(!eligible){if(this.active)this.reset();return;}
      if(!this.active)this.start();
    }
    start(){
      if(!this.eligible())return false;
      this.active=true;this.hidden=false;this.effectFailed=false;this.started=performance.now();this.elapsed=0;this.resultData=this.result();this.state='VICTORY_CONFIRMED';
      this.app.pause();this.app.particles=[];if(this.app.tdViz)this.app.tdViz.combatParticles=[];
      if(this.app.cinematic){this.app.cinematic.clearCombat();this.app.cinematic.transition=null;this.app.cinematic.setFocusedLabels(null);}
      document.getElementById('combat-banner').classList.add('hidden');
      // Full battlefield remains visible in the normal views.
      this.saved2D={zoom:this.app.tacticalZoom,pan:{...this.app.tacticalPan},tdZoom:this.app.tdViz?.zoomLevel,tdX:this.app.tdViz?.panOffsetX,tdY:this.app.tdViz?.panOffsetY};
      this.app.tacticalZoom=1;this.app.tacticalPan={x:0,y:0};if(this.app.tdViz){this.app.tdViz.zoomLevel=1;this.app.tdViz.panOffsetX=0;this.app.tdViz.panOffsetY=0;}
      document.getElementById('zoom-level-badge').textContent='100%';
      this.el('team').textContent=this.resultData.name;this.el('college').textContent=this.resultData.college;this.el('result').textContent=this.resultData.detail;
      this.el('overlay').style.setProperty('--winner-color',this.resultData.winner===1?'#00e5ff':'#ff376c');
      this.updateOverlay();this.playAudio();if(this.reduced)this.skip();return true;
    }
    tick(now){
      if(!this.active || document.hidden)return;
      this.elapsed=Math.max(0,now-this.started);
      let index=1;for(let i=2;i<TIMES.length;i++)if(this.elapsed>=TIMES[i])index=i;
      if(this.state!==STAGES[index]){this.state=STAGES[index];this.updateOverlay();if(index===5)this.speak();}
    }
    get stage(){return STAGES.indexOf(this.state);}
    updateOverlay(){const overlay=this.el('overlay');overlay.classList.toggle('hidden',!this.active || this.hidden);overlay.dataset.stage=this.state;overlay.dataset.complete=String(this.state==='COMPLETE');this.el('phase').textContent=TITLES[this.stage];this.el('skip').disabled=this.state==='COMPLETE';}
    skip(){if(!this.active && !this.start())return;this.started=performance.now()-TIMES[6];this.elapsed=TIMES[6];this.state='COMPLETE';this.hidden=false;this.stopAudio();this.updateOverlay();}
    replay(){if(!this.eligible())return;this.reset();this.start();}
    viewBattlefield(){this.hidden=true;this.stopAudio();this.cleanup3D();this.updateOverlay();}
    showBracket(){
      const r=this.resultData;if(!r)return;this.viewBattlefield();
      document.getElementById('championship-pairing').textContent=`${r.metadata.p1_name} vs ${r.metadata.p2_name}`;
      document.getElementById('championship-bracket-result').textContent=`Champion: ${r.name} · ${r.detail}`;
      const panel=document.getElementById('championship-bracket');panel.classList.remove('hidden');
      document.querySelector('.tab-btn[data-tab="tab-tournament"]').click();panel.focus();panel.scrollIntoView({block:'nearest'});
      window.dispatchEvent(new CustomEvent('championship:bracket',{detail:{winner:r.winner}}));
    }
    reset(){
      this.cleanup3D();this.stopAudio();this.active=false;this.state='IDLE';this.elapsed=0;this.resultData=null;this.hidden=false;
      if(this.saved2D){this.app.tacticalZoom=this.saved2D.zoom;this.app.tacticalPan=this.saved2D.pan;if(this.app.tdViz){this.app.tdViz.zoomLevel=this.saved2D.tdZoom;this.app.tdViz.panOffsetX=this.saved2D.tdX;this.app.tdViz.panOffsetY=this.saved2D.tdY;}this.saved2D=null;}
      this.updateOverlay();
    }
    draw2D(ctx,pos,frame){
      if(!this.active || this.hidden)return;
      const t=this.reduced?0:this.elapsed/1000,stage=this.stage,gold='#ffd978',color=this.resultData.winner===1?'#00e5ff':'#ff376c',nodes=this.app.replayData.map.nodes;
      ctx.save();ctx.lineCap='round';
      if(stage>=2){
        ctx.shadowColor=gold;ctx.shadowBlur=this.quality==='low'?0:10;
        for(const lane of this.app.replayData.map.lanes){const a=pos(lane.node_a),b=pos(lane.node_b);if(!a || !b)continue;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.strokeStyle='rgba(255,207,102,.35)';ctx.lineWidth=3;ctx.stroke();if(stage<6){const p=(t*.3+lane.node_a*.11)%1;ctx.beginPath();ctx.arc(a.x+(b.x-a.x)*p,a.y+(b.y-a.y)*p,3,0,Math.PI*2);ctx.fillStyle=gold;ctx.fill();}}
      }
      for(const node of nodes){const d=frame.nodes[String(node.id)],p=pos(node.id);if(!p || !d)continue;
        if(d.owner===3-this.resultData.winner && this.app.engineMode==='2d'){ctx.fillStyle=`rgba(3,7,16,${Math.min(.4,this.elapsed/3000*.4)})`;ctx.beginPath();ctx.arc(p.x,p.y,22,0,Math.PI*2);ctx.fill();}
        if(d.owner===this.resultData.winner){ctx.strokeStyle=color;ctx.lineWidth=node.id===(this.resultData.winner===1?0:14)?4:2;ctx.beginPath();ctx.ellipse(p.x,p.y+20,30+(stage<6?Math.sin(t*2)*2:0),10,0,0,Math.PI*2);ctx.stroke();
          if(stage>=2){const g=ctx.createLinearGradient(p.x,p.y-75,p.x,p.y+20);g.addColorStop(0,'rgba(255,213,111,0)');g.addColorStop(1,'rgba(255,213,111,.22)');ctx.fillStyle=g;ctx.beginPath();ctx.moveTo(p.x-30,p.y-75);ctx.lineTo(p.x+30,p.y-75);ctx.lineTo(p.x+12,p.y+20);ctx.lineTo(p.x-12,p.y+20);ctx.fill();}
        }
        const survivor=(d.resident_player || d.owner)===this.resultData.winner && Object.values(d.units || {}).some(n=>n>0);
        if(stage>=3 && survivor){ // Salute marks refer only to actual surviving squads.
          ctx.strokeStyle=color;ctx.lineWidth=2;const bob=stage<6?Math.sin(t*3+node.id)*3:0;
          for(let i=0;i<3;i++){const x=p.x-12+i*12,y=p.y-31+bob;ctx.beginPath();ctx.moveTo(x,y+7);ctx.lineTo(x,y-4);ctx.lineTo(x+6,y-7);ctx.stroke();}
        }
      }
      const center=pos(7);if(center && stage>=2){ctx.strokeStyle=gold;ctx.lineWidth=3;ctx.beginPath();ctx.ellipse(center.x,center.y+13,44,16,0,0,Math.PI*2);ctx.stroke();}
      if(center && stage>=4){const rise=Math.min(1,Math.max(0,(this.elapsed-TIMES[4])/1000));this.trophy2D(ctx,center.x,center.y-30-rise*35,Math.max(.55,Math.min(1,(this.app.displayWidth || 800)/900)));}
      if(center && stage>=4 && stage<6){const n=QUALITY[this.quality].particles;ctx.shadowBlur=0;for(let i=0;i<n;i++){const age=(t-6.5+i*.037)%2.2;if(age<0)continue;const x=center.x+Math.sin(i*29.3)*age*100,y=center.y-90-age*65+age*age*36;ctx.fillStyle=i%3===0?color:gold;ctx.save();ctx.translate(x,y);ctx.rotate(i+age*3);ctx.fillRect(-2,-3,4,6);ctx.restore();}}
      ctx.restore();
    }
    trophy2D(ctx,x,y,scale){
      ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);ctx.shadowColor='#ffcf66';ctx.shadowBlur=this.quality==='low'?0:22;
      const g=ctx.createLinearGradient(-25,0,25,0);g.addColorStop(0,'#b97816');g.addColorStop(.48,'#fff0b0');g.addColorStop(1,'#d99825');ctx.fillStyle=g;ctx.strokeStyle='#ffe6a0';ctx.lineWidth=4;
      ctx.beginPath();ctx.moveTo(-21,-25);ctx.lineTo(21,-25);ctx.quadraticCurveTo(23,6,0,13);ctx.quadraticCurveTo(-23,6,-21,-25);ctx.fill();
      for(const side of [-1,1]){ctx.beginPath();ctx.moveTo(side*20,-21);ctx.bezierCurveTo(side*49,-28,side*42,6,side*14,5);ctx.stroke();}
      ctx.fillRect(-4,10,8,22);ctx.fillRect(-20,30,40,8);ctx.fillRect(-25,38,50,10);ctx.shadowBlur=0;ctx.fillStyle='#735018';ctx.font='bold 16px serif';ctx.textAlign='center';ctx.fillText('★',0,-7);ctx.restore();
    }
    build3D(viz){
      const T=window.THREE,q=QUALITY[this.quality],root=new T.Group();root.name='championship-celebration';this.fx={viz,root,materials:[],units:[],nodes:[],camera:viz.camera.position.clone(),target:viz.controls.target.clone(),mode:this.app.engineMode,quality:this.quality};
      const gold=new T.MeshStandardMaterial({color:0xffcf66,emissive:0xc78319,emissiveIntensity:.45,metalness:.7,roughness:.3});
      const trophy=new T.Group();const mesh=(geo,x,y,z)=>{const m=new T.Mesh(geo,gold);m.position.set(x,y,z);trophy.add(m);return m;};
      mesh(new T.CylinderGeometry(10,3,15,q.segments),0,24,0);mesh(new T.CylinderGeometry(2,2,13,q.segments),0,10,0);mesh(new T.BoxGeometry(17,3,12),0,2,0);mesh(new T.BoxGeometry(22,4,16),0,-1,0);
      for(const side of [-1,1]){const handle=mesh(new T.TorusGeometry(7,1.2,5,q.segments,Math.PI*1.6),side*10,24,0);handle.rotation.z=side<0?Math.PI*.8:-Math.PI*.2;}
      const center=this.app.replayData.map.nodes.find(n=>n.id===7),p=viz.mapToWorld(center.x,center.y);trophy.position.set(p.x,60,p.z);root.add(trophy);this.fx.trophy=trophy;
      const paths=[];for(const lane of this.app.replayData.map.lanes){const a=this.app.replayData.map.nodes.find(n=>n.id===lane.node_a),b=this.app.replayData.map.nodes.find(n=>n.id===lane.node_b);if(!a || !b)continue;const from=viz.mapToWorld(a.x,a.y),to=viz.mapToWorld(b.x,b.y);paths.push(from.x,7,from.z,to.x,7,to.z);}
      const pathGeo=new T.BufferGeometry();pathGeo.setAttribute('position',new T.Float32BufferAttribute(paths,3));const energy=new T.LineSegments(pathGeo,new T.LineBasicMaterial({color:0xffd978,transparent:true,opacity:.65}));root.add(energy);this.fx.energy=energy;
      const sparkGeo=new T.BufferGeometry(),count=Math.min(paths.length/6,q.particles);sparkGeo.setAttribute('position',new T.BufferAttribute(new Float32Array(count*3),3));const sparks=new T.Points(sparkGeo,new T.PointsMaterial({color:0xffedb2,size:4,depthWrite:false}));root.add(sparks);this.fx.sparks=sparks;this.fx.paths=paths;
      const frame=this.app.replayData.frames[this.app.currentFrameIdx];
      for(const [id,obj] of viz.nodeObjects){const d=frame.nodes[String(id)];if(!d)continue;
        this.fx.nodes.push({obj,scale:obj.group.scale.clone()});
        if(obj.buildingMesh)obj.buildingMesh.traverse(child=>{if(child.isMesh && child.material){const originals=Array.isArray(child.material)?child.material:[child.material],clones=originals.map(m=>m.clone());this.fx.materials.push({child,original:child.material,clones,owner:d.owner});child.material=Array.isArray(child.material)?clones:clones[0];}});
        if(d.owner===this.resultData.winner){const cone=new T.Mesh(new T.ConeGeometry(18,85,6,1,true),new T.MeshBasicMaterial({color:0xffd371,transparent:true,opacity:.11,side:T.DoubleSide,depthWrite:false}));cone.position.copy(obj.group.position);cone.position.y=44;root.add(cone);}
        if((d.resident_player || d.owner)===this.resultData.winner){const group=viz.garrisonGroups.get(id);if(group)for(const unit of group.children)this.fx.units.push({unit,y:unit.position.y,rotation:unit.rotation.z});}
      }
      const positions=new Float32Array(q.particles*3);const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));const cloud=new T.Points(geometry,new T.PointsMaterial({color:0xffd978,size:3,transparent:true,opacity:.85,depthWrite:false}));root.add(cloud);this.fx.cloud=cloud;viz.scene.add(root);
    }
    render3D(viz){
      if(!this.active || this.hidden){if(this.fx)this.cleanup3D();return;}
      if(this.effectFailed)return;
      try{
        if(this.qualityViz!==viz){if(viz.quality!==this.quality && viz.applyQuality)viz.applyQuality(this.quality);this.qualityViz=viz;}
        if(this.fx && (this.fx.viz!==viz || this.fx.mode!==this.app.engineMode || this.fx.quality!==this.quality || !this.fx.nodes.every(n=>viz.nodeObjects.get(n.obj.nodeId)?.group===n.obj.group || n.obj.group.parent===viz.scene)))this.cleanup3D();
        if(!this.fx)this.build3D(viz);
        const fx=this.fx,t=this.elapsed/1000,stage=this.stage;viz.particles=[];if(viz.combatCloud)viz.combatCloud.geometry.setDrawRange(0,0);
        fx.energy.visible=stage>=2;fx.energy.material.opacity=stage<6 && !this.reduced ? .55+Math.sin(t*2)*.15 : .65;
        fx.sparks.visible=stage>=2 && stage<6 && !this.reduced;const points=fx.sparks.geometry.attributes.position;for(let i=0;i<points.count;i++){const p=(t*.3+i*.11)%1,a=i*6;points.setXYZ(i,fx.paths[a]+(fx.paths[a+3]-fx.paths[a])*p,8,fx.paths[a+2]+(fx.paths[a+5]-fx.paths[a+2])*p);}points.needsUpdate=true;
        fx.trophy.visible=stage>=4;fx.trophy.position.y=54+Math.min(1,Math.max(0,(this.elapsed-TIMES[4])/1200))*25;fx.trophy.rotation.y=stage<6 && !this.reduced?Math.sin(t*.4)*.18:0;
        fx.root.children.forEach(child=>{if(child.geometry?.type==='ConeGeometry')child.visible=stage>=2;});
        for(const item of fx.materials)for(const m of item.clones){if(item.owner===3-this.resultData.winner && m.color)m.color.copy((Array.isArray(item.original)?item.original[0]:item.original).color).multiplyScalar(1-Math.min(.6,t*.18));if(item.owner===this.resultData.winner && stage>=2 && m.emissive){m.emissive.setHex(0xd49c32);m.emissiveIntensity=.28;}}
        fx.units.forEach(({unit,y,rotation},i)=>{unit.position.y=y+(stage>=3 && stage<6 && !this.reduced?Math.max(0,Math.sin(t*3+i)) * 3:0);unit.rotation.z=rotation+(stage>=3 && stage<6 && !this.reduced?Math.sin(t*3+i)*.12:0);});
        const attr=fx.cloud.geometry.attributes.position;fx.cloud.visible=stage>=4 && stage<6 && !this.reduced;for(let i=0;i<attr.count;i++){const age=(t-6.5+i*.037)%2.2;attr.setXYZ(i,Math.sin(i*29.3)*age*45,100-age*25,Math.cos(i*19.7)*age*45);}attr.needsUpdate=true;
        // A manual cinematic camera stays manual. The automatic director is explicit opt-in.
        const canMove=this.app.engineMode==='3d' || (this.app.engineMode==='cinematic' && this.app.cinematic?.mode==='automatic');
        if(canMove && !this.reduced){const target=viz.defaultCameraPosition.clone().multiplyScalar(this.app.engineMode==='cinematic' && stage===4?.7:.96);if(this.app.engineMode==='cinematic' && stage===4)target.y*=.6;const blend=1-Math.exp(-.035);viz.camera.position.lerp(target,blend);viz.controls.target.lerp(new THREE.Vector3(0,stage>=4?18:0,0),blend);viz.controls.update();}
      }catch(error){this.cleanup3D();this.hidden=false;this.updateOverlay();if(!this.effectFailed){this.effectFailed=true;this.app.notify('The championship result is preserved. Using the lightweight celebration.');}}
    }
    cleanup3D(){const fx=this.fx;if(!fx)return;this.fx=null;
      for(const {child,original,clones} of fx.materials){child.material=original;clones.forEach(m=>m.dispose());}
      for(const {unit,y,rotation} of fx.units){unit.position.y=y;unit.rotation.z=rotation;}
      if(!fx.viz.disposed){fx.viz.camera.position.copy(fx.camera);fx.viz.controls.target.copy(fx.target);fx.viz.controls.update();}
      if(fx.root.parent)fx.root.parent.remove(fx.root);window.Arena3DArt.dispose(fx.root);
    }
    async playAudio(){
      if(!this.el('audio').checked)return;
      try{const C=window.AudioContext || window.webkitAudioContext;if(!C)return;const ctx=new C();this.audio=ctx;await ctx.resume();if(this.audio!==ctx || !this.active){await ctx.close();return;}
        const master=ctx.createGain();master.gain.value=.07;master.connect(ctx.destination);const now=ctx.currentTime+.65;
        [261.63,329.63,392,523.25,659.25,783.99].forEach((freq,i)=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type='triangle';o.frequency.value=freq;g.gain.setValueAtTime(0,now+i*.22);g.gain.linearRampToValueAtTime(.7,now+i*.22+.06);g.gain.exponentialRampToValueAtTime(.001,now+i*.22+1.5);o.connect(g);g.connect(master);o.start(now+i*.22);o.stop(now+i*.22+1.6);});
        // Short filtered noise swell gives a quiet crowd texture without an audio download.
        const buffer=ctx.createBuffer(1,ctx.sampleRate*2,ctx.sampleRate),samples=buffer.getChannelData(0);for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*.15;const source=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();source.buffer=buffer;filter.type='lowpass';filter.frequency.value=1400;gain.gain.setValueAtTime(0,now+2);gain.gain.linearRampToValueAtTime(.5,now+2.4);gain.gain.linearRampToValueAtTime(0,now+4);source.connect(filter);filter.connect(gain);gain.connect(master);source.start(now+2);
      }catch{this.stopAudio();}
    }
    speak(){if(!this.el('commentary').checked || !window.speechSynthesis)return;try{const hi=this.el('language').value==='hi-IN',text=hi?`${this.resultData.name}, चैंपियंस लीग 2026 के विजेता।`:`${this.resultData.name}. Champions League 2026 tournament champions.`;const utterance=new SpeechSynthesisUtterance(text);utterance.lang=this.el('language').value;utterance.voice=speechSynthesis.getVoices().find(v=>v.voiceURI===this.el('voice').value) || null;utterance.rate=.9;utterance.volume=.7;speechSynthesis.speak(utterance);}catch{}}
    stopAudio(){if(this.audio){this.audio.close().catch(()=>{});this.audio=null;}if(window.speechSynthesis)window.speechSynthesis.cancel();}
    dispose(){this.reset();this.events.abort();}
  }
  window.ChampionshipVictory=ChampionshipVictory;
})();
