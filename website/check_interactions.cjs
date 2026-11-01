// Exercise the generated production JS and exact authority-exported values.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=process.argv[2]||path.join(__dirname,'site');
const html=fs.readFileSync(path.join(root,'findings.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const DATA=JSON.parse(fs.readFileSync(path.join(root,'findings-data.json'),'utf8'));
class Element{constructor(){this.children=[];this.style={};this.value='';this.textContent='';this.innerHTML='';this.disabled=false;}replaceChildren(...c){this.children=c;if(c.length&&'value' in c[0])this.value=c[0].value;}append(...c){this.children.push(...c);}addEventListener(){}closest(){return table;}querySelector(){return head;}}
const table=new Element(),head=new Element(),muted=[new Element(),new Element()];
const elements={units:new Element()};elements.units.value='total';
const context=vm.createContext({document:{getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element(),querySelectorAll:selector=>selector.includes('not(#source)')?muted:[...muted,elements.source??=new Element()]}});vm.runInContext(script,context);
let cases=0,simulationCases=0;
for(let i=0;i<DATA.studies.length;i++){
 elements.study.value=String(i);vm.runInContext('selectStudy()',context);const s=DATA.studies[i];
 for(const c of Object.keys(s.comparisons))for(const m of s.metrics)for(const unit of ['total','per']){
  elements.comparison.value=c;elements.metric.value=m;elements.units.value=unit;vm.runInContext('render()',context);
  if(s.kind==='simulation'){
   const expected=s.summary.filter(r=>r.model+'_'+r.gate===c);assert.equal(expected.length,4);assert.equal(elements.rows.children.length,4);assert.equal(elements.units.disabled,true);assert.equal(elements.units.value,'total');assert.equal(elements.chart.children.length,0);assert.notEqual(elements.source.hidden,true,'simulation provenance must stay visible');assert(!elements.number.textContent.includes('Pooled'));
   for(let j=0;j<4;j++){const r=expected[j],values=elements.rows.children[j].children.map(x=>x.textContent);assert.equal(r.n,20);assert.deepEqual(values,[s.regime_names[r.regime],20,r.mean_gain.toFixed(4),r.mean_standard_error.toFixed(4),r.median_gain.toFixed(4),r.wins+' / 20','['+r.win_wilson95.map(x=>x.toFixed(3)).join(', ')+']',r.off_floor]);}simulationCases++;
  }else{
   assert.equal(elements.units.disabled,false);assert.equal(elements.rows.children.length,s.windows.length+1);const n=s.windows.reduce((a,w)=>a+w.n,0),sum=s.windows.reduce((a,w)=>a+w.values[c][m],0),v=unit==='per'?sum/n:sum;assert.equal(elements.rows.children.at(-1).children[2].textContent,(v>0?'+':'')+v.toFixed(unit==='per'?4:3));
  }
  assert(!elements.number.textContent.includes('NaN'));cases++;
 }
}
const observed=DATA.studies.find(s=>s.name.includes('(S04)'));assert(observed);assert.deepEqual(observed.metrics,['joint']);assert.equal(Object.keys(observed.comparisons).length,5);assert.equal(observed.windows.reduce((a,w)=>a+w.n,0),315);
const simulation=DATA.studies.filter(s=>s.kind==='simulation');assert.equal(simulation.length,1);assert.equal(simulation[0].summary.length,20);assert.equal(simulationCases,10);
// Switching back must restore denominator semantics and unit controls.
elements.study.value='0';vm.runInContext('selectStudy()',context);assert.equal(elements.units.disabled,false);
console.log(JSON.stringify({passed:true,selector_combinations:cases,simulation_selector_cases:simulationCases,simulation_summary_rows:20,independent_histories_per_row:20,no_simulation_pooling:true,no_simulation_target_conversion:true,observed_S04_targets:315}));
