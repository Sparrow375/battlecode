// Theme-specific, true 3D geometry. No simulation decisions live here.
(() => {
  const colors = { medieval: 0x8c9da8, cyber: 0x293d61, galactic: 0x7583a2, wasteland: 0x94735a, championship: 0x424f70 };
  const ownerColor = owner => owner === 1 ? 0x238bff : owner === 2 ? 0xf52d55 : 0x8294aa;
  function kit(theme, owner, quality = 'medium') {
    const group = new THREE.Group();
    const color = ownerColor(owner);
    const material = (value, glow = false) => {
      const mat = new THREE.MeshLambertMaterial({ color: value,
        emissive: glow ? value : 0x000000, emissiveIntensity: glow ? .55 : 0, fog: false });
      // The vendored Three.js predates automatic sRGB color management.
      mat.color.convertSRGBToLinear(); mat.emissive.convertSRGBToLinear();
      return mat;
    };
    const stone = material(colors[theme]), team = material(color), light = material(color, true);
    const gold = material(0xe6b94f, true), dark = material(0x233044), glass = material(0x9eeeff, true);
    function mesh(geo, mat, x=0,y=0,z=0) {
      const m = new THREE.Mesh(geo,mat); m.position.set(x,y,z); m.castShadow=true; m.receiveShadow=true; group.add(m); return m;
    }
    const box = (x,y,z,w,h,d,mat=stone) => mesh(new THREE.BoxGeometry(w,h,d),mat,x,y,z);
    const cylinder = (x,y,z,r,h,mat=stone,vertices=quality==='low'?6:12) => mesh(new THREE.CylinderGeometry(r,r,h,vertices),mat,x,y,z);
    const ring = (y,r,mat=light) => { const m=mesh(new THREE.TorusGeometry(r,.65,quality==='low'?4:6,quality==='low'?16:quality==='high'?48:32),mat,0,y,0); m.rotation.x=Math.PI/2; return m; };
    return { group,color,stone,team,light,gold,dark,glass,mesh,box,cylinder,ring,material };
  }

  function building(theme, kind, owner, quality = 'medium') {
    const k=kit(theme,owner,quality), {group,box,cylinder,ring,mesh,stone,team,light,gold,dark,glass}=k;
    const surface=document.createElement('canvas');surface.width=surface.height=64;
    const paint=surface.getContext('2d');paint.fillStyle='#ffffff';paint.fillRect(0,0,64,64);
    paint.strokeStyle=theme==='medieval'||theme==='championship'?'#9a9a9a':'#707070';paint.lineWidth=1;
    for(let y=0;y<64;y+=theme==='cyber'?8:16) {
      paint.beginPath();paint.moveTo(0,y);paint.lineTo(64,y);paint.stroke();
      for(let x=0;x<64;x+=24) {paint.beginPath();paint.moveTo(x+(y%32?12:0),y);paint.lineTo(x+(y%32?12:0),y+16);paint.stroke();}
    }
    const texture=new THREE.CanvasTexture(surface);
    stone.map=texture;team.map=texture;
    const core=kind==='core', tower=kind==='tower';
    cylinder(0,2,0,core?29:20,4,dark,8); ring(4,core?29:20);
    if(kind==='relic') {
      cylinder(0,5,0,18,6,stone); ring(9,17,gold);
      const crystal=mesh(new THREE.OctahedronGeometry(theme==='championship'?8:6.5),theme==='championship'?gold:glass,0,24,0);
      crystal.scale.y=1.8;
      if(theme==='wasteland') { box(-13,15,0,5,18,9,stone); box(13,15,0,5,18,9,stone); }
      if(theme==='championship') {
        cylinder(0,13,0,3,14,gold);
        for(const x of [-10,10]) { const handle=mesh(new THREE.TorusGeometry(8,1.5,8,24,Math.PI),gold,x,25,0); handle.rotation.z=x<0?Math.PI/2:-Math.PI/2; }
      }
      group.userData.reactor=crystal;
      return group;
    }
    if(theme==='galactic' && core) {
      const planet=mesh(new THREE.SphereGeometry(24,quality==='low'?12:quality==='high'?32:24,quality==='low'?8:16),team,0,27,0);
      const orbit=ring(25,34,glass); orbit.rotation.z=.24;
      for(let i=0;i<6;i++) { const a=i*Math.PI/3; box(Math.cos(a)*12,54,Math.sin(a)*12,4,14+i%3*4,4,stone); }
      const shield=mesh(new THREE.SphereGeometry(27,24,16),new THREE.MeshBasicMaterial({color:k.color,transparent:true,opacity:.12,wireframe:true}),0,27,0);
      group.userData.planet=planet; group.userData.shieldDome=shield;
    } else if(theme==='galactic') {
      cylinder(0,9,0,tower?9:17,10,stone); ring(14,tower?11:18);
      if(tower) cylinder(0,24,0,5,30,team);
      const dish=mesh(new THREE.SphereGeometry(9,16,8,0,Math.PI*2,0,Math.PI/2),stone,0,tower?40:23,0); dish.rotation.z=.5;
      cylinder(0,tower?42:23,0,1,14,light);
    } else if(theme==='cyber') {
      const h=core?42:tower?36:22;
      box(0,h/2+4,0,core?31:tower?12:24,h,core?25:19,stone);
      for(let y=10;y<h;y+=8) {
        box(0,y,core?13:10,core?24:8,2,1,light);
        box(core?16:13,y,0,1,2,13,glass);
      }
      if(core) for(const x of [-22,22]) { box(x,18,0,9,28,20,team); cylinder(x,39,0,.8,14,light); }
      cylinder(0,h+10,0,1,14,light); ring(5,core?30:20);
    } else if(theme==='wasteland') {
      const h=core?26:tower?32:17;
      box(0,h/2+4,0,core?40:tower?13:29,h,core?30:23,stone);
      box(0,11,core?15.5:12,core?17:8,13,1,dark);
      for(const x of [-1,1]) box(x*(core?21:15),12,0,4,18,25,team);
      cylinder(core?12:0,h+11,0,.9,18,dark);
      const dish=mesh(new THREE.SphereGeometry(core?9:5,12,8,0,Math.PI*2,0,Math.PI/2),stone,-8,h+7,0); dish.rotation.z=.6;
      for(const x of [-8,8]) box(x,h,11,3,3,2,glass);
    } else {
      // Medieval castles and the championship's gold-trimmed citadels.
      const trim=theme==='championship'?gold:stone, h=core?31:tower?34:20, w=core?35:tower?13:26;
      box(0,h/2+4,0,w,h,core?27:21,team);
      box(0,11,core?14:11,10,14,2,dark);
      const offsets=core?[-20,20]:[-w/2,w/2];
      for(const x of offsets) {
        cylinder(x,h/2+7,0,core?7:4,h+6,stone,8);
        mesh(new THREE.ConeGeometry(core?9:6,13,8),team,x,h+16,0);
        cylinder(x,h+26,0,.5,9,trim);
        box(x+3,h+28,0,6,4,.6,team);
      }
      for(let x=-w/2;x<=w/2;x+=7) box(x,h+6,11,4,5,4,trim);
      for(const x of [-8,8]) box(x,h*.62,core?14:11,3,5,1,glass);
      for(let y=12;y<h-3;y+=8) for(const x of [-w/2-1,w/2+1]) box(x,y,0,1.2,2,9,trim);
      if(theme==='championship') { box(0,h+3,0,w+2,2,23,gold); ring(6,core?30:21,gold); }
    }
    return group;
  }

  function unit(theme, role, owner, masked, quality = 'medium') {
    const k=kit(theme,owner,quality), {group,mesh,box,cylinder,stone,team,light,dark,gold}=k;
    if(masked) { mesh(new THREE.OctahedronGeometry(3),stone,0,4,0); return group; }
    if(theme==='galactic' || role==='scout') {
      const ship=mesh(new THREE.ConeGeometry(2,8,4),team,0,5,0); ship.rotation.x=Math.PI/2;
      box(0,5,1,8,.6,3,stone); mesh(new THREE.SphereGeometry(.8,6,6),light,0,5,4);
    } else if(role==='siege') {
      box(0,2,0,7,3,9,team); box(0,4,0,4,2,5,stone);
      const barrel=cylinder(0,5,-3,1,7,dark,8); barrel.rotation.x=Math.PI/2;
      for(const x of [-3.5,3.5]) box(x,1.5,0,1.5,3,10,dark);
    } else {
      box(0,4,0,3.5,4,2.5,team); mesh(new THREE.SphereGeometry(1.6,8,8),stone,0,7.5,0);
      for(const x of [-1,1]) { box(x,1,0,1,3,1.4,dark); box(x*2.6,4,0,1.2,3,1.4,stone); }
      if(role==='guard') box(-3,4,-1,2.8,4,1,theme==='championship'?gold:team);
      else { const weapon=cylinder(2.8,5,-2,.4,5,dark,6); weapon.rotation.x=Math.PI/2; }
      if(theme==='cyber') box(0,7.5,-1.4,2,.6,.5,light);
    }
    group.userData.unitType=role; group.userData.owner=owner; return group;
  }

  function environment(theme, quality = 'medium') {
    const k=kit(theme,0,quality), {group,mesh,box,cylinder,ring,stone,team,dark,gold,glass,material}=k;
    const count=quality==='low'?10:quality==='high'?22:16;
    for(let i=0;i<count;i++) {
      const angle=i/count*Math.PI*2, x=Math.cos(angle)*405, z=Math.sin(angle)*255;
      if(theme==='galactic') {
        const rock=mesh(new THREE.DodecahedronGeometry(5+i%4*2,0),stone,x,6+i%3*6,z); rock.rotation.set(i,.3*i,.2*i);
        if(i%4===0) mesh(new THREE.OctahedronGeometry(6),gold,x,13,z);
      } else if(theme==='medieval') {
        cylinder(x,8,z,2,16,dark,6); mesh(new THREE.ConeGeometry(12,32,7),material(0x247637),x,25,z);
      } else if(theme==='wasteland') {
        box(x,4,z,10,8,8,stone); if(i%3===0) cylinder(x,18,z,7,18,stone,10);
      } else if(theme==='cyber') {
        box(x,10+i%4*8,z,10,20+i%4*16,12,stone); box(x,12+i%4*8,z+6.5,7,2,1,glass);
      } else {
        cylinder(x,8,z,6,16,dark,6); mesh(new THREE.OctahedronGeometry(4),glass,x,20,z);
        if(i%5===0) { cylinder(x,35,z,.6,60,gold,6); box(x+9,42,z,16,28,1,team); }
      }
    }
    if(theme==='championship') { const podium=building(theme,'relic',0); podium.position.set(0,8,-280); podium.scale.setScalar(1.8); group.add(podium); }
    return group;
  }
  function dispose(object) {
    const geometries=new Set(), materials=new Set(), textures=new Set();
    object.traverse(child => { if(child.geometry) geometries.add(child.geometry); if(child.material) for(const m of Array.isArray(child.material)?child.material:[child.material]) { materials.add(m); if(m.map) textures.add(m.map); } });
    geometries.forEach(g=>g.dispose()); materials.forEach(m=>m.dispose()); textures.forEach(t=>t.dispose());
  }
  window.Arena3DArt={building,unit,environment,dispose};
})();
