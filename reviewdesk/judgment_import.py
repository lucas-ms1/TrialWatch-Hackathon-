"""Deterministic, unsaved LawPhil judgment previews over supplied local content.

No retrieval, model request, factual extraction, scoring, review or storage occurs.
Selected paragraphs remain quotations with derived locators and supplied metadata.
"""
from copy import deepcopy
from datetime import date, datetime
import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit

from .server import APIError, MAX_BODY, encoded, iso_date, public_url, require_fields, string, validate_candidate
from .rights import RightsService

REQUEST_VERSION = 'judgment-import/1'
PREVIEW_VERSION = 'judgment-preview/1'
PROVIDER = 'lawphil'
SYNTHETIC_PROVIDER = 'synthetic_fixture'
PUBLISHER = 'LawPhil / Arellano Law Foundation'
COURT = 'Supreme Court of the Philippines'
SYNTHETIC_PUBLISHER = 'Synthetic judgment fixture'
SYNTHETIC_COURT = 'Fictional Court'
LICENSE_URL = 'https://lawphil.net/copyright.html'
LICENSE_LABEL = 'Attribution-NonCommercial 4.0 (as stated by LawPhil)'
COLLECTION_NOTICE = 'The collection is licensed under a Creative Commons Attribution-Non Commercial 4.0 Philippine license.'
MAX_RAW_BYTES = 750000
MAX_SOURCE_CHARS = 500000
MAX_PASSAGES = 1000
MAX_SELECTED = 50
MAX_EXCERPT_CHARS = 12000
DOCUMENT_FIELDS = {'document_id', 'title', 'url', 'publisher', 'publication_date', 'decision_date',
                   'retrieved_at', 'language', 'translation_status', 'court', 'country', 'citations', 'proceeding_id'}
OPTIONAL_DOCUMENT_FIELDS = {'raw_sha256', 'decoded_encoding'}


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _optional_string(value, field, maximum=2000):
    return None if value is None else string(value, field, maximum)


def _timestamp(value):
    if value is None:
        return None
    value = string(value, 'retrieved_at', 100)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if 'T' not in value or parsed.utcoffset() is None:
            raise ValueError()
    except ValueError as exc:
        raise APIError('retrieved_at needs a timezone-qualified timestamp or null.') from exc
    return value


def _decision_date(value):
    """Preserve partial decision dates; never invent an exact day or event date."""
    if value is None:
        return {'raw': None, 'exact': None, 'precision': 'unknown'}
    value = string(value, 'decision_date', 10)
    if re.fullmatch(r'\d{4}', value):
        try:
            date(int(value), 1, 1)
        except ValueError as exc:
            raise APIError('Invalid decision year.') from exc
        return {'raw': value, 'exact': None, 'precision': 'year'}
    if re.fullmatch(r'\d{4}-\d{2}', value):
        try:
            date(int(value[:4]), int(value[5:]), 1)
        except ValueError as exc:
            raise APIError('Invalid decision month.') from exc
        return {'raw': value, 'exact': None, 'precision': 'month'}
    return {'raw': iso_date(value, 'decision_date'), 'exact': value, 'precision': 'day'}


def _lawphil_url(value):
    value = public_url(value)
    parts = urlsplit(value)
    if (parts.scheme != 'https' or parts.hostname not in {'lawphil.net', 'www.lawphil.net'} or parts.port not in {None, 443}
            or parts.query or parts.fragment
            or not re.fullmatch(r'/judjuris/[A-Za-z0-9_/-]+\.html', parts.path)):
        raise APIError('This adapter accepts only canonical HTTPS lawphil.net or www.lawphil.net/judjuris/*.html document URLs.', 400, 'judgment_provider_scope')
    return value


