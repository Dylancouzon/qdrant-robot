// Exercise the shipped monitor DOM with isolated responses and no browser or Jetson.
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('node:fs');const assert=require('node:assert/strict');
const page=fs.readFileSync(require('node:path').join(__dirname,'../talk.html'),'utf8');
const objects=[{id:'one',owner:'visitor-001',owner_label:'Sam',label:"Sam's mouse",sightings:2,last_seen:10,views:Array.from({length:7},(_,i)=>({id:'view-'+i,time:10,source:'taught'}))},{id:'two',owner:'visitor-002',owner_label:'Sam',label:"Sam's bottle",sightings:1,last_seen:20,views:[{id:'second-view',time:20,source:'taught'}]}];
let list=structuredClone(objects),available=true,accepted=true,posts=[],live=null,delayedRead=null,delayedMap=null,mapData={session:'a',at:100,total:0,nodes:[],recall:{turn:'',ids:[]}},reducedMotion=false,intervals=[];
const console=new VirtualConsole();const errors=[];console.on('jsdomError',e=>errors.push(String(e)));console.forwardTo(global.console);
const dom=new JSDOM(page,{url:'http://127.0.0.1:8765',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){
  w.HTMLElement.prototype.scrollIntoView=()=>{};w.matchMedia=()=>({matches:reducedMotion});w.confirm=()=>true;w.scrollTo=()=>{};
  w.setInterval=fn=>{intervals.push(fn);return 0;};w.setTimeout=()=>0;
  w.fetch=async(url,options)=>{
    if(url==='/status')return {ok:true,json:async()=>({phase:live?'Listening':'Idle',active:!!live,error:'',view_ready:!!live})};
    if(url==='/memory')return {ok:available,json:async()=>delayedRead?await delayedRead:structuredClone(list)};
    if(url==='/memory_map')return {ok:true,json:async()=>delayedMap?await delayedMap:structuredClone(mapData)};
    if(url==='/robot')return {ok:true,json:async()=>live};
    posts.push([url,JSON.parse(options.body)]);return {ok:accepted,status:accepted?202:409};
  };
  Object.defineProperty(w.HTMLElement.prototype,'offsetWidth',{get(){return this.className==='savedview'?100:400;}});
  Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 324;}});
  Object.defineProperty(w.HTMLElement.prototype,'scrollWidth',{get(){return this.className==='views'?this.children.length*112-12:324;}});
}});
const w=dom.window,d=w.document,run=s=>w.eval(s),tick=()=>new Promise(r=>setTimeout(r,30));
(async()=>{
 await run("openTab('memory')");await tick();
 assert.equal(d.querySelectorAll('.owner').length,2);assert.equal(d.querySelectorAll('.objectcard').length,2);
 assert.match(d.querySelector('#memoryStats').textContent,/2 objects8 saved views2 visitors/);
 const first=d.querySelector('#memory-one');first.querySelector('details').open=true;first.querySelector('.views').scrollLeft=224;first.querySelector('[data-edit]').focus();
 await run("memoryEdit('remove_view',{object:'one',view:'view-2'},'Remove view')");
 assert.equal(d.activeElement.dataset.focusKey,'manage-one');
 assert.match(d.querySelector('#memoryNotice').textContent,/Applying 1 memory edit/);assert.equal(d.querySelector('#memory-one [data-edit]').disabled,true);
 for(let i=0;i<12;i++)await run('loadMemory()');
 assert.equal(run('pendingEdits.size'),1);run('pendingEdits.get("one").started=Date.now()-9000');await run('loadMemory()');assert.match(d.querySelector('#memoryNotice').textContent,/Still waiting/);
 // A refresh failure must leave the pending deletion visible and retain cards.
 available=false;await run('loadMemory()');assert.match(d.querySelector('#memoryError').textContent,/Memory unavailable/);assert.match(d.querySelector('#memoryNotice').textContent,/Still waiting/);assert.equal(d.querySelectorAll('.objectcard').length,2);
 available=true;list[0].views=list[0].views.filter(v=>v.id!=='view-2');await run('loadMemory()');await tick();
 assert.match(d.querySelector('#memoryNotice').textContent,/Remove view completed/);assert.equal(d.querySelector('#memory-one details').open,true);assert.equal(d.querySelector('#memory-one .views').scrollLeft,224);
 // A second removal keeps the same position and existing manage panel.
 await run("memoryEdit('remove_view',{object:'one',view:'view-3'},'Remove next view')");list[0].views=list[0].views.filter(v=>v.id!=='view-3');await run('loadMemory()');await tick();assert.equal(d.querySelector('#memory-one .views').scrollLeft,224);assert.equal(d.querySelector('#memory-one details').open,true);
 await run("openTab('live')");list[0].last_seen++;await run('loadMemory()');assert.equal(d.querySelector('#memory-one .views'),null);await run("openTab('memory')");await tick();assert.equal(d.querySelector('#memory-one .views').scrollLeft,224);
 accepted=false;await run("memoryEdit('forget_object',{object:'one'},'Forget mouse')");assert.match(d.querySelector('#memoryError').textContent,/changed/);assert.equal(d.querySelector('#memory-one [data-edit]').disabled,false);
 run(`evidence({knowledge:['A source <script>'],statements:['My mouse is blue'],memories:[{label:"Sam's mouse",object:'one',view:'view-0',source:'Observed object',text:'On the desk',time:10}],memory_ids:['point-1'],timing:{first_text_ms:1200,speech_ready_ms:1800}},{shards:['knowledge','seen'],hits:[['knowledge: a source',.82],['seen: a mouse',null]],ms:13.2})`);
 assert.equal(d.querySelectorAll('.sourcecard').length,3);assert.equal(d.querySelector('#textLatency').textContent,'1.20s');assert.match(d.querySelector('#retrievalContent').textContent,/includes work beyond Edge queries/);assert.equal(d.querySelector('#evidence script'),null);
 const map=d.querySelector('#memoryMap svg');run(`evidence({knowledge:['A source <script>'],statements:['My mouse is blue'],memories:[{label:"Sam's mouse",object:'one',view:'view-0',source:'Observed object',text:'On the desk',time:10}],memory_ids:['point-1'],timing:{first_text_ms:1200,speech_ready_ms:1900}},{shards:['knowledge','seen'],hits:[['knowledge: a source',.82],['seen: a mouse',null]],ms:13.2})`);assert.equal(d.querySelector('#memoryMap svg'),map);
 // The map keeps real point identities across timing updates, samples, and recalls.
 const point={id:'seen:one',kind:'said',label:'My mouse is blue',created:90,object:'things:one'};
 const hub={id:'things:one',kind:'object',label:'mouse',created:80};
 const snapshot={session:'a',at:100,total:2,nodes:[point,hub],recall:{turn:'',ids:[]}};
 run('showMap('+JSON.stringify(snapshot)+')');
 const dot=d.querySelector('[data-id="seen:one"]'),position=dot.getAttribute('transform');
 assert.equal(d.querySelectorAll('.memorypoint.new').length,0);assert.equal(d.querySelectorAll('#mapSvg line').length,1);
 assert.match(d.querySelector('#mapCount').textContent,/2 memories/);assert.match(d.querySelector('#memoryMap').getAttribute('aria-label'),/Positions are schematic/);
 dot.focus();assert.equal(d.querySelector('#mapDetail').hidden,false);assert.equal(d.querySelector('#mapDetail').textContent,point.label);dot.blur();
 const fresh={id:'seen:new',kind:'observed',label:'Clock',created:101};
 const next={...snapshot,at:102,total:3,nodes:[point,hub,fresh],recall:{turn:'t1',ids:[point.id,hub.id]}};
 run('showMap('+JSON.stringify(next)+')');assert.equal(d.querySelector('[data-id="seen:one"]'),dot);assert.equal(dot.getAttribute('transform'),position);
 assert.equal(d.querySelector('[data-id="seen:new"]').classList.contains('new'),true);assert.equal(dot.classList.contains('recalled'),true);
 dot.classList.remove('recalled');run('showMap('+JSON.stringify({...next,at:104})+')');assert.equal(dot.classList.contains('recalled'),false,'the same turn does not restart a pulse');
 run('showMap('+JSON.stringify({...next,at:106,recall:{turn:'t2',ids:[point.id]}})+')');assert.equal(dot.classList.contains('recalled'),true,'a new turn recalls the same point');
 const captioned={...point,kind:'observed',label:'Main object: a blue mouse'};
 run('showMap('+JSON.stringify({...next,at:107,nodes:[captioned,hub,fresh]})+')');assert.equal(dot.dataset.kind,'observed');assert.equal(dot.getAttribute('aria-label'),captioned.label);assert.equal(dot.getAttribute('transform'),position);
 const hubPosition=d.querySelector('[data-id="things:one"]').getAttribute('transform');
 run('showMap('+JSON.stringify({...next,at:107.1,nodes:[fresh]})+')');run('showMap('+JSON.stringify({...next,at:107.2})+')');assert.equal(d.querySelector('[data-id="things:one"]').getAttribute('transform'),hubPosition,'sample reentry keeps object position');
 const old={id:'seen:old',kind:'said',label:'Earlier evidence',created:1};
 run('showMap('+JSON.stringify({...next,at:108,total:400,nodes:[hub,old],recall:{turn:'t3',ids:[old.id]}})+')');
 assert.equal(d.querySelector('[data-id="seen:one"]'),null);assert.equal(d.querySelector('[data-id="seen:old"]').classList.contains('new'),false,'sample turnover is not a birth');assert.equal(d.querySelector('#mapDetail').textContent,'');assert.equal(d.querySelector('#mapCount').textContent,'2 / 400');
 run('showMap('+JSON.stringify({...next,session:'restarted',at:109})+')');assert.equal(d.querySelectorAll('.memorypoint.new').length,0,'reconnect loads stored points without births');
 // A deletion invalidates a map response that started before it completed.
 await run("openTab('live')");run('mapLastRead=0');let releaseMap;delayedMap=new Promise(resolve=>{releaseMap=resolve});const staleMap=run('loadMap()');await tick();run('resetMap()');releaseMap(next);await staleMap;delayedMap=null;assert.equal(d.querySelectorAll('.memorypoint').length,0);
 mapData=next;run('mapLastRead=0');await run('loadMap()');assert.equal(d.querySelectorAll('.memorypoint').length,3);
 d.querySelector('[data-id="things:one"]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await tick();assert.equal(d.querySelector('#memoryPanel').hidden,false);await run("openTab('live')");
 d.querySelector('#memorySearch').value='bottle';d.querySelector('#memorySearch').dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('.objectcard').length,1);
 d.querySelector('#evidence .textlink').click();await tick();assert.equal(d.querySelector('#memorySearch').value,'');assert.equal(d.querySelectorAll('.objectcard').length,2);
 await run("openTab('live')");intervals[0]();assert.equal(d.querySelector('#tipText').textContent,'Hey Edgy, this is my phone.');assert.match(d.querySelector('.tipBubble').textContent,/Say/);
 d.querySelector('#commandTip').focus();intervals[0]();assert.equal(d.querySelector('#tipText').textContent,'Hey Edgy, this is my phone.');assert.match(d.querySelector('.tipBubble').textContent,/Say/);d.activeElement.blur();
 reducedMotion=true;intervals[0]();assert.equal(d.querySelector('#tipText').textContent,'Hey Edgy, this is my phone.');assert.match(d.querySelector('.tipBubble').textContent,/Say/);reducedMotion=false;
 // Exercise confirmed voice deletion through status polling, including a stale in-flight read.
 await run("openTab('live')");let releaseRead;delayedRead=new Promise(resolve=>{releaseRead=resolve});const staleRead=run('loadMemory()');await tick();
 mapData={session:'a',at:110,total:0,nodes:[],recall:{turn:'',ids:[]}};live={status:'Listening',transcript:[{id:'deleted',question:'Yes',answer:'Done.'}],evidence:{deleted:true,turn_id:'deletion-1'},memory:null};
 await run('status()');releaseRead(structuredClone(list));await staleRead;delayedRead=null;
 assert.equal(d.querySelectorAll('.objectcard').length,0);assert.equal(run('savedObjects.length'),0);assert.equal(d.querySelectorAll('#evidence img').length,0);assert.equal(d.querySelector('#retrievalContent').textContent,'');assert.equal(d.querySelectorAll('#memoryMap .memorypoint').length,0);assert.equal(d.querySelector('#transcript').textContent.includes('clock'),false);
 assert.equal(run('carouselUpdates.length'),0);await run("openTab('memory')");assert.equal(d.querySelectorAll('.objectcard').length,2);
 live.evidence={deleted:true,turn_id:'deletion-2'};await run('status()');assert.equal(d.querySelectorAll('.objectcard').length,0);assert.equal(run('carouselUpdates.length'),0);
 // Cooling is a head warning; camera, microphone, and the normal session remain usable.
 live.control={head:{enabled:true,warning:'Head motor cooling. 180 seconds minimum. I can still see and talk.'}};
 await run('status()');assert.match(d.querySelector('#headWarning').textContent,/180 seconds minimum/);
 assert.equal(d.querySelector('#phase').textContent,'Listening');assert.equal(d.querySelector('#camera').hidden,false);assert.equal(d.querySelector('#mute').disabled,false);assert.equal(d.querySelector('#headStop').disabled,false);
 live.control.head.warning='Head motor cooling. Waiting for safe temperature. I can still see and talk.';
 await run('status()');assert.match(d.querySelector('#headWarning').textContent,/Waiting for safe temperature/);
 live.control.head.warning='';await run('status()');assert.equal(d.querySelector('#headWarning').textContent,'');
 live.control.head.warning='Head motor cooling.';await run('status()');
 run('clearLive()');assert.equal(d.querySelector('#headWarning').textContent,'');assert.equal(d.querySelector('#speechLatency').textContent,'—');assert.equal(d.querySelectorAll('#memoryMap .memorypoint').length,0);assert.equal(errors.length,0,errors.join('\n'));
 global.console.log('PASS: two visitor IDs with the same name, queued edits, failed refresh, repeated removal, view retention, conflicts, evidence safety, timing, stable stored memory IDs, births, sample turnover, recall pulses, map deletion races, search, tips, confirmed voice deletion, stale-read rejection, and clearing.');dom.window.close();
})().catch(e=>{global.console.error(e);dom.window.close();process.exitCode=1;});
