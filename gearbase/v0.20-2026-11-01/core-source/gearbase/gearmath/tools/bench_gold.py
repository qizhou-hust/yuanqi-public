"""Blank engineer forms and complete, source-bound gold imports. No model labels.

This validates the supplied attestation, not a person's identity or credentials.
The actual forty-question benchmark is never changed by this tool.
"""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
from . import bench as B

OUTCOMES = {'compiled', 'needs_clarification', 'blocked_unsupported_scope', 'blocked_invalid_inputs'}
FIELDS = {'status', 'annotator', 'labeled_at', 'expected_outcome',
          'expected_structured_requirement', 'expected_questions', 'expected_key_points', 'scoring_rule'}


def _hash(obj):
    try:
        raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
    except (ValueError, TypeError) as exc:
        raise ValueError('Gold data must be finite JSON') from exc
    return hashlib.sha256(raw).hexdigest()


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Explicit nonblank name required')
    return value.strip().casefold()


def _base(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get('cases'), list) or len(doc['cases']) != 40:
        raise ValueError('Complete original forty-question benchmark required')
    ids = [row['id'] for row in doc['cases']]
    if len(set(ids)) != 40 or any(not isinstance(i, str) or not i.strip() for i in ids):
        raise ValueError('Benchmark IDs must be unique nonblank strings')
    return ids


def template(cases_doc=None):
    doc = B.load_cases() if cases_doc is None else cases_doc
    _base(doc)
    blank = {key: None for key in FIELDS}
    blank['status'] = 'pending_engineer_label'
    return {'schema': 'gearbase.engineer-gold-form/1', 'benchmark_sha256': _hash(doc),
            'implementation_authors': None, 'independence_attested': False, 'reviewer_role': None,
            'cases': [{'id': row['id'], 'text_zh': row['text_zh'], 'gold': copy.deepcopy(blank)} for row in doc['cases']]}


def apply(form, cases_doc=None):
    doc = B.load_cases() if cases_doc is None else cases_doc
    ids = _base(doc)
    required = {'schema', 'benchmark_sha256', 'implementation_authors', 'independence_attested', 'reviewer_role', 'cases'}
    if not isinstance(form, dict) or set(form) != required or form['schema'] != 'gearbase.engineer-gold-form/1':
        raise ValueError('Unknown or missing engineer form fields')
    if form['benchmark_sha256'] != _hash(doc):
        raise ValueError('Stale or changed benchmark identity')
    authors = form['implementation_authors']
    if not isinstance(authors, list) or not authors:
        raise ValueError('Implementation authors must be explicitly identified')
    author_ids = {_name(v) for v in authors}
    if len(author_ids) != len(authors) or form['independence_attested'] is not True or form['reviewer_role'] != 'gear_engineer':
        raise ValueError('Distinct authors and explicit independent gear-engineer attestation required')
    rows = form['cases']
    if not isinstance(rows, list) or len(rows) != 40 or [r.get('id') for r in rows if isinstance(r, dict)] != ids:
        raise ValueError('Complete unique original forty-case coverage and order required')
    result = copy.deepcopy(doc)
    for source, submitted, target in zip(doc['cases'], rows, result['cases']):
        if set(submitted) != {'id', 'text_zh', 'gold'} or submitted['text_zh'] != source['text_zh']:
            raise ValueError('Question text or record fields changed')
        gold = submitted['gold']
        if not isinstance(gold, dict) or set(gold) != FIELDS or gold['status'] != 'labeled':
            raise ValueError('Each case needs complete signed engineer labels')
        if _name(gold['annotator']) in author_ids:
            raise ValueError('Annotator must differ from implementation authors')
        date = gold['labeled_at']
        try:
            parsed = datetime.date.fromisoformat(date)
        except (TypeError, ValueError) as exc:
            raise ValueError('Each case requires an ISO date') from exc
        if parsed.isoformat() != date:
            raise ValueError('Dates must use YYYY-MM-DD')
        if not isinstance(gold['expected_outcome'], str) or gold['expected_outcome'] not in OUTCOMES or not isinstance(gold['expected_structured_requirement'], dict):
            raise ValueError('Explicit supported outcome and structured requirement required')
        questions = gold['expected_questions']
        if not isinstance(questions, list) or any(not isinstance(v, str) or not v.strip() for v in questions) or len(set(questions)) != len(questions):
            raise ValueError('Expected question fields must be an explicit unique list')
        if not isinstance(gold['expected_key_points'], str) or gold['scoring_rule'] is not None:
            raise ValueError('Key points must be text; unsupported custom scoring rules are rejected')
        _hash(gold)
        target['gold'] = copy.deepcopy(gold)
    result['status'] = 'engineer_labeled_attestation_supplied'
    receipt = {'schema': 'gearbase.engineer-gold-import/1', 'complete': True, 'labeled_cases': 40,
               'pending_engineer_label': 0, 'benchmark_sha256': _hash(doc), 'form_sha256': _hash(form),
               'annotated_benchmark_sha256': _hash(result),
               'identity_and_credentials': 'supplied attestation; not independently verified',
               'source_benchmark_changed': False, 'milestone_closed': False}
    return result, receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--template', type=Path)
    group.add_argument('--labels', type=Path)
    p.add_argument('--out', type=Path)
    args = p.parse_args(argv)
    if args.template:
        if args.template.resolve() == B.BENCH.resolve():
            p.error('The source benchmark cannot be overwritten by a blank template')
        args.template.parent.mkdir(parents=True, exist_ok=True)
        args.template.write_text(json.dumps(template(), ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        return 0
    if args.out is None:
        p.error('--labels requires --out')
    targets = { (args.out/name).resolve() for name in ('annotated-benchmark.json', 'import-receipt.json', 'result.json') }
    if B.BENCH.resolve() in targets or args.labels.resolve() in targets:
        p.error('Generated files cannot overwrite the benchmark or submitted annotations')
    labelled, receipt = apply(json.loads(args.labels.read_text(encoding='utf8')))
    score = B.evaluate(B.rule_baseline, labelled)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in [('annotated-benchmark.json', labelled), ('import-receipt.json', receipt), ('result.json', score)]:
        (args.out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')
    return 0 if score['metrics']['hallucination_gate'] == 'pass' else 1


if __name__ == '__main__': raise SystemExit(main())