class _Paragraphs(HTMLParser):
    """Extract visible paragraph text without evaluating markup or instructions."""
    BLOCKS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre'}
    IGNORE = {'script', 'style', 'nav', 'header', 'footer', 'form', 'button', 'select', 'option',
              'iframe', 'object', 'embed', 'svg', 'canvas', 'noscript', 'template', 'head'}
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
    NAV_MARKERS = {'navigation', 'navbar', 'nav', 'menu', 'menus', 'header', 'footer', 'site-header', 'site-footer', 'breadcrumbs'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.tag = None
        self.parts = []
        self.references = []
        self.anchor = None
        self.ignored = []
        self.license_notices = []

    def _flush(self):
        if self.tag is None:
            return
        text = re.sub(r'\s+', ' ', ''.join(self.parts)).strip()
        if text:
            self.rows.append({'text': text, 'tag': self.tag, 'footnote_refs': deepcopy(self.references)})
        self.tag, self.parts, self.references, self.anchor = None, [], [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.ignored:
            if tag not in self.VOID:
                self.ignored.append(tag)
            return
        markers = set((attrs.get('id', '') + ' ' + attrs.get('class', '')).lower().split())
        if tag in self.IGNORE or markers & self.NAV_MARKERS or attrs.get('aria-hidden') == 'true':
            if tag not in self.VOID:
                self.ignored = [tag]
            return
        if tag in self.BLOCKS:
            self._flush()
            self.tag = tag
        elif tag == 'br' and self.tag:
            self.parts.append(' ')
        if tag == 'a' and self.tag:
            target = attrs.get('href', '')
            if not target.startswith('#') and (attrs.get('class') == 'nt' or attrs.get('name', '').startswith('fnt')):
                target = '#' + (attrs.get('name') or attrs.get('id') or 'footnote-reference')
            if target.startswith('#'):
                self.anchor = {'target': target[:300], 'text': ''}

    def handle_endtag(self, tag):
        if self.ignored:
            if tag in self.ignored:
                del self.ignored[len(self.ignored) - 1 - self.ignored[::-1].index(tag):]
            return
        if tag == 'a' and self.anchor is not None:
            if self.anchor['text'].strip():
                self.references.append(self.anchor)
            self.anchor = None
        if tag == self.tag:
            self._flush()

    def handle_data(self, data):
        if not self.ignored and self.tag:
            self.parts.append(data)
            if self.anchor is not None:
                self.anchor['text'] += data

    def handle_comment(self, data):
        if re.search(r'copyright|creative commons|attribution.noncommercial', data, re.I):
            self.license_notices.append({'origin': 'embedded_html_comment', 'text': data.strip()})

    def finish(self):
        self.close()
        self._flush()
        return self.rows


def _rows(document):
    has_html, has_text = 'html' in document, 'text' in document
    if has_html == has_text:
        raise APIError('Supply exactly one local html or text field.')
    raw = document['html'] if has_html else document['text']
    # Check raw size before parsing, without silently truncating it.
    if not isinstance(raw, str) or not raw.strip() or len(raw.encode('utf-8')) > MAX_RAW_BYTES:
        raise APIError('Supply nonempty local judgment content of at most 750000 UTF-8 bytes.', 413, 'judgment_size')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in raw):
        raise APIError('Judgment content contains unsupported control characters.')
    if has_html:
        parser = _Paragraphs()
        try:
            parser.feed(raw)
            rows = parser.finish()
        except (ValueError, RecursionError) as exc:
            raise APIError('Could not parse the supplied HTML paragraphs.') from exc
        method = 'HTML paragraph extraction; scripts/styles/navigation excluded; entities decoded and whitespace normalized. Numbering is derived, not official.'
    else:
        rows = [{'text': re.sub(r'\s+', ' ', p).strip(), 'tag': 'text', 'footnote_refs': []}
                for p in re.split(r'\n\s*\n', raw.replace('\r\n', '\n').replace('\r', '\n')) if p.strip()]
        method = 'Supplied text split on blank lines; whitespace normalized. Numbering is derived, not official.'
    if not rows:
        raise APIError('No visible judgment paragraphs were found. Supply paragraph text; do not substitute navigation or script contents.')
    if len(rows) > MAX_PASSAGES:
        raise APIError('The supplied document exceeds the 1000-paragraph preview bound.', 413, 'judgment_size')
    source_text = '\n\n'.join(row['text'] for row in rows)
    if len(source_text) > MAX_SOURCE_CHARS:
        raise APIError('Clean source text exceeds the structured-intake 500000-character limit.', 413, 'judgment_size')
    return raw, rows, source_text, method, deepcopy(parser.license_notices) if has_html else []


def _inspect(payload, existing_candidates):
    if not isinstance(payload, dict) or set(payload) - {'schema_version', 'provider', 'document', 'selected_passage_ids'}:
        raise APIError('Unexpected judgment preview fields.')
    provider = payload.get('provider')
    if payload.get('schema_version') != REQUEST_VERSION or not isinstance(provider, str) or provider not in {PROVIDER, SYNTHETIC_PROVIDER}:
        raise APIError('Only the judgment-import/1 LawPhil pilot or explicit synthetic fixture is supported.', 400, 'judgment_provider_scope')
    synthetic = provider == SYNTHETIC_PROVIDER
    document = payload.get('document')
    if not isinstance(document, dict) or not DOCUMENT_FIELDS <= set(document) or set(document) - (DOCUMENT_FIELDS | OPTIONAL_DOCUMENT_FIELDS | {'html', 'text'}):
        raise APIError('Judgment document fields differ from the permitted bundle contract.')
    metadata = {key: deepcopy(document[key]) for key in DOCUMENT_FIELDS}
    metadata['document_id'] = string(metadata['document_id'], 'document_id', 240)
    metadata['title'] = string(metadata['title'], 'title', 1000)
    metadata['url'] = public_url(metadata['url']) if synthetic else _lawphil_url(metadata['url'])
    if synthetic and (urlsplit(metadata['url']).scheme != 'https' or urlsplit(metadata['url']).hostname != 'example.invalid' or urlsplit(metadata['url']).port is not None):
        raise APIError('Synthetic fixture sources must use HTTPS example.invalid URLs.', 400, 'judgment_provider_scope')
    if metadata['publisher'] != (SYNTHETIC_PUBLISHER if synthetic else PUBLISHER) or metadata['court'] != (SYNTHETIC_COURT if synthetic else COURT) or metadata['country'] != 'Philippines':
        raise APIError('Provider/publisher/court/country metadata must match the explicit Philippine LawPhil pilot.', 400, 'judgment_provider_scope')
    metadata['publication_date'] = iso_date(metadata['publication_date'], 'publication_date')
    decision = _decision_date(metadata['decision_date'])
    metadata['retrieved_at'] = _timestamp(metadata['retrieved_at'])
    metadata['language'] = string(metadata['language'], 'language', 100)
    metadata['translation_status'] = string(metadata['translation_status'], 'translation_status', 1000)
    metadata['proceeding_id'] = _optional_string(metadata['proceeding_id'], 'proceeding_id', 1000)
    if not isinstance(metadata['citations'], list) or len(metadata['citations']) > 20:
        raise APIError('citations must be a list of at most twenty supplied citation strings.')
    metadata['citations'] = [string(c, 'citation', 1000) for c in metadata['citations']]
    if len(metadata['citations']) != len(set(metadata['citations'])):
        raise APIError('Repeated supplied citation.')
    supplied_raw_sha = document.get('raw_sha256')
    if supplied_raw_sha is not None and (not isinstance(supplied_raw_sha, str) or not re.fullmatch(r'[a-f0-9]{64}', supplied_raw_sha)):
        raise APIError('raw_sha256 must be a supplied lowercase SHA256 digest or null.')
    decoded_encoding = _optional_string(document.get('decoded_encoding'), 'decoded_encoding', 100)
    raw, rows, source_text, method, embedded_notices = _rows(document)
    text_sha = _sha(source_text)
    identity_url = metadata['url'].replace('https://www.lawphil.net/', 'https://lawphil.net/', 1) if not synthetic else metadata['url']
    document_key = _sha(provider + '\n' + identity_url)[:24]
    candidate_id = 'judgment_' + document_key + '_' + text_sha[:16]
    source_id = 'judgment_source_' + document_key
    identity = {'document_key': document_key, 'candidate_id': candidate_id, 'source_id': source_id,
        'provider_document_id': metadata['document_id'], 'document_url': metadata['url'], 'text_version_sha256': text_sha,
        'proceeding_id': metadata['proceeding_id'], 'proceeding_identity_status': 'supplied identifier; not authenticated' if metadata['proceeding_id'] else 'unknown',
        'unit': 'One source-document grouping; not an authenticated distinct-case or defendant count.', 'persons': 'not extracted'}
    passages, section = [], 'Judgment text'
    for index, row in enumerate(rows, 1):
        text = row['text']
        if row['tag'].startswith('h') or (len(text) <= 150 and re.fullmatch(r'(?:[A-Z][A-Z .,-]* )?OPINION', text)):
            section = text
        attribution = ('Quotation from a wholly fictional judgment fixture; no real court document.' if synthetic else
                       'Quotation from ' + metadata['court'] + ' judgment as reproduced by LawPhil; passage type not classified.')
        passages.append({'id': 'JP%04d' % index, 'number': index, 'text': text,
            'locator': ('Derived HTML paragraph ' if 'html' in document else 'Derived text paragraph ') + str(index) + ' (not an official paragraph number)',
            'section': section, 'footnote_refs': deepcopy(row['footnote_refs']), 'attribution': attribution,
            'selectable': len(text) <= MAX_EXCERPT_CHARS,
            'selection_note': None if len(text) <= MAX_EXCERPT_CHARS else 'Paragraph exceeds the 12000-character claim excerpt bound; it has not been truncated.'})
    exact, same_document = [], []
    if not isinstance(existing_candidates, (list, tuple)):
        raise APIError('existing_candidates must be supplied as candidate records.')
    for candidate in existing_candidates:
        if not isinstance(candidate, dict):
            raise APIError('Invalid existing candidate record.')
        if candidate.get('id') == candidate_id:
            exact.append(candidate_id)
        elif any(s.get('url') == metadata['url'] or s.get('id') == source_id for s in candidate.get('sources', []) if isinstance(s, dict)):
            same_document.append(candidate.get('id'))
    permission = {'provider': provider, 'source_url': metadata['url'], 'license_label': 'MIT (original fictional fixture)' if synthetic else LICENSE_LABEL,
        'license_url': None if synthetic else LICENSE_URL, 'scope': 'Original synthetic software fixture.' if synthetic else 'Noncommercial local three-document pilot; attribution retained.',
        'policy_check': 'Acquisition/policy check belongs to the permitted upstream caller; this local parser performs no access or policy verification.',
        'embedded_notices': embedded_notices, 'collection_notice_separate_from_embedded': not synthetic,
        'collection_notice': None if synthetic else {'text': COLLECTION_NOTICE, 'url': LICENSE_URL},
        'notice_version_difference': bool(not synthetic and any(re.search(r'NonCommercial\s+3\.0', n['text'], re.I) for n in embedded_notices)),
        'public_package_included': synthetic}
    warnings = ['Document metadata are supplied, not independently verified.',
                'Selected passages are quotations; party claims, court findings and opinion roles need source review.',
                'Decision, publication, retrieval and underlying event dates remain separate. Current case status is unknown.',
                'Rights mappings remain null; advocacy context and any assessed rights require their own evidence/review.']
    if metadata['proceeding_id'] is None:
        warnings.append('Proceeding identifier is unknown; no document/case/person merge was performed.')
    if decision['precision'] != 'day':
        warnings.append('Decision date is ' + decision['precision'] + '; no exact date was invented.')
    if metadata['publication_date'] is None:
        warnings.append('Publication date is unknown; the decision date was not substituted for it.')
    if metadata['retrieved_at'] is None:
        warnings.append('Retrieval time is unknown; no web retrieval is claimed by this supplied-content preview.')
    if exact:
        warnings.append('This exact document/text version is already represented; reopen it instead of importing a duplicate.')
    if same_document:
        warnings.append('A different text version or grouping for this document URL already exists; compare it before treating this as a new case.')
    if permission['notice_version_difference']:
        warnings.append('Embedded page notice states Attribution-NonCommercial 3.0; current collection notice states 4.0. Both notices are retained separately; no version is silently relabelled.')
    return {'schema_version': PREVIEW_VERSION, 'provider': provider, 'material_type': 'synthetic' if synthetic else 'manual_intake',
        'document': {**metadata, 'decision_date_detail': decision, 'source_text': source_text},
        'passages': passages, 'identity': identity, 'permission': permission,
        'provenance': {'adapter_version': 'lawphil-local-preview/1', 'raw_content_sha256': _sha(raw),
            'raw_content_hash_role': 'Supplied decoded content re-encoded as UTF-8, before HTML cleaning.',
            'original_bytes_sha256_supplied': supplied_raw_sha, 'decoded_encoding_supplied': decoded_encoding,
            'source_text_sha256': text_sha, 'normalization': method, 'metadata_origin': 'supplied bundle',
            'raw_content_included': False, 'network_requests': 0, 'model_requests': 0, 'saved': False},
        'duplicate': {'exact': bool(exact), 'candidate_ids': exact, 'same_document_candidate_ids': same_document,
                      'proceeding_merge_performed': False},
        'warnings': warnings, 'max_selected_passages': MAX_SELECTED, 'selected_passage_ids': [], 'intake': None}


def inspect_judgment(payload, existing_candidates=()):
    """Return metadata and exact selectable paragraphs, without an intake/save."""
    return _inspect(payload, existing_candidates)


def preview_judgment(payload, existing_candidates=()):
    """Build an unsaved genuine rights-intake/2 from explicitly selected passages."""
    result = _inspect(payload, existing_candidates)
    selected = payload.get('selected_passage_ids')
    if (not isinstance(selected, list) or not 1 <= len(selected) <= MAX_SELECTED
            or any(not isinstance(pid, str) for pid in selected) or len(selected) != len(set(selected))):
        raise APIError('Select 1-50 distinct supplied passage IDs.')
    by_id = {p['id']: p for p in result['passages']}
    if not set(selected) <= set(by_id):
        raise APIError('Selected passage ID does not resolve to this supplied document.', 400, 'judgment_excerpt_error')
    if any(not by_id[pid]['selectable'] for pid in selected):
        raise APIError('A selected paragraph exceeds the exact excerpt size bound; no truncation is performed.', 413, 'judgment_size')
    # Source order, not checkbox click order, determines stable claim display.
    selected = [p['id'] for p in result['passages'] if p['id'] in selected]
    result['selected_passage_ids'] = selected
    if result['duplicate']['exact']:
        return result
    document, identity = result['document'], result['identity']
    source_id = identity['source_id']
    date_note = 'Underlying passage event date unknown. Supplied judgment decision date: ' + (document['decision_date'] or 'unknown') + ' (' + document['decision_date_detail']['precision'] + ' precision); publication date: ' + (document['publication_date'] or 'unknown') + '.'
    claims = [{'id': pid, 'text': 'Selected judgment passage ' + str(by_id[pid]['number']) + '.', 'source_id': source_id,
               'excerpt': by_id[pid]['text'], 'locator': by_id[pid]['locator'], 'event_date': None,
               'date_note': date_note, 'attribution': by_id[pid]['attribution'] + ' Section label: ' + by_id[pid]['section']}
              for pid in selected]
    source = {'id': source_id, 'title': document['title'], 'publisher': document['publisher'], 'url': document['url'],
              'publication_date': document['publication_date'], 'retrieved_at': document['retrieved_at'],
              'language': document['language'], 'translation_status': document['translation_status'],
              'access_note': result['permission']['license_label'] + ('; ' + LICENSE_URL + '. Collection notice: ' + COLLECTION_NOTICE + ' Noncommercial local pilot, retained attribution. ' if result['provider'] == PROVIDER else '. Entirely invented original fixture. ') +
                  'Supplied local content; this preview made no source request. ' + result['provenance']['normalization'] +
                  (' Embedded notices: ' + ' | '.join(n['text'] for n in result['permission']['embedded_notices']) if result['permission']['embedded_notices'] else ''),
              'lineage_note': ('LawPhil-hosted judgment reproduction.' if result['provider'] == PROVIDER else 'Entirely fictional source, not a real judgment.') + ' One document/text version, not independent corroboration or an authenticated original court record. Document key ' + identity['document_key'] + '; text SHA256 ' + result['provenance']['source_text_sha256'] + '.'}
    candidate = {'id': identity['candidate_id'], 'title': document['title'], 'person': 'Person identifiers not extracted',
        'proceeding': document['court'] + '; supplied proceeding identifier: ' + (document['proceeding_id'] or 'unknown'),
        'country': document['country'], 'material_type': result['material_type'], 'as_of': None,
        'summary': 'Selected quoted passages from ' + document['title'] + '.', 'suggested_decision': 'uncertain',
        'review_reasons': ['Inspect the selected judgment passages and supplied document metadata.'],
        'unknowns': ['Underlying event dates, document/proceeding/person identity match and present case status are not established by this import.',
                     'No factual/legal summary, concern score, affected preferences, current advocacy opportunity or human review was inferred.'],
        'related_candidate_ids': [], 'sources': [source], 'claims': claims,
        'notes': ['Local deterministic judgment preview; selected passages are exact quotations of the cleaned supplied source text.',
                  'Supplied document ID: ' + document['document_id'] + '; document key: ' + identity['document_key'],
                  'Supplied citations: ' + (', '.join(document['citations']) or 'none'),
                  'Decoded content UTF-8 SHA256 (before HTML cleaning): ' + result['provenance']['raw_content_sha256'],
                  'Supplied original capture bytes SHA256 (not independently verified): ' + (result['provenance']['original_bytes_sha256_supplied'] or 'unknown'),
                  'Supplied decoded encoding: ' + (result['provenance']['decoded_encoding_supplied'] or 'unknown'),
                  'Supplied decision date: ' + (document['decision_date'] or 'unknown') + '; never substituted for publication or passage-event date.'],
        'rights_metadata': {'case_unit': 'One source-document grouping; supplied proceeding ID ' + (document['proceeding_id'] or 'unknown') + '. No distinct-case/defendant merge established.',
                            'identity_uncertainty': 'Supplied title, court, proceeding ID and citations require inspection; persons are not extracted.'}}
    intake = {'schema_version': 'rights-intake/2', 'candidate': candidate,
              'source_texts': {source_id: document['source_text']}, 'prepared_mappings': None}
    validate_candidate(candidate)
    RightsService.validate_context(candidate['rights_metadata'])
    for claim in claims:
        if claim['excerpt'] not in intake['source_texts'][claim['source_id']]:
            raise APIError('Exact selected excerpt is absent from its own source text.', 400, 'judgment_excerpt_error')
    if len(encoded(intake).encode('utf-8')) > MAX_BODY:
        raise APIError('Selected intake exceeds the 1 MiB API body limit; no content has been truncated.', 413, 'judgment_size')
    result['intake'] = intake
    return result
