#!/usr/bin/env python3
"""Collect allowlisted public indicators; never infer an all-clear from a failed fetch."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DHS_PAGE='https://www.dhs.gov/national-terrorism-advisory-system'
DHS_FEEDS=['https://www.dhs.gov/ntas/1.1/feed.xml','https://www.dhs.gov/ntas/1.1/alerts.xml']
FRANCE_DIPLO='https://www.diplomatie.gouv.fr/fr/information-par-pays/alertes/vigilance-renforcee-pour-les-ressortissants-francais-a-l-etranger'
class SourceBlocked(ValueError):pass
class SourceNeedsReview(ValueError):pass
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
def utc(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise SourceNeedsReview('Timestamp has no timezone')
    return result.astimezone(timezone.utc)
def check_content(text):
    if any(x in text.lower() for x in ('browser validation','enable javascript','access denied','request blocked','triggerinterstitialchallenge')):
        raise SourceBlocked('Public source returned a security/interstitial page')
def parse(kind,text):
    check_content(text)
    if kind=='clock':
        m=re.search(r'It is now (\d{1,3}) seconds to midnight',text,re.I)
        if m and 0<int(m[1])<600:return m[1]+' seconds', 'Symbolic setting · Bulletin of the Atomic Scientists'
    if kind=='uk':
        m=re.search(r'(?:The threat to the UK \(England, Wales, Scotland and Northern Ireland\) from terrorism is|current (?:UK national )?(?:terrorism )?threat level(?: for the UK)?(?: from international terrorism)? is|Current Threat Level:|UK national threat level is)\s*(?:\([^)]*\)\s*)?(LOW|MODERATE|SUBSTANTIAL|SEVERE|CRITICAL)\b',text,re.I)
        if m:return m[1].upper(),'UK terrorism · JTAC / official government publication'
    if kind=='dhs':
        # Ignore archive text; only an explicit current statement qualifies.
        current=text.split('Expired Advisories',1)[0]
        if re.search(r'There are (?:currently )?no (?:current|active) (?:NTAS )?(?:advisories|alerts|bulletins)',current,re.I):
            return 'No active advisory','DHS NTAS · explicit current-source statement; not a general threat all-clear'
    raise SourceNeedsReview('Current setting not recognized; source review required')

MONTHS={m:i for i,m in enumerate(['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'],1)}
def french_date(text):
    match=re.search(r'(\d{1,2})\s+('+ '|'.join(MONTHS) +r')\s+(20\d{2})',text,re.I)
    if not match:raise SourceNeedsReview('Dated national statement required')
    return datetime(int(match[3]),MONTHS[match[2].lower()],int(match[1]),tzinfo=timezone.utc)
def parse_france(text,now):
    check_content(text)
    levels=r'(Vigilance renforcée|Urgence attentat|Alerte attentat|Vigilance)'
    # Exact national-scope statement, not a heading listing possible levels or
    # advice for French citizens abroad alone.
    m=re.search(r'Plan Vigipirate\s+20\d{2}\s+prévoit un stade\s*[«“"]?\s*'+levels+r'\s*[»”"]?\s+sur le territoire français',text,re.I)
    if m:
        stamp=re.search(r'Date de mise en ligne le\s*:\s*(.{0,30})',text,re.I)
        source_date=french_date(stamp[1] if stamp else '')
        review_due=source_date+timedelta(days=90)
        if source_date>now or now>=review_due:raise SourceNeedsReview('Dated fallback needs a newer national-posture statement')
        return m[1].capitalize(),{'note':'France Vigipirate · national posture explicitly stated by the Foreign Ministry; publication '+source_date.date().isoformat()+'. This dated fallback is reviewed after 90 days.', 'source_date':source_date.date().isoformat(),'review_due':review_due.isoformat()}
    m=re.search(r'(?:abaisse|maintient|porte).{0,130}?(?:territoire national|territoire).{0,80}?niveau [“"«]?\s*'+levels,text,re.I)
    if m:
        # The education page's explicit national statement includes its effective
        # date. Do not pick up a historical paragraph in a later year indefinitely.
        effective=re.search(r'(?:active|effet)\s+(?:depuis|à compter du)\s+(.{0,30})',text,re.I)
        since=french_date(effective[1] if effective else '')
        if since.year!=now.year or since>now:raise SourceNeedsReview('National statement needs a current-year review')
        return m[1].capitalize(),{'note':'France Vigipirate · explicit national posture; effective '+since.date().isoformat(), 'source_date':since.date().isoformat(),'review_due':datetime(since.year+1,1,1,tzinfo=timezone.utc).isoformat()}
    m=re.search(r'Positionnée au nouveau stade\s*[«“"]?\s*'+levels+r'.{0,100}?posture.{0,35}?(20\d{2})',text,re.I)
    if m and int(m[2])==now.year:
        return m[1].capitalize(),{'note':'France Vigipirate · SGDSN published seasonal national posture for '+m[2], 'review_due':datetime(now.year+1,1,1,tzinfo=timezone.utc).isoformat()}
    raise SourceNeedsReview('No explicit current national posture found')

def ntas_time(value):
    if not value:raise SourceNeedsReview('NTAS effective/expiration date missing')
    try:return datetime.strptime(value,'%Y/%m/%d %H:%M').replace(tzinfo=timezone.utc)
    except ValueError:return utc(value)
def official_dhs_link(value):
    url=urljoin(DHS_PAGE,value)
    parts=urlsplit(url)
    if parts.hostname not in ('dhs.gov','www.dhs.gov') or parts.username or parts.scheme not in ('https','http'):
        raise SourceNeedsReview('Advisory link is outside the official DHS origin')
    return url.replace('http://','https://',1)
def parse_ntas(data,now):
    check_content(data.decode('utf-8',errors='replace'))
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise SourceNeedsReview('Unexpected XML declarations')
    try:root=ET.fromstring(data)
    except ET.ParseError as exc:raise SourceNeedsReview('NTAS feed is not valid XML') from exc
    if root.tag!='alerts' or root.attrib or (root.text or '').strip():raise SourceNeedsReview('Unexpected NTAS feed root')
    active=[];transitions=[];expired=0;scheduled=0;seen={}
    for node in root:
        if node.tag!='alert':raise SourceNeedsReview('Unknown NTAS feed entry')
        start=ntas_time(node.get('start'));end=ntas_time(node.get('end'))
        if end<=start:raise SourceNeedsReview('Invalid NTAS validity interval')
        if end<=now:expired+=1;continue
        if start>now:scheduled+=1;transitions.append(start);continue
        level=re.sub(r'\s+','',node.get('type','')).lower()
        if level not in ('elevatedthreat','imminentthreat','bulletin'):raise SourceNeedsReview('Unknown advisory type')
        raw_link=node.get('link') or node.get('href')
        if not raw_link:raise SourceNeedsReview('Advisory source link missing')
        link=official_dhs_link(raw_link)
        summary=plain(' '.join(node.find('summary').itertext())) if node.find('summary') is not None else ''
        if not summary:raise SourceNeedsReview('Reference-only or incomplete NTAS entry requires source review')
        identity=(link,start,end)
        if identity in seen:
            if seen[identity]!=(level,summary):raise SourceNeedsReview('Conflicting duplicate NTAS advisory')
            continue
        seen[identity]=(level,summary)
        active.append(dict(type={'elevatedthreat':'Elevated threat','imminentthreat':'Imminent threat','bulletin':'Bulletin'}[level],summary=summary[:300],url=link,effective_at=start.isoformat(),expires_at=end.isoformat()))
        transitions.append(end)
    note='Official DHS XML feed. Feed coverage alone does not independently exclude other NTAS bulletins or establish a general threat all-clear.'
    metadata=dict(note=note,advisories=active,expired_entries=expired,scheduled_entries=scheduled)
    if transitions:metadata['valid_until']=min(transitions).isoformat()
    if active:
        priority={'Imminent threat':3,'Elevated threat':2,'Bulletin':1};top=max(active,key=lambda a:priority[a['type']])['type']
        return top+' · '+str(len(active))+' active',metadata
    return 'No active feed alerts',metadata

def display_indicator(item,snapshot,now=None):
    now=now or datetime.now(timezone.utc)
    state=item['state'];reading=item.get('last_verified') if state!='verified' else None
    reading=reading or item;value=reading['value']
    has_reading=state=='verified' or bool(item.get('last_verified'))
    if has_reading:
        try:
            if reading.get('valid_until') and now>=utc(reading['valid_until']):return 'expired','Advisory update required'
            if reading.get('review_due') and now>=utc(reading['review_due']):return 'expired','Source review due'
            age=(now-utc(reading['verified_at'])).total_seconds()
            if age>snapshot['stale_after_hours']*3600 or age < -300:return 'stale','Stale · '+value
            if state!='verified':return 'last_verified',value+' · last verified'
        except (ValueError,KeyError,TypeError):return 'needs_review','Source needs review'
    return state,value

SPECS=[
 ('clock','Doomsday Clock',['https://thebulletin.org/doomsday-clock/']),
 ('dhs','US Homeland Security',DHS_FEEDS+[DHS_PAGE]),
 ('uk','Europe / United Kingdom',['https://www.gov.uk/terrorism-national-emergency','https://www.mi5.gov.uk/threats-and-advice/terrorism-threat-levels']),
 ('france','Europe / France',['https://www.sgdsn.gouv.fr/vigipirate',FRANCE_DIPLO,'https://www.education.gouv.fr/consignes-de-securite-applicables-dans-les-etablissements-relevant-du-ministere-de-l-education-456201'])]

STATE_VALUES={'not_disclosed':'Not publicly disclosed','source_blocked':'Source blocked','retrieval_failed':'Retrieval failed','needs_review':'Source needs review'}
def collect(fetch=None,now=None,previous=None,capture_dir=None):
    now=now or datetime.now(timezone.utc).isoformat();instant=utc(now)
    def network(url):
        with urlopen(Request(url,headers={'User-Agent':'DoomsdayWatch/1.0 public indicator verification'}),timeout=15) as response:
            if response.status!=200:raise ValueError('Unsuccessful response')
            data=response.read(3*1024*1024+1)
            if len(data)>3*1024*1024:raise SourceNeedsReview('Source exceeds capture size limit')
            return data
    fetch=fetch or network;items=[];previous={i['id']:i for i in (previous or {}).get('items',[])}
    def retrieve(item,url):
        try:
            data=fetch(url)
            # Keep exact successful response bytes, including XML and challenge
            # responses. Never treat saved bytes as verification by themselves.
            if capture_dir is not None:
                directory=Path(capture_dir);directory.mkdir(parents=True,exist_ok=True)
                name=hashlib.sha256(url.encode()).hexdigest()[:16]+('.xml' if url.endswith('.xml') else '.html')
                (directory/name).write_bytes(data)
            item['attempts'].append(dict(url=url,outcome='retrieved',sha256=hashlib.sha256(data).hexdigest()))
            return data
        except Exception as exc:
            state='source_blocked' if isinstance(exc,SourceBlocked) or isinstance(exc,HTTPError) and exc.code in (401,403,429) else 'retrieval_failed'
            item['attempts'].append(dict(url=url,outcome=state,reason=str(exc)[:200]));raise
    for key,label,urls in SPECS:
        item=dict(id=key,label=label,value='Retrieval failed',state='retrieval_failed',checked_at=now,source_url=urls[0] if urls else '',source_refs=[],note='The public source could not be retrieved. This is not a low-risk reading.',attempts=[])
        failures=[]
        for url in urls:
            try:
                data=retrieve(item,url);text=plain(data.decode('utf-8',errors='replace'))
                if key=='dhs' and url.endswith('.xml'):
                    value,metadata=parse_ntas(data,instant)
                    if value=='No active feed alerts':
                        # Check bulletin coverage against the public landing page
                        # when available. A blocked page leaves the narrower feed
                        # result visible, with its scope explicitly stated.
                        try:
                            page=retrieve(item,DHS_PAGE);current=plain(page.decode('utf-8',errors='replace'));check_content(current)
                            try:
                                value,page_note=parse('dhs',current);metadata['note']=page_note+'; official XML feed also checked.';item['source_refs'].append(DHS_PAGE)
                            except SourceNeedsReview:
                                if 'Current Advisories' in current:raise SourceNeedsReview('NTAS page and empty feed need reconciliation')
                        except (HTTPError,OSError,SourceBlocked):pass
                elif key=='france':value,metadata=parse_france(text,instant)
                else:
                    value,note=parse(key,text);metadata=dict(note=note)
                item.update(value=value,state='verified',source_url=url,verified_at=now,sha256=hashlib.sha256(data).hexdigest(),**metadata)
                item['source_refs'].append(url)
                for attempt in reversed(item['attempts']):
                    if attempt['url']==url and attempt['outcome']=='retrieved':attempt['parsed']=True;break
                break
            except Exception as exc:
                state='source_blocked' if isinstance(exc,SourceBlocked) or isinstance(exc,HTTPError) and exc.code in (401,403,429) else 'needs_review' if isinstance(exc,(ValueError,ET.ParseError)) else 'retrieval_failed'
                failures.append(state)
                if item['attempts'] and item['attempts'][-1].get('url')==url:item['attempts'][-1].update(outcome=state,reason=str(exc)[:200])
                if key=='dhs' and url.endswith('.xml') and state=='needs_review':break
        if item['state']!='verified':
            state='needs_review' if 'needs_review' in failures else 'source_blocked' if 'source_blocked' in failures else 'retrieval_failed'
            item.update(state=state,value=STATE_VALUES[state],note='Public information exists, but '+('the retrieved content needs review.' if state=='needs_review' else 'automated retrieval was blocked.' if state=='source_blocked' else 'the source could not be retrieved.')+' No current risk level is inferred.')
            old=previous.get(key,{})
            if old.get('state')=='verified':item['last_verified']={key:old[key] for key in ('value','verified_at','source_url','source_refs','note','sha256','valid_until','review_due','advisories') if key in old}
            elif old.get('last_verified'):item['last_verified']=old['last_verified']
        items.append(item)
    return dict(schema_version=2,checked_at=now,stale_after_hours=36,items=items)

if __name__=='__main__':
    path=ROOT/'site/status.json';previous=json.loads(path.read_text()) if path.exists() else None
    snapshot=collect(previous=previous,capture_dir=ROOT/'private/status-captures')
    path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    for item in snapshot['items']:print(item['id'],item['state'],item['value'])
