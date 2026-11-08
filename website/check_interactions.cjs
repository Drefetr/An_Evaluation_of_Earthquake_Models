// Exercise the generated production JS and exact authority-exported values.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=process.argv[2]||path.join(__dirname,'site');
const html=fs.readFileSync(path.join(root,'findings.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const DATA=JSON.parse(fs.readFileSync(path.join(root,'findings-data.json'),'utf8'));
const joint=DATA.studies.filter(s=>s.kind==='joint_simulation');
const dispositions=DATA.studies.filter(s=>s.kind==='joint_disposition_simulation');
assert(!(joint.length&&dispositions.length),'The same joint campaign cannot activate success and disposition views together');
// The installed legacy site deliberately has no joint data or panel. Once data
// exist, require real HTML nodes; the lightweight DOM stub must not invent them.
if(joint.length||dispositions.length){
 const markup=html.slice(0,html.indexOf('<script>')).replace(/<!--[\s\S]*?-->/g,'');
 const ids=[];
 // Tokenize attributes, including quoted values, so data-id and an id-looking
 // string inside another attribute cannot impersonate the actual id attribute.
 const tags=markup.match(/<[A-Za-z][^"'<>]*(?:(?:"[^"]*"|'[^']*')[^"'<>]*)*>/g)||[];
 for(const tag of tags){
  const attributes=tag.replace(/^<[A-Za-z][^\s/>]*/,'');
  const attribute=/\s+([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  for(const match of attributes.matchAll(attribute)){
   if(match[1].toLowerCase()==='id')ids.push(match[2]??match[3]??match[4]??'');
  }
 }
 for(const id of joint.length?['joint-diagnostics','joint-search-rows','joint-floor-rows']:[]){
  assert.equal(ids.filter(value=>value===id).length,1,'Joint dataset requires one actual panel node: '+id);
 }
 for(const id of dispositions.length?['joint-disposition-diagnostics','joint-disposition-census','joint-disposition-search-rows','joint-disposition-floor-rows']:[]){
  assert.equal(ids.filter(value=>value===id).length,1,'Disposition dataset requires one actual panel node: '+id);
 }
}
class Element{constructor(){this.children=[];this.style={};this.value='';this.textContent='';this.innerHTML='';this.disabled=false;}replaceChildren(...c){this.children=c;if(c.length&&'value' in c[0])this.value=c[0].value;}append(...c){this.children.push(...c);}addEventListener(){}closest(){return table;}querySelector(){return head;}}
const table=new Element(),head=new Element(),muted=[new Element(),new Element()];
const elements={units:new Element()};elements.units.value='total';
function assertDispositionHidden(){
 if(dispositions.length||elements['joint-disposition-diagnostics'])assert.equal(elements['joint-disposition-diagnostics']?.hidden,true);
}
function assertJointHidden(){
 if(joint.length||elements['joint-diagnostics'])assert.equal(elements['joint-diagnostics']?.hidden,true);
}
const context=vm.createContext({document:{getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element(),querySelectorAll:selector=>selector.includes('not(#source)')?muted:[...muted,elements.source??=new Element()]}});vm.runInContext(script,context);
let cases=0,simulationCases=0,jointCases=0,dispositionCases=0;
for(let i=0;i<DATA.studies.length;i++){
 elements.study.value=String(i);vm.runInContext('selectStudy()',context);const s=DATA.studies[i];
 for(const c of Object.keys(s.comparisons))for(const m of s.metrics)for(const unit of ['total','per']){
  elements.comparison.value=c;elements.metric.value=m;elements.units.value=unit;vm.runInContext('render()',context);
  if(s.kind==='joint_disposition_simulation'){
   const expected=s.summary.filter(r=>r.model+'_'+r.gate===c);assert.equal(expected.length,4);
   assert.equal(elements.rows.children.length,4);assert.equal(elements.units.disabled,true);assert.equal(elements.units.value,'total');assert.equal(elements.chart.children.length,0);
   assertJointHidden();assert.equal(elements['joint-disposition-diagnostics'].hidden,false);assert.equal(elements['refitted-floor'].hidden,true);
   assert.notEqual(elements.source.hidden,true);assert(!elements.number.textContent.includes('Pooled'));
   assert.equal(elements.number.textContent,s.counts.planned_histories+' planned histories: '+s.counts.complete_histories+' computed, '+s.counts.scientific_unknown_histories+' unavailable');
   assert(elements.heading.textContent.endsWith(' minus '+s.comparator.toLowerCase()));
   assert(head.innerHTML.includes('Pointwise Wilson'));assert(!head.innerHTML.includes('MC SE'));
   assert.equal(elements['joint-disposition-search-rows'].children.length,4);assert.equal(elements['joint-disposition-floor-rows'].children.length,4);
   for(let j=0;j<4;j++){
    const r=expected[j],label=s.regime_names[r.regime]+(r.primary?' (primary)':'');assert.equal(r.planned_histories,20);
    assert.equal(r.computed_histories+r.unavailable_histories,20);
    const d=s.display_summary.find(v=>v.regime===r.regime&&v.model===r.model&&v.gate===r.gate);assert(d);
    const got=elements.rows.children[j].children.map(x=>x.textContent);
    if(r.statistics_available){
     assert.equal(r.computed_histories,20);assert.equal(r.unavailable_histories,0);const f=r.full_regime;
     assert.deepEqual(got,[label,20,20,0,d.mean_gain,d.median_gain,f.wins+' / 20','['+d.wilson95.join(', ')+']',f.off_floor]);
     assert.deepEqual(elements['joint-disposition-search-rows'].children[j].children.map(x=>x.textContent),[label,f.coordinate_boundaries.a.lower+' / '+f.coordinate_boundaries.a.upper,f.eta_lower+' / '+f.eta_upper,f.optimizer_failed_attempts,f.null_search_gap_cases,f.coarse_fine_gate_disagreements]);
     assert.deepEqual(elements['joint-disposition-floor-rows'].children[j].children.map(x=>x.textContent),[label,f.floor_returns,f.near_zero,f.positive_near_zero,f.robust_positive,f.robust_negative]);
    }else{
     assert(r.unavailable_histories>0);assert.equal(r.full_regime,null);assert.equal(d.mean_gain,null);assert.equal(d.median_gain,null);assert.equal(d.wilson95,null);
     assert.deepEqual(got,[label,20,r.computed_histories,r.unavailable_histories,...Array(5).fill('Unavailable')]);
     for(const id of ['joint-disposition-search-rows','joint-disposition-floor-rows'])assert.deepEqual(elements[id].children[j].children.map(x=>x.textContent),[label,...Array(5).fill('Unavailable')]);
    }
    for(const value of got)assert(!['null','undefined','NaN'].includes(String(value)));
   }
   assert.equal(elements['joint-disposition-census'].textContent,s.counts.planned_outcomes+' planned procedure outcomes: '+s.counts.computed_outcomes+' computed and '+s.counts.unavailable_outcomes+' unavailable. All planned slots and reasons are retained in the data download.');
   dispositionCases++;
  }else if(s.kind==='joint_simulation'){
   assertDispositionHidden();
   const expected=s.summary.filter(r=>r.model+'_'+r.gate===c);assert.equal(expected.length,4);
   assert.equal(elements.rows.children.length,4);assert.equal(elements.units.disabled,true);assert.equal(elements.units.value,'total');assert.equal(elements.chart.children.length,0);
   assert.equal(elements['joint-diagnostics'].hidden,false);assert.equal(elements['refitted-floor'].hidden,true);
   assert.notEqual(elements.source.hidden,true);assert(!elements.number.textContent.includes('Pooled'));
   assert(elements.heading.textContent.endsWith(' minus '+s.comparator.toLowerCase()));
   assert(head.innerHTML.includes('Pointwise Wilson'));assert(!head.innerHTML.includes('MC SE'));
   assert.equal(elements['joint-search-rows'].children.length,4);assert.equal(elements['joint-floor-rows'].children.length,4);
   for(let j=0;j<4;j++){
    const r=expected[j],label=s.regime_names[r.regime]+(r.primary?' (primary)':'');assert.equal(r.N,20);
    const display=s.display_summary.find(d=>d.regime===r.regime&&d.model===r.model&&d.gate===r.gate);assert(display);
    assert.deepEqual(elements.rows.children[j].children.map(x=>x.textContent),[label,20,display.mean_gain,display.median_gain,r.wins+' / 20','['+display.wilson95.join(', ')+']',r.off_floor]);
    assert.deepEqual(elements['joint-search-rows'].children[j].children.map(x=>x.textContent),[label,r.coordinate_boundaries.a.lower+' / '+r.coordinate_boundaries.a.upper,r.eta_lower+' / '+r.eta_upper,r.optimizer_failed_attempts,r.unknowns,r.null_search_gap_cases,r.coarse_fine_gate_disagreements]);
    assert.deepEqual(elements['joint-floor-rows'].children[j].children.map(x=>x.textContent),[label,r.floor_returns,r.near_zero,r.positive_near_zero,r.robust_positive,r.robust_negative]);
   }
   jointCases++;
  }else if(s.kind==='simulation'){
   assertJointHidden();assertDispositionHidden();
   const expected=s.summary.filter(r=>r.model+'_'+r.gate===c);assert.equal(expected.length,4);assert.equal(elements.rows.children.length,4);assert.equal(elements.units.disabled,true);assert.equal(elements.units.value,'total');assert.equal(elements.chart.children.length,0);assert.notEqual(elements.source.hidden,true,'simulation provenance must stay visible');assert(!elements.number.textContent.includes('Pooled'));
   for(let j=0;j<4;j++){const r=expected[j],values=elements.rows.children[j].children.map(x=>x.textContent);assert.equal(r.n,20);assert.deepEqual(values,[s.regime_names[r.regime],20,r.mean_gain.toFixed(4),r.mean_standard_error.toFixed(4),r.median_gain.toFixed(4),r.wins+' / 20','['+r.win_wilson95.map(x=>x.toFixed(3)).join(', ')+']',r.off_floor]);}
   assert.equal(elements['refitted-floor'].hidden,false);const sensitivity=s.refitted_floor.filter(r=>r.model+'_'+r.gate===c);assert.equal(sensitivity.length,4);assert.equal(elements['floor-rows'].children.length,4);
   for(let j=0;j<4;j++){const r=sensitivity[j];assert.deepEqual(elements['floor-rows'].children[j].children.map(x=>x.textContent),[s.regime_names[r.regime],r.original_mean_gain.toFixed(4),r.mean_gain.toFixed(4),r.wins+' / '+r.N]);}simulationCases++;
  }else{
   assertJointHidden();assertDispositionHidden();
   assert.equal(elements['refitted-floor'].hidden,true);assert.equal(elements.units.disabled,false);assert.equal(elements.rows.children.length,s.windows.length+1);const n=s.windows.reduce((a,w)=>a+w.n,0),sum=s.windows.reduce((a,w)=>a+w.values[c][m],0),v=unit==='per'?sum/n:sum;assert.equal(elements.rows.children.at(-1).children[2].textContent,(v>0?'+':'')+v.toFixed(unit==='per'?4:3));
  }
  assert(!elements.number.textContent.includes('NaN'));cases++;
 }
}
const observed=DATA.studies.find(s=>s.name.includes('(S04)'));assert(observed);assert.deepEqual(observed.metrics,['joint']);assert.equal(Object.keys(observed.comparisons).length,5);assert.equal(observed.windows.reduce((a,w)=>a+w.n,0),315);
const simulation=DATA.studies.filter(s=>s.kind==='simulation');assert.equal(simulation.length,1);assert.equal(simulation[0].summary.length,20);assert.equal(simulationCases,10);
assert(joint.length<=1);assert.equal(jointCases,joint.length*10);
if(joint.length){assert.equal(joint[0].summary.length,20);assert.deepEqual(joint[0].metrics,['joint']);assert.equal(Object.keys(joint[0].comparisons).length,5);}
assert(dispositions.length<=1);assert.equal(dispositionCases,dispositions.length*10);
if(dispositions.length){
 const s=dispositions[0];assert.equal(s.summary.length,20);assert.deepEqual(s.metrics,['joint']);assert.equal(Object.keys(s.comparisons).length,5);
 assert.equal(s.outcomes.length,400);assert.equal(s.counts.planned_outcomes,400);
 assert.equal(s.outcomes.filter(r=>r.availability==='computed').length,s.counts.computed_outcomes);
 assert.equal(s.outcomes.filter(r=>r.availability==='unavailable').length,s.counts.unavailable_outcomes);
 assert.equal(s.counts.computed_outcomes+s.counts.unavailable_outcomes,400);
}
// Switching back must restore denominator semantics and unit controls.
elements.study.value='0';vm.runInContext('selectStudy()',context);assert.equal(elements.units.disabled,false);assertJointHidden();assertDispositionHidden();
// Joint -> original simulation must restore the original fixed/intercept panel too.
elements.study.value=String(DATA.studies.indexOf(simulation[0]));vm.runInContext('selectStudy()',context);assert.equal(elements['refitted-floor'].hidden,false);assertJointHidden();assertDispositionHidden();
console.log(JSON.stringify({passed:true,selector_combinations:cases,simulation_selector_cases:simulationCases,simulation_summary_rows:20,joint_selector_cases:jointCases,joint_summary_rows:joint.length?20:0,disposition_selector_cases:dispositionCases,disposition_summary_rows:dispositions.length?20:0,independent_histories_per_row:20,no_simulation_pooling:true,no_simulation_target_conversion:true,observed_S04_targets:315}));
