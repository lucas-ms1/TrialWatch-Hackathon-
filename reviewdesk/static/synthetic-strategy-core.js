'use strict';

// Assemble source-backed fictional route templates, then check separate prerequisites.
// No model, network request, persistence or execution occurs here.
(() => {
  const clone = value => JSON.parse(JSON.stringify(value));
  const references = ['support_context_ids','contrary_context_ids','authority_context_ids','timing_context_ids','feasibility_context_ids','harm_context_ids','preferences_context_ids'];
  const issues = {preparation_facilities:'time and access to prepare the defence',challenge_evidence:'questioning the principal witness and hearing rebuttal',self_incrimination:'an inquiry into the disputed confession'};

  function decide(requested,option,context,legalAvailable) {
    const claims = new Map(context.claims.map(c=>[c.id,c]));
    const topic = (ids,topics) => ids.some(id=>topics.includes(claims.get(id)?.topic));
    const f=option.factors,reasons=[];
    if(requested==='insufficient_basis')return ['insufficient_basis',['No case-specific rights and route basis supports a recommendation.']];
    if(requested==='defer')return ['defer',['Defer this route until its stated reconsideration condition; private preparation remains available.']];
    if(requested==='against')return option.contrary_context_ids.length || topic(option.harm_context_ids,['harm','preferences']) ? ['against',['Cited adverse evidence or the expressed preference supports advice against this specified route.']] : ['insufficient_basis',['Missing information alone does not support advice against a route.']];
    if(requested==='prepare_verify')return legalAvailable || option.support_context_ids.some(id=>!['party_label','country_indicator','attention'].includes(claims.get(id)?.topic)) ? ['prepare_verify',['A case-specific basis identifies a limited preparation task.']] : ['insufficient_basis',['No case-specific basis identifies a targeted preparation task.']];
    if(!(topic(option.support_context_ids,['legal_opportunity','issue_position','institution']) && topic(option.authority_context_ids,['institution','legal_opportunity']) && f.opportunity==='supported'))reasons.push('Issue-specific opportunity and authority are not both supported.');
    if(!legalAvailable)reasons.push('Relevant rights dimensions are unavailable or stale.');
    if(requested==='refer_coordinate') {
      if(!['partner_coordination','mechanism_referral'].includes(option.route))reasons.push('A relevant partner or mechanism route is required.');
      if(!topic(option.feasibility_context_ids,['capacity','organization']))reasons.push('Partner availability and capacity are unsupported.');
    } else if(['verification','deferral'].includes(option.route))reasons.push('This is a preparation or deferral route.');
    if(f.feasibility!=='feasible' || !topic(option.feasibility_context_ids,['capacity','organization']))reasons.push('Practical capacity and access need a sourced basis.');
    if(f.harm!=='mitigated' || !topic(option.harm_context_ids,['harm']))reasons.push('Route-specific risks and safeguards need checking.');
    if(f.preferences!=='requested' || !topic(option.preferences_context_ids,['preferences']))reasons.push('The affected person’s relevant instruction is unknown, opposed or unsupported.');
    if(f.urgency==='time_sensitive' && !option.timing_context_ids.some(id=>['deadline','procedure'].includes(claims.get(id)?.topic) && claims.get(id)?.relevant_date))reasons.push('The timing window lacks a dated procedural passage.');
    if(f.urgency==='unknown')reasons.push('Timing remains unknown.');
    if(option.blocking_unknowns.length)reasons.push('Explicit blocking unknowns need resolving before this route.');
    return reasons.length ? [option.support_context_ids.length || legalAvailable ? 'prepare_verify' : 'insufficient_basis',reasons] : [requested,['The limited route has cited opportunity, authority, capacity, safeguards, preferences and timing. Human review remains pending.']];
  }

  function generate(input,scenario,library) {
    if(input.synthetic!==true || input.candidate?.material_type!=='synthetic' || input.candidate.id!==library.case_id)throw new Error('This generator is for the Mara Vale fictional demonstration.');
    if(!Object.hasOwn(library.scenarios,scenario))throw new Error('Choose a listed fictional scenario.');
    if(input.stale)throw new Error('The evidence changed. Update the fictional assessment before generating from it.');
    const context=clone(input.context), evidence=clone(input.candidate),assessment=clone(input.assessment);
    if(!context?.claims || !assessment?.dimensions)throw new Error('A saved fictional context and rights assessment are required.');
    // Updates are authored for the original packet, not for arbitrary later factual edits.
    const original=library.base_fixture;
    const quoteMatch=(actual,expected)=>expected.every(c=>actual.some(x=>x.id===c.id && x.source_id===c.source_id && x.excerpt===c.excerpt && x.text===c.text));
    if(!quoteMatch(context.claims,original.context.claims) || !quoteMatch(evidence.claims,original.candidate.claims) || assessment.revision!==original.assessment.revision || context.revision!==original.context.revision || assessment.evidence_revision!==original.assessment.evidence_revision)throw new Error('This fictional packet has changed. The scenario templates need adapting to its new version.');
    const updates=clone(library.updates[scenario] || []);
    if(updates.length) {
      context.sources.push({...clone(library.update_source),title:'Alternative fictional scenario update — '+library.scenarios[scenario],url:'https://example.invalid/strategy-scenario/'+scenario});
      context.claims.push(...updates);
    }
    const claims=new Map(context.claims.map(c=>[c.id,c])), dimensions=new Map(assessment.dimensions.map(d=>[d.dimension_id,d]));
    const covered=Object.keys(issues).filter(id=>dimensions.get(id)?.status==='scored');
    const legalAvailable=covered.length>0;
    const hasRoute=claims.has('CX02') && claims.has('CX03') && legalAvailable;
    const options=[];
    function add(template,scope) {
      const o=clone(template);o.dimension_ids=scope.filter(id=>dimensions.has(id));
      for(const field of references)o[field]=o[field].filter(id=>claims.has(id));
      o.support_evidence_ids=[...new Set(o.dimension_ids.flatMap(id=>dimensions.get(id).support_claim_ids))].filter(id=>evidence.claims.some(c=>c.id===id)).sort();
      o.contrary_evidence_ids=[...new Set(o.dimension_ids.flatMap(id=>dimensions.get(id).contrary_claim_ids))].filter(id=>evidence.claims.some(c=>c.id===id)).sort();
      [o.disposition,o.rule_reasons]=decide(o.requested_disposition,o,context,legalAvailable);
      options.push(o);
    }
    if(covered.length || context.claims.some(c=>['legal_opportunity','capacity','institution'].includes(c.topic)))add(library.templates.packet_review,covered);
    if(hasRoute) {
      const o=clone(scenario==='counsel_ready'?library.templates.counsel_ready:library.templates.counsel_unready);
      o.objective='Seek a procedural remedy for '+covered.map(id=>issues[id]).join('; ')+'.';
      add(o,covered);
    }
    if(scenario==='clinic_ready' && covered.length)add(library.templates.clinic_referral,covered);
    if(claims.has('CX05') || claims.has('UP20'))add(scenario==='privacy'?library.templates.public_opposed:library.templates.public_deferred,['expression_necessity']);
    let selected=options.find(o=>o.disposition==='intervene_now') || options.find(o=>o.disposition==='refer_coordinate') || options.find(o=>o.route==='verification');
    if(!selected){add(library.templates.no_basis,[]);selected=options.at(-1);}
    return {schema_version:'synthetic-strategy-preview/1',synthetic:true,saved:false,origin:'deterministic_synthetic_generation',model_run:false,human_review:'pending',generated_at:new Date().toISOString(),scenario,scenario_label:library.scenarios[scenario],candidate_id:evidence.id,original_proposal_id:input.original_proposal_id || null,source_assessment_revision:assessment.revision,source_context_revision:context.revision,selected_option_id:selected.id,disposition:selected.disposition,options,selection_reason:library.selection_reason,generation_method:'Browser route templates assemble options from the fictional rights issues and cited context. Separate prerequisite rules check each route; no model request is made.',context,evidence:{claims:evidence.claims,sources:evidence.sources},rights_status:'The synthetic-prepared legal assessment remains pending human review. Scenario updates do not approve it.',alternative_updates:updates};
  }
  window.SyntheticStrategy = {generate,decide};
})();
