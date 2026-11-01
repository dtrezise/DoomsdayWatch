#!/usr/bin/env python3
"""Validate research records without network access or external dependencies."""
import csv
import re
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
STATUS = {'unverified', 'partially_verified', 'verified', 'contradicted', 'withdrawn'}
CLASSES = {'confirmed_fact', 'reported_claim', 'analytical_inference', 'speculation'}
CONFIDENCE = {'not_assessed', 'low', 'moderate', 'high'}
SECTORS = {'military_logistics', 'emergency_procurement', 'geopolitical_developments',
           'civilian_infrastructure', 'medical_preparedness', 'financial_insurance',
           'continuity_of_government', 'astronomical_hazards'}
KEYS = {'events': 'event_id', 'claims': 'claim_id', 'sources': 'source_id',
        'leads': 'lead_id', 'anomalies': 'anomaly_id', 'baselines': 'baseline_id',
        'watchlist': 'indicator_id', 'verification_log': 'check_id'}
REQUIRED = {
    'events': ['event_date', 'sector', 'description', 'verification_status'],
    'claims': ['event_id', 'source_id', 'proposition', 'evidence_class', 'verification_status', 'confidence', 'evidence_note'],
    'sources': ['url', 'publisher', 'title', 'source_type', 'access_outcome', 'independence_group', 'accessed_at'],
    'leads': ['sector', 'subject', 'priority', 'next_action', 'status'],
    'anomalies': ['lead_id', 'sector', 'status', 'baseline_gap', 'alternatives'],
    'baselines': ['sector', 'year', 'metric', 'status', 'limitations'],
    'watchlist': ['sector', 'indicator', 'review_trigger', 'cadence', 'status'],
    'verification_log': ['checked_at', 'source_id', 'action', 'outcome']}


def validate(root=ROOT):
    errors, tables, indexes = [], {}, {}
    for name, key in KEYS.items():
        try:
            with (root / 'data' / f'{name}.csv').open(newline='') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []
                rows = list(reader)
            missing = set([key] + REQUIRED[name]) - set(columns)
            if missing:
                errors.append(f'{name}: missing columns {sorted(missing)}')
                continue
            tables[name] = rows
            indexes[name] = {r[key]: r for r in rows}
            if len(indexes[name]) != len(rows):
                errors.append(f'{name}: duplicate IDs')
            for r in rows:
                prefix = f'{name}/{r.get(key)}'
                if None in r or any(v is None for v in r.values()):
                    errors.append(f'{prefix}: malformed CSV row')
                    continue
                for field in [key] + REQUIRED[name]:
                    if not r[field]:
                        errors.append(f'{prefix}: empty {field}')
                if 'sector' in r and r['sector'] not in SECTORS:
                    errors.append(f'{prefix}: invalid sector')
                if 'verification_status' in r and r['verification_status'] not in STATUS:
                    errors.append(f'{prefix}: invalid verification status')
                for field in ('event_date', 'first_reported', 'published_at', 'accessed_at', 'verified_at', 'checked_at', 'last_reviewed', 'last_checked'):
                    value = r.get(field, '')
                    if value:
                        try:
                            if not re.fullmatch(r'\d{4}(-\d{2}){0,2}', value):
                                raise ValueError()
                            date.fromisoformat(value + {4: '-01-01', 7: '-01', 10: ''}[len(value)])
                        except (ValueError, KeyError):
                            errors.append(f'{prefix}: invalid {field}')
        except OSError as exc:
            errors.append(str(exc))
    for name, rows in tables.items():
        for r in rows:
            for field, target in [('source_id', 'sources'), ('event_id', 'events'), ('lead_id', 'leads')]:
                if name != target and r.get(field) and r[field] not in indexes.get(target, {}):
                    errors.append(f'{name}: unresolved {field} {r[field]}')
    for r in tables.get('claims', []):
        if r['evidence_class'] not in CLASSES or r['confidence'] not in CONFIDENCE:
            errors.append(f"{r['claim_id']}: invalid evidence class or confidence")
        if r['verification_status'] == 'verified':
            source = indexes.get('sources', {}).get(r['source_id'], {})
            if not r['verified_at'] or source.get('access_outcome') != 'full_text':
                errors.append(f"{r['claim_id']}: verified claim requires dated full-text evidence")
        if r['evidence_class'] == 'confirmed_fact' and r['verification_status'] != 'verified':
            errors.append(f"{r['claim_id']}: confirmed fact must be verified")
    for r in tables.get('baselines', []):
        if r['status'] == 'missing' and r['value']:
            errors.append(f"{r['baseline_id']}: missing baseline cannot contain a value")
        if r['value'] and (not r['source_id'] or not r['unit']):
            errors.append(f"{r['baseline_id']}: measurement needs source and unit")
    return errors, tables


if __name__ == '__main__':
    errors, tables = validate()
    if errors:
        print('\n'.join(errors))
        raise SystemExit(1)
    print(f'Validated {sum(map(len, tables.values()))} records across {len(tables)} tables.')
