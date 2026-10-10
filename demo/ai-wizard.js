'use strict';

// Presentation only: reuse the desk's rendered records, forms and save handlers.
(() => {
  const positions = new Map();
  const titles = ['Open saved draft', 'Read draft', 'Evidence and gaps', 'Compare alternatives'];
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const button = (text, action, value) => {
    const node = element('button', 'button', text);
    node.type = 'button';
    node.dataset[action] = value;
    return node;
  };

  window.mountAiWizard = ({item, record, evidenceHtml, assessed, proposal}) => {
    const layout = document.querySelector('#case-view .case-layout');
    const main = layout?.querySelector('.case-main');
    if (!main || main.querySelector('.ai-wizard')) return;
    const panels = [...main.children];
    const start = panels[0];
    const draft = main.querySelector(':scope > .ai-record');
    const sources = main.querySelector(':scope > #ai-source-passages');
    const standards = main.querySelector(':scope > .ai-standards');
    const options = main.querySelector(':scope > #ai-draft-options');
    const sidebar = layout.querySelector('.case-sidebar');
    const review = sidebar?.querySelector('.panel');
    const preparation = sidebar?.querySelector('#ai-worksheet-form')?.closest('.panel');
    const historyPanel = panels.find(p => p.querySelector(':scope > h2')?.textContent === 'Preserved draft revisions');
    const previous = positions.get(item.id);
    let step = previous?.step ?? 0;
    if (previous && previous.recordId !== (record?.id || null) && record) step = 1;
    if (!record) step = 0;
    if (!previous) {
      const requested = Number(new URL(location.href).searchParams.get('draftStep'));
      if (record && Number.isInteger(requested) && requested >= 1 && requested <= 4) step = requested - 1;
    }

    const shell = element('div', 'ai-wizard');
    const header = element('section', 'panel ai-wizard-header');
    header.append(element('p', 'eyebrow', 'AI DRAFT'), element('h2', '', 'Pending AI draft'));
    const nav = element('nav', 'ai-step-nav');
    nav.setAttribute('aria-label', 'Pending AI draft steps');
    const steps = element('ol', 'ai-steps');
    titles.forEach((title, index) => {
      const li = element('li');
      const control = button('', 'aiStep', String(index));
      control.append(element('span', 'ai-step-number', String(index + 1)), element('span', '', title));
      control.setAttribute('aria-controls', 'ai-phase-' + index);
      control.disabled = !record && index > 0;
      li.append(control);
      steps.append(li);
    });
    nav.append(steps);
    const position = element('p', 'sidebar-copy ai-step-position');
    position.setAttribute('aria-live', 'polite');
    header.append(nav, position);
    // New request errors remain visible on the step where the user made the request.
    [...start.querySelectorAll(':scope > .error, :scope > [role="status"]')].forEach(node => header.append(node));
    shell.append(header);
    const phases = titles.map((title, index) => {
      const phase = element('section', 'ai-phase');
      phase.id = 'ai-phase-' + index;
      phase.setAttribute('aria-label', title);
      shell.append(phase);
      return phase;
    });
    start.querySelector('h2').textContent = 'Open or prepare a draft';
    start.querySelector('.sidebar-copy').textContent = 'Open a saved draft, import a completed bundle, or prepare a new draft when available.';
    start.querySelector('.eyebrow')?.remove();
    const choices = element('div', 'ai-start-choices');
    const savedChoice = element('article', 'ai-start-choice');
    savedChoice.append(element('h3', '', 'Read a saved draft'), element('p', 'sidebar-copy', record ? 'Saved revision ' + record.revision + ' · human review pending' : 'No draft has been saved for this case.'));
    const openSaved = button('Open saved draft →', 'aiStep', '1');
    openSaved.classList.add('primary');
    openSaved.disabled = !record;
    const reload = button('Reload saved state', 'aiReopen', '');
    reload.disabled = !!header.querySelector('[role="status"]');
    savedChoice.append(openSaved, reload);
    choices.append(savedChoice);
    const tools = start.querySelector('#ai-live-form')?.closest('details');
    const importing = start.querySelector('#ai-import-form')?.closest('details');
    if (!record && tools) {
      tools.querySelector('[type="submit"]').disabled = true;
      tools.append(element('p', 'help', 'Import a validated draft bundle first to supply the clean input for this generation route.'));
    }
    const newChoice = element('article', 'ai-start-choice');
    newChoice.append(element('h3', '', 'Prepare another draft'), element('p', 'sidebar-copy', 'Import the files from a completed run, or inspect the local generation route.'));
    newChoice.append(button('Import completed draft', 'aiRoute', 'import'), button('New draft / availability', 'aiRoute', 'live'));
    choices.append(newChoice);
    start.querySelector('h2').after(choices);
    phases[0].append(start);
    if (historyPanel) {
      const history = element('details', 'panel ai-draft-history');
      history.append(element('summary', '', 'Earlier saved draft revisions'), historyPanel);
      phases[0].append(history);
    }
    if (draft) {
      draft.querySelector('h2').textContent = 'Attributed draft';
      phases[1].append(draft);
      const mappings = draft.querySelector('.ai-mappings')?.closest('details');
      if (mappings) {
        mappings.open = false;
        mappings.querySelector('.sidebar-copy').textContent = 'These are the preserved mappings in this draft. The separate rights assessment may have a newer revision.';
        const mappingPanel = element('section', 'panel');
        mappingPanel.append(element('h2', '', 'Original draft mappings'), mappings);
        phases[2].append(mappingPanel);
      }
    }
    panels.filter(p => ['Chronology', 'Stage questions', 'Gaps and next checks'].includes(p.querySelector(':scope > h2')?.textContent)).forEach(p => {
      const heading = p.querySelector('h2');
      const detail = element('details', 'panel ai-phase-detail');
      detail.append(element('summary', '', heading.textContent));
      heading.remove();
      p.querySelectorAll(':scope > details').forEach(row => row.open = false);
      detail.append(p);
      phases[2].append(detail);
    });
    if (options) {
      options.querySelector('h2').textContent = 'Bounded alternatives';
      options.querySelectorAll('.strategy-option').forEach(option => {
        const detail = element('details', 'source-record');
        detail.append(element('summary', '', 'Evidence, conditions and next steps'));
        [...option.children].slice(3).forEach(child => detail.append(child));
        option.append(detail);
      });
      phases[3].append(options);
    }
    if (preparation) {
      const selection = preparation.querySelector('[name="selected_option_id"]');
      if (selection && previous?.selectedOption && [...selection.options].some(o => o.value === previous.selectedOption)) selection.value = previous.selectedOption;
      if (assessed) {
        preparation.querySelector('form').remove();
        preparation.querySelector('.sidebar-copy').textContent = 'A rights assessment is already saved. Preparing a proposal based on that assessment uses the Advocacy / intervention worksheet.';
        preparation.append(element('p', 'help', 'The saved draft and its alternatives remain available here.'));
      }
      phases[3].append(preparation);
    }
    if (proposal) {
      const savedProposal = element('section', 'panel ai-saved-proposal');
      savedProposal.append(element('h2', '', 'Saved proposal'), element('p', 'sidebar-copy', 'Revision ' + proposal.revision + ' · ' + (proposal.stale ? 'stale dependencies' : String(proposal.review_status || 'human review pending').replaceAll('_', ' '))));
      if (proposal.stale) savedProposal.append(element('p', 'notice warning', 'Dependencies changed. The earlier proposal is retained.'));
      const downloads = element('div', 'export-actions');
      [['md', 'Cited proposal ↓'], ['json', 'Proposal JSON ↓']].forEach(([format, title]) => {
        const a = element('a', 'button', title);
        a.href = '/api/interventions/export/' + encodeURIComponent(proposal.id || proposal.recommendation_id) + '?format=' + format;
        a.download = '';
        downloads.append(a);
      });
      savedProposal.append(downloads);
      phases[3].append(savedProposal);
    }
    if (review) {
      review.querySelectorAll('[data-case-tab]').forEach(node => node.remove());
      const reviews = element('details', 'panel ai-review-details');
      reviews.append(element('summary', '', 'Draft status and source-summary review scope'), review);
      phases[1].append(reviews);
    }

    // Citations open a read-only detail window without switching the active case tab.
    const dialog = element('dialog', 'ai-evidence-dialog');
    dialog.setAttribute('aria-labelledby', 'ai-evidence-title');
    const dialogHeader = element('div', 'dialog-heading');
    const dialogTitle = element('h2', '', 'Cited evidence');
    dialogTitle.id = 'ai-evidence-title';
    dialogHeader.append(dialogTitle, button('Close evidence', 'aiCloseEvidence', ''));
    const sourceBundle = element('div', 'ai-cited-sources');
    if (sources) sourceBundle.append(sources);
    if (standards) sourceBundle.append(standards);
    const claimsBundle = element('div', 'ai-cited-claims');
    claimsBundle.innerHTML = evidenceHtml;
    claimsBundle.querySelectorAll('form').forEach(form => form.closest('details')?.remove());
    dialog.append(dialogHeader, sourceBundle, claimsBundle);
    shell.append(dialog);

    const footer = element('div', 'panel ai-wizard-actions');
    const back = button('← Back', 'aiStep', '0');
    const next = button('Next →', 'aiStep', '1');
    next.classList.add('primary');
    const evidenceButton = button('View cited evidence', 'aiEvidence', '');
    evidenceButton.disabled = !record;
    footer.append(back, evidenceButton, next);
    shell.append(footer);
    main.replaceChildren(shell);
    layout.classList.add('ai-wizard-layout');
    sidebar.hidden = true;

    const showStep = (value, focus = true) => {
      step = Math.max(0, Math.min(3, value));
      if (!record) step = 0;
      phases.forEach((phase, index) => phase.hidden = index !== step);
      steps.querySelectorAll('button').forEach((control, index) => {
        if (index === step) control.setAttribute('aria-current', 'step');
        else control.removeAttribute('aria-current');
      });
      position.textContent = 'Step ' + (step + 1) + ' of 4 · ' + titles[step];
      back.disabled = step === 0;
      back.dataset.aiStep = String(step - 1);
      next.dataset.aiStep = String(step === 3 ? 0 : step + 1);
      next.textContent = step === 3 ? 'Back to draft choices' : 'Next: ' + titles[step + 1] + ' →';
      next.disabled = !record;
      positions.set(item.id, {...positions.get(item.id), step, recordId: record?.id || null});
      const address = new URL(location.href);
      address.searchParams.set('draftStep', String(step + 1));
      history.replaceState(null, '', address);
      if (focus) {
        const heading = phases[step].querySelector('h2');
        heading?.setAttribute('tabindex', '-1');
        heading?.focus({preventScroll:true});
        header.scrollIntoView({block:'start', behavior:'smooth'});
      }
    };
    const showEvidence = (target, claims = false) => {
      sourceBundle.hidden = claims;
      claimsBundle.hidden = !claims;
      dialogTitle.textContent = claims ? 'Current intake claims' : 'Draft source passages and legal excerpts';
      if (!dialog.open) dialog.showModal();
      if (target) {
        for (let parent = target.parentElement; parent && parent !== dialog; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
        target.setAttribute('tabindex', '-1');
        target.focus({preventScroll:true});
        target.scrollIntoView({block:'start'});
      } else dialog.scrollTop = 0;
    };
    shell.addEventListener('click', event => {
      const control = event.target.closest('button, a');
      if (!control) return;
      if (control.dataset.aiStep !== undefined) {
        event.stopPropagation();
        showStep(Number(control.dataset.aiStep));
      } else if (control.dataset.aiRoute) {
        const detail = control.dataset.aiRoute === 'import' ? importing : tools;
        if (detail) {detail.open = true; detail.scrollIntoView({block:'nearest'});}
      } else if (control.dataset.aiCloseEvidence !== undefined) dialog.close();
      else if (control.dataset.aiEvidence !== undefined) showEvidence();
      else if (control.dataset.aiAnchor || control.dataset.claimLink) {
        const id = control.dataset.aiAnchor || 'claim-' + control.dataset.claimLink;
        const target = document.getElementById(id);
        if (!target || (!dialog.contains(target) && !control.dataset.claimLink)) return;
        event.preventDefault();
        event.stopPropagation();
        showEvidence(target, !!control.dataset.claimLink);
      }
    }, true);
    shell.addEventListener('change', event => {
      if (event.target.matches('#ai-worksheet-form [name="selected_option_id"]')) positions.set(item.id, {...positions.get(item.id), selectedOption:event.target.value});
    });
    showStep(step, false);
  };
})();
