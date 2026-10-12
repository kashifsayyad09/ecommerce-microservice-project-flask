/* Drocart Shop - interactive 3D background (Three.js) + card tilt */
(function(){
  var reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var mobile=window.innerWidth<720;
  // ---- Card tilt (delegated, works for dynamically rendered cards)
  var SEL='.product-card,.cat-tile,.deal-card,.promo-tile,.promo-banner,.deal-hero,.deal-mini';
  if(!reduce&&!mobile){
    document.addEventListener('pointermove',function(e){
      var el=e.target.closest&&e.target.closest(SEL); if(!el)return;
      var r=el.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
      el.style.setProperty('--ry',(x*14).toFixed(2)+'deg');el.style.setProperty('--rx',(-y*14).toFixed(2)+'deg');
    });
    document.addEventListener('pointerout',function(e){
      var el=e.target.closest&&e.target.closest(SEL); if(!el)return;
      el.style.setProperty('--rx','0deg');el.style.setProperty('--ry','0deg');
    });
  }
  // ---- 3D scene
  if(typeof THREE==='undefined')return;
  var cv=document.createElement('canvas');cv.id='bg3d';document.body.prepend(cv);
  var renderer=new THREE.WebGLRenderer({canvas:cv,antialias:!mobile,alpha:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,mobile?1.5:2));
  var scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(60,1,.1,200);cam.position.z=30;
  scene.add(new THREE.AmbientLight(0x6666ff,.6));
  var l1=new THREE.PointLight(0x22d3ee,1.6,120);l1.position.set(20,15,20);scene.add(l1);
  var l2=new THREE.PointLight(0xf472b6,1.4,120);l2.position.set(-25,-10,15);scene.add(l2);
  // star field
  var N=mobile?500:1400,pos=new Float32Array(N*3);
  for(var i=0;i<N*3;i++)pos[i]=(Math.random()-.5)*160;
  var g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));
  var stars=new THREE.Points(g,new THREE.PointsMaterial({color:0x9aa8ff,size:.22,transparent:true,opacity:.85}));scene.add(stars);
  // floating 3D shapes (glass solids + wireframe shells)
  var shapes=[],geos=[new THREE.IcosahedronGeometry(2.2,0),new THREE.OctahedronGeometry(2.2),new THREE.TorusGeometry(1.8,.55,16,40),new THREE.TetrahedronGeometry(2.4),new THREE.TorusKnotGeometry(1.5,.45,80,12)];
  var cols=[0x7c5cff,0x22d3ee,0xf472b6,0x60a5fa];
  for(var k=0;k<(mobile?8:16);k++){
    var geo=geos[k%geos.length],c=cols[k%cols.length];
    var m=new THREE.Mesh(geo,new THREE.MeshPhongMaterial({color:c,transparent:true,opacity:.28,shininess:120,flatShading:true}));
    var w=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color:c,wireframe:true,transparent:true,opacity:.5}));
    var grp=new THREE.Group();grp.add(m);grp.add(w);
    grp.position.set((Math.random()-.5)*70,(Math.random()-.5)*45,(Math.random()-.5)*40-8);
    var s=.6+Math.random()*1.1;grp.scale.set(s,s,s);
    grp.userData={rx:(Math.random()-.5)*.01,ry:(Math.random()-.5)*.012,fy:Math.random()*6,sp:.3+Math.random()*.6,y0:grp.position.y};
    scene.add(grp);shapes.push(grp);
  }
  // hero: large wireframe knot in the centre-back
  var hero=new THREE.Mesh(new THREE.TorusKnotGeometry(7,1.6,160,20),new THREE.MeshBasicMaterial({color:0x7c5cff,wireframe:true,transparent:true,opacity:.18}));
  hero.position.set(0,0,-30);scene.add(hero);
  function size(){var w=window.innerWidth,h=window.innerHeight;renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();}
  size();window.addEventListener('resize',size);
  var mx=0,my=0,sy=0;
  window.addEventListener('pointermove',function(e){mx=e.clientX/window.innerWidth-.5;my=e.clientY/window.innerHeight-.5;});
  window.addEventListener('scroll',function(){sy=window.scrollY;},{passive:true});
  var t=0,run=true;document.addEventListener('visibilitychange',function(){run=!document.hidden;if(run)loop();});
  function loop(){
    if(!run)return;requestAnimationFrame(loop);t+=.01;
    if(!reduce){
      shapes.forEach(function(s){s.rotation.x+=s.userData.rx;s.rotation.y+=s.userData.ry;s.position.y=s.userData.y0+Math.sin(t*s.userData.sp+s.userData.fy)*2;});
      stars.rotation.y+=.0006;hero.rotation.x+=.002;hero.rotation.y+=.003;
    }
    cam.position.x+=(mx*8-cam.position.x)*.04;
    cam.position.y+=((-my*6-sy*.012)-cam.position.y)*.04;
    cam.lookAt(0,-sy*.004,0);
    renderer.render(scene,cam);
  }
  loop();
})();
