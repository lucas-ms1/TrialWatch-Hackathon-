'use strict';

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const array = value => Array.isArray(value) ? value : [];
  const decisionNames = {include:'Included',defer:'Needs follow-up',exclude:'Excluded',duplicate:'Duplicate'};
  const materialNames = {historical:'Historical replay',synthetic:'Synthetic fixture',manual_intake:'Manual intake'};
  const state = {data:null,selected:null,drafts:new Map(),campaignDrafts:new Map(),view:'comparison',search:'',filter:'all',tab:'evidence',saving:false,intakeDirty:false,preview:null};
  let toastTimer;

  const dateLabel = value => {
    if (!value) return 'Date unknown';
    const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T12:00:00Z' : value);
    return Number.isNaN(parsed.getTime()) ? String(value) : new Intl.DateTimeFormat('en',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(parsed);
  };
  const dateTimeLabel = value => {
    if (!value) return 'Time not recorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('en',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(date);
  };
  const safeUrl = value => {try {const url = new URL(value);return ['https:','http:'].includes(url.protocol) ? url.href : null;} catch {return null;}};
  const sourceLink = (source, label) => {
    const url = safeUrl(source?.url);
    return url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label || source.title || source.publisher)} <span aria-hidden="true">↗</span></a>` : esc(label || source?.title || 'Source link unavailable');
  };
  const candidates = () => array(state.data?.candidates);
  const candidate = () => candidates().find(item => item.id === state.selected);
  const latest = id => state.data?.reviews?.[id] || null;
  const history = id => array(state.data?.history?.[id]);
  const campaignFor = id => state.data?.campaigns?.[id] || null;
  const campaignStale = id => !!campaignFor(id) && campaignFor(id).review_revision !== latest(id)?.revision;
  const hasDirty = id => [state.drafts,state.campaignDrafts].some(drafts=>drafts.get(id)?.dirty);
  const statusBadge = review => review ? `<span class="badge ${review.decision === 'include' ? 'badge-teal' : review.decision === 'defer' ? 'badge-amber' : 'badge-neutral'}">${esc(decisionNames[review.decision] || review.decision)}</span>` : '<span class="badge badge-outline">Unreviewed</span>';
  const visibleCaseSummary = item => item.id === 'saturday_abra_notice_20261010' && item.summary === 'Part 1 attributed preparation only. Historical 2023 documents do not establish current status.' ? '' : item.summary;
  const currentEvidenceStatus = item => {
    const review = latest(item.id), included = array(review?.included_claim_ids), analysis = campaignFor(item.id);
    return `<section class="unknown-panel" aria-label="Current saved human-review scope"><h3>Saved evidence review</h3>${review ? `<p>${esc(review.reviewer)} · review r${review.revision} · ${esc(dateTimeLabel(review.reviewed_at))} · ${esc(decisionNames[review.decision] || review.decision)}</p><p><strong>Selected observation IDs:</strong> ${esc(included.join(', ') || 'none')}.</p><p>${array(item.claims).length - included.length} observations outside this review.</p>${analysis ? `<p>Analysis r${analysis.revision} · evidence review r${analysis.review_revision}${campaignStale(item.id) ? ' · stale: evidence review changed' : ''}.</p>` : ''}` : '<p>No saved evidence review. Preparation pending.</p>'}</section>`;
  };

  async function api(path, options) {
    let response;
    try {response = await fetch(path, {headers:{'Content-Type':'application/json'},...options});} catch {throw new Error('The local review desk is unavailable. Check that the server is running, then try again.');}
    let data;
    try {data = await response.json();} catch {throw new Error('The server returned an unreadable response. Your edits are still on this page.');}
    if (!response.ok) {
      const message = typeof data.error === 'string' ? data.error : data.error?.message || data.message || `Request failed (${response.status}).`;
      const error = new Error(message);error.status = response.status;throw error;
    }
    return data;
  }

  function draftFor(item) {
    if (!state.drafts.has(item.id)) {
      const saved = latest(item.id);
      const corrections = {};
      for (const correction of array(saved?.corrections)) corrections[correction.claim_id] = {...correction};
      const included = saved && Array.isArray(saved.included_claim_ids) ? [...saved.included_claim_ids] : array(item.claims).map(claim => claim.id);
      state.drafts.set(item.id,{expected_revision:saved?.revision ?? 0,reviewer:saved?.reviewer || '',decision:saved?.decision || (item.suggested_decision === 'uncertain' ? 'defer' : item.suggested_decision || 'defer'),reason:saved?.reason || '',duplicate_of:saved?.duplicate_of || '',corrections,included_claim_ids:included,editing:new Set(),dirty:false,error:null,conflict:false,rebaseNote:false});
    }
    return state.drafts.get(item.id);
  }

  function markDirty(draft) {
    draft.dirty = true;
    const label = $('#dirty-status');
    if (label) {label.textContent = 'Unsaved changes';label.hidden = false;}
    const note = $('#export-state-note');
    if (note) note.textContent = 'Downloads use the last saved review. Save your edits first to include them.';
    renderQueue();
  }

  function showToast(message) {clearTimeout(toastTimer);$('#toast').textContent = message;$('#toast').hidden = false;toastTimer = setTimeout(() => {$('#toast').hidden = true;},5000);}
  function globalError(message) {$('#global-error').textContent = message;$('#global-error').hidden = !message;}

  function renderQueue() {
    const matching = candidates().filter(item => {
      const searchText = [item.title,item.person,item.proceeding,item.country,item.summary].join(' ').toLowerCase();
      const status = latest(item.id)?.decision || 'pending';
      return searchText.includes(state.search.toLowerCase()) && (state.filter === 'all' || state.filter === status);
    });
    $('#queue-count').textContent = matching.length;
    $('#candidate-list').innerHTML = matching.length ? matching.map(item => {
      const index = candidates().indexOf(item) + 1;
      const saved = latest(item.id);
      const dirty = hasDirty(item.id);
      return `<button type="button" class="candidate-button" data-select="${esc(item.id)}" aria-current="${state.view==='dossier' && item.id === state.selected}"><span class="candidate-number"><span>FILE ${String(index).padStart(2,'0')}${dirty ? '<span class="unsaved-dot" title="Unsaved changes"></span>' : ''}</span><span>${esc(item.country || 'Philippines')}</span></span><span class="candidate-name">${esc(item.person || item.title)}</span><span class="candidate-proceeding">${esc(item.title || item.proceeding)}</span><span class="candidate-footer">${campaignFor(item.id) ? `<span class="badge ${campaignStale(item.id)?'badge-amber':'badge-teal'}">${campaignStale(item.id)?'Analysis stale':'Analysis saved'}</span>` : statusBadge(saved)}<time>${esc(item.material_type === 'synthetic' ? 'Synthetic' : dateLabel(item.as_of))}</time></span></button>`;
    }).join('') : '<p class="empty-state">No candidates match this view. Try another search or review state.</p>';
  }

  function renderClaim(item, original, index, draft) {
    const corrected = draft.corrections[original.id];
    const claim = corrected ? {...original,...corrected,date_note:corrected.event_date !== original.event_date ? 'Reviewer correction; check the date against the supporting passage.' : original.date_note,attribution:corrected.source_id !== original.source_id ? 'Reviewer correction citing selected source; factual support not independently verified' : original.attribution} : original;
    const source = array(item.sources).find(s => s.id === claim.source_id);
    const included = draft.included_claim_ids.includes(original.id);
    const editing = draft.editing.has(original.id);
    return `<article class="claim-card${included ? '' : ' excluded-claim'}" data-claim-card="${esc(original.id)}"><div class="claim-topline"><span class="claim-index">REPORTED STATEMENT ${String(index+1).padStart(2,'0')}</span><label class="export-check"><input type="checkbox" data-include="${esc(original.id)}" ${included ? 'checked' : ''}> In export</label></div>${corrected ? '<p class="correction-tag">Reviewer correction · original retained</p>' : ''}<p class="claim-text">${esc(claim.text)}</p><blockquote class="evidence-quote">“${esc(claim.excerpt)}”</blockquote><div class="source-citation">${sourceLink(source, `${source?.publisher || 'Source'} · ${dateLabel(source?.publication_date)}`)}<span class="locator">${esc(claim.locator || 'Location not recorded')}</span></div><div class="claim-date"><strong>Event date:</strong> ${esc(dateLabel(claim.event_date))}${claim.date_note ? ` · ${esc(claim.date_note)}` : ''}</div><div class="claim-actions"><span class="claim-attribution"><strong>Source attribution:</strong> ${esc(claim.attribution || 'Source-attributed reporting')}<br><strong>Evidence review:</strong> ${latest(item.id) ? latest(item.id).included_claim_ids.includes(original.id) ? `Selected observation ${esc(original.id)} in review r${latest(item.id).revision} by ${esc(latest(item.id).reviewer)}.` : `Observation ${esc(original.id)} is outside the current selected review scope.` : 'No named-human review saved.'}</span><button type="button" class="text-button" data-edit-claim="${esc(original.id)}" aria-expanded="${editing}">${editing ? 'Close editor' : corrected ? 'Edit correction' : 'Correct with evidence'}</button></div>${editing ? `<div class="correction-form"><p class="field-help">Propose a supported correction. The original stays unchanged; corrections save with your review.</p><label>Corrected statement<textarea rows="3" data-correction="${esc(original.id)}" data-key="text">${esc(claim.text)}</textarea></label><label>Event date<input type="date" data-correction="${esc(original.id)}" data-key="event_date" value="${esc(claim.event_date || '')}"><span class="field-help">Leave blank if the source does not establish the event date.</span></label><label>Supporting source<select data-correction="${esc(original.id)}" data-key="source_id">${array(item.sources).map(s=>`<option value="${esc(s.id)}" ${s.id===claim.source_id ? 'selected' : ''}>${esc(s.publisher)} · ${esc(dateLabel(s.publication_date))} · ${esc(s.title)}</option>`).join('')}</select></label><label>Exact supporting excerpt<textarea rows="3" data-correction="${esc(original.id)}" data-key="excerpt">${esc(claim.excerpt)}</textarea></label><label>Passage location<input data-correction="${esc(original.id)}" data-key="locator" value="${esc(claim.locator)}"></label><span class="field-help">Use a short exact passage from the selected saved source. A correction cannot add unsupported facts.</span>${corrected ? `<button type="button" class="text-button" data-reset-claim="${esc(original.id)}">Restore original in this review</button>` : ''}</div>` : ''}${corrected ? `<details class="original-claim"><summary>View the unchanged original</summary><p>${esc(original.text)}</p><p>Event date: ${esc(dateLabel(original.event_date))}</p><p>“${esc(original.excerpt)}”</p><p>${esc(original.locator)}</p><p>Original attribution: ${esc(original.attribution || 'Source-attributed reporting')}</p></details>` : ''}</article>`;
  }

  function preparationNotes(item) {
    const reasons = array(item.review_reasons), notes = array(item.notes);
    if (!reasons.length && !notes.length) return '';
    return `<details class="source-details"><summary>Import notes</summary>${reasons.length ? `<h4>Review suggestions</h4><ul class="reason-list">${reasons.map(reason=>`<li>${esc(reason)}</li>`).join('')}</ul>` : ''}${notes.map(note=>`<p class="context-note">${esc(note)}</p>`).join('')}</details>`;
  }

  function renderEvidence(item) {
    const draft = draftFor(item);
    const related = array(item.related_candidate_ids).map(id => candidates().find(other => other.id === id)).filter(Boolean);
    return `${renderTimeline(item,draft)}${visibleCaseSummary(item) ? `<p class="summary">${esc(visibleCaseSummary(item))}</p>` : ''}${currentEvidenceStatus(item)}<section class="evidence-section" aria-label="Source-attributed statements"><div class="section-header"><h3>Select and check the evidence</h3><span class="section-meta">${array(item.claims).length} claim${array(item.claims).length === 1 ? '' : 's'} · source passages attached</span></div>${array(item.claims).map((claim,index)=>renderClaim(item,claim,index,draft)).join('') || '<p class="empty-state">No supported claims have been recorded.</p>'}</section>${array(item.unknowns).length ? `<section class="unknown-panel"><h3>Unknowns</h3><ul>${item.unknowns.map(unknown=>`<li>${esc(unknown)}</li>`).join('')}</ul></section>` : ''}<section class="sources-list" aria-label="Source provenance"><div class="section-header"><h3>Sources & provenance</h3><span class="section-meta">${array(item.sources).length} saved reference${array(item.sources).length===1?'':'s'}</span></div>${array(item.sources).map(source=>`<details class="source-details"><summary>${esc(source.publisher)} <span>· ${esc(dateLabel(source.publication_date))}</span></summary><p>${sourceLink(source)}</p><dl><dt>Published</dt><dd>${esc(dateLabel(source.publication_date))}</dd><dt>Retrieved</dt><dd>${esc(source.retrieved_at ? dateTimeLabel(source.retrieved_at) : 'Not recorded')}</dd><dt>Language</dt><dd>${esc(source.language || 'Not recorded')}</dd><dt>Translation</dt><dd>${esc(source.translation_status || 'Not recorded')}</dd></dl>${source.access_note ? `<p><strong>Access:</strong> ${esc(source.access_note)}</p>` : ''}${source.lineage_note ? `<p><strong>Reporting relationship:</strong> ${esc(source.lineage_note)}</p>` : ''}</details>`).join('')}</section>${related.length ? `<div class="section-header"><h3>Related files</h3></div>${related.map(other=>`<button type="button" class="related-link" data-select="${esc(other.id)}">${esc(other.title || other.person)}</button><br>`).join('')}` : ''}${preparationNotes(item)}<div class="step-next"><span>Save an Include decision, then classify the observations for comparison.</span><button type="button" class="button" data-tab="analysis">Analyze this campaign <span aria-hidden="true">→</span></button></div>`;
  }

  function renderHistory(item) {
    const entries = [...history(item.id)].sort((a,b)=>(b.revision || 0)-(a.revision || 0));
    return `<details class="history-panel"><summary>Review history <span class="count">${entries.length}</span></summary>${entries.length ? entries.map(entry=>`<article class="history-item"><strong>Revision ${esc(entry.revision)} · ${esc(decisionNames[entry.decision] || entry.decision)}</strong><p>${esc(entry.reviewer)} · ${esc(dateTimeLabel(entry.reviewed_at))}</p><p>${esc(entry.reason)}</p>${entry.duplicate_of ? `<p>Duplicate of: ${esc(candidates().find(c=>c.id===entry.duplicate_of)?.title || entry.duplicate_of)}</p>` : ''}<p>${array(entry.included_claim_ids).length} observations selected · ${array(entry.corrections).length} corrections<br><strong>Exact selected observation IDs:</strong> ${esc(array(entry.included_claim_ids).join(', ') || 'none')}</p>${array(entry.corrections).length ? `<details><summary>Inspect saved evidence changes</summary>${entry.corrections.map(change=>`<div class="history-correction"><strong>${esc(change.claim_id)}</strong><p>${esc(change.text)}</p><p>Event date: ${esc(dateLabel(change.event_date))}</p><p>“${esc(change.excerpt)}”</p><p>${esc(change.source_id)} · ${esc(change.locator)}</p></div>`).join('')}</details>` : ''}</article>`).join('') : '<p class="context-note">No human review has been saved for this candidate in this desk.</p>'}</details>`;
  }

  function renderReview() {
    const item = candidate();if (!item) return;
    const draft = draftFor(item), saved = latest(item.id);
    const options = [{value:'include',title:'Include for follow-up',detail:'Relevant to the defined review queue.'},{value:'defer',title:'Need more information',detail:'Keep the missing evidence visible.'},{value:'exclude',title:'Exclude from this queue',detail:'Record why the report falls outside scope.'},{value:'duplicate',title:'Link as duplicate',detail:'Identify the existing candidate.'}];
    const allTargets = candidates().filter(c=>c.id!==item.id).sort((a,b)=>Number(array(item.related_candidate_ids).includes(b.id))-Number(array(item.related_candidate_ids).includes(a.id)));
    $('#review-panel').innerHTML = `<p class="eyebrow">THE HUMAN DECISION</p><h2>Review evidence</h2><p class="review-intro">Select observations, add a reason and save Include to continue to Analysis.</p><div class="saved-state ${saved?'':'pending'}">${saved ? `<strong>${esc(decisionNames[saved.decision] || saved.decision)} · revision ${esc(saved.revision)}</strong><br>${esc(saved.reviewer)} · ${esc(dateTimeLabel(saved.reviewed_at))}<br>Exact selected observation IDs: ${esc(array(saved.included_claim_ids).join(', ') || 'none')}` : '<strong>Review pending.</strong><br>Select observations and save a decision.'}</div>${draft.rebaseNote ? '<div class="conflict-note">The latest saved review is shown above and in history. Your unsaved edits are retained. Check the changes before saving a new revision.</div>' : ''}<form id="review-form" class="review-form"><label class="reviewer-label" for="reviewer">Reviewer name<input id="reviewer" data-review-field="reviewer" required maxlength="120" value="${esc(draft.reviewer)}" placeholder="Your name" autocomplete="name"></label><fieldset class="decision-fieldset"><legend>Evidence review decision</legend><div class="decision-options">${options.map(option=>`<label class="decision-option"><input type="radio" name="decision" data-review-field="decision" value="${option.value}" ${draft.decision===option.value?'checked':''} required><span><strong>${option.title}</strong><small>${option.detail}</small></span></label>`).join('')}</div></fieldset><label class="duplicate-field" id="duplicate-field" ${draft.decision==='duplicate'?'':'hidden'}>Existing candidate<select id="duplicate-target" data-review-field="duplicate_of" ${draft.decision==='duplicate'?'required':''}><option value="">Choose the matching candidate…</option>${allTargets.map(target=>`<option value="${esc(target.id)}" ${draft.duplicate_of===target.id?'selected':''}>${esc(target.person || target.title)} · ${esc(target.title || target.proceeding)}</option>`).join('')}</select><span class="field-help">The reports stay separate. A duplicate decision links them for review.</span></label><label class="review-reason" for="review-reason">Reason & next action<textarea id="review-reason" data-review-field="reason" required rows="4" maxlength="5000" placeholder="What supports your decision? What should an analyst check next?">${esc(draft.reason)}</textarea></label><div id="review-error" class="inline-error" role="alert" ${draft.error?'':'hidden'}>${esc(draft.error || '')}${draft.conflict?'<button type="button" class="button" id="refresh-conflict">Load latest review · keep my edits</button>':''}</div><div class="save-block"><p class="dirty-status" id="dirty-status" ${draft.dirty?'':'hidden'}>Unsaved changes</p><button type="submit" class="button button-primary review-save" ${state.saving?'disabled':''}>${state.saving?'Saving…':'Save review'} <span aria-hidden="true">→</span></button><p class="save-note">Save records your decision and any corrections.</p></div></form><section class="export-panel"><h3>Evidence-only download <span class="badge ${saved?'badge-teal':'badge-neutral'}">${saved?'Saved review':'Draft'}</span></h3><p id="export-state-note">${draft.dirty ? 'Downloads use the last saved review. Save your edits first to include them.' : saved ? 'Download the saved decision, selected claims, citations and open questions.' : 'Download an unreviewed draft.'}</p><div class="export-buttons"><a class="button" href="/api/export/${encodeURIComponent(item.id)}?format=md" download>Markdown <span aria-hidden="true">↓</span></a><a class="button" href="/api/export/${encodeURIComponent(item.id)}?format=json" download>JSON <span aria-hidden="true">↓</span></a></div></section>${renderHistory(item)}`;
  }

  function renderTimeline(item,draft) {
    const claims = array(item.claims).filter(claim=>draft.included_claim_ids.includes(claim.id)).map(claim=>{
      const correction=draft.corrections[claim.id];
      return correction?{...claim,...correction,date_note:correction.event_date!==claim.event_date?'Reviewer correction; check the date against the supporting passage.':claim.date_note,attribution:correction.source_id!==claim.source_id?'Reviewer correction citing selected source; factual support not independently verified':claim.attribution}:claim;
    });
    const dated = claims.filter(claim=>claim.event_date).sort((a,b)=>a.event_date.localeCompare(b.event_date));
    const undated = claims.filter(claim=>!claim.event_date);
    const row = claim => {
      const source = array(item.sources).find(source=>source.id===claim.source_id);
      return `<li><div class="timeline-date">${claim.event_date?esc(dateLabel(claim.event_date)):'Event date unknown'}<span>${claim.event_date?'Reported event date':'Kept outside the dated sequence'}</span></div><div class="timeline-content"><p>${esc(claim.text)}</p><div class="source-citation">${sourceLink(source,source?.publisher || 'Source')} · Published ${esc(dateLabel(source?.publication_date))}</div>${claim.date_note?`<p class="timeline-note">${esc(claim.date_note)}</p>`:''}<details><summary>Supporting passage</summary><blockquote class="evidence-quote">“${esc(claim.excerpt)}”</blockquote><p class="source-citation">${esc(claim.locator)} · ${esc(claim.attribution || 'Source-attributed reporting')}</p></details></div></li>`;
    };
    return `<section class="timeline-section"><div class="section-header"><h3>Cited chronology</h3><span class="section-meta">${claims.length} selected statements</span></div><p class="section-intro">Ordered by event date. Undated observations appear below.</p><ol class="timeline">${dated.map(row).join('') || '<li class="timeline-empty">No dated events selected.</li>'}</ol>${undated.length?`<div class="undated-heading">DATE UNRESOLVED <span>${undated.length}</span></div><ol class="timeline undated">${undated.map(row).join('')}</ol>`:''}<p class="context-note">${draft.dirty?'Preview includes unsaved evidence edits. Save the review before using them in an analysis.':'This view uses the selected evidence. Each saved analysis keeps its own evidence snapshot.'}</p></section>`;
  }

  const categories={social_media:'Social media',international_attention:'International attention',campaign_action:'Campaign action',legal_outcome:'Legal outcome',policy_outcome:'Policy development',context:'Case context'};
  const categoryHelp={social_media:'Documented posts or online activity.',international_attention:'Documented attention from international actors.',campaign_action:'Documented advocacy actions, such as a petition or public call.',legal_outcome:'A reported legal development; a scheduled hearing belongs in context.',policy_outcome:'Reported proposal, decision or implementation; check its stage.',context:'Background, allegations, plans or scheduled events.'};
  const analysisFields=['analyst','campaign_label','objective','interpretation','alternative_explanations','limitations'];

  function analysisDraftFor(item) {
    if(!state.campaignDrafts.has(item.id)) {
      const saved=campaignFor(item.id);
      state.campaignDrafts.set(item.id,{...Object.fromEntries(analysisFields.map(key=>[key,saved?.[key] || (key==='analyst'?latest(item.id)?.reviewer || '':'')])),codings:Object.fromEntries(array(saved?.codings).map(coding=>[coding.claim_id,coding.category])),expected_revision:saved?.revision ?? 0,expected_review_revision:latest(item.id)?.revision ?? 0,dirty:false,error:null,conflict:false,rebaseNote:false});
    }
    return state.campaignDrafts.get(item.id);
  }

  function reviewedClaims(item) {
    const review=latest(item.id),corrections=Object.fromEntries(array(review?.corrections).map(value=>[value.claim_id,value]));
    return array(item.claims).filter(claim=>array(review?.included_claim_ids).includes(claim.id)).map(claim=>corrections[claim.id]?{...claim,...corrections[claim.id],date_note:'Human correction; date and source support not independently verified.'}:claim);
  }

  const analysisClaims=(analysis,category)=>array(analysis?.evidence_snapshot?.claims).filter(claim=>array(analysis?.codings).some(coding=>coding.claim_id===claim.id && coding.category===category));
  const evidenceSource=(snapshot,claim)=>array(snapshot?.sources).find(source=>source.id===claim.source_id);

  function observationCard(claim,snapshot,compact=false) {
    const source=evidenceSource(snapshot,claim);
    return `<article class="observation-card${compact?' compact':''}"><p>${esc(claim.text)}</p><div class="observation-date"><strong>${claim.event_date?esc(dateLabel(claim.event_date)):'Event date unknown'}</strong><span>${claim.event_date?'Reported event date':'Not placed in the dated sequence'}</span></div><div class="source-citation">${sourceLink(source,source?.publisher || 'Source')} · Published ${esc(dateLabel(source?.publication_date))}</div><details><summary>Source passage & date note</summary><blockquote class="evidence-quote">“${esc(claim.excerpt)}”</blockquote><p class="source-citation">${esc(claim.locator)} · ${esc(claim.attribution || 'Source-attributed reporting')}</p>${claim.date_note?`<p class="timeline-note">${esc(claim.date_note)}</p>`:''}</details></article>`;
  }

  function renderComparison() {
    const items=candidates(),saved=items.filter(item=>campaignFor(item.id)),stale=saved.filter(item=>campaignStale(item.id));
    const categoryRow=([key,label])=>`<tr class="comparison-category category-${key}"><th scope="row"><span class="category-dot"></span>${label}<small>${esc(categoryHelp[key])}</small></th>${items.map(item=>{const analysis=campaignFor(item.id),claims=analysisClaims(analysis,key);return `<td>${!analysis?'<span class="not-coded">Not coded yet</span>':claims.length?`<span class="presence documented">Documented in selected evidence</span><span class="observation-count">${claims.length} coded observation${claims.length===1?'':'s'}</span>${['legal_outcome','policy_outcome'].includes(key)?`<ul class="outcome-summary">${claims.map(claim=>`<li><p>${esc(claim.text)}</p><span>Event: ${esc(dateLabel(claim.event_date))}</span></li>`).join('')}</ul>`:''}<details class="comparison-observations"><summary>Inspect evidence</summary>${claims.map(claim=>observationCard(claim,analysis.evidence_snapshot,true)).join('')}</details>`:'<span class="presence absent">Not documented in selected evidence</span>'}</td>`;}).join('')}</tr>`;
    $('#candidate-detail').innerHTML=`<div class="comparison-heading"><div><p class="eyebrow">CAMPAIGN COMPARISON / PHILIPPINES</p><h2>Campaign comparison</h2><p>Compare saved analyses and open the source passages or timelines.</p></div><div class="comparison-export"><span class="badge ${saved.length?'badge-teal':'badge-outline'}">${saved.length} saved analys${saved.length===1?'is':'es'}</span>${saved.length?'<div class="export-buttons"><a class="button button-primary" href="/api/campaign-export?format=md" download>Comparison memo ↓</a><a class="button" href="/api/campaign-export?format=json" download>JSON ↓</a></div><button type="button" class="text-button" id="load-comparison-preview">Preview saved memo</button>':'<p>Save an analysis to create the cited comparison memo.</p>'}</div></div>${stale.length?`<div class="conflict-note"><strong>${stale.length} saved analys${stale.length===1?'is has':'es have'} changed evidence.</strong> These columns retain their original snapshots. Review and resave before using the comparison.</div>`:''}${!saved.length?'<div class="comparison-start"><span class="start-number">01</span><p><strong>Start with one dossier.</strong> Check its passages, save an Include review, then classify and analyze the observations.</p></div>':''}<div class="comparison-table-wrap" role="region" aria-label="Campaign evidence comparison" tabindex="0"><table class="comparison-table"><caption>Saved analyst classifications across campaign dossiers. Scroll horizontally for additional dossiers.</caption><thead><tr><th scope="col">Evidence dimension</th>${items.map((item,index)=>{const analysis=campaignFor(item.id);return `<th scope="col"><span class="column-number">DOSSIER ${String(index+1).padStart(2,'0')} · ${esc(materialNames[item.material_type] || item.material_type)}</span><h3>${esc(analysis?.campaign_label || item.person || item.title)}</h3><p>${esc(analysis?.objective || visibleCaseSummary(item))}</p><span class="badge ${analysis?(campaignStale(item.id)?'badge-amber':'badge-teal'):'badge-outline'}">${analysis?(campaignStale(item.id)?(latest(item.id)?.decision==='include'?'Evidence changed':'No longer included'):`Analysis r${analysis.revision}`):'Awaiting analyst review'}</span><div class="column-actions"><button type="button" class="text-button" data-open-dossier="${esc(item.id)}" data-dossier-tab="${analysis?'analysis':'evidence'}">${analysis?'Edit analysis':'Review dossier'} →</button>${analysis?`<button type="button" class="text-button" data-open-dossier="${esc(item.id)}" data-dossier-tab="timeline">Inspect timeline ↗</button>`:''}</div></th>`;}).join('')}</tr></thead><tbody>${Object.entries(categories).map(categoryRow).join('')}<tr class="interpretation-row"><th scope="row">Analyst interpretation</th>${items.map(item=>`<td>${campaignFor(item.id)?esc(campaignFor(item.id).interpretation):'<span class="not-coded">No interpretation saved</span>'}</td>`).join('')}</tr><tr><th scope="row">Alternative explanations<small>Other reasons a development could occur.</small></th>${items.map(item=>`<td>${campaignFor(item.id)?esc(campaignFor(item.id).alternative_explanations):'<span class="not-coded">Not yet assessed</span>'}</td>`).join('')}</tr><tr><th scope="row">Gaps & limits</th>${items.map(item=>{const analysis=campaignFor(item.id);return `<td>${analysis?`<p>${esc(analysis.limitations)}</p><ul class="comparison-gaps">${array(analysis.evidence_snapshot?.unknowns).map(gap=>`<li>${esc(gap)}</li>`).join('')}</ul>`:'<span class="not-coded">Review source coverage and unknowns</span>'}</td>`;}).join('')}</tr></tbody></table></div>${state.preview?.id==='comparison'?`<details class="saved-preview" open><summary>Saved comparison memo</summary><p class="field-help">Actual Markdown export. Unsaved edits are excluded.</p><pre>${esc(state.preview.text)}</pre></details>`:''}`;
  }

  function renderDetail() {
    const comparison=state.view==='comparison';
    $('#workspace').classList.toggle('comparison-mode',comparison);$('#review-panel').hidden=comparison;$('#comparison-open').setAttribute('aria-current',comparison?'page':'false');
    if(comparison){renderComparison();return;}
    const item=candidate();if(!item){$('#candidate-detail').innerHTML='<p class="empty-state">Add a report to begin a campaign dossier.</p>';$('#review-panel').innerHTML='';return;}
    const material=item.material_type || 'historical',review=latest(item.id),analysis=campaignFor(item.id);
    const notice=material==='synthetic'?'<strong>Fictional practice dossier.</strong>':material==='manual_intake'?'<strong>Manual source intake.</strong> Current status unverified.':`<strong>Historical reporting through ${esc(dateLabel(item.as_of))}.</strong> Current status unverified.`;
    const steps=[{id:'evidence',number:'01',label:'Evidence',status:review?'Review saved':'Inspect & select'},{id:'analysis',number:'02',label:'Analysis',status:analysis?(campaignStale(item.id)?'Needs refresh':'Analysis saved'):'Classify & interpret'},{id:'timeline',number:'03',label:'Timeline',status:analysis?'Saved event lanes':'After analysis'}];
    $('#candidate-detail').innerHTML=`<button type="button" class="text-button back-comparison" data-comparison>← Compare campaigns</button><div class="detail-kicker"><p class="eyebrow">${esc(item.country || 'Philippines')} / CAMPAIGN DOSSIER</p><span class="badge badge-neutral">${esc(materialNames[material] || material)}</span></div><h2 class="candidate-title">${esc(item.person || item.title)}</h2><p class="detail-proceeding">${esc(item.title || item.proceeding)}</p><div class="historical-notice">${notice}</div><nav class="workflow-tabs" aria-label="Campaign analysis workflow">${steps.map(step=>`<button type="button" data-tab="${step.id}" aria-current="${state.tab===step.id?'step':'false'}"><span class="step-number">${step.number}</span><span><strong>${step.label}</strong><small>${step.status}</small></span></button>`).join('')}</nav><div id="workflow-content">${state.tab==='analysis'?renderAnalysis(item):state.tab==='timeline'?renderCampaignTimeline(item):renderEvidence(item)}</div>`;
    if(state.tab==='evidence')renderReview();else renderAnalysisSidebar(item);
    if(state.saving)document.querySelectorAll('#candidate-detail input,#candidate-detail textarea,#candidate-detail select,#candidate-detail button,#review-panel input,#review-panel textarea,#review-panel select,#review-panel button').forEach(control=>{control.disabled=true;});
  }

  function renderAnalysis(item) {
    const draft=analysisDraftFor(item),saved=campaignFor(item.id),claims=reviewedClaims(item),ready=latest(item.id)?.decision==='include' && !draftFor(item).dirty;
    const field=(key,label,placeholder,help='')=>`<label>${label}<textarea data-analysis-field="${key}" rows="3" maxlength="8000" required placeholder="${esc(placeholder)}">${esc(draft[key])}</textarea>${help?`<span class="field-help">${help}</span>`:''}</label>`;
    return `<div class="section-heading"><p class="eyebrow">HUMAN CLASSIFICATION & INTERPRETATION</p><h3>Campaign analysis</h3><p>Assign a category to each selected observation, then add your interpretation.</p></div>${!ready?`<div class="prerequisite"><strong>${draftFor(item).dirty?'Save your evidence changes first.':'Start with an Include review.'}</strong><p>Only the saved, selected evidence is used in this analysis.</p><button type="button" class="button" data-tab="evidence">Review evidence ←</button></div>`:''}${campaignStale(item.id)?'<div class="conflict-note"><strong>The evidence review has changed.</strong> Check every selected observation and save a new analysis. The previous snapshot remains in the comparison until you save.</div>':''}${draft.rebaseNote?'<div class="conflict-note">Latest revisions loaded. Your text and classifications are retained; inspect them against the current evidence before saving.</div>':''}${item.material_type==='synthetic' && item.demo_analysis?'<div class="fictional-helper"><span>Fill the fictional example, then save your analysis.</span><button type="button" class="button" id="fill-fictional-analysis">Fill fictional example</button></div>':''}<form id="campaign-form" class="advocacy-form"><div class="form-section"><div class="form-section-title"><span>1</span><h4>Name the campaign & its objective</h4></div><div class="form-grid"><label>Analyst name<input data-analysis-field="analyst" required maxlength="200" autocomplete="name" value="${esc(draft.analyst)}" placeholder="Your name"></label><label>Campaign label<input data-analysis-field="campaign_label" required maxlength="8000" value="${esc(draft.campaign_label)}" placeholder="A clear label for this comparison"></label></div>${field('objective','Campaign objective / comparison scope','What did the campaign seek, and what period or evidence are you comparing?','Cite the reported objective or label your analytical scope.')}</div><div class="form-section"><div class="form-section-title"><span>2</span><h4>Classify the selected observations</h4></div><p class="section-intro">Choose one category per statement. Use Case context for allegations, scheduled events and background.</p><div class="coding-list">${claims.map((claim,index)=>`<article class="coding-card"><span class="claim-index">SELECTED OBSERVATION ${String(index+1).padStart(2,'0')}</span><p>${esc(claim.text)}</p><div class="coding-date">Event: ${esc(dateLabel(claim.event_date))} · Published: ${esc(dateLabel(array(item.sources).find(source=>source.id===claim.source_id)?.publication_date))}</div><details><summary>Inspect supporting passage</summary><blockquote class="evidence-quote">“${esc(claim.excerpt)}”</blockquote><p class="source-citation">${sourceLink(array(item.sources).find(source=>source.id===claim.source_id))} · ${esc(claim.locator)}</p>${claim.date_note?`<p class="timeline-note">${esc(claim.date_note)}</p>`:''}</details><label>Observation category<select data-coding="${esc(claim.id)}" required><option value="">Choose a category…</option>${Object.entries(categories).map(([key,name])=>`<option value="${key}" ${draft.codings[claim.id]===key?'selected':''}>${name}</option>`).join('')}</select></label><p class="coding-help" id="coding-help-${esc(claim.id)}">${esc(categoryHelp[draft.codings[claim.id]] || 'Choose a category.')}</p></article>`).join('') || '<p class="empty-state">Save an Include review with selected statements to classify evidence here.</p>'}</div></div><div class="form-section"><div class="form-section-title"><span>3</span><h4>Interpret the sequence</h4></div>${field('interpretation','What does this sequence suggest?','Describe the sequence and explain your interpretation.')}${field('alternative_explanations','Alternative explanations','Consider legal merits, procedural timing, independent decisions, other advocacy or missing events.')}${field('limitations','Evidence limits & unanswered questions','List missing evidence, uncertain dates and your next checks.')}</div><div class="inline-error" id="campaign-error" role="alert" ${draft.error?'':'hidden'}>${esc(draft.error || '')}${draft.conflict?'<button type="button" class="button" id="refresh-analysis">Load latest revisions · keep my analysis</button>':''}</div><div class="form-save"><div><p class="dirty-status" id="analysis-dirty">${draft.dirty?'Unsaved analysis edits':saved?`Saved analysis · revision ${saved.revision}`:'No analyst assessment saved yet'}</p><p class="save-note">Saving records your classifications and an evidence snapshot. The comparison and export use only saved work.</p></div><button type="submit" class="button button-primary" ${!ready || state.saving?'disabled':''}>${state.saving?'Saving…':'Save analysis'} →</button></div></form>`;
  }

  function renderCampaignTimeline(item) {
    const saved=campaignFor(item.id);
    if(!saved)return '<div class="section-heading"><p class="eyebrow">SOURCE-BOUNDED EVENT LANES</p><h3>A timeline begins with classified evidence.</h3><p>Save an analysis to see documented activity and outcomes in separate lanes.</p><button type="button" class="button button-primary" data-tab="analysis">Classify observations →</button></div>';
    return `<div class="section-heading"><p class="eyebrow">SAVED ANALYSIS R${saved.revision} / EVIDENCE R${saved.review_revision}</p><h3>Activity and outcomes, in sequence.</h3><p>Known event dates appear in order; undated observations appear below.</p></div>${campaignStale(item.id)?'<div class="conflict-note">This is a preserved snapshot. The current evidence review has changed; inspect and resave the analysis.</div>':''}${renderSequence(saved)}<div class="event-lanes">${Object.entries(categories).map(([key,label])=>{const claims=analysisClaims(saved,key),dated=claims.filter(claim=>claim.event_date).sort((a,b)=>a.event_date.localeCompare(b.event_date)),undated=claims.filter(claim=>!claim.event_date);return `<section class="event-lane category-${key}"><header><span class="category-dot"></span><h4>${label}</h4><span>${claims.length} coded</span></header><p class="lane-help">${esc(categoryHelp[key])}</p>${dated.length?`<div class="lane-events">${dated.map(claim=>observationCard(claim,saved.evidence_snapshot)).join('')}</div>`:claims.length?'<p class="lane-empty">No known event dates in this lane.</p>':'<p class="lane-empty">Not documented in selected evidence.</p>'}${undated.length?`<div class="undated-heading">EVENT DATE UNKNOWN · ${undated.length}</div><div class="lane-events undated">${undated.map(claim=>observationCard(claim,saved.evidence_snapshot)).join('')}</div>`:''}</section>`;}).join('')}</div>`;
  }

  function renderSequence(saved) {
    const claims=array(saved.evidence_snapshot?.claims),dated=claims.filter(claim=>claim.event_date).sort((a,b)=>a.event_date.localeCompare(b.event_date)),undated=claims.length-dated.length;
    return `<section class="sequence-overview"><h4>Across the lanes · known event dates</h4><ol>${dated.map(claim=>{const category=array(saved.codings).find(coding=>coding.claim_id===claim.id)?.category;return `<li class="category-${esc(category)}"><time>${esc(dateLabel(claim.event_date))}</time><span><i class="category-dot" aria-hidden="true"></i>${esc(categories[category])}</span><p>${esc(claim.text)}</p></li>`;}).join('') || '<li class="lane-empty">No known event dates in the selected evidence.</li>'}</ol>${undated?`<p class="sequence-unknown">${undated} observation${undated===1?' has':'s have'} an unknown event date and ${undated===1?'is':'are'} shown separately in the source lanes below.</p>`:''}</section>`;
  }

  function renderAnalysisSidebar(item) {
    const saved=campaignFor(item.id),claims=reviewedClaims(item),draft=state.campaignDrafts.get(item.id),history=array(state.data?.campaign_history?.[item.id]);
    $('#review-panel').innerHTML=`<p class="eyebrow">THE COMPARISON RECORD</p><h2>Saved analysis</h2><p class="review-intro">Save your categories and interpretation, then compare dossiers.</p><div class="saved-state ${!saved || campaignStale(item.id)?'pending':''}">${saved?`<strong>Analysis revision ${saved.revision}${campaignStale(item.id)?' · evidence changed':''}</strong><br>${esc(saved.analyst)} · ${esc(dateTimeLabel(saved.saved_at))}<br>Based on evidence review ${saved.review_revision}`:'<strong>No saved analysis.</strong><br>Classifications and interpretation must be saved explicitly.'}</div><div class="brief-metrics"><div><strong>${saved?array(saved.codings).length:claims.length}</strong><span>${saved?'saved coded observations':'selected statements'}</span></div><div><strong>${saved?array(saved.evidence_snapshot?.claims).filter(claim=>!claim.event_date).length:'—'}</strong><span>unknown event dates</span></div></div><div class="category-key">${Object.entries(categories).map(([key,label])=>`<div class="category-${key}"><span class="category-dot"></span><strong>${label}</strong><p>${esc(categoryHelp[key])}</p></div>`).join('')}</div><button type="button" class="button next-stage" data-comparison>Compare campaigns →</button>${draft?.dirty?'<p class="dirty-status">Your unsaved edits stay in this tab session; comparisons use saved work.</p>':''}<details class="history-panel"><summary>Analysis history <span class="count">${history.length}</span></summary>${[...history].reverse().map(entry=>`<article class="history-item"><strong>Revision ${entry.revision} · evidence ${entry.review_revision}</strong><p>${esc(entry.analyst)} · ${esc(dateTimeLabel(entry.saved_at))}</p><p>${esc(entry.campaign_label)}</p><p>${esc(entry.interpretation)}</p><p>${array(entry.codings).length} coded observations</p></article>`).join('') || '<p class="context-note">Saved analysis revisions will appear here.</p>'}</details>`;
  }

  function renderAll() {
    for(const [id,draft] of state.drafts)if(!draft.dirty && draft.expected_revision!==(latest(id)?.revision ?? 0))state.drafts.delete(id);
    for(const [id,draft] of state.campaignDrafts)if(!draft.dirty && (draft.expected_revision!==(campaignFor(id)?.revision ?? 0) || draft.expected_review_revision!==(latest(id)?.revision ?? 0)))state.campaignDrafts.delete(id);
    const dataset = state.data.dataset || {};
    $('#dataset-kind').textContent = dataset.kind === 'synthetic' ? 'Synthetic collection' : dataset.kind === 'manual_intake' ? 'Manual collection' : 'Historical replay';
    $('#dataset-description').textContent = (dataset.label || 'Saved collection') + ' · ' + Object.keys(state.data.reviews || {}).length + ' saved evidence reviews';
    renderQueue();renderDetail();$('#workspace').setAttribute('aria-busy','false');
  }

  async function loadState() {state.data = await api('/api/state');if (!candidates().some(item=>item.id===state.selected)) state.selected = candidates()[0]?.id || null;renderAll();}

  function selectCandidate(id) {if (state.saving || !candidates().some(item=>item.id===id)) return;state.selected=id;state.view='dossier';state.preview=null;renderQueue();renderDetail();if (window.matchMedia('(max-width:730px)').matches) $('#candidate-detail').scrollIntoView({block:'start',behavior:'smooth'});}

  document.addEventListener('click', async event => {
    const tab=event.target.closest('[data-tab]');
    if (tab) {if(state.saving)return;state.tab=tab.dataset.tab;renderDetail();return;}
    if(event.target.closest('#comparison-open') || event.target.closest('[data-comparison]')){if(state.saving)return;state.view='comparison';renderQueue();renderDetail();return;}
    const openDossier=event.target.closest('[data-open-dossier]');if(openDossier){state.tab=openDossier.dataset.dossierTab || 'evidence';selectCandidate(openDossier.dataset.openDossier);return;}
    if(event.target.closest('#fill-fictional-analysis')) {
      const item=candidate();if(item.material_type!=='synthetic' || !item.demo_analysis)return;
      const draft=analysisDraftFor(item);for(const key of ['objective','interpretation','alternative_explanations','limitations'])draft[key]=item.demo_analysis[key] || '';draft.campaign_label=item.demo_analysis.campaign_label || item.person || item.title;
      for(const claim of reviewedClaims(item)){const category=array(item.claims).find(original=>original.id===claim.id)?.demo_category;if(categories[category])draft.codings[claim.id]=category;}
      draft.dirty=true;renderQueue();renderDetail();showToast('Fictional example filled as an unsaved draft. Inspect it before saving.');return;
    }
    if(event.target.closest('#refresh-analysis')) {
      const item=candidate(),draft=analysisDraftFor(item);
      try{state.data=await api('/api/state');draft.expected_revision=campaignFor(item.id)?.revision ?? 0;draft.expected_review_revision=latest(item.id)?.revision ?? 0;draft.error=null;draft.conflict=false;draft.rebaseNote=true;renderAll();}catch(error){draft.error=error.message;renderDetail();}return;
    }
    if(event.target.closest('#load-comparison-preview')) {
      const button=$('#load-comparison-preview');button.disabled=true;button.textContent='Loading saved memo…';
      try{const response=await fetch('/api/campaign-export?format=md');if(!response.ok)throw new Error('The comparison memo could not be loaded. Save an analysis and try again.');state.preview={id:'comparison',text:await response.text()};if(state.view==='comparison')renderDetail();}catch(error){globalError(error.message);button.disabled=false;button.textContent='Try saved memo again';}return;
    }
    const selected = event.target.closest('[data-select]');if (selected) {selectCandidate(selected.dataset.select);return;}
    const edit = event.target.closest('[data-edit-claim]');
    if (edit) {const draft = draftFor(candidate());const id = edit.dataset.editClaim;draft.editing.has(id)?draft.editing.delete(id):draft.editing.add(id);renderDetail();if (draft.editing.has(id)) $(`[data-correction="${CSS.escape(id)}"][data-key="text"]`)?.focus();return;}
    const reset = event.target.closest('[data-reset-claim]');if (reset) {const draft=draftFor(candidate());delete draft.corrections[reset.dataset.resetClaim];markDirty(draft);renderDetail();return;}
    if (event.target.closest('.intake-open')) {$('#intake-dialog').showModal();return;}
    if (event.target.closest('#intake-close')) {$('#intake-dialog').close();return;}
    if (event.target.closest('#refresh-conflict')) {
      const item=candidate(),draft=draftFor(item);
      try {state.data=await api('/api/state');draft.expected_revision=latest(item.id)?.revision ?? 0;draft.conflict=false;draft.error=null;draft.rebaseNote=true;renderAll();} catch(error) {draft.error=error.message;renderReview();}
    }
  });

  document.addEventListener('input', event => {
    if (event.target.closest('#intake-form')) state.intakeDirty=true;
    if (event.target.id==='queue-search') {state.search=event.target.value;renderQueue();return;}
    const item=candidate();if (!item) return;
    if(event.target.dataset.analysisField || event.target.dataset.coding) {
      const draft=analysisDraftFor(item);
      if(event.target.dataset.analysisField)draft[event.target.dataset.analysisField]=event.target.value;
      if(event.target.dataset.coding){draft.codings[event.target.dataset.coding]=event.target.value;const help=document.getElementById(`coding-help-${event.target.dataset.coding}`);if(help)help.textContent=categoryHelp[event.target.value] || 'Choose a category.';}
      draft.dirty=true;$('#analysis-dirty').textContent='Unsaved analysis edits';renderQueue();return;
    }
    const draft=draftFor(item);
    if (event.target.dataset.reviewField) {
      const field=event.target.dataset.reviewField;draft[field]=event.target.value;markDirty(draft);
      if(field==='decision') {$('#duplicate-field').hidden=draft.decision!=='duplicate';$('#duplicate-target').required=draft.decision==='duplicate';}
    }
    if (event.target.dataset.correction) {
      const id=event.target.dataset.correction, original=array(item.claims).find(claim=>claim.id===id);
      if(!draft.corrections[id]) draft.corrections[id]={claim_id:id,text:original.text,event_date:original.event_date || null,source_id:original.source_id,excerpt:original.excerpt,locator:original.locator};
      draft.corrections[id][event.target.dataset.key]=event.target.dataset.key==='event_date'?(event.target.value || null):event.target.value;markDirty(draft);
      const timeline=$('.timeline-section');if(timeline)timeline.outerHTML=renderTimeline(item,draft);
    }
  });

  document.addEventListener('change', event => {
    if (event.target.id==='queue-filter') {state.filter=event.target.value;renderQueue();return;}
    if (event.target.dataset.include) {const draft=draftFor(candidate()),id=event.target.dataset.include;draft.included_claim_ids=event.target.checked?[...new Set([...draft.included_claim_ids,id])]:draft.included_claim_ids.filter(value=>value!==id);event.target.closest('.claim-card').classList.toggle('excluded-claim',!event.target.checked);markDirty(draft);const timeline=$('.timeline-section');if(timeline)timeline.outerHTML=renderTimeline(candidate(),draft);}
  });

  document.addEventListener('submit', async event => {
    if(event.target.id==='campaign-form') {
      event.preventDefault();if(state.saving)return;
      const item=candidate(),draft=analysisDraftFor(item),claims=reviewedClaims(item);
      if(latest(item.id)?.decision!=='include' || draftFor(item).dirty){draft.error='Save an Include evidence review before saving an analysis.';renderDetail();return;}
      const payload={expected_revision:draft.expected_revision,expected_review_revision:draft.expected_review_revision,...Object.fromEntries(analysisFields.map(key=>[key,draft[key].trim()])),codings:claims.map(claim=>({claim_id:claim.id,category:draft.codings[claim.id]}))};
      if(analysisFields.some(key=>!payload[key]) || payload.codings.some(coding=>!categories[coding.category])){draft.error='Complete the analyst fields and classify every selected observation.';renderDetail();return;}
      state.saving=true;draft.error=null;renderDetail();
      try{await api(`/api/campaigns/${encodeURIComponent(item.id)}`,{method:'POST',body:JSON.stringify(payload)});state.campaignDrafts.delete(item.id);state.data=await api('/api/state');state.preview=null;state.saving=false;renderAll();showToast('Campaign analysis saved with its evidence snapshot. Ready to compare.');}catch(error){state.saving=false;draft.error=error.message;draft.conflict=error.status===409;state.campaignDrafts.set(item.id,draft);renderDetail();$('#campaign-error')?.scrollIntoView({block:'nearest'});}return;
    }
    if (event.target.id==='review-form') {
      event.preventDefault();if(state.saving)return;
      const item=candidate(),draft=draftFor(item);
      if(!draft.reviewer.trim() || !draft.reason.trim()) {draft.error='Add your name and a reason for the decision.';renderReview();return;}
      const payload={expected_revision:draft.expected_revision,reviewer:draft.reviewer.trim(),decision:draft.decision,reason:draft.reason.trim(),duplicate_of:draft.decision==='duplicate'?draft.duplicate_of:null,corrections:Object.values(draft.corrections),included_claim_ids:[...draft.included_claim_ids]};
      state.saving=true;draft.error=null;renderDetail();
      try {await api(`/api/reviews/${encodeURIComponent(item.id)}`,{method:'POST',body:JSON.stringify(payload)});state.drafts.delete(item.id);state.data=await api('/api/state');const analysisDraft=state.campaignDrafts.get(item.id);if(analysisDraft)analysisDraft.expected_review_revision=latest(item.id)?.revision ?? 0;state.saving=false;renderAll();showToast('Evidence review saved. Continue to Analysis to classify the observations.');} catch(error) {state.saving=false;draft.error=error.status===409?'Another review was saved after you opened this candidate. Load the latest review to compare it with your retained edits.':error.message;draft.conflict=error.status===409;state.drafts.set(item.id,draft);renderDetail();$('#review-error')?.scrollIntoView({block:'nearest'});}
    }
    if(event.target.id==='intake-form') {
      event.preventDefault();const form=event.target,button=$('#intake-submit'),errorBox=$('#intake-error');
      const payload=Object.fromEntries(new FormData(form));payload.publication_date=payload.publication_date || null;
      if(!payload.source_text.includes(payload.excerpt)) {errorBox.textContent='The supporting excerpt must appear exactly in the pasted source text. Copy the passage without changing its wording.';errorBox.hidden=false;return;}
      if(!safeUrl(payload.url)) {errorBox.textContent='Use a public source URL beginning with https:// or http://.';errorBox.hidden=false;return;}
      button.disabled=true;button.textContent='Adding…';errorBox.hidden=true;
      try {const previousIds=new Set(candidates().map(c=>c.id));const result=await api('/api/intake',{method:'POST',body:JSON.stringify(payload)});state.data=await api('/api/state');state.selected=result.candidate?.id || result.id || candidates().find(c=>!previousIds.has(c.id))?.id || state.selected;state.search='';state.filter='all';state.tab='evidence';state.view='dossier';state.preview=null;state.intakeDirty=false;$('#queue-search').value='';$('#queue-filter').value='all';renderAll();form.reset();form.elements.country.value='Philippines';$('#intake-dialog').close();showToast('Report added as unreviewed manual intake.');} catch(error) {errorBox.textContent=error.message;errorBox.hidden=false;} finally {button.disabled=false;button.innerHTML='Add to queue <span aria-hidden="true">→</span>';}
    }
  });

  $('#about-toggle').addEventListener('click',()=>{const open=$('#about-panel').hidden;$('#about-panel').hidden=!open;$('#about-toggle').setAttribute('aria-expanded',String(open));});
  window.addEventListener('beforeunload',event=>{if(state.intakeDirty || candidates().some(item=>hasDirty(item.id))){event.preventDefault();event.returnValue='';}});
  loadState().catch(error=>{globalError(error.message);$('#workspace').setAttribute('aria-busy','false');$('#candidate-list').innerHTML='<p class="empty-state">Could not load the collection.</p>';$('#candidate-detail').innerHTML='<p class="empty-state">Refresh this page after the local server is available.</p>';});
})();
