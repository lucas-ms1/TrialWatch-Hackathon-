"""Build an entirely invented pending draft example; never calls a provider."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewdesk.draft_contract import schema_for, validate_draft
from reviewdesk.rights import RUBRIC


def fixture():
    candidate = json.loads((ROOT / 'reviewdesk/rights.synthetic.v2.json').read_text(encoding='utf-8'))['candidates'][0]
    passages, links, summaries, chronology, citations = [], [], [], [], []
    for index, claim in enumerate(candidate['claims'], 1):
        pid = 'AP%02d' % index
        locator = {'pdf_page': 1, 'printed_page': None, 'paragraph_or_heading': claim['locator']}
        passages.append({'passage_id': pid, 'source_id': claim['source_id'], 'quote': claim['excerpt'], 'locator': locator,
            'surrounding_context_note': 'Entirely invented software fixture; no source was retrieved.',
            'date_roles': {'invented_hearing_date': claim['event_date']}, 'uncertainty': 'Fictional account only.'})
        links.append({'proposition_id': claim['id'], 'support_passage_ids': [pid]})
        summaries.append({'text': claim['text'], 'proposition_ids': [claim['id']], 'passage_ids': [pid], 'limits': 'Fictional attributed account; no authentication. Repeated reporting is not independent corroboration.'})
        chronology.append({'event': 'Invented account at the fictional hearing: ' + claim['text'], 'date': claim['event_date'], 'date_role': 'invented hearing date',
            'proposition_ids': [claim['id']], 'passage_ids': [pid], 'limits': 'Fixture chronology is not causation or a real legal finding.'})
        citations.append({'passage_id': pid, 'source_id': claim['source_id'], 'quote': claim['excerpt'], 'locator': json.dumps(locator), 'attribution': claim['attribution']})
    stage_names = ['preliminary_investigation', 'criminal_charge_notice', 'arrest_information']
    stds = [{'passage_id': 'STD-SYNTH-' + str(i + 1), 'source_id': 'synthetic_standard', 'quote': 'Invented standard-review question for software demonstration only.',
             'locator': {'pdf_page': 1, 'printed_page': None, 'paragraph_or_heading': stage}} for i, stage in enumerate(stage_names)]
    supplied = {'format': 'part2-clean-input/1', 'task': 'Prepare an entirely fictional contested-notice worksheet.',
        'output_request': 'Pending attributed summary, competing account, unresolved stages and two bounded alternatives.',
        'cutoff': {'latest_selected_document_date': '2026-09-12', 'current_status_verified': False, 'current_status': None},
        'units': {'dossier': 'Invented software fixture', 'persons': 'Fictional person only'},
        'source_metadata': [{'source_id': s['id'], 'title': s['title'], 'publisher': s['publisher'], 'url': s['url'], 'publication_date': s['publication_date'],
            'language': s['language'], 'translation_status': s['translation_status'], 'source_dependence': s['lineage_note']} for s in candidate['sources']],
        'factual_passages': passages, 'identifier_links': links,
        'standards': {'rubric_version': RUBRIC['version'], 'stage_guards': [{'scope': stage, 'passage_ids': [stds[i]['passage_id']], 'status': 'pending qualified legal review'} for i, stage in enumerate(stage_names)],
            'source_metadata': [], 'passages': stds, 'version_limits': 'Invented stage-question snippet; no real standard is asserted by this fixture.', 'qualified_legal_review': 'pending'},
        'rubric': deepcopy(RUBRIC), 'constraints': ['Entirely synthetic', 'No model call', 'No approval or executed action', 'Keep all twenty mappings null'],
        'review_status': 'human_review_pending', 'prior_exposure_limit': 'Software fixture; no independent substantive evaluation.'}
    options = []
    for oid, disposition, route in [('verify_records', 'prepare_verify', 'Inspect supplied fictional records locally'), ('defer_public_route', 'defer', 'Defer a specified fictional public advocacy route')]:
        options.append({'option_id': oid, 'proposed_disposition': disposition, 'objective': route, 'beneficiaries': 'Invented person; no real beneficiary.', 'route': route,
            'actor_authority': 'Local fixture preparation only; external authority unknown.', 'support_passage_ids': ['AP01', 'AP04'], 'contrary_passage_ids': ['AP03'],
            'urgency': 'Unknown; no current deadline established.', 'opportunity': 'Unknown; no available external route established.', 'feasibility': 'Local preparation can be demonstrated; outside access unknown.',
            'potential_harm': 'Unknown; missing evidence does not establish safety.', 'unknowns': ['Original service receipt, stage and current status unknown.', 'Affected person preferences and current external authority unknown.'],
            'prerequisites': ['Inspect supplied support and competing passages; legal review remains separate.'], 'next_step': 'Compare retained fictional passages locally; no outreach or new collection.',
            'reconsideration_trigger': 'Relevant record, qualified stage review and properly established preferences become available through a separately authorized route.', 'execution_status': 'proposal_only'})
    draft = {'schema_version': 'part2-pending-draft/1', 'dossier_id': candidate['id'], 'review_status': 'human_review_pending', 'rubric_version': RUBRIC['version'],
        'summary': summaries, 'chronology': chronology, 'citations': citations,
        'stage_questions': [{'stage': stage, 'factual_passage_ids': ['AP01', 'AP03'], 'standard_passage_ids': [stds[i]['passage_id']],
            'questions': ['Which stage, event-date law and exception would apply if this were a real case?'], 'applicability_status': 'unresolved',
            'missing_facts': ['Original stage and notice/service records.'], 'limits': 'Invented software question; not a legal assessment.'} for i, stage in enumerate(stage_names)],
        'gaps': [{'question': 'When and how were charge details delivered?', 'passage_ids': ['AP01', 'AP03'], 'why_it_matters': 'The fictional accounts compete; no service receipt resolves them.', 'next_check': 'Compare only supplied fictional text; keep original-record need unknown.'}],
        'options': options, 'assessment_mappings': [{'dimension_id': d['id'], 'mapping': None} for d in RUBRIC['dimensions']],
        'limitations': ['Entirely invented; no model request, real source, legal finding, efficacy claim or action.'],
        'human_checkpoint': {'source_review_ids': [l['proposition_id'] for l in links] + [p['passage_id'] for p in passages],
            'request': 'A real reviewer may report inspecting exact fictional passages; software tests do not supply that review.', 'legal_review_status': 'separate_pending', 'approval': None}}
    schema = schema_for(candidate['id'], supplied)
    validate_draft(candidate['id'], draft, supplied, candidate, schema)
    raw = lambda obj: json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    return {'candidate_id': candidate['id'], 'material_type': 'synthetic', 'description': 'Entirely invented pending draft; no live inference or human approval.',
        'import_payload': {'expected_revision': 0, 'author': 'Synthetic preparation label', 'origin': 'synthetic_fixture',
            'draft_json': raw(draft), 'model_input_json': raw(supplied), 'schema_json': raw(schema), 'receipt_json': None}}


if __name__ == '__main__':
    destination = ROOT / 'examples/ai-draft.synthetic.json'
    destination.write_text(json.dumps(fixture(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Built invented pending draft fixture:', destination)
