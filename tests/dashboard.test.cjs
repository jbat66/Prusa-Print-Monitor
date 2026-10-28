const {test}=require('node:test');

const assert=require('node:assert/strict');

const vm=require('node:vm');

const fs=require('node:fs');

function dashboard(options={}){

 const elements={}, timers=[];let plays=0;

 const element=id=>elements[id] ||= {textContent:'',style:{},value:'desktop',setAttribute(){},removeAttribute(){}};

 const context={document:{getElementById:element,body:{dataset:{},style:{setProperty(){}}}},

 navigator:options.navigator||{userAgent:"Desktop browser"},
 localStorage:{getItem(){return options.savedLayout;},setItem(){}},Audio:class{paused=true;play(){plays++;this.paused=false;return Promise.resolve();}pause(){this.paused=true;}addEventListener(){}},

 Date,Math,String,console,setInterval(){},setTimeout(fn){timers.push(fn);},fetch:async(url)=>({ok:true,json:async()=>url.startsWith('/api/camera/status')?context.cameraResponse:context.next})};

 context.cameraResponse={state:'connecting',message:'Connecting camera…'};

 context.next={state:'PRINTING',remaining:600,filament:300,connected:true,updated:Date.now()/1000,server_time:Date.now()/1000,event:0,alert:true,camera:true,refresh:60,repeat:30};

 vm.createContext(context);vm.runInContext(fs.readFileSync('static/app.js','utf8'),context);

 return {context,element,timers,plays:()=>plays,run:code=>vm.runInContext(code,context)};

}

const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('state changes alert until acknowledged; unchanged polls do not restart',async()=>{

 const d=dashboard();await settle();await d.element('sound').onclick();const baseline=d.plays();

 assert.equal(d.run('pending'),false);assert.equal(d.element('ack').hidden,true);

 d.context.next={...d.context.next,state:'PAUSED',event:1};await d.timers.shift()();

 assert.equal(d.plays(),baseline+1);assert.equal(d.run('pending'),true);assert.equal(d.element('ack').hidden,false);

 d.run('audio.pause(); lastPlayed=Date.now()-31000; tick()');assert.equal(d.plays(),baseline+2);

 d.element('ack').onclick();d.run('lastPlayed=0; tick()');assert.equal(d.plays(),baseline+2);

 await d.timers.shift()();assert.equal(d.run('pending'),false);

});

test('mute suppresses playback; camera and layout controls work',async()=>{

 const d=dashboard();await settle();await d.element('sound').onclick();d.element('mute').onclick();

 d.context.next={...d.context.next,state:'FINISHED',event:1};const before=d.plays();await d.timers.shift()();assert.equal(d.plays(),before);

 d.element('camera-toggle').onclick();assert.match(d.element('camera').src,/^\/camera\?viewer=\d+$/);assert.equal(d.element('camera-toggle').textContent,'Camera Enabled');assert.equal(d.element('camera-panel').hidden,false);

 d.element('camera-toggle').onclick();assert.equal(d.element('camera-panel').hidden,true);assert.equal(d.element('camera-toggle').textContent,'Enable Camera');

 d.element('layout').value='large';d.element('layout').onchange();assert.equal(d.context.document.body.dataset.layout,'large');

});

test('disconnect freezes countdown and hides finish estimate',async()=>{

 const d=dashboard();await settle();d.context.next={...d.context.next,connected:false};await d.timers.shift()();

 assert.equal(d.element('remaining').textContent,'0:10:00');assert.equal(d.element('finish').textContent,'\u2014');

 assert.match(d.element('connection').textContent,/Disconnected/);

});

test('disabled settings share the existing notice row',async()=>{

 const d=dashboard();await settle();

 for(const [alert,camera,message] of [

  [false,false,'Alerts and Camera are disabled in container settings'],

  [false,true,'Alerts are disabled in container settings'],

  [true,false,'Camera is disabled in container settings']]){

  d.context.next={...d.context.next,alert,camera,version:'0.2'};

  await d.timers.shift()();

  assert.equal(d.element('notice').textContent,message);

  assert.equal(d.element('version').textContent,'v0.2');

 }

 d.context.next={...d.context.next,alert:true,camera:true};await d.timers.shift()();

 assert.equal(d.element('notice').textContent,'Click Enable sounds to allow browser audio');

});



test('camera status updates without relying on an image load event',async()=>{

 const d=dashboard();await settle();d.element('camera-toggle').onclick();

 d.context.cameraResponse={state:'live',message:'Live camera'};await d.run('cameraStatus()');

 assert.equal(d.element('camera-status').textContent,'Live camera');

 d.context.cameraResponse={state:'error',message:'Camera timed out. Check UNRAID container logs and CAMERA_URL.'};await d.run('cameraStatus()');

 assert.match(d.element('camera-status').textContent,/timed out/);

});


test('mobile devices use Mobile and hide Full screen while desktop preserves preferences',async()=>{
 for(const navigator of [
  {userAgent:'Mozilla Android Mobile'},
  {userAgentData:{mobile:true}},
  {platform:'MacIntel',maxTouchPoints:5,userAgent:'Desktop Safari'}]){
  const d=dashboard({navigator,savedLayout:'large'});await settle();
  assert.equal(d.element('layout').value,'mobile');
  assert.equal(d.element('fullscreen').hidden,true);
  d.element('layout').value='compact';d.element('layout').onchange();
  assert.equal(d.context.document.body.dataset.layout,'compact');
 }
 const desktop=dashboard({savedLayout:'large'});await settle();
 assert.equal(desktop.element('layout').value,'large');
 assert.equal(desktop.element('fullscreen').hidden,false);
});
test('layout options are alphabetical and Acknowledge is above the controls',()=>{
 const html=fs.readFileSync('static/index.html','utf8');
 const options=[...html.matchAll(/<option[^>]*>([^<]+)<\/option>/g)].map(m=>m[1]);
 assert.deepEqual(options,[...options].sort((a,b)=>a.localeCompare(b)));
 assert.match(html,/<div id="ack-row" class="ack-row" hidden><button id="ack" hidden disabled>Acknowledge<\/button><\/div><footer>/);
});

test('Mute appears after sounds are enabled and updates the notice immediately',async()=>{
 const d=dashboard();await settle();
 assert.equal(d.element('mute').hidden,true);
 await d.element('sound').onclick();
 assert.equal(d.element('mute').hidden,false);
 assert.equal(d.element('notice').style.color,'#57d69a');
 d.element('mute').onclick();
 assert.equal(d.element('notice').textContent,'Sounds muted \u2022 Unmute to allow alerts to play');
 assert.equal(d.element('mute').textContent,'Unmute');
 assert.equal(d.element('notice').style.color,'#ffb258');
 await d.timers.shift()();
 assert.equal(d.element('notice').textContent,'Sounds muted \u2022 Unmute to allow alerts to play');
 d.element('mute').onclick();
 assert.equal(d.element('notice').textContent,'Sounds ready \u2022 no unacknowledged changes');
 assert.equal(d.element('notice').style.color,'#57d69a');
});
