/* Reading layer for saved intervention proposals. Existing forms and records stay intact. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const sentence = value => {
    const text = String(value || '').trim();
    // Keep complete sentences, rather than clipping away qualifications mid-sentence.
    return text.match(/^.*?[.!?](?=\s|$)/s)?.[0] || text;
  };
  const readable = value => String(value || 'Unknown').replaceAll('_',' ').replace(/^./, c => c.toUpperCase());
  const hasIdentifiers = text => /\b(?:AP|AC|CX|MV)\d+\b|\b(?:draft|recommendation)_[a-z0-9]+\b|\bAC\/AP\b/.test(text);
  const readablePlan = (text,option) => {
    const first=sentence(text);
    if(!hasIdentifiers(first))return first;
    const objective=sentence(option.objective);
    return hasIdentifiers(objective)?option.label:objective;
  };
  const factorNames = {urgency:'Timing', opportunity:'Available route', feasibility:'Practical capacity', harm:'Potential harm', preferences:'Affected person’s preferences'};
  const factorValues = {
    urgency:{time_sensitive:'Time sensitive', routine:'No urgent window recorded', unknown:'Timing unknown'},
    opportunity:{supported:'A relevant route is described', not_established:'No relevant route established', unknown:'Route unknown'},
    feasibility:{feasible:'Capacity supported by supplied evidence', needs_verification:'Access and capacity need checking', unknown:'Capacity unknown'},
    harm:{material_risk:'Risks need safeguards', mitigated:'Safeguards described', unknown:'Risks unknown'},
    preferences:{requested:'Relevant preferences expressed', opposed:'Affected person opposes this route', unknown:'Preferences not established'}
  };
  const factorText = (key,value) => factorValues[key]?.[value] || readable(value);
  const headlines = {
    prepare_verify:'Check the key facts before taking action',
    intervene_now:'Propose action through the specified route',
    refer_coordinate:'Prepare a referral or coordination request',
    defer:'Defer this route for now',
    against:'Do not pursue this route at present',
    insufficient_basis:'More evidence is needed before recommending a route'
  };
  const humanStates = {pending_human_review:'Awaiting human review',accept:'Accepted in scoped human review',revise:'Revised in scoped human review',reject:'Rejected in human review',defer:'Human decision deferred',stale:'Needs an updated proposal'};
  const routeNames = {verification:'Record checking',deferral:'Deferred route',legal_support:'Legal support',partner_coordination:'Partner coordination',quiet_engagement:'Quiet engagement',public_advocacy:'Public advocacy',policy_advocacy:'Policy advocacy',mechanism_referral:'Mechanism referral'};

  // Authored explanation of the original fictional snapshot only. Later context revisions
  // use the generic declared-role explanations below; this creates no saved approval.
  const fictionalRelevance = {
    CX01:'Sets the preparation window before the next fictional hearing. The date alone does not show that intervention would help.',
    CX02:'Provides a reason to prepare: the fictional procedure lets counsel ask to reconsider the evidence rulings. It does not establish that a request would succeed.',
    CX03:'Identifies counsel as the permitted filer and the judge as the decision maker. It gives this preparation team no filing mandate.',
    CX04:'Supports comparing the supplied packet locally. Missing originals and unconfirmed filing capacity mean further action still needs verification.',
    CX05:'Supports caution about publicity: it could expose family information or cause unwanted attention, and no protection plan is agreed.',
    CX06:'Limits a public campaign or referral: there is no recorded instruction from Mara about either route, so her preferences cannot be assumed.',
    CX07:'Challenges the defence account of late charge delivery. The prosecution asserts earlier delivery, but the unreadable receipt and disputed identity leave it unresolved.',
    CX08:'Challenges the coercion allegation. The prosecution denies force and says a recording exists; without that recording, voluntariness remains unresolved.',
    CX09:'Preserves the prosecution’s public-order argument and opposition to reopening the rulings. Its stated position does not establish the alleged disorder or justify the restriction.'
  };
  const fictionalTitles = {CX01:'The next hearing',CX02:'An available procedural route',CX03:'Who can file and decide',CX04:'Capacity to check the records',CX05:'Risks of a public campaign',CX06:'Mara’s preferences are unknown',CX07:'A competing charge-delivery account',CX08:'A competing confession account',CX09:'The prosecution’s public-order position'};
  const originalFiction = record => record.candidate_id==='synthetic_mara_vale_20261010' && record.context_snapshot?.revision===1 && record.context_snapshot?.sources?.some(s=>s.id==='demo_context');
  function relevance(record,claim,role,option) {
    if(originalFiction(record) && fictionalRelevance[claim.id])return fictionalRelevance[claim.id];
    if(role==='contrary')return 'A competing account to weigh against the case claims and assumptions behind this option. It is not treated as an established fact.';
    if(role==='capacity')return `Addresses the records, access or resources needed for this step. The worksheet’s capacity judgment is: ${factorText('feasibility',option.factors?.feasibility).toLowerCase()}.`;
    if(role==='harm')return 'Identifies a possible adverse consequence or a safeguard to examine before using this route.';
    if(role==='preferences')return 'Relevant to whether the affected person wants this route. Missing preferences remain unknown.';
    if(role==='authority')return 'Identifies who can use or decide on a relevant route. A described power is separate from this team’s authority to act.';
    if(role==='timing' || claim.topic==='deadline')return 'Supplies the timing window this option relies on. A deadline alone does not establish a benefit from acting.';
    if(claim.topic==='capacity')return relevance(record,claim,'capacity',option);
    if(claim.topic==='legal_opportunity' || claim.topic==='institution' || claim.topic==='issue_position')return 'Describes a route, authority or issue-specific position cited in support of considering this option. Its relevance and practical availability still need review.';
    return 'Cited as part of the case-specific basis for considering this option. Inspect the attributed passage and the option’s rationale before relying on it.';
  }
  function evidenceCard(record,option,id,role) {
    const context=record.context_snapshot || record.context || {}, claim=list(context.claims).find(c=>c.id===id);
    if(!claim)return `<p class="notice warning">A cited context passage could not be resolved. Inspect the saved record before relying on this option.</p>`;
    const source=list(context.sources).find(s=>s.id===claim.source_id), rid=record.id || record.recommendation_id;
    const target=`adv-context-${rid}-${id}`;
    return `<article class="adv-evidence-card${role==='contrary'?' is-competing':''}">
      <h5>${esc(originalFiction(record) && fictionalTitles[id] || ({deadline:'Timing of the next step',capacity:'Records, access and capacity',harm:'Risks and safeguards',preferences:'Affected preferences',institution:'Who has authority',legal_opportunity:'A possible procedural route',issue_position:'An attributed position'}[claim.topic]) || readable(claim.topic))}</h5>
      <a class="adv-evidence-title" href="#${esc(target)}" data-adv-anchor="${esc(target)}">${esc(source?.title || 'Source title unavailable')}</a>
      <p class="adv-evidence-account">${esc(sentence(claim.text))}</p>
      <p class="adv-evidence-relevance"><strong>Why it matters:</strong> ${esc(relevance(record,claim,role,option))}</p>
      <details class="adv-exact-passage"><summary>Exact passage and citation</summary>
        <p><strong>Record:</strong> ${esc(claim.id)} · ${esc(readable(claim.topic))}<br><strong>Attribution:</strong> ${esc(claim.attribution)}</p>
        <blockquote>“${esc(claim.excerpt)}”</blockquote>
        <p>${esc(claim.locator)}<br>Relevant date: ${esc(claim.relevant_date || 'Unknown')} · ${esc(claim.date_note)}</p>
        <p>Published: ${esc(source?.publication_date || 'Unknown')} · ${esc(source?.publisher || 'Unknown publisher')}<br>Language: ${esc(source?.language)} · ${esc(source?.translation_status)}</p>
        ${/^https?:\/\//.test(source?.url || '')?`<p><a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">Open source document ↗</a></p>`:''}
        <p><strong>Uncertainty:</strong> ${esc(claim.uncertainty)}<br><strong>Freshness:</strong> ${esc(claim.freshness_note)}</p>
      </details>
    </article>`;
  }
  function evidenceGroups(record,option) {
    const groups=[
      ['Reasons to consider this option',list(option.support_context_ids).map(id=>[id,'support'])],
      ['Competing accounts to resolve',list(option.contrary_context_ids).map(id=>[id,'contrary'])],
      ['Authority, timing and practical limits',[
        ...list(option.authority_context_ids).map(id=>[id,'authority']),
        ...list(option.timing_context_ids).map(id=>[id,'timing']),
        ...list(option.feasibility_context_ids).map(id=>[id,'capacity']),
        ...list(option.harm_context_ids).map(id=>[id,'harm']),
        ...list(option.preferences_context_ids).map(id=>[id,'preferences'])]]
    ];
    const seen=new Set();
    return groups.map(([title,refs],index)=>{
      const inGroup=new Set(), distinct=refs.filter(([id])=>!inGroup.has(id) && inGroup.add(id) && (index<2 || !seen.has(id)));
      distinct.forEach(([id])=>seen.add(id));
      if(!distinct.length && refs.length)return '';
      return `<section class="adv-evidence-group"><h4>${esc(title)}</h4>${distinct.length?distinct.map(([id,role])=>evidenceCard(record,option,id,role)).join(''):'<p class="help">No passage supplied for this part. This remains a gap.</p>'}</section>`;
    }).join('');
  }
  function disclosure(title,node,{open=false,className='adv-tool'}={}) {
    const details=document.createElement('details'); details.className=className; details.open=open;
    const summary=document.createElement('summary'); summary.textContent=title;
    details.append(summary,node); return details;
  }
  function wrapDisclosure(node,title,options) {
    const parent=node.parentNode, next=node.nextSibling;
    const wrapped=disclosure(title,node,options);
    parent.insertBefore(wrapped,next);
    return wrapped;
  }
  function compactOption(record,option,original) {
    const selected=option.id===record.selected_option_id, effective=record.disposition || record.requested_disposition;
    const card=document.createElement('article'); card.className='adv-option-card'+(selected?' is-selected':'');
    // The author rationale supplies a complete readable first sentence; exact next-step
    // references and the rest of the saved reasoning remain in the full worksheet.
    const overview=readablePlan(selected && record.requested_disposition===effective ? record.rationale : option.next_step || option.objective,option);
    card.innerHTML=`<div class="adv-option-heading"><span class="badge${selected?' blue':''}">${selected?(record.stale?'Earlier selected option':'Selected proposal'):'Alternative considered'}</span><span class="help">${esc(routeNames[option.route] || readable(option.route))}</span></div>
      <h3>${esc(option.label)}</h3><p>${esc(overview)}</p>
      <p class="adv-option-condition"><strong>Capacity:</strong> ${esc(factorText('feasibility',option.factors?.feasibility))}<br><strong>Preferences:</strong> ${esc(factorText('preferences',option.factors?.preferences))}</p>
      <details class="adv-option-evidence"><summary>Why consider it? Evidence and limits</summary><p class="help">Prepared relevance explanations; human review is pending unless separately recorded. Competing accounts challenge case claims; capacity, risks and preferences can limit the action.</p>${evidenceGroups(record,option)}</details>`;
    if(original) {
      // Keep the original complete renderer, including every condition, passage ID,
      // hypothesis and next step, within an expandable record rather than discarding it.
      for(const [i,tag] of [...original.querySelectorAll('.metric-tags span')].entries()) {
        const key=['urgency','opportunity','feasibility','harm','preferences'][i];
        if(key)tag.textContent=`${factorNames[key]}: ${factorText(key,option.factors?.[key])}`;
      }
      const context=record.context_snapshot || record.context || {}, rid=record.id || record.recommendation_id;
      for(const link of original.querySelectorAll('[data-adv-anchor]')) {
        const claim=list(context.claims).find(c=>link.dataset.advAnchor===`adv-context-${rid}-${c.id}`);
        const source=list(context.sources).find(s=>s.id===claim?.source_id);
        if(claim && source) {
          link.textContent=source.title;
          link.title=`${claim.id} · ${claim.locator}`;
        }
      }
      const details=disclosure('Full option, conditions and source references',original,{className:'adv-option-full'});
      card.append(details);
    }
    return card;
  }
  function mountRecommendation(panel,record,item) {
    const options=list(record.options || record.proposal?.options), selected=options.find(o=>o.id===record.selected_option_id);
    if(!selected)return;
    const originals=[...panel.querySelectorAll(':scope > .strategy-option')];
    const grid=document.createElement('div'); grid.className='adv-option-grid';
    options.forEach((option,i)=>grid.append(compactOption(record,option,originals[i])));
    const exports=panel.querySelector(':scope > .export-actions');
    if(exports) {
      const links=[...exports.querySelectorAll('a')];
      if(links[0])links[0].textContent='Download cited proposal';
      if(links[1])links[1].textContent='Download proposal JSON';
      exports.remove();
    }
    const preserved=document.createElement('div'); preserved.className='adv-preserved-record';
    while(panel.firstChild)preserved.append(panel.firstChild);
    const ledger=disclosure('Sources, decision rules and saved record',preserved,{className:'adv-record-details'});
    const disposition=record.disposition || record.requested_disposition;
    const headline=record.stale?'This earlier proposal needs an update':headlines[disposition] || readable(disposition);
    const planned=record.requested_disposition===disposition?readablePlan(record.rationale,selected):'Check the unresolved prerequisites before considering the requested route. Read the decision rules for what changed.';
    const review=list(record.reviews).at(-1);
    const status=humanStates[record.review_status] || humanStates.pending_human_review;
    panel.classList.add('adv-reading-panel');
    panel.innerHTML=`<div class="adv-decision-heading"><div><p class="eyebrow">${record.stale?'EARLIER PROPOSAL':'PROPOSED NEXT STEP'}</p><h2>${esc(headline)}</h2></div><span class="badge ${record.stale?'amber':'blue'}">${esc(status)}</span></div>
      ${record.stale?'<p class="notice warning">The evidence, assessment or context used by this proposal has changed. Update the proposal before relying on it; its original reasoning remains below.</p>':''}
      ${review?.revised_disposition?`<p class="notice"><strong>Recorded human revision:</strong> ${esc(headlines[review.revised_disposition] || readable(review.revised_disposition))}. ${esc(review.revision_note)}</p>`:''}
      <div class="adv-main-step"><h3>${esc(selected.label)}</h3><p>${esc(planned)}</p></div>
      <div class="adv-decision-facts"><div><h3>Why this step?</h3><p>${esc(sentence(selected.factors?.reason || record.rationale))}</p></div><div><h3>When?</h3><p>${esc(selected.timing_window || 'Timing is not established.')}</p></div><div><h3>Who could do it?</h3><p>${esc(selected.actor || 'Actor and mandate are not established.')}</p></div></div>
      <div class="adv-readiness" aria-label="Separate intervention factors">${Object.keys(factorNames).map(key=>`<div><span>${esc(factorNames[key])}</span><strong>${esc(factorText(key,selected.factors?.[key]))}</strong></div>`).join('')}</div>
      <div class="adv-before-action"><h3>What still needs checking?</h3><ul>${list(selected.blocking_unknowns).map(text=>`<li>${esc(text)}</li>`).join('') || '<li>No blocking unknown entered. Inspect the stated prerequisites and risk evidence.</li>'}</ul></div>
      <div class="adv-comparison-heading"><h3>Options considered</h3><p>Compare the proposed step with its alternative.</p></div>`;
    panel.append(grid,ledger);
    if(exports)panel.append(exports);
    const note=document.createElement('p');note.className='help adv-save-note';note.textContent='Saving a proposal or review records a decision; it does not carry out the action.';panel.append(note);
  }
  window.mountAdvocacyReader = ({item,record}) => {
    const layout=document.querySelector('#case-view .case-layout'), main=layout?.querySelector('.case-main'), sidebar=layout?.querySelector('.case-sidebar');
    if(!main || main.dataset.advReader)return;
    main.dataset.advReader='true'; layout.classList.add('advocacy-reader-layout');
    const intro=main.querySelector('.adv-steps')?.closest('section');
    if(intro && record) {
      const error=intro.querySelector('[role="alert"]');
      if(error)main.insertBefore(error,intro);
      intro.remove();
    }
    if(intro && !record)intro.querySelector('a[href="#intervention-human-review"]')?.remove();
    const panel=main.querySelector('.recommendation-panel');
    if(panel && record)mountRecommendation(panel,record,item);
    // Case background remains available, while the active proposal gets the reading space.
    const caseHeading=document.querySelector('#case-view > .case-heading'), caseDetails=document.querySelector('#case-view > .source-record');
    if(caseDetails && caseHeading) {
      const description=caseHeading.querySelector('.lede');
      if(description)caseDetails.append(description);
      const assessmentExports=caseHeading.querySelector('.export-actions');
      if(assessmentExports)caseDetails.append(assessmentExports);
    }
    for(const [selector,title] of [['#context-editor','Update the dated case context'],['#options-editor','Prepare or revise the options']]) {
      const node=main.querySelector(selector);
      if(node)wrapDisclosure(node,title,{open:!record});
    }
    const followup=main.querySelector('#intervention-followup-form')?.closest('section');
    if(followup)wrapDisclosure(followup,'Record an action or outcome');
    const history=[...main.querySelectorAll(':scope > section')].find(n=>n.querySelector('h2')?.textContent==='Recommendation and context history');
    if(history)wrapDisclosure(history,'Earlier proposals and context versions');
    if(sidebar) {
      const review=sidebar.querySelector('#intervention-human-review') || sidebar.firstElementChild;
      if(review && record) {
        const disclosureNode=disclosure('Review this proposal — accept, revise, reject or defer',review,{className:'adv-tool adv-review-tool'});
        panel?.after(disclosureNode);
      }
      const related=document.createElement('div');
      while(sidebar.firstChild)related.append(sidebar.firstChild);
      if(related.children.length)main.append(disclosure('Related cases and background context',related));
      sidebar.hidden=true;
    }
    main.addEventListener('click',event=>{
      const link=event.target.closest('.adv-evidence-title');
      if(!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
      const exact=link.closest('.adv-evidence-card')?.querySelector('.adv-exact-passage');
      if(!exact)return;
      event.preventDefault(); event.stopPropagation(); exact.open=true;
      exact.querySelector('summary')?.focus({preventScroll:true});
    });
  };
})();
