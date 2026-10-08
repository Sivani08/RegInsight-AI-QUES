import React,{useEffect,useRef,useState} from 'react';
import * as THREE from 'three';

export default function EvidenceScene(){
  const host=useRef(null),paused=useRef(false);const [playing,setPlaying]=useState(true),[available,setAvailable]=useState(true);
  useEffect(()=>{paused.current=!playing},[playing]);
  useEffect(()=>{
    let renderer,frame,observer;const objects=[];
    try{
      renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.current.appendChild(renderer.domElement);
      const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(36,1,.1,100);camera.position.set(0,1,11);
      const group=new THREE.Group();scene.add(group);scene.add(new THREE.AmbientLight(0xffffff,2));
      const light=new THREE.DirectionalLight(0xffffff,4);light.position.set(4,5,7);scene.add(light);
      const material=new THREE.MeshPhysicalMaterial({color:0x328d86,metalness:.35,roughness:.2,transparent:true,opacity:.72,side:THREE.DoubleSide});objects.push(material);
      const geo=new THREE.IcosahedronGeometry(1.7,1);objects.push(geo);
      const core=new THREE.Mesh(geo,material);core.rotation.z=.3;group.add(core);
      const edgeGeo=new THREE.EdgesGeometry(geo),lineMaterial=new THREE.LineBasicMaterial({color:0x085e65,transparent:true,opacity:.32});objects.push(edgeGeo,lineMaterial);group.add(new THREE.LineSegments(edgeGeo,lineMaterial));
      for(let ring=0;ring<3;ring++){
        const g=new THREE.TorusGeometry(2.5+ring*.25,.012,8,128),m=new THREE.MeshBasicMaterial({color:0x72a4a7,transparent:true,opacity:.55});objects.push(g,m);
        const orbit=new THREE.Mesh(g,m);orbit.rotation.set(ring*.65+.45,ring*.72,.25);group.add(orbit);
        for(let j=0;j<5;j++){
          const a=j*Math.PI*2/5+ring;const sg=new THREE.SphereGeometry(.055+j*.006,16,16),sm=new THREE.MeshStandardMaterial({color:ring===1?0xbc9658:0x286b77,metalness:.5,roughness:.25});objects.push(sg,sm);
          const node=new THREE.Mesh(sg,sm);node.position.set(Math.cos(a)*(2.5+ring*.25),Math.sin(a)*(2.5+ring*.25),0);orbit.add(node);
        }
      }
      function resize(){if(!host.current)return;const {width,height}=host.current.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix()}
      observer=new ResizeObserver(resize);observer.observe(host.current);resize();
      const gentle=matchMedia('(prefers-reduced-motion: reduce)').matches;
      let last=0;function render(t){frame=requestAnimationFrame(render);if(!document.hidden&&!paused.current){group.rotation.y+=Math.min(t-last,40)*(gentle?.000045:.00018);group.rotation.x=gentle?0:Math.sin(t*.00012)*.12;}last=t;renderer.render(scene,camera)}render(0);
    }catch{setAvailable(false)}
    return()=>{cancelAnimationFrame(frame);observer?.disconnect();objects.forEach(o=>o.dispose());renderer?.dispose();renderer?.domElement.remove()}
  },[]);
  return <div className="evidence-scene"><div ref={host} className="scene-canvas" role="img" aria-label="Animated three-dimensional evidence network, a conceptual illustration"/>{!available&&<div className="scene-fallback">◈</div>}<span className="scene-label label-a">SOURCE RECORDS<span>Traceable by design</span></span><span className="scene-label label-b">DETERMINISTIC CORE<span>Every number has a source</span></span><span className="scene-label label-c">HUMAN OVERSIGHT<span>Evidence before decisions</span></span><button className="motion-toggle" onClick={()=>setPlaying(!playing)} aria-pressed={playing}>{playing?'Pause animation':'Play animation'}</button><span className="scene-caption">Conceptual evidence network · Interactive 3D</span></div>
}
