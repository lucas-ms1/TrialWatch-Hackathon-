'use strict';

(() => {
  const base = new URL('.', document.currentScript.src);
  const ready = fetch(new URL('data/snapshot.json', base), {cache:'no-store'})
    .then(response => {if (!response.ok) throw new Error('The saved demo could not be loaded. Refresh the page.'); return response.json();});
  const normalize = path => {
    const address = new URL(path, 'https://snapshot.invalid');
    return address.pathname + (address.searchParams.has('format') ? '?format=' + address.searchParams.get('format') : '');
  };
  window.StaticDemo = {
    async request(path, payload) {
      if (payload !== undefined) throw new Error('This published demo is read-only. Use the local app to prepare or save changes.');
      const snapshot = await ready, key = normalize(path);
      if (!Object.prototype.hasOwnProperty.call(snapshot.responses, key)) throw new Error('This operation is not part of the saved demo.');
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
      const description = 'Four public-source cases and one fictional illustration · original preparation and review status retained.';
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
