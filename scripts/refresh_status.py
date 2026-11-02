#!/usr/bin/env python3
"""Collect public indicators. Ambiguous, blocked and expired responses fail closed."""
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)
def plain(data):
    parser=Text();parser.feed(data);return ' '.join(' '.join(parser.parts).split())
def parse(kind,text):
    if any(x in text.lower() for x in ('browser validation','enable javascript','access denied','request blocked')):
        raise ValueError('Source returned a security/interstitial page')
    if kind=='clock':
        m=re.search(r'It is now (\d{1,3}) seconds to midnight',text,re.I)
        if m and 0<int(m[1])<600:return m[1]+' seconds', 'Symbolic setting · Bulletin of the Atomic Scientists'
    if kind=='uk':
        m=re.search(r'(?:The threat to the UK \(England, Wales, Scotland and Northern Ireland\) from terrorism is|current (?:UK national )?(?:terrorism )?threat level(?: for the UK)?(?: from international terrorism)? is|Current Threat Level:|UK national threat level is)\s*(?:\([^)]*\)\s*)?(LOW|MODERATE|SUBSTANTIAL|SEVERE|CRITICAL)\b',text,re.I)
        if m:return m[1].upper(),'UK terrorism · JTAC / official government publication'
    if kind=='france':
        m=re.search(r'(?:abaisse|maintient|porte).{0,130}?(?:territoire national|territoire).{0,80}?niveau [“"«]?\s*(Vigilance renforcée|Urgence attentat|Alerte attentat|Vigilance)',text,re.I)
        if m:return m[1].capitalize(),'France · Vigipirate national posture'
    # NTAS is a dated advisory system, not the retired color scale. No generic
    # inference from a missing bulletin, archive list or page title is allowed.
    if kind=='dhs':
        if re.search(r'There are (?:currently )?no (?:current|active) (?:NTAS )?(?:advisories|alerts|bulletins)',text,re.I):
            return 'No active advisory','DHS NTAS · explicit current-source statement'
        raise ValueError('Active advisory and expiry could not be unambiguously established')
    raise ValueError('Current setting not recognized; editorial review required')

SPECS=[
 ('clock','Doomsday Clock',['https://thebulletin.org/doomsday-clock/']),
 ('defcon','DEFCON',[]),
 ('dhs','US Homeland Security',['https://www.dhs.gov/national-terrorism-advisory-system']),
 ('uk','Europe / United Kingdom',['https://www.gov.uk/terrorism-national-emergency','https://www.mi5.gov.uk/threats-and-advice/terrorism-threat-levels']),
 ('france','Europe / France',['https://www.education.gouv.fr/consignes-de-securite-applicables-dans-les-etablissements-relevant-du-ministere-de-l-education-456201'])]

def collect(fetch=None,now=None):
    now=now or datetime.now(timezone.utc).isoformat()
    def network(url):
        with urlopen(Request(url,headers={'User-Agent':'DoomsdayWatch/1.0 public indicator verification'}),timeout=25) as response:
            if response.status!=200:raise ValueError('Unsuccessful response')
            return response.read(3*1024*1024)
    fetch=fetch or network;items=[]
    for key,label,urls in SPECS:
        item=dict(id=key,label=label,value='Not verified',state='unavailable',checked_at=now,source_url=urls[0] if urls else '',note='Current public value could not be verified.',attempts=[])
        if key=='defcon':
            item.update(value='Not publicly verified',note='No authenticated official public current-level feed is available to this publication. Third-party estimates are not official DEFCON.');items.append(item);continue
        for url in urls:
            try:
                data=fetch(url);text=plain(data.decode('utf-8',errors='replace'));value,note=parse(key,text)
                item.update(value=value,note=note,state='verified',source_url=url,verified_at=now,sha256=hashlib.sha256(data).hexdigest())
                directory=ROOT/'private/status-captures';directory.mkdir(parents=True,exist_ok=True)
                (directory/(key+'.html')).write_bytes(data)
                item['attempts'].append(dict(url=url,outcome='verified'));break
            except Exception as exc:
                item['attempts'].append(dict(url=url,outcome='unavailable',reason=str(exc)[:200]))
        items.append(item)
    return dict(schema_version=1,checked_at=now,stale_after_hours=36,items=items)

if __name__=='__main__':
    snapshot=collect();(ROOT/'site/status.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    for item in snapshot['items']:print(item['id'],item['state'],item['value'])
