'use strict';

(() => {
  const base = new URL('.', document.currentScript.src);
  const cid = 'organizer_melayu_raya_20261010';
  const stateRoute = '/api/rights/state';
  const maps = new Set(['latest', 'history', 'review_history', 'evidence_review_history',
    'evidence_addition_history', 'case_profiles', 'prepared_mappings',
    'original_prepared_mappings', 'prepared_rubric_versions']);
  const owns = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const read = path => fetch(new URL(path, base), {cache:'no-store'})
    .then(response => {if (!response.ok) throw new Error('The saved demo could not be loaded. Refresh the page.'); return response.json();});
  const ready = Promise.all([read('data/snapshot.json'), read('data/organizer-redacted.json')])
    .then(([snapshot, overlay]) => {
      const addedState = overlay.responses?.[stateRoute];
      const candidate = addedState?.candidates?.[0];
      const rightsMaps = addedState?.rights;
      if (overlay.schema_version !== 'static-case-overlay/1' || overlay.candidate_id !== cid
        || candidate?.id !== cid || addedState.candidates.length !== 1
        || Object.keys(addedState).some(key => !['candidates', 'rights'].includes(key))
        || snapshot.case_count !== 5
        || snapshot.responses[stateRoute].candidates.length !== 5)
        throw new Error('The additional saved case does not match this demo.');
      if (snapshot.responses[stateRoute].candidates.some(candidate => candidate.id === cid))
        throw new Error('The additional saved case would replace an existing case.');
      const result = JSON.parse(JSON.stringify(snapshot));
      const state = result.responses[stateRoute];
      state.candidates.push(candidate);
      for (const [name, entries] of Object.entries(rightsMaps)) {
        if (!maps.has(name) || !state.rights[name] || Object.keys(entries).length > 1)
          throw new Error('The additional rights record would replace an existing record.');
        if (Object.keys(entries).length === 0) continue;
        if (!owns(entries, cid) || owns(state.rights[name], cid))
          throw new Error('The additional rights record would replace an existing record.');
        state.rights[name][cid] = entries[cid];
      }
      if (!owns(rightsMaps, 'case_profiles') || !owns(rightsMaps, 'latest'))
        throw new Error('The additional saved rights profile is incomplete.');
      const routes = new Set(['/api/interventions/state/' + cid, '/api/ai-drafts/state/' + cid]);
      if (Object.keys(overlay.responses).length !== routes.size + 1)
        throw new Error('The additional saved case responses are incomplete.');
      for (const [route, value] of Object.entries(overlay.responses)) {
        if (route === stateRoute) continue;
        if (!routes.has(route) || owns(result.responses, route) || value.candidate_id !== cid)
          throw new Error('The additional saved response would replace an existing response.');
        result.responses[route] = value;
      }
      const recommendation = overlay.responses['/api/interventions/state/' + cid].latest;
      const exportRoutes = new Set(['json', 'md'].flatMap(format => [
        '/api/rights/export/' + cid + '?format=' + format,
        '/api/interventions/export/' + recommendation.id + '?format=' + format
      ]));
      if (Object.keys(overlay.exports).length !== exportRoutes.size)
        throw new Error('The additional saved case exports are incomplete.');
      for (const [route, file] of Object.entries(overlay.exports)) {
        if (!exportRoutes.has(route) || owns(result.exports, route)
          || !/^exports\/[A-Za-z0-9_.-]+\.(json|md)$/.test(file))
          throw new Error('The additional saved export would replace an existing export.');
        result.exports[route] = file;
      }
      result.case_count = state.candidates.length;
      if (overlay.snapshot_label) result.snapshot_label = overlay.snapshot_label;
      if (overlay.snapshot_at) result.snapshot_at = overlay.snapshot_at;
      return result;
    });
  const normalize = path => {
    const address = new URL(path, 'https://snapshot.invalid');
    return address.pathname + (address.searchParams.has('format') ? '?format=' + address.searchParams.get('format') : '');
  };
  window.StaticDemo = {
    async request(path, payload) {
      if (payload !== undefined) throw new Error('This published demo is read-only. Use the local app to prepare or save changes.');
      const snapshot = await ready, key = normalize(path);
      if (!owns(snapshot.responses, key)) throw new Error('This operation is not part of the saved demo.');
      return JSON.parse(JSON.stringify(snapshot.responses[key]));
    }
  };

  const writingSelector = '#intake-open,#judgment-import-open,[data-case-tab="edit"],[data-edit-assessment],[data-ai-example],[data-load-intervention],[data-blank-intervention],[data-ai-route],[data-aiRoute]';
  document.addEventListener('submit', event => {
    event.preventDefault();
    if (!['filters','ssp-generate-form'].includes(event.target.id)) event.stopImmediatePropagation();
  }, true);
  document.addEventListener('click', event => {
    if (event.target.closest(writingSelector)) {event.preventDefault();event.stopImmediatePropagation();}
  }, true);

  const hide = node => {if (node) node.dataset.readOnlyHidden = 'true';};
  const clean = snapshot => {
    document.querySelectorAll(writingSelector).forEach(hide);
    document.querySelectorAll('form:not(#filters):not(#ssp-generate-form)').forEach(form => {
      hide(form);
      const wrapper = form.closest('details');
      if (wrapper && (form.dataset.correctionForm !== undefined || form.id.startsWith('intervention-') || ['ai-live-form','ai-import-form','ai-worksheet-form'].includes(form.id))) hide(wrapper);
      if (form.id.startsWith('intervention-')) hide(form.closest('section'));
      if (form.id === 'ai-worksheet-form') hide(form.closest('.panel'));
      if (form.id === 'rights-review-form' && !form.closest('.panel')?.querySelector('.history-item')) hide(form.closest('.panel'));
    });
    document.querySelectorAll('.ai-start-choice').forEach(card => {
      if (card.querySelector('h3')?.textContent === 'Prepare another draft') hide(card);
    });
    const start = document.querySelector('#ai-phase-0 > .panel');
    if (start) {
      const heading = start.querySelector('h2');
      if (heading && heading.textContent !== 'Open a saved draft') heading.textContent = 'Open a saved draft';
      const help = start.querySelector(':scope > .sidebar-copy');
      const text = 'Read the saved draft and its alternatives. New drafting is available in the local app.';
      if (help && help.textContent !== text) help.textContent = text;
      const route = [...start.querySelectorAll('.notice')].find(node => node.textContent.includes('Local model route:'));
      hide(route);
    }
    const banner = document.querySelector('.static-demo-banner');
    if (banner && !banner.dataset.ready) {
      banner.textContent = 'Read-only demo · ' + snapshot.case_count + ' saved cases · snapshot ' + snapshot.snapshot_label + '. Browse evidence and options; fictional strategy generation works here. Editing and saving use the local app.';
      banner.dataset.ready = 'true';
    }
    const collection = document.querySelector('#collection-kind');
    if (collection) {
      const title = collection.querySelector('strong'), help = collection.querySelector('.help');
      const label = 'Saved demo collection · ' + snapshot.case_count + ' cases';
      const description = 'Four public-source cases, one supplied case with redacted passages and one fictional illustration · original preparation and review status retained.';
      if (title && title.textContent !== label) title.textContent = label;
      if (help && help.textContent !== description) help.textContent = description;
    }
    document.querySelectorAll('a[href]').forEach(anchor => {
      const href = anchor.getAttribute('href');
      if (href?.startsWith('/api/')) {
        const file = snapshot.exports[normalize(href)];
        if (file) {anchor.href = new URL(file, base).href;anchor.download = file.split('/').pop();}
        else {anchor.removeAttribute('href');anchor.setAttribute('aria-disabled','true');}
      } else if (href?.startsWith('/rights.html')) anchor.href = new URL(href.slice(1), base).href;
    });
  };
  ready.then(snapshot => {
    const observer = new MutationObserver(() => clean(snapshot));
    observer.observe(document.body, {childList:true,subtree:true});
    clean(snapshot);
  }).catch(() => {});
})();
