const $ = id => document.getElementById(id);
let data, received=0, event=null, pending=false, enabled=false, muted=false, lastPlayed=0, cameraOn=false;
const audio = new Audio('/alert');
audio.preload = 'none';
audio.addEventListener('error',()=>{if(data?.alert)$('notice').textContent='Cannot play alert file. Check its format and mount.';});
const colors={PRINTING:'#57d69a',PAUSED:'#ffbf69',FINISHED:'#70baff',IDLE:'#9baebf',READY:'#9baebf',ERROR:'#ff6b78',ATTENTION:'#ffbf69',STOPPED:'#ff6b78'};
function duration(n){if(n===null)return '—';n=Math.max(0,Math.ceil(n));return `${Math.floor(n/3600)}:${String(Math.floor(n/60)%60).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;}
function tick(){
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
 if(pending&&enabled&&!muted&&data.alert&&Date.now()-lastPlayed>=data.repeat*1000&&audio.paused){lastPlayed=Date.now();audio.currentTime=0;audio.play().catch(()=>{$('notice').textContent='Sound blocked. Click Enable sounds to retry.';enabled=false;});}
}
async function poll(){try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error();const next=await r.json();if(event!==null&&next.event!==event){pending=true;lastPlayed=0;}event=next.event;data=next;received=Date.now();$('notice').textContent=!data.alert?'Alerts disabled in container settings':pending?'State changed • acknowledge to stop repeating':enabled?'Sounds ready • no unacknowledged changes':'Click Enable sounds to allow browser audio';$('sound').disabled=!data.alert;$('mute').disabled=!data.alert;$('camera-toggle').disabled=!data.camera;tick();}catch{if(data)data.connected=false;$('connection').textContent='● Dashboard connection lost';}finally{setTimeout(poll,2000);}}
$('sound').onclick=async()=>{try{audio.muted=true;await audio.play();audio.pause();audio.currentTime=0;audio.muted=false;enabled=true;lastPlayed=0;$('sound').textContent='Sounds enabled';tick();}catch{audio.muted=false;$('notice').textContent='Unable to enable audio. Check the sound file.';}};
$('mute').onclick=()=>{muted=!muted;audio.pause();$('mute').textContent=muted?'Unmute':'Mute';$('mute').setAttribute('aria-pressed',muted);};
$('ack').onclick=()=>{pending=false;audio.pause();audio.currentTime=0;$('notice').textContent='Acknowledged';tick();};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{$('notice').textContent='Full screen unavailable in this browser';}};
$('camera-toggle').onclick=()=>{cameraOn=!cameraOn;$('camera-panel').hidden=!cameraOn;$('camera-toggle').textContent=cameraOn?'Camera on':'Camera off';if(cameraOn){$('camera-status').textContent='Connecting camera…';$('camera').src='/camera';}else $('camera').removeAttribute('src');};
$('camera').onload=()=>{$('camera-status').textContent='Live camera';};$('camera').onerror=()=>{$('camera-status').textContent='Camera unavailable. Check CAMERA_URL, then toggle to retry.';};
try{$('layout').value=localStorage.getItem('layout')||'desktop';}catch{}
function layout(){document.body.dataset.layout=$('layout').value;try{localStorage.setItem('layout',$('layout').value);}catch{}}
$('layout').onchange=layout;layout();setInterval(tick,1000);poll();
