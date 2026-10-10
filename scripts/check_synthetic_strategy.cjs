'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');

function check() {
  const sandbox={window:{},Date};vm.createContext(sandbox);
  for(const file of ['synthetic-strategy-data.js','synthetic-strategy-core.js','synthetic-strategy.js','rights.js']) {
    const source=fs.readFileSync(path.join(root,'reviewdesk/static',file),'utf8');
    const parsed=new vm.Script(source,{filename:file});
    if(['synthetic-strategy-data.js','synthetic-strategy-core.js'].includes(file))parsed.runInContext(sandbox);
  }
  const fixture=JSON.parse(fs.readFileSync(path.join(root,'examples/synthetic-strategy.fixture.json'),'utf8'));
  const before=JSON.stringify(fixture), library=sandbox.window.SyntheticStrategyLibrary, core=sandbox.window.SyntheticStrategy;
  const expected={original:['prepare_verify',3,'defer'],counsel_ready:['intervene_now',3,'defer'],clinic_ready:['refer_coordinate',4,'defer'],privacy:['prepare_verify',3,'against']};
  const results=[];
  for(const [scenario,[disposition,count,publicDisposition]] of Object.entries(expected)) {
    const result=core.generate(fixture,scenario,library);
    assert.equal(result.disposition,disposition);assert.equal(result.options.length,count);
    assert.equal(result.options.find(o=>o.id==='public_route').disposition,publicDisposition);
    assert.equal(result.saved,false);assert.equal(result.model_run,false);assert.equal(result.human_review,'pending');
    const contexts=new Set(result.context.claims.map(c=>c.id)),evidence=new Set(result.evidence.claims.map(c=>c.id));
    for(const o of result.options) {
      for(const field of ['support_context_ids','contrary_context_ids','authority_context_ids','timing_context_ids','feasibility_context_ids','harm_context_ids','preferences_context_ids'])assert(o[field].every(id=>contexts.has(id)));
      for(const field of ['support_evidence_ids','contrary_evidence_ids'])assert(o[field].every(id=>evidence.has(id)));
    }
    if(scenario==='counsel_ready')assert.equal(result.options.find(o=>o.id==='public_route').factors.preferences,'unknown');
    if(scenario==='clinic_ready')assert.equal(result.options.find(o=>o.id==='counsel_request').disposition,'prepare_verify');
    results.push(result);
  }
  // Exercise cited Markdown output as well as JSON snapshots.
  const component=fs.readFileSync(path.join(root,'reviewdesk/static/synthetic-strategy.js'),'utf8');
  const constants=component.slice(component.indexOf('const labels='),component.indexOf('let snapshot='));
  const markdown=component.slice(component.indexOf('function markdown()'),component.indexOf("$('#ssp-generate-form')",component.indexOf('function markdown()')));
  for(const snapshot of results){
    const box={snapshot};vm.createContext(box);vm.runInContext(constants+'\n'+markdown+'\nthis.text=markdown();',box);
    assert(box.text.includes('Competing case evidence'));assert(box.text.includes('Capacity:'));assert(box.text.includes('human review pending'));
    for(const option of snapshot.options)for(const id of [...option.support_evidence_ids,...option.contrary_evidence_ids])assert(box.text.includes(snapshot.evidence.claims.find(c=>c.id===id).excerpt));
    for(const claim of snapshot.alternative_updates)assert(box.text.includes(claim.text));
  }
  assert.equal(JSON.stringify(fixture),before);
  assert.throws(()=>core.generate({...fixture,stale:true},'counsel_ready',library),/evidence changed/);
  assert.throws(()=>core.generate({...fixture,candidate:{...fixture.candidate,material_type:'historical'}},'original',library),/fictional/);
  assert.throws(()=>core.generate(fixture,'unlisted',library),/listed/);
  const changed=JSON.parse(before);changed.context.claims[0].excerpt='Changed fictional date';
  assert.throws(()=>core.generate(changed,'original',library),/packet has changed/);
  const later=JSON.parse(before);later.assessment.revision=2;
  assert.throws(()=>core.generate(later,'original',library),/packet has changed/);
  const original=results[0], o=JSON.parse(JSON.stringify(original.options.find(x=>x.id==='counsel_request')));
  o.factors.feasibility='feasible';o.factors.harm='mitigated';o.factors.preferences='requested';
  // Stated factors cannot override explicitly unresolved prerequisites.
  assert.equal(core.decide('intervene_now',o,original.context,true)[0],'prepare_verify');
  const minimal={claims:[{id:'deadline',topic:'deadline',relevant_date:'2026-10-12'},{id:'party',topic:'party_label'}]};
  const sparse={...o,support_context_ids:['party'],authority_context_ids:[],feasibility_context_ids:[],harm_context_ids:[],preferences_context_ids:[],timing_context_ids:['deadline'],blocking_unknowns:[]};
  assert.equal(core.decide('intervene_now',sparse,minimal,false)[0],'prepare_verify');
  assert.equal(core.decide('prepare_verify',sparse,minimal,false)[0],'insufficient_basis');
  return {status:'passed',scenarios:results.map(r=>({scenario:r.scenario,disposition:r.disposition,options:r.options.length})),checks:18,results};
}
module.exports={check};
if(require.main===module){const result=check();delete result.results;console.log(JSON.stringify(result,null,2));}
