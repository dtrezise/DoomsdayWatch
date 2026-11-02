#!/usr/bin/env python3
"""Check the exact public reference URLs and preserve retrieved bytes locally."""
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from archive import ROOT, DEFAULT, capture


def selected_sources(root=ROOT):
    with (root/'data/sources.csv').open(newline='') as f:sources={s['source_id']:s for s in csv.DictReader(f)}
    with (root/'data/claims.csv').open(newline='') as f:claims={c['claim_id']:c for c in csv.DictReader(f)}
    findings=json.loads((root/'site/findings.json').read_text())
    media=json.loads((root/'site/media.json').read_text())
    ids=set()
    for finding in findings:
        if finding['publication_status']!='published':continue
        ids.update(claims[cid]['source_id'] for cid in finding['claim_ids'])
        image=media[finding['image_id']];ids.add(image['source_id'])
        ids.update(sid for sid,s in sources.items() if s['url']==image['license_url'])
    ids.update(item['source_id'] for item in json.loads((root/'site/alert_systems.json').read_text()))
    status=json.loads((root/'site/status.json').read_text())
    status_urls={url for item in status['items'] if item['state']=='verified' for url in item.get('source_refs',[item['source_url']])}
    ids.update(sid for sid,source in sources.items() if source['url'] in status_urls)
    return [sources[sid] for sid in sorted(ids)]


def fetch(source):
    checked=datetime.now(timezone.utc).isoformat()
    result={'source_id':source['source_id'],'url':source['url'],'checked_at':checked,'status':'needs_review','method':'HTTP GET'}
    try:
        request=Request(source['url'],headers={'User-Agent':'DoomsdayWatch/1.0 editorial reference verification'})
        with urlopen(request,timeout=30) as response:
            data=response.read(12*1024*1024)
            media_type=response.headers.get_content_type()
            if response.status!=200 or not data:raise ValueError('Empty or unsuccessful response')
            if source['url'].endswith('.xml'):
                if b'<!DOCTYPE' in data.upper() or ET.fromstring(data).tag!='alerts':raise ValueError('Invalid NTAS XML response')
            elif len(data)<200:raise ValueError('Empty or incomplete response')
            if media_type=='text/html':
                head=data[:20000].decode('utf-8',errors='replace').lower()
                if any(marker in head for marker in ('browser validation page','triggerinterstitialchallenge','<title>access denied','<title>just a moment','<title>gcore')):
                    raise ValueError('Source returned a challenge page, not documentary content')
            if media_type=='application/pdf' and not data.startswith(b'%PDF'):raise ValueError('Invalid PDF response')
            result.update(status='retrieved',http_status=response.status,final_url=response.url,media_type=media_type,sha256=hashlib.sha256(data).hexdigest())
            return result,data
    except Exception as exc:result['error']=str(exc)
    return result,None


if __name__=='__main__':
    sources=selected_sources()
    directory=ROOT/'private/source-captures';directory.mkdir(parents=True,exist_ok=True)
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result,data in pool.map(fetch,sources):
            if data:
                path=directory/(result['source_id']+'.capture');path.write_bytes(data)
                result['capture_id']=capture(ROOT,DEFAULT,result['source_id'],path,result['checked_at'],result['media_type'],'Editorial source-link verification; raw response, dynamic dependencies not bundled')
            results.append(result)
            print(result['source_id'],result['status'],result.get('http_status',''),result.get('error',''))
    (ROOT/'site/reference_checks.json').write_text(json.dumps(results,indent=2)+'\n')
    if any(r['status']!='retrieved' for r in results):raise SystemExit(1)
