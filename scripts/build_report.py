#!/usr/bin/env python3
"""Generate a reviewable inventory, never automated intelligence judgments."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from validate import ROOT, validate


def cell(value):
    return value.replace('|', '\\|').replace('\n', ' ')


def build():
    errors, tables = validate()
    if errors:
        raise SystemExit('\n'.join(errors))
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    sources = {r['source_id']: r for r in tables['sources']}
    lines = ['# Research evidence inventory', '',
             f'Generated: {today} (America/New_York). Research cutoff: see master assessment.', '',
             'Draft inventory only. This file contains reported and unverified material and makes no threat judgment.', '',
             '## Claim status', '']
    for status, count in sorted(Counter(r['verification_status'] for r in tables['claims']).items()):
        lines.append(f'- {status}: {count}')
    lines += ['', '## Chronological records', '',
              '| Event date | Event | Status |', '|---|---|---|']
    for event in sorted(tables['events'], key=lambda r: r['event_date']):
        lines.append('| ' + ' | '.join(cell(event[k]) for k in ('event_date', 'description', 'verification_status')) + ' |')
    lines += ['', '## Claims and citations', '',
              '| Claim | Proposition | Class / status / confidence | Source |', '|---|---|---|---|']
    for claim in tables['claims']:
        source = sources[claim['source_id']]
        url = source['url'] if source['url'].startswith('https://') else '../' + source['url']
        lines.append(f"| {claim['claim_id']} | {cell(claim['proposition'])} | {claim['evidence_class']} / {claim['verification_status']} / {claim['confidence']} | [{source['source_id']}]({url}) |")
    lines += ['', '## Open work', '',
              f"Open leads: {sum(r['status'] == 'open' for r in tables['leads'])}.",
              f"Missing sector/year baseline records: {sum(r['status'] == 'missing' for r in tables['baselines'])}.", '',
              'Review source access outcomes, corrections and competing explanations before using this inventory in an assessment.']
    out = ROOT / 'reports' / f'{today}_evidence_inventory.md'
    out.write_text('\n'.join(lines) + '\n')
    print(out)


if __name__ == '__main__':
    build()
