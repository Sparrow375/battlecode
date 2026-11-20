// Presentation only. Artwork is an atlas of independent transparent objects.
(() => {
  const themes = {
    medieval: { name: 'Medieval Conquest', sky: '#9ad03b', ground: '#7bb828', accent: '#ffd166', path: '#e9d8a6', edge: '#997b53', ink: '#583115', metal: '#697787', effect: '#ffd166' },
    cyber: { name: 'Cyber Warfare', sky: '#172347', ground: '#070c1c', accent: '#55e7ff', path: '#69f0ff', edge: '#224b70', ink: '#10203c', metal: '#243458', effect: '#ce80ff' },
    galactic: { name: 'Galactic Dominion', sky: '#0a0714', ground: '#03040d', accent: '#8b6ee8', path: '#7a9de0', edge: '#1a1a3a', ink: '#080b1a', metal: '#3a4466', effect: '#9b7ef0' },
    wasteland: { name: 'Wasteland Survival', sky: '#8c6a3a', ground: '#4a3018', accent: '#c9922a', path: '#b89060', edge: '#3d2a14', ink: '#231a0e', metal: '#6b5c48', effect: '#d4883a' },
    championship: { name: 'The Ultimate Arena', sky: '#202735', ground: '#090d16', accent: '#f5d787', path: '#eac978', edge: '#554a32', ink: '#131c2b', metal: '#3f4b62', effect: '#ffe4a0' }
  };
  Object.values(themes).forEach(Object.freeze);
  Object.freeze(themes);

  const assetCache = new Map();
  const sources = new Map(), backgrounds = new Map();
  function getAtlas(src = 'assets/arenas/theme-atlas.png') {
    if (!sources.has(src)) sources.set(src,new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => { sources.delete(src); reject(new Error('Arena asset could not load: '+src)); };
      image.src = src;
    }));
    return sources.get(src);
  }
  function sprite(atlas, row, column, owner, unit = false) {
    // Bounds follow the authored atlas; every object remains independently interactive.
    const columns = [[0,290],[300,515],[525,785],[790,1030],[1035,1280],[1285,1536]];
    const rows = [[0,250],[250,505],[505,735],[735,1024]];
    const [left,right] = unit ? [column*atlas.width/4,(column+1)*atlas.width/4] : columns[column];
    const [top,bottom] = unit ? [row*atlas.height/4,(row+1)*atlas.height/4] : rows[row];
    const canvas = document.createElement('canvas'); canvas.width=canvas.height=256;
    const ctx=canvas.getContext('2d');
    const scale=Math.min(248/(right-left),248/(bottom-top));
    const w=(right-left)*scale,h=(bottom-top)*scale;
    ctx.drawImage(atlas,left,top,right-left,bottom-top,(256-w)/2,256-h,w,h);
    if (owner !== 1 && (unit || column !== 3 && column !== 5)) {
      const pixels=ctx.getImageData(0,0,256,256), data=pixels.data;
      for(let i=0;i<data.length;i+=4) {
        const r=data[i],g=data[i+1],b=data[i+2];
        if(b>r*1.18 && b>g*.96 && b-r>20) {
          if(owner===2) { data[i]=Math.min(255,b*1.12); data[i+1]=r*.65; data[i+2]=Math.max(r,g*.4); }
          else { const gray=r*.21+g*.52+b*.27; data[i]=gray*.85; data[i+1]=gray*.94; data[i+2]=gray; }
        }
      }
      ctx.putImageData(pixels,0,0);
    }
    return canvas;
  }
  function loadAssets(id) {
    if(!themes[id] || id==='medieval') return Promise.reject(new Error('Unknown arena pack: '+id));
    if(assetCache.has(id)) return assetCache.get(id);
    const pending=Promise.all([getAtlas(),getAtlas('assets/arenas/unit-atlas.png'),getAtlas('assets/arenas/terrain-atlas.png')]).then(([atlas,units,terrain])=>{
      const row=['cyber','galactic','wasteland','championship'].indexOf(id), pack={};
      for(const [suffix,owner] of [['p1',1],['p2',2],['neutral',0]]) {
        for(const [kind,column] of [['castle',0],['tower',1],['barracks',2]]) pack[kind+'_'+suffix]=sprite(atlas,row,column,owner);
      }
      pack.tower_stone=pack.tower_neutral; pack.barracks=pack.barracks_neutral;
      pack.relic_shrine=sprite(atlas,row,3,1);
      for(const suffix of ['p1','p2']) {
        ['knight','rogue','cannon','eagle'].forEach((role,column)=>{pack[role+'_'+suffix]=sprite(units,row,column,suffix==='p1'?1:2,true);});
      }
      const decoration=sprite(atlas,row,5,1);
      for(const kind of ['tree','rock','hut','fence']) pack[kind]=decoration;
      const plate=document.createElement('canvas');plate.width=terrain.width/2;plate.height=terrain.height/2;
      plate.getContext('2d').drawImage(terrain,(row%2)*terrain.width/2,Math.floor(row/2)*terrain.height/2,terrain.width/2,terrain.height/2,0,0,plate.width,plate.height);
      backgrounds.set(id,plate);terrainCache.clear();
      return pack;
    }).catch(error=>{assetCache.delete(id);throw error;});
    assetCache.set(id,pending); return pending;
  }

  const terrainCache=new Map();
  function drawTerrain(ctx,width,height,id) {
    const key=id+'_'+Math.round(width)+'_'+Math.round(height);
    let canvas=terrainCache.get(key);
    if(!canvas) {
      canvas=document.createElement('canvas'); canvas.width=Math.max(1,Math.ceil(width)); canvas.height=Math.max(1,Math.ceil(height));
      paintTerrain(canvas.getContext('2d'),canvas.width,canvas.height,id);
      if(terrainCache.size>12) terrainCache.clear();
      terrainCache.set(key,canvas);
    }
    ctx.fillStyle=themes[id].ground; ctx.fillRect(-2500,-2500,width+5000,height+5000);
    ctx.drawImage(canvas,0,0,width,height);
  }
  function paintTerrain(c,w,h,id) {
    const t=themes[id];
    if (backgrounds.has(id)) { c.drawImage(backgrounds.get(id),0,0,w,h); return; }
    const gradient=c.createRadialGradient(w*.5,h*.4,0,w*.5,h*.5,Math.max(w,h)*.8);
    gradient.addColorStop(0,t.sky); gradient.addColorStop(1,t.ground);
    c.fillStyle=gradient;c.fillRect(0,0,w,h);
    let seed=371; const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    const glow=(x,y,r,color)=> {const g=c.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,color);g.addColorStop(1,'transparent');c.fillStyle=g;c.fillRect(x-r,y-r,r*2,r*2);};
    if(id==='galactic') {
      // Deep-space base: very dark, near-black with subtle violet centre
      const deep=c.createRadialGradient(w*.5,h*.45,0,w*.5,h*.5,Math.max(w,h)*.9);
      deep.addColorStop(0,'#0d0920');deep.addColorStop(.55,'#070612');deep.addColorStop(1,'#03040d');
      c.fillStyle=deep;c.fillRect(0,0,w,h);
      // Three large, dim nebula clouds — muted violet and midnight blue only
      glow(w*.72,h*.22,w*.28,'#2a0a4a18');
      glow(w*.18,h*.68,w*.22,'#09244a1a');
      glow(w*.55,h*.8, w*.18,'#1a0a3a12');
      // Fine star field — lower density, dimmer, two-size variety
      for(let i=0;i<520;i++){
        c.fillStyle=i%5===0?'#b0c8ff':'#e8f0ff';
        c.globalAlpha=.08+random()*.28;
        const s=i%18===0?1.6:i%7===0?1.1:.7;
        c.fillRect(random()*w,random()*h,s,s);
      }
      c.globalAlpha=1;
      // Single dim decorative planet peek (bottom-left corner only, reduced)
      const planet=c.createRadialGradient(0,h+100,40,0,h+100,210);
      planet.addColorStop(0,'#0e2550');planet.addColorStop(.85,'#1a4a78');planet.addColorStop(.96,'#3a8ab0');planet.addColorStop(1,'transparent');
      c.fillStyle=planet;c.fillRect(0,h-110,220,110);
      // Single thin orbital ring — dim, single-width stroke
      c.strokeStyle='#2d6a9a28';c.lineWidth=1.2;
      c.beginPath();c.ellipse(w/2,h/2,w*.46,h*.44,0,0,Math.PI*2);c.stroke();
      // Corner HUD frame shared with cyber (applied below)
    }
    if(id==='cyber'||id==='galactic') {
      c.strokeStyle=id==='cyber'?'#1d8caf29':'#274c8022';c.lineWidth=1;
      for(let x=0;x<w;x+=28){c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.stroke();}
      for(let y=0;y<h;y+=28){c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();}
      if(id==='cyber') {
        for(let i=0;i<40;i++){const x=random()*w,y=random()*h;c.strokeStyle=i%3?'#188fce55':'#c32caf66';c.beginPath();c.moveTo(x,y);c.lineTo(x+25,y);c.lineTo(x+40,y+15);c.lineTo(x+75,y+15);c.stroke();glow(x,y,4,'#2ae6ff');}
        glow(w*.15,h*.2,180,'#0875a222');glow(w*.9,h*.9,180,'#af25882a');
      }
    }
    if(id==='wasteland'||id==='medieval') {
      for(let i=0;i<5500;i++){c.globalAlpha=.06+random()*.07;c.fillStyle=i%2?'#352a1b':'#fff2bb';const x=random()*w,y=random()*h;c.fillRect(x,y,2+random()*5,1+random()*2);}
      c.globalAlpha=1;
      if(id==='wasteland') {
        // Muted cracked-earth overlay — sparse irregular lines in dark rust
        c.strokeStyle='#2a180a44';c.lineWidth=1;
        for(let i=0;i<90;i++){const x=random()*w,y=random()*h;c.beginPath();c.moveTo(x,y);c.lineTo(x+6+random()*14,y+random()*8-4);c.lineTo(x+random()*22+8,y+random()*12-2);c.stroke();}
        // Very dim dusty-amber glow top-right only (sun barely visible)
        glow(w*.88,0,w*.38,'#8c541818');
      }
    }
    if(id==='championship') {
      c.fillStyle='#222e43';c.fillRect(0,0,w,h);
      for(let y=0;y<h;y+=32) for(let x=-50;x<w;x+=64) {c.strokeStyle=(x+y)%3?'#3e49614d':'#7886a02b';c.strokeRect(x+(y/32%2)*32,y,64,32);}
      for(const [x,color] of [[w*.08,'#177fff44'],[w*.92,'#ff235044']]) glow(x,h*.5,w*.45,color);
      c.strokeStyle='#daae54';c.lineWidth=5;c.beginPath();c.moveTo(50,14);c.lineTo(w-50,14);c.lineTo(w-14,50);c.lineTo(w-14,h-50);c.lineTo(w-50,h-14);c.lineTo(50,h-14);c.lineTo(14,h-50);c.lineTo(14,50);c.closePath();c.stroke();
      for(const x of [w*.15,w*.85]) {const g=c.createLinearGradient(x,0,w/2,h);g.addColorStop(0,'#ffe2a42a');g.addColorStop(1,'transparent');c.fillStyle=g;c.beginPath();c.moveTo(x,0);c.lineTo(w/2-80,h);c.lineTo(w/2+80,h);c.closePath();c.fill();}
    }
    if(id==='cyber'||id==='galactic') {
      // Cyber: bright cyan frame; Galactic: dim violet frame
      c.strokeStyle=id==='cyber'?'#35b8e9':'#4a3878';c.lineWidth=id==='cyber'?1.3:1.0;
      c.beginPath();c.moveTo(32,10);c.lineTo(w-32,10);c.lineTo(w-10,32);c.lineTo(w-10,h-32);c.lineTo(w-32,h-10);c.lineTo(32,h-10);c.lineTo(10,h-32);c.lineTo(10,32);c.closePath();c.stroke();
    }
  }
  window.ArenaThemes=Object.freeze({themes,loadAssets,drawTerrain});
})();
