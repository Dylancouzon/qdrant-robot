// Exercise the shipped monitor DOM with isolated responses and no browser or Jetson.
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('node:fs');const assert=require('node:assert/strict');
const page=fs.readFileSync(require('node:path').join(__dirname,'../talk.html'),'utf8');
const objects=[{id:'one',owner:'visitor-001',owner_label:'Sam',label:"Sam's mouse",sightings:2,last_seen:10,views:Array.from({length:7},(_,i)=>({id:'view-'+i,time:10,source:'taught'}))},{id:'two',owner:'visitor-002',owner_label:'Sam',label:"Sam's bottle",sightings:1,last_seen:20,views:[{id:'second-view',time:20,source:'taught'}]}];
let list=structuredClone(objects),available=true,accepted=true,posts=[],live=null,delayedRead=null,reducedMotion=false,intervals=[];
const console=new VirtualConsole();const errors=[];console.on('jsdomError',e=>errors.push(String(e)));console.forwardTo(global.console);
const dom=new JSDOM(page,{url:'http://127.0.0.1:8765',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){
  w.HTMLElement.prototype.scrollIntoView=()=>{};w.matchMedia=()=>({matches:reducedMotion});w.confirm=()=>true;w.scrollTo=()=>{};
  w.setInterval=fn=>{intervals.push(fn);return 0;};w.setTimeout=()=>0;
  w.fetch=async(url,options)=>{
    if(url==='/status')return {ok:true,json:async()=>({phase:live?'Listening':'Idle',active:!!live,error:'',view_ready:!!live})};
    if(url==='/memory')return {ok:available,json:async()=>delayedRead?await delayedRead:structuredClone(list)};
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
 assert.equal(d.querySelectorAll('.sourcecard').length,3);assert.equal(d.querySelectorAll('#memoryMap .node').length,2);assert.match(d.querySelector('#memoryMap').getAttribute('aria-label'),/2 collections searched, 2 retrieval entries/);assert.equal(d.querySelector('#textLatency').textContent,'1.20s');assert.match(d.querySelector('#retrievalContent').textContent,/includes work beyond Edge queries/);assert.equal(d.querySelector('#evidence script'),null);
 const map=d.querySelector('#memoryMap svg');run(`evidence({knowledge:['A source <script>'],statements:['My mouse is blue'],memories:[{label:"Sam's mouse",object:'one',view:'view-0',source:'Observed object',text:'On the desk',time:10}],memory_ids:['point-1'],timing:{first_text_ms:1200,speech_ready_ms:1900}},{shards:['knowledge','seen'],hits:[['knowledge: a source',.82],['seen: a mouse',null]],ms:13.2})`);assert.equal(d.querySelector('#memoryMap svg'),map);
 d.querySelector('#memorySearch').value='bottle';d.querySelector('#memorySearch').dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('.objectcard').length,1);
 d.querySelector('#evidence .textlink').click();await tick();assert.equal(d.querySelector('#memorySearch').value,'');assert.equal(d.querySelectorAll('.objectcard').length,2);
 await run("openTab('live')");intervals[0]();assert.equal(d.querySelector('#tipText').textContent,'Hey Edgy, this is my phone.');
 d.querySelector('#commandTip').focus();intervals[0]();assert.equal(d.querySelector('#tipText').textContent,'Hey Edgy, this is my phone.');d.activeElement.blur();
 reducedMotion=true;intervals[0]();assert.equal(d.querySelector('#tipText').textContent,'Hey Edgy, this is my phone.');reducedMotion=false;
 // Exercise confirmed voice deletion through status polling, including a stale in-flight read.
 await run("openTab('live')");let releaseRead;delayedRead=new Promise(resolve=>{releaseRead=resolve});const staleRead=run('loadMemory()');await tick();
 live={status:'Listening',transcript:[{id:'deleted',question:'Yes',answer:'Done.'}],evidence:{deleted:true,turn_id:'deletion-1'},memory:null};
 await run('status()');releaseRead(structuredClone(list));await staleRead;delayedRead=null;
 assert.equal(d.querySelectorAll('.objectcard').length,0);assert.equal(run('savedObjects.length'),0);assert.equal(d.querySelectorAll('#evidence img').length,0);assert.equal(d.querySelector('#retrievalContent').textContent,'');assert.equal(d.querySelector('#memoryMap').dataset.search,'null');assert.equal(d.querySelector('#transcript').textContent.includes('clock'),false);
 assert.equal(run('carouselUpdates.length'),0);await run("openTab('memory')");assert.equal(d.querySelectorAll('.objectcard').length,2);
 live.evidence={deleted:true,turn_id:'deletion-2'};await run('status()');assert.equal(d.querySelectorAll('.objectcard').length,0);assert.equal(run('carouselUpdates.length'),0);
 run('clearLive()');assert.equal(d.querySelector('#speechLatency').textContent,'—');assert.equal(d.querySelectorAll('#memoryMap .node').length,0);assert.equal(errors.length,0,errors.join('\n'));
 global.console.log('PASS: two visitor IDs with the same name, queued edits, failed refresh, repeated removal, view retention, conflicts, evidence safety, timing, stable map, search, tips, confirmed voice deletion, stale-read rejection, and clearing.');dom.window.close();
})().catch(e=>{global.console.error(e);dom.window.close();process.exitCode=1;});
