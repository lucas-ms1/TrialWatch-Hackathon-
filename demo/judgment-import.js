'use strict';

(() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const array = value => Array.isArray(value) ? value : [];
  const plain = value => typeof value==='string' || typeof value==='number' ? String(value) : value?.name || value?.title || '';
  const sourceLink = value => {
    try {const parsed=new URL(value);return ['http:','https:'].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : null;} catch {return null;}
  };
  const locator = value => typeof value==='string' ? value : value ? Object.entries(value).map(([key,text])=>`${key.replaceAll('_',' ')}: ${plain(text)}`).join(' · ') : 'Location not recorded';
  const PAGE_SIZE=10, MAX_SELECTED=50;
  const passageText = passage => String(passage.text || passage.excerpt || '');
  const snippet = text => {const compact=text.replace(/\s+/g,' ').trim();return compact.length>190?compact.slice(0,190)+'…':compact;};
  const footnote = value => value && typeof value==='object' ? [plain(value.text),plain(value.target)].filter(Boolean).join(' · ') : plain(value);

  function mount(host, options={}) {
    if(!host || typeof host.querySelector!=='function')throw new Error('Provide a container for the judgment importer.');
    const request=options.request;
    if(typeof request!=='function')throw new Error('Provide the local request helper.');
    const state={providerData:null,filename:'',preview:null,selected:new Set(),query:'',page:0,busy:false,error:'',saved:null,disposed:false};
    const $=selector=>host.querySelector(selector);
    const announce = message => {const element=$('[data-ji-status]');if(element)element.textContent=message;};
    const inspectPath=options.inspectPath || '/api/judgments/inspect';
    const previewPath=options.previewPath || '/api/judgments/preview';
    const locked = () => state.busy || !!state.saved || !!state.preview?.duplicate?.exact;
    const selectable = passage => passage.selectable!==false;
    const number = passage => passage.number || array(state.preview?.passages).indexOf(passage)+1;

    function documentFields(preview) {
      const metadata=preview.document || preview.metadata || {};
      return {
        title:plain(metadata.title || metadata.case_name || metadata.name || preview.title) || state.filename,
        citation:plain(metadata.citation || metadata.cite) || array(metadata.citations).map(item=>plain(item.cite || item)).filter(Boolean).join(' · '),
        court:plain(metadata.court),jurisdiction:plain(metadata.jurisdiction || metadata.country),
        date:plain(metadata.decision_date || metadata.document_date),
        url:sourceLink(metadata.url || metadata.source_url || preview.provenance?.source_url || preview.provenance?.url)
      };
    }

    function filteredPassages() {
      const query=state.query.trim().toLocaleLowerCase();
      return array(state.preview?.passages).filter(passage=>!query || [passage.id,number(passage),passageText(passage),locator(passage.locator),passage.section].join(' ').toLocaleLowerCase().includes(query));
    }

    function renderBrowser() {
      const filtered=filteredPassages(),pages=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));
      state.page=Math.max(0,Math.min(state.page,pages-1));
      const start=state.page*PAGE_SIZE,visible=filtered.slice(start,start+PAGE_SIZE);
      return `<div class="ji-pagination"><span>${filtered.length?`${start+1}–${start+visible.length} of ${filtered.length}`:'No matching passages'}${state.query.trim()?' matches':''}</span><nav aria-label="Passage pages"><button type="button" class="button" data-ji-page="${state.page-1}" aria-label="Previous passage page" ${state.page===0?'disabled':''}>Previous</button><span>Page ${state.page+1} / ${pages}</span><button type="button" class="button" data-ji-page="${state.page+1}" aria-label="Next passage page" ${state.page>=pages-1?'disabled':''}>Next</button></nav></div><div class="ji-passages">${visible.map(passage=>`<article class="ji-passage${selectable(passage)?'':' ji-unselectable'}" data-ji-row="${escape(passage.id)}"><label class="ji-passage-choice"><input type="checkbox" data-ji-passage="${escape(passage.id)}" aria-label="Select passage ${escape(number(passage))} (${escape(passage.id)})" ${state.selected.has(passage.id)?'checked':''} ${locked() || !selectable(passage) || (state.selected.size>=MAX_SELECTED && !state.selected.has(passage.id))?'disabled':''}><span>Passage ${escape(number(passage))} <small>(${escape(passage.id)})</small></span></label><p class="ji-snippet">${escape(snippet(passageText(passage)))}</p><p class="ji-locator">${escape(locator(passage.locator))}</p>${!selectable(passage)?`<p class="ji-selection-note">${escape(passage.selection_note || 'This passage cannot be selected.')}</p>`:''}<details class="ji-details"><summary>Show passage details</summary><blockquote>${escape(passageText(passage))}</blockquote>${passage.section?`<p><strong>Section:</strong> ${escape(passage.section)}</p>`:''}${passage.attribution?`<p><strong>Attribution:</strong> ${escape(passage.attribution)}</p>`:''}${array(passage.footnote_refs).length?`<p><strong>Footnotes:</strong> ${array(passage.footnote_refs).map(value=>escape(footnote(value))).join(', ')}</p>`:''}</details></article>`).join('') || '<p class="ji-empty">Try another word or passage number.</p>'}</div>`;
    }

    function selectedList() {
      const selected=array(state.preview?.passages).filter(passage=>state.selected.has(passage.id));
      return selected.length?`<details class="ji-details ji-selected-list"><summary>Selected passages · ${selected.length}</summary><div>${selected.map(passage=>`<button type="button" class="button" data-ji-jump="${escape(passage.id)}">${escape(number(passage))} · ${escape(passage.id)}</button>`).join('')}</div></details>`:'';
    }

    function renderPreview() {
      const preview=state.preview,metadata=documentFields(preview),passages=array(preview.passages);
      const licenseUrl=sourceLink(preview.permission?.license_url),duplicate=preview.duplicate?.exact,synthetic=preview.provider==='synthetic_fixture' || preview.material_type==='synthetic';
      return `<section class="ji-preview" aria-labelledby="ji-preview-title"><div class="ji-section-heading"><div><p class="ji-kicker">${state.saved?'SAVED EVIDENCE':'UNSAVED PREVIEW'} · ${synthetic?'SYNTHETIC EXAMPLE':'LAWPHIL SOURCE'}</p><h3 id="ji-preview-title">${escape(metadata.title)}</h3></div><span class="ji-count">${passages.length} passages</span></div><p class="ji-case-meta">${[metadata.citation,metadata.court,metadata.jurisdiction].filter(Boolean).map(escape).join(' · ') || 'Case metadata not supplied'}${metadata.date?`<br>Decision date: ${escape(metadata.date)}`:''}${metadata.url && !synthetic?`<br><a href="${escape(metadata.url)}" target="_blank" rel="noopener noreferrer">Source document ↗</a>`:''}</p>${duplicate?`<p class="ji-empty">This document is already imported.${typeof options.onOpenExisting==='function'?' <button type="button" class="button" data-ji-existing>Open existing case</button>':' Open it from the Case index.'}</p>`:''}<details class="ji-details"><summary>Source details and reuse terms</summary>${preview.permission?.license_label?`<p>${escape(preview.permission.license_label)}${licenseUrl?` · <a href="${escape(licenseUrl)}" target="_blank" rel="noopener noreferrer">Reuse terms ↗</a>`:''}</p>`:''}<pre>${escape(JSON.stringify({document:Object.fromEntries(Object.entries(preview.document || {}).filter(([key])=>!['html','text','source_text'].includes(key))),identity:preview.identity,provenance:preview.provenance,permission:preview.permission,warnings:preview.warnings,duplicate:preview.duplicate},null,2))}</pre></details><div class="ji-selection-bar"><span data-ji-selected-count>${state.selected.size} / ${MAX_SELECTED} selected</span><span>Choose up to ${MAX_SELECTED} passages.</span></div><div data-ji-selected-list>${selectedList()}</div><label class="ji-search">Find passages<input type="search" data-ji-search value="${escape(state.query)}" placeholder="Text, locator or passage number"></label><div data-ji-browser>${renderBrowser()}</div><div class="ji-actions"><span>${state.saved?'Case evidence saved.':`Save ${state.selected.size} selected ${state.selected.size===1?'passage':'passages'} as case evidence.`}</span><button type="button" class="button primary" data-ji-save ${locked() || !state.selected.size?'disabled':''}>${state.saved?'Saved':state.busy?'Saving…':'Save selected passages'}</button></div></section>`;
    }

    function render() {
      if(state.disposed)return;
      host.innerHTML=`<div class="judgment-import"><div class="ji-header"><div><p class="ji-kicker">CASE INTAKE</p><h2>Import a judgment</h2></div><button type="button" class="icon-button" data-ji-cancel aria-label="Close judgment import" ${state.busy?'disabled':''}>×</button></div><p class="ji-intro">Load a bundle, preview its text and select passages.</p>${state.error?`<div class="error ji-error" role="alert">${escape(state.error)}</div>`:''}<form class="ji-file-form" data-ji-file-form><label>LawPhil judgment bundle or synthetic example (.json)<input type="file" data-ji-file accept=".json,application/json" ${state.busy?'disabled':''}><span class="ji-file-note">${state.filename?escape(state.filename):'JSON with document metadata and HTML or text.'}</span></label><button type="submit" class="button" ${state.busy || !state.providerData?'disabled':''}>${state.busy && !state.preview?'Preparing…':'Preview passages'}</button></form><p class="ji-status" data-ji-status role="status" aria-live="polite">${state.busy?'Preparing the local preview…':''}</p>${state.preview?renderPreview():''}</div>`;
    }

    function previewRequest(selectedIds=null) {
      return {schema_version:'judgment-import/1',provider:state.providerData.provider,document:state.providerData.document,...(selectedIds?{selected_passage_ids:selectedIds}:{})};
    }

    function validateBundle(value) {
      if(!value || value.schema_version!=='judgment-import/1' || !['lawphil','synthetic_fixture'].includes(value.provider) || !value.document || typeof value.document!=='object' || Array.isArray(value.document))throw new Error('Choose a LawPhil or synthetic judgment-import/1 bundle with document metadata and HTML or text.');
      return value;
    }

    async function prepare() {
      if(state.busy || !state.providerData)return;
      state.busy=true;state.error='';state.preview=null;state.saved=null;state.selected.clear();state.query='';state.page=0;render();
      try {
        const result=await request(inspectPath,previewRequest());
        if(!result || result.schema_version!=='judgment-preview/1' || !Array.isArray(result.passages))throw new Error('The preview response has no passage list.');
        if(state.disposed)return;
        state.preview=result;state.busy=false;render();announce(`${result.passages.length} passages ready. Select up to ${MAX_SELECTED}.`);
      } catch(error){if(state.disposed)return;state.busy=false;state.error=error?.message || String(error);render();}
    }

    async function save() {
      if(locked() || !state.preview || !state.selected.size || state.selected.size>MAX_SELECTED)return;
      state.busy=true;state.error='';render();announce('Validating selected passages…');
      try {
        const selectedIds=array(state.preview.passages).filter(passage=>state.selected.has(passage.id)).map(passage=>passage.id);
        const validated=await request(previewPath,previewRequest(selectedIds));
        if(!validated?.intake || validated.intake.schema_version!=='rights-intake/2' || validated.intake.prepared_mappings!==null)throw new Error('The preview did not produce a valid case intake. Nothing was saved.');
        if(state.disposed)return;
        announce('Saving case evidence…');
        const result=await request('/api/rights/intake',validated.intake);
        if(state.disposed)return;
        state.saved=result;state.busy=false;render();announce('Case evidence saved. Rights are unassessed.');
        if(typeof options.onSaved==='function') {
          try {await options.onSaved(result,{intake:validated.intake,preview:validated,selectedIds});}
          catch(error){if(state.disposed)return;state.error='Case evidence was saved, but opening it failed: '+(error?.message || String(error));render();}
        }
      } catch(error){if(state.disposed)return;state.busy=false;state.error=error?.message || String(error);render();}
    }

    async function onChange(event) {
      const element=event.target;
      if(element.matches('[data-ji-file]')) {
        if(state.busy)return;
        state.error='';state.providerData=null;state.preview=null;state.saved=null;state.selected.clear();state.query='';state.page=0;
        try {
          const file=element.files?.[0];if(!file){state.filename='';render();return;}
          state.filename=file.name;
          const maxBytes=options.maxBytes || 1000000;
          if(file.size>maxBytes)throw new Error(`Choose a JSON file no larger than ${Math.round(maxBytes/1000)} KB.`);
          const text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());
          if(state.disposed)return;
          state.providerData=validateBundle(JSON.parse(text));render();announce('File loaded. Preview its passages.');
        } catch(error){if(state.disposed)return;state.error=error instanceof SyntaxError?'The file is not valid JSON. Choose the original judgment bundle.':error?.message || String(error);render();}
        return;
      }
      if(element.matches('[data-ji-passage]')) {
        if(locked())return;
        const passage=array(state.preview?.passages).find(item=>item.id===element.dataset.jiPassage);
        if(!passage || !selectable(passage)){element.checked=false;return;}
        if(element.checked && state.selected.size<MAX_SELECTED)state.selected.add(passage.id);else if(!element.checked)state.selected.delete(passage.id);
        updateSelection();
      }
    }

    function updateBrowser() {const region=$('[data-ji-browser]');if(region)region.innerHTML=renderBrowser();}

    function updateSelection() {
      const count=state.selected.size;
      const counter=$('[data-ji-selected-count]');if(counter)counter.textContent=`${count} / ${MAX_SELECTED} selected`;
      const saveButton=$('[data-ji-save]');if(saveButton)saveButton.disabled=locked() || !count;
      const explanation=$('.ji-actions>span');if(explanation)explanation.textContent=`Save ${count} selected ${count===1?'passage':'passages'} as case evidence.`;
      const shortlist=$('[data-ji-selected-list]');if(shortlist)shortlist.innerHTML=selectedList();
      host.querySelectorAll('[data-ji-passage]').forEach(input=>{const passage=array(state.preview?.passages).find(item=>item.id===input.dataset.jiPassage);input.checked=state.selected.has(input.dataset.jiPassage);input.disabled=locked() || !passage || !selectable(passage) || (count>=MAX_SELECTED && !input.checked);});
      announce(`${count} of ${MAX_SELECTED} passages selected.`);
    }

    function onInput(event) {
      if(event.target.matches('[data-ji-search]')){state.query=event.target.value;state.page=0;updateBrowser();}
    }

    function onClick(event) {
      const page=event.target.closest('[data-ji-page]');
      if(page){if(page.disabled)return;const direction=Number(page.dataset.jiPage)>state.page?1:-1;state.page=Number(page.dataset.jiPage);updateBrowser();const buttons=[...host.querySelectorAll('[data-ji-page]')],nextFocus=buttons.find(button=>!button.disabled && Number(button.dataset.jiPage)===state.page+direction) || buttons.find(button=>!button.disabled);nextFocus?.focus();announce(`Passage page ${state.page+1}.`);return;}
      const jump=event.target.closest('[data-ji-jump]');
      if(jump){state.query='';const search=$('[data-ji-search]');if(search)search.value='';state.page=Math.floor(array(state.preview?.passages).findIndex(p=>p.id===jump.dataset.jiJump)/PAGE_SIZE);updateBrowser();const row=[...host.querySelectorAll('[data-ji-row]')].find(item=>item.dataset.jiRow===jump.dataset.jiJump);if(row){row.querySelector('details').open=true;row.scrollIntoView({block:'nearest'});row.querySelector('summary').focus();}return;}
      if(event.target.closest('[data-ji-save]')){save();return;}
      if(event.target.closest('[data-ji-existing]') && typeof options.onOpenExisting==='function'){const id=array(state.preview?.duplicate?.candidate_ids)[0];if(id)options.onOpenExisting(id);return;}
      if(event.target.closest('[data-ji-cancel]') && !state.busy && typeof options.onCancel==='function')options.onCancel();
    }
    function onSubmit(event) {if(event.target.matches('[data-ji-file-form]')){event.preventDefault();prepare();}}
    host.addEventListener('change',onChange);host.addEventListener('input',onInput);host.addEventListener('click',onClick);host.addEventListener('submit',onSubmit);render();
    return {
      async preview(providerData,filename='Judgment bundle') {if(state.busy)return;state.error='';try{state.providerData=validateBundle(providerData);state.filename=filename;await prepare();}catch(error){state.error=error?.message || String(error);render();}},
      destroy(){state.disposed=true;host.removeEventListener('change',onChange);host.removeEventListener('input',onInput);host.removeEventListener('click',onClick);host.removeEventListener('submit',onSubmit);},
      get dirty(){return !!state.preview && !state.saved;}
    };
  }

  window.TrialWatchJudgmentImport=Object.freeze({mount});
})();
