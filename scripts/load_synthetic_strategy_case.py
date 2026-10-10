"""Add the original fictional worked case to a fresh/local synthetic starter."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reviewdesk.server import ReviewStore


def load_case(store):
    fixture=json.loads((ROOT/'examples/synthetic-strategy.fixture.json').read_text(encoding='utf-8'))
    candidate=deepcopy(fixture['candidate'])
    if fixture.get('synthetic') is not True or candidate['material_type']!='synthetic':
        raise ValueError('The demonstration must remain fictional.')
    if any('example.invalid' not in source['url'] for source in candidate['sources']+fixture['context']['sources']):
        raise ValueError('The demonstration unexpectedly contains a real source.')
    cid=candidate['id']
    with store.connection() as connection:
        if cid in store.candidates(connection):
            raise ValueError('The fictional case already exists. Its saved records were left intact.')
    dimensions=[{k:v for k,v in d.items() if k!='score'} for d in fixture['assessment']['dimensions']]
    texts={s['id']:'\n\n'.join(c['excerpt'] for c in candidate['claims'] if c['source_id']==s['id']) for s in candidate['sources']}
    store.rights.intake({'schema_version':'rights-intake/2','candidate':candidate,'source_texts':texts,'prepared_mappings':None})
    store.rights.save(cid,{'expected_revision':0,'expected_evidence_revision':0,'rubric_version':fixture['assessment']['rubric_version'],'analyst':'Original fictional demonstration preparation','preparation':'synthetic_prepared','dimensions':dimensions})
    fields=('schema_version','author','origin','evidence_cutoff','sources','claims','unknowns','cluster','comparables')
    context={k:deepcopy(fixture['context'][k]) for k in fields}
    context['expected_revision']=0
    context['source_texts']={s['id']:'\n\n'.join(c['excerpt'] for c in context['claims'] if c['source_id']==s['id']) for s in context['sources']}
    store.interventions.context(cid,context)
    return cid


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',type=Path,default=ROOT/'reviewdesk/rights.synthetic.v2.json')
    parser.add_argument('--state-dir',type=Path,default=ROOT/'data/processed/connecteddesk-v2')
    args=parser.parse_args()
    store=ReviewStore(args.seed,args.state_dir)
    try:
        cid=load_case(store)
    except ValueError as error:
        parser.exit(1,str(error)+'\n')
    print('Loaded '+cid+' with twenty pending fictional dimensions and context. No human review or proposal was saved.')
