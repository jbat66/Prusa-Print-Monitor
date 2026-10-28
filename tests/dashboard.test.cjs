const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function dashboard(){
 const elements={}, timers=[];let plays=0;
 const element=id=>elements[id] ||= {textContent:'',style:{},value:'desktop',setAttribute(){},removeAttribute(){}};
 const context={document:{getElementById:element,body:{dataset:{},style:{setProperty(){}}}},
 localStorage:{getItem(){},setItem(){}},Audio:class{paused=true;play(){plays++;this.paused=false;return Promise.resolve();}pause(){this.paused=true;}addEventListener(){}},
 Date,Math,String,console,setInterval(){},setTimeout(fn){timers.push(fn);},fetch:async()=>({ok:true,json:async()=>context.next})};
 context.next={state:'PRINTING',remaining:600,filament:300,connected:true,updated:Date.now()/1000,server_time:Date.now()/1000,event:0,alert:true,camera:true,refresh:60,repeat:30};
 vm.createContext(context);vm.runInContext(fs.readFileSync('static/app.js','utf8'),context);
 return {context,element,timers,plays:()=>plays,run:code=>vm.runInContext(code,context)};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('state changes alert until acknowledged; unchanged polls do not restart',async()=>{
 const d=dashboard();await settle();await d.element('sound').onclick();const baseline=d.plays();
 assert.equal(d.run('pending'),false);
 d.context.next={...d.context.next,state:'PAUSED',event:1};await d.timers.shift()();
 assert.equal(d.plays(),baseline+1);assert.equal(d.run('pending'),true);
 d.run('audio.pause(); lastPlayed=Date.now()-31000; tick()');assert.equal(d.plays(),baseline+2);
 d.element('ack').onclick();d.run('lastPlayed=0; tick()');assert.equal(d.plays(),baseline+2);
 await d.timers.shift()();assert.equal(d.run('pending'),false);
});
test('mute suppresses playback; camera and layout controls work',async()=>{
 const d=dashboard();await settle();await d.element('sound').onclick();d.element('mute').onclick();
 d.context.next={...d.context.next,state:'FINISHED',event:1};const before=d.plays();await d.timers.shift()();assert.equal(d.plays(),before);
 d.element('camera-toggle').onclick();assert.equal(d.element('camera').src,'/camera');assert.equal(d.element('camera-panel').hidden,false);
 d.element('camera-toggle').onclick();assert.equal(d.element('camera-panel').hidden,true);
 d.element('layout').value='large';d.element('layout').onchange();assert.equal(d.context.document.body.dataset.layout,'large');
});
test('disconnect freezes countdown and hides finish estimate',async()=>{
 const d=dashboard();await settle();d.context.next={...d.context.next,connected:false};await d.timers.shift()();
 assert.equal(d.element('remaining').textContent,'0:10:00');assert.equal(d.element('finish').textContent,'—');
 assert.match(d.element('connection').textContent,/Disconnected/);
});
