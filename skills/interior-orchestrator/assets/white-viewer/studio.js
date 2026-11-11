(function(root){
'use strict';
root.WhiteStudio={version:1,create(E,renderer,scene,c){
 if(c.profileId!=='white-home3d-v1'||c.profileVersion!==1)throw new Error('不支持的白模光影版本');
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,c.renderer.maxPixelRatio));renderer.setClearColor(c.studio.background);renderer.outputColorSpace=E.SRGBColorSpace;renderer.toneMapping=E.ACESFilmicToneMapping;renderer.toneMappingExposure=c.renderer.exposure;renderer.shadowMap.enabled=true;renderer.shadowMap.type=3;
 const s=c.studio,p=c.shadows,hemi=new E.HemisphereLight(s.hemisphereSky,s.hemisphereGround,s.hemisphereIntensity);scene.add(hemi);
 const key=new E.DirectionalLight(s.keyColor,s.keyIntensity);key.position.set(...s.keyPosition);key.target.position.set(...s.target);key.castShadow=true;key.shadow.mapSize.set(p.mapSize,p.mapSize);Object.assign(key.shadow.camera,p.frustum);key.shadow.normalBias=p.normalBias;key.shadow.bias=p.bias;key.shadow.radius=p.radius;key.shadow.blurSamples=p.blurSamples;scene.add(key,key.target);
 const fill=new E.DirectionalLight(s.fillColor,s.fillIntensity);fill.position.set(...s.fillPosition);fill.target.position.set(...s.target);scene.add(fill,fill.target);
 const ec=document.createElement('canvas'),env=s.environment;ec.width=env.width;ec.height=env.height;const ctx=ec.getContext('2d'),gradient=ctx.createLinearGradient(0,0,0,env.height);env.stops.forEach(stop=>gradient.addColorStop(...stop));ctx.fillStyle=gradient;ctx.fillRect(0,0,env.width,env.height);ctx.fillStyle='#ffffff';ctx.fillRect(...env.softbox);const texture=new E.Texture(ec);texture.mapping=303;texture.colorSpace=E.SRGBColorSpace;texture.needsUpdate=true;scene.environment=texture;scene.environmentIntensity=s.environmentIntensity;
 const lights=c.fixtures.map((f,i)=>{const light=new E.PointLight('#ffce8b',f.maxIntensity*f.initialBrightness/100,f.rangeM,2);light.position.set(...f.position);light.position.x+=f.emitterOffsetM[0];light.position.y+=f.emitterOffsetM[1];light.position.z+=f.emitterOffsetM[2];light.castShadow=i<p.maxShadowedFixtures;light.shadow.mapSize.set(p.pointMapSize,p.pointMapSize);light.shadow.normalBias=.01;light.shadow.bias=-.0001;scene.add(light);return light;});
 let enabled=true;
 return {key,fill,hemi,lights,setFixturePower(value){enabled=!!value;lights.forEach((l,i)=>l.intensity=enabled?c.fixtures[i].maxIntensity*c.fixtures[i].initialBrightness/100:0);},prepareModel(model){model.traverse(o=>{if(!o.isMesh)return;const mats=Array.isArray(o.material)?o.material:[o.material];const glass=mats.some(m=>m.transmission>0);o.castShadow=!glass;o.receiveShadow=!glass;});},dispose(){texture.dispose();[key,fill,hemi,...lights].forEach(l=>{l.shadow?.map?.dispose();l.shadow?.mapPass?.dispose();scene.remove(l);});scene.remove(key.target,fill.target);}};
}};
})(window);
