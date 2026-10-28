const $ = id => document.getElementById(id);
let data, received=0, event=null, pending=false, enabled=false, muted=false, lastPlayed=0, cameraOn=false, cameraViewer=Date.now();
let audioContext, alertBuffer, alertSource;
const audio={paused:true,currentTime:0,
 pause(){
  const source=alertSource;alertSource=null;this.paused=true;
  if(source){source.onended=null;try{source.stop();}catch{}source.disconnect();}
 },
 async play(){
  if(!audioContext||audioContext.state!=='running'||!alertBuffer)throw Error('Audio not ready');
  this.pause();
  const source=audioContext.createBufferSource();source.buffer=alertBuffer;
  source.connect(audioContext.destination);alertSource=source;this.paused=false;
  source.onended=()=>{source.disconnect();if(alertSource===source){alertSource=null;this.paused=true;}};
  try{source.start();}catch(error){this.pause();throw error;}
 }
};
function audioInterrupted(){
 if(enabled&&audioContext.state!=='running'){
  enabled=false;audio.pause();$('sound').textContent='Enable sounds';
  setNotice('Audio paused by browser. Tap Enable sounds to resume alerts.');tick();
 }
}
const colors={PRINTING:'#57d69a',PAUSED:'#ffbf69',FINISHED:'#70baff',IDLE:'#9baebf',READY:'#9baebf',ERROR:'#ff6b78',ATTENTION:'#ffbf69',STOPPED:'#ff6b78'};
function duration(n){if(n===null)return '—';n=Math.max(0,Math.ceil(n));return `${Math.floor(n/3600)}:${String(Math.floor(n/60)%60).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;}
function tick(){
 const now=new Date();$('clock').textContent=now.toLocaleTimeString([], {hour:'numeric',minute:'2-digit',second:'2-digit'});
 $('clock').setAttribute('datetime',now.toISOString());
 if(!data)return;
 const age=(Date.now()-received)/1000, stale=age>Math.max(10,data.refresh*2), connected=data.connected&&!stale;
 $('connection').textContent=connected?'● Connected':'● Disconnected • data may be stale';
 $('connection').style.color=connected?'#57d69a':'#ffbf69';
 $('state').textContent=data.state;document.body.style.setProperty('--accent',colors[data.state]||'#ffbf69');
 const elapsed=connected&&data.state==='PRINTING'?Math.max(0,data.server_time-data.updated+age):0;
 const remaining=data.remaining===null?null:Math.max(0,data.remaining-elapsed);
 $('remaining').textContent=duration(remaining);
 $('finish').textContent=connected&&data.state==='PRINTING'&&remaining!==null?new Date(Date.now()+remaining*1000).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'}):'—';
 $('filament').textContent=data.filament>0?duration(Math.max(0,data.filament-elapsed)):'—';
 $('filament-note').textContent=data.filament>0?(elapsed>=data.filament?'Change due • awaiting printer update':'Until the next change'):'No change scheduled / not reported';
 $('freshness').textContent=data.updated?`Last updated ${new Date(data.updated*1000).toLocaleTimeString()}${connected?'':' • showing last known status'}`:'No successful printer update yet';
 $('ack').disabled=!pending;
 $('ack').hidden=!pending;
 $('ack-row').hidden=!pending;
 $('mute').hidden=!enabled||!data.alert;
 $('sound').hidden=enabled;
 if(pending&&enabled&&!muted&&data.alert&&Date.now()-lastPlayed>=data.repeat*1000&&audio.paused){lastPlayed=Date.now();audio.currentTime=0;audio.play().catch(()=>{enabled=false;audio.pause();$('sound').textContent='Enable sounds';setNotice('Sound blocked. Click Enable sounds to retry.');});}
}
function settingsNotice(){
 if(!data.alert&&!data.camera)return 'Alerts and Camera are disabled in container settings';
 if(!data.alert)return 'Alerts are disabled in container settings';
 if(!data.camera)return 'Camera is disabled in container settings';
 return '';
}
function updateNotice(){
 if(data.alert&&enabled&&muted){setNotice('Sounds muted • Unmute to allow alerts to play');return;}
 const settings=settingsNotice();
 const status=data.alert?(pending?'State changed • acknowledge to stop repeating':enabled?'Sounds ready • no unacknowledged changes':'Click Enable sounds to allow browser audio'):'';
 setNotice(settings||status,!settings&&data.alert&&enabled&&!muted&&!pending);
}
function setNotice(message,ready=false){
 $('notice').textContent=message;
 $('notice').style.color=ready?'#57d69a':'#ffb258';
}
async function poll(){try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error();const next=await r.json();if(event!==null&&next.event!==event){pending=true;lastPlayed=0;}event=next.event;data=next;received=Date.now();updateNotice();$('version').textContent=`v${data.version}`;$('sound').disabled=!data.alert;$('mute').disabled=!data.alert;$('camera-toggle').disabled=!data.camera;tick();if(cameraOn)await cameraStatus();}catch{if(data)data.connected=false;$('connection').textContent='● Dashboard connection lost';}finally{setTimeout(poll,2000);}}
$('sound').onclick=async()=>{
 $('sound').disabled=true;
 try{
  if(!audioContext||audioContext.state==='closed'){
   const Context=globalThis.AudioContext||globalThis.webkitAudioContext;
   if(!Context)throw Error('Web Audio unavailable');
   audioContext=new Context();
   audioContext.addEventListener('statechange',audioInterrupted);
  }
  // Unlock with true silence during the tap, never by playing the alarm.
  const resumed=audioContext.resume();
  const silence=audioContext.createBufferSource();
  silence.buffer=audioContext.createBuffer(1,1,audioContext.sampleRate);
  silence.connect(audioContext.destination);silence.onended=()=>silence.disconnect();silence.start();
  await resumed;
  if(audioContext.state!=='running')throw Error('Audio remains suspended');
  if(!alertBuffer){
   const response=await fetch('/alert',{cache:'no-store'});
   if(!response.ok)throw Error('Cannot load alert');
   alertBuffer=await audioContext.decodeAudioData(await response.arrayBuffer());
  }
  if(audioContext.state!=='running')throw Error('Audio was interrupted while loading');
  enabled=true;lastPlayed=0;$('sound').textContent='Sounds enabled';updateNotice();tick();
 }catch{
  enabled=false;audio.pause();$('sound').textContent='Enable sounds';
  setNotice('Unable to enable audio. Tap Enable sounds again; check the sound file if this persists.');tick();
 }finally{$('sound').disabled=!data?.alert;}
};
$('mute').onclick=()=>{muted=!muted;audio.pause();$('mute').textContent=muted?'Unmute':'Mute';$('mute').setAttribute('aria-pressed',muted);updateNotice();tick();};
$('ack').onclick=()=>{pending=false;audio.pause();audio.currentTime=0;updateNotice();tick();};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{setNotice('Full screen unavailable in this browser');}};
$('camera-toggle').onclick=()=>{cameraOn=!cameraOn;$('camera-panel').hidden=!cameraOn;$('camera-toggle').textContent=cameraOn?'Camera Enabled':'Enable Camera';if(cameraOn){$('camera-status').textContent='Connecting camera…';cameraViewer++;$('camera').src=`/camera?viewer=${cameraViewer}`;}else{setCameraFocus(false);$('camera').removeAttribute('src');}};
function setCameraFocus(focused){
 focused=focused&&cameraOn;
 document.body.dataset.cameraFocus=String(focused);
 $('camera-back').hidden=!focused;
 $('camera').setAttribute('aria-expanded',String(focused));
 $('camera').setAttribute('aria-label',focused?'Return to printer status view':'Expand camera view');
}
$('camera').ondblclick=()=>setCameraFocus(document.body.dataset.cameraFocus!=='true');
$('camera').onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('camera').ondblclick();}};
$('camera-back').onclick=()=>setCameraFocus(false);
document.addEventListener?.('keydown',event=>{if(event.key==='Escape')setCameraFocus(false);});
async function cameraStatus(){
 const viewer=cameraViewer;
 try{
  const response=await fetch(`/api/camera/status?viewer=${viewer}`,{cache:'no-store'});
  if(!response.ok)throw Error();
  const status=await response.json();
  if(cameraOn&&viewer===cameraViewer)$('camera-status').textContent=status.message;
 }catch{if(cameraOn&&viewer===cameraViewer)$('camera-status').textContent='Cannot read camera status. Check UNRAID container logs.';}
}
$('camera').onload=()=>{$('camera-status').textContent='Live camera';};$('camera').onerror=()=>{$('camera-status').textContent='Camera unavailable. Check CAMERA_URL, then toggle to retry.';};
const mobileDevice=typeof navigator!=='undefined'&&(
 navigator.userAgentData?.mobile===true||/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent||'')||
 (navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1));
let initialLayout='desktop';
try{initialLayout=localStorage.getItem('layout')||'desktop';}catch{}
$('layout').value=mobileDevice?'mobile':initialLayout;
$('fullscreen').hidden=mobileDevice;
function layout(){document.body.dataset.layout=$('layout').value;try{localStorage.setItem('layout',$('layout').value);}catch{}}
$('layout').onchange=layout;layout();setInterval(tick,1000);poll();
