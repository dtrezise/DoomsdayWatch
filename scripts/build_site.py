#!/usr/bin/env python3
"""Build the public, allowlisted GitHub Pages artifact using standard Python only."""
import argparse
import html
import hashlib
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring
from validate import ROOT, validate
from refresh_status import display_indicator
from zoneinfo import ZoneInfo

SECTORS = {
 'military_logistics': ('Military logistics', 'Exercises, transport, activation and actual utilization.'),
 'emergency_procurement': ('Emergency procurement', 'Awards, obligations, delivery schedules and quantities.'),
 'geopolitical_developments': ('Geopolitical developments', 'Diplomacy, conflicts and independently corroborated events.'),
 'civilian_infrastructure': ('Civilian infrastructure', 'Energy, communications, cyber resilience and public advice.'),
 'medical_preparedness': ('Medical preparedness', 'Medical capability, stockpiles and authorization pathways.'),
 'financial_insurance': ('Financial & insurance', 'Dated risk pricing, shipping costs and comparable coverage.'),
 'continuity_of_government': ('Continuity of government', 'Public continuity policies, exercises and activation.'),
 'astronomical_hazards': ('Astronomical hazards', 'Dated asteroid-risk and space-weather products.')}


def esc(value):
    return html.escape(str(value), quote=True)


def date_label(value):
    parsed = date.fromisoformat(value)
    return parsed.strftime("%B") + f" {parsed.day}, {parsed.year}"


def inline(value):
    value = esc(value)
    value = re.sub(r'\[([^\]]+)\]\((https://[^\s)]+)\)', r'<a href="\2" rel="noreferrer">\1</a>', value)
    value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
    value = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)
    return value


def markdown(value):
    """Render the repo's prose subset; raw HTML and local Markdown links stay escaped."""
    out, paragraph, listing, table = [], [], False, False
    def flush():
        if paragraph:
            out.append('<p>' + inline(' '.join(paragraph)) + '</p>')
            paragraph.clear()
    for line in value.splitlines() + ['']:
        if line.startswith('# '):
            continue
        if line.startswith('|'):
            flush()
            if listing: out.append('</ul>'); listing = False
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(re.fullmatch(r':?-+:?', c) for c in cells):
                continue
            if not table:
                out.append('<div class="table-wrap"><table>'); table = True
            out.append('<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in cells) + '</tr>')
            continue
        if table: out.append('</table></div>'); table = False
        if not line.strip():
            flush()
            if listing: out.append('</ul>'); listing = False
        elif line.startswith('##'):
            flush()
            if listing: out.append('</ul>'); listing = False
            level = min(len(line) - len(line.lstrip('#')), 3)
            out.append(f'<h{level}>' + inline(line.lstrip('# ')) + f'</h{level}>')
        elif re.match(r'^(- |\d+\. )', line):
            flush()
            if not listing: out.append('<ul>'); listing = True
            out.append('<li>' + inline(re.sub(r'^(- |\d+\. )', '', line)) + '</li>')
        else:
            paragraph.append(line)
    return '\n'.join(out)


def load_public(root=ROOT):
    errors, tables = validate(root)
    if errors: raise ValueError('\n'.join(errors))
    config = json.loads((root/'site/config.json').read_text())
    parsed = urlsplit(config['url'])
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Site URL must be an absolute HTTPS URL without query or fragment')
    claims = {c['claim_id']: c for c in tables['claims']}
    sources = {s['source_id']: s for s in tables['sources']}
    all_findings = json.loads((root/'site/findings.json').read_text())
    ids = set()
    for f in all_findings:
        if not re.fullmatch(r'F\d{3,}', f['id']) or f['id'] in ids:
            raise ValueError('Finding ID invalid or duplicated')
        ids.add(f['id'])
        if f['sector'] not in SECTORS or not f['claim_ids']:
            raise ValueError(f"{f['id']}: missing sector or claims")
        if f['publication_status'] not in {'draft', 'published', 'withdrawn'}:
            raise ValueError('Invalid publication status')
        if f['publication_status'] != 'published': continue
        if f['updated_at'] < f['published_at'] or f['updated_at'] > config['research_cutoff']:
            raise ValueError('Finding dates outside research cutoff')
        for cid in f['claim_ids']:
            c = claims.get(cid)
            if not c or c['verification_status'] != 'verified' or c['evidence_class'] != 'confirmed_fact':
                raise ValueError(f"{f['id']}: public finding requires verified confirmed claims: {cid}")
            s = sources[c['source_id']]
            if s['access_outcome'] != 'full_text' or not s['url'].startswith('https://'):
                raise ValueError('Public finding requires inspectable external source')
    media = json.loads((root/'site/media.json').read_text())
    checks = {c['source_id']: c for c in json.loads((root/'site/reference_checks.json').read_text())}
    published = [f for f in all_findings if f['publication_status'] == 'published']
    public_ids = {f['id'] for f in published}
    for finding in published:
        image = media.get(finding.get('image_id'))
        if not image or not image.get('credit') or not image.get('license_url') or not image.get('caption'):
            raise ValueError('Published story requires sourced image and credit metadata')
        image_path = root/'site'/image['path']
        if not image_path.resolve().is_relative_to((root/'site/assets/photos').resolve()) or not image_path.is_file():
            raise ValueError('Missing or unsafe story image')
        if image['source_url'] != sources[image['source_id']]['url']:
            raise ValueError('Image source URL must match its registered source')
        licence_ids = {sid for sid, source in sources.items() if source['url'] == image['license_url']}
        if not licence_ids:
            raise ValueError('Image reuse policy requires a registered checked reference')
        source_ids = {claims[cid]['source_id'] for cid in finding['claim_ids']} | {image['source_id']} | licence_ids
        for sid in source_ids:
            check = checks.get(sid, {})
            if check.get('url') != sources[sid]['url'] or check.get('status') != 'retrieved' or check.get('http_status') != 200:
                raise ValueError(f"{finding['id']}: missing successful reference check for {sid}")
    slugs = set()
    for investigation in json.loads((root/'site/investigations.json').read_text()):
        if not re.fullmatch(r'[a-z0-9-]+', investigation['slug']) or investigation['slug'] in slugs:
            raise ValueError('Invalid or duplicate investigation slug')
        slugs.add(investigation['slug'])
        if not investigation['finding_ids'] or not set(investigation['finding_ids']).issubset(public_ids):
            raise ValueError('Public investigations require sourced published reporting')
        if investigation['image_id'] not in media:
            raise ValueError('Investigation requires a sourced image')
    return config, tables, published

class Site:
    def __init__(self, root, out):
        self.root, self.out = root, out
        self.config, self.tables, self.findings = load_public(root)
        self.base = urlsplit(self.config['url']).path.rstrip('/')
        self.claims = {c['claim_id']: c for c in self.tables['claims']}
        self.sources = {s['source_id']: s for s in self.tables['sources']}
        self.events = {e['event_id']: e for e in self.tables['events']}
        self.media = json.loads((root/'site/media.json').read_text())
        self.checks = {c['source_id']:c for c in json.loads((root/'site/reference_checks.json').read_text())}
        self.investigations = json.loads((root/'site/investigations.json').read_text())
        self.by_id = {f['id']:f for f in self.findings}
        self.routes = []

    def href(self, path=''):
        return self.base + '/' + path.lstrip('/')

    def absolute(self, path=''):
        return self.config['url'].rstrip('/') + '/' + path.lstrip('/')

    def asset_href(self, path):
        digest=hashlib.sha256((self.root/'site'/path).read_bytes()).hexdigest()[:12]
        return self.href(path)+'?v='+digest

    def asset_absolute(self, path):
        digest=hashlib.sha256((self.root/'site'/path).read_bytes()).hexdigest()[:12]
        return self.absolute(path)+'?v='+digest

    def share(self, f):
        payload = dict(title=f['title'], summary=f['summary'], status='Document review · verified source records',
                       boundary=f['boundary'], url=self.absolute(f"findings/{f['id']}/"))
        return f'<button type="button" class="share-trigger" data-share="{esc(json.dumps(payload))}">Share story ↗</button>'

    def heading(self, title, desc, label='Reporting'):
        return f'<header class="page-heading"><p class="eyebrow">{esc(label)}</p><h1>{esc(title)}</h1><p class="dek">{esc(desc)}</p></header>'

    def page(self, route, title, description, body, active='', image='assets/share.png'):
        cfg = self.config
        canonical = self.absolute(route)
        content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Doomsday Watch</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}"><meta property="og:type" content="{'website' if not route else 'article'}"><meta property="og:site_name" content="Doomsday Watch">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(self.asset_absolute(image))}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{esc(title)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(description)}"><meta name="twitter:image" content="{esc(self.asset_absolute(image))}">
<link rel="icon" href="{self.href('assets/favicon.svg')}" type="image/svg+xml"><link rel="stylesheet" href="{self.asset_href('assets/style.css')}">
<link rel="alternate" type="application/atom+xml" title="Doomsday Watch reporting" href="{self.href('feed.xml')}"><script defer src="{self.asset_href('assets/app.js')}"></script></head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="edition-bar wrap"><span>Independent reporting</span><span>Security · Infrastructure · Civil preparedness</span><time datetime="{esc(cfg['research_cutoff'])}">{esc(date_label(cfg["research_cutoff"]))} edition</time></div>
<header class="masthead wrap"><a class="brand" href="{self.href()}"><span class="brand-name">Doomsday Watch<span>{esc(cfg["subtitle"])}</span></span></a>{self.status_panel()}</header>
<main id="main" class="wrap">{body}</main>
<footer><div class="wrap footer-main"><div><a class="footer-brand" href="{self.href()}">Doomsday Watch</a><p>Independent reporting on preparedness, security and resilience.</p></div><div class="footer-links"><a href="{self.href('methods/')}">Methods</a><a href="{self.href('sources/')}">Source registry</a><a href="{self.href('corrections/')}">Corrections</a><a href="{self.href('about/')}">About the publication</a><a href="{self.href('feed.xml')}">RSS / Atom</a></div></div><div class="wrap footer-note"><p>The appearance of U.S. Department of War (DoW) visual information does not imply or constitute DoW endorsement.</p><a href="{esc(cfg['repository'])}">Public research repository ↗</a></div></footer>
<dialog id="share-dialog" aria-labelledby="share-title"><div class="dialog-top"><p class="eyebrow">Share this story</p><button type="button" id="close-share" class="dialog-close" aria-label="Close share composer">×</button></div><h2 id="share-title">Share story</h2><label for="share-text">Suggested post · edit before sharing</label><textarea id="share-text" rows="8"></textarea><div class="actions"><button class="primary" id="copy-post" type="button">Copy post</button><button class="button secondary" id="copy-link" type="button">Copy link</button><button class="button secondary" id="native-share" type="button">Share…</button></div><div class="share-destinations"><a data-destination="email">Email</a><a data-destination="facebook" target="_blank" rel="noopener noreferrer">Facebook ↗</a><a data-destination="linkedin" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a></div><p class="message" id="share-message" role="status"></p><p class="subtle">Social previews use the published headline and image. Custom text may need to be pasted into your post.</p></dialog>
</body></html>'''
        path = self.out/route/'index.html' if route else self.out/'index.html'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)
        self.routes.append(route)

    def source_ids(self, finding):
        return sorted({self.claims[cid]['source_id'] for cid in finding['claim_ids']})

    def photo(self, image_id, full=False, eager=False):
        m=self.media[image_id]
        return f'''<figure class="story-photo {esc(image_id)}"><img src="{self.asset_href(m['path'])}" alt="{esc(m['alt'])}" width="{m['width']}" height="{m['height']}" loading="{'eager' if eager else 'lazy'}" decoding="async"><figcaption>{esc(m['caption'])+' ' if full else ''}<span>{esc(m['credit'])}</span> <a href="{esc(m['source_url'])}" rel="noreferrer" aria-label="Image source: {esc(m['credit'])}">↗</a></figcaption></figure>'''

    def references(self, source_ids, prefix, image_id=None, finding=None):
        ids=sorted(set(source_ids))
        items=[]
        for sid in ids:
            s=self.sources[sid];c=self.checks[sid]
            items.append(f'''<li><a href="{esc(s['url'])}" rel="noreferrer">{esc(s['title'])} ↗</a><p>{esc(s['publisher'])} · {esc(s['published_at'] or 'Publication date not recorded')}</p><p>{esc(s['locator'])}. Link checked {esc(c['checked_at'][:10])}.</p></li>''')
        notes=''
        if finding:
            notes=f'<h3>Reporting notes</h3><p>{esc(finding["boundary"])}</p><p><strong>Source support:</strong> high confidence in the documented proposition. Broader interpretations are assessed separately.</p>'
        if image_id:
            m=self.media[image_id]
            notes+=f'<h3>Image credit & reuse</h3><p>{esc(m["credit"])}. <a href="{esc(m["source_url"])}">Original record</a> · <a href="{esc(m["license_url"])}">{esc(m["license"])}</a>. {esc(m["changes"])}</p>'
        return f'<details class="references" id="refs-{esc(prefix)}"><summary>Sources & reporting notes <span>{len(ids)} reference'+('s' if len(ids)!=1 else '')+f'</span></summary><div class="reference-body"><ol>{"".join(items)}</ol>{notes}</div></details>'

    def card(self, finding, layout='standard'):
        f=finding
        if layout == 'lead':
            return f'''<article class="story-card lead" data-finding data-sector="{f['sector']}"><p class="eyebrow">{esc(f['kicker'])} <span>/ {esc(f['format'])}</span></p><h2><a href="{self.href('findings/'+f['id']+'/')}">{esc(f['title'])}</a></h2>{self.photo(f['image_id'],eager=True)}<p class="story-dek">{esc(f['summary'])}</p><div class="story-meta"><time datetime="{f['published_at']}">{esc(date_label(f['published_at']))}</time>{self.share(f)}</div>{self.references(self.source_ids(f),f['id'],f['image_id'])}</article>'''
        return f'''<article class="story-card {layout}" data-finding data-sector="{f['sector']}">{self.photo(f['image_id'])}<div class="story-copy"><p class="eyebrow">{esc(f['kicker'])} <span>/ {esc(f['format'])}</span></p><h3><a href="{self.href('findings/'+f['id']+'/')}">{esc(f['title'])}</a></h3><p class="story-dek">{esc(f['summary'])}</p><div class="story-meta"><time datetime="{f['published_at']}">{esc(date_label(f["published_at"]))}</time>{self.share(f)}</div>{self.references(self.source_ids(f),f['id'],f['image_id'])}</div></article>'''

    def event_date(self,finding):
        return finding.get('event_date') or min(self.events[self.claims[cid]['event_id']]['event_date'] for cid in finding['claim_ids'])

    def watch_notes(self,f):
        if not f.get('watch_reason'):return ''
        return '<aside class="watch-notes" aria-label="Investigation watch criteria"><p class="eyebrow">On our watch</p><p>'+esc(f['watch_reason'])+'</p><h3>Historical comparison</h3><p>'+esc(f['baseline_note'])+'</p><h3>Next records to watch</h3><p>'+esc(f['change_trigger'])+'</p><span class="watch-status">'+esc(f['watch_status'])+'</span></aside>'

    def watch_article(self,f,eager=False):
        text=''.join('<section><h3>'+esc(section['heading'])+'</h3>'+''.join('<p>'+esc(p)+'</p>' for p in section['paragraphs'])+'</section>' for section in f['sections'])
        return f'''<article class="watch-story" id="watch-{f['id']}" data-watch-story="{f['id']}"><header><p class="eyebrow">{esc(f['kicker'])} / {esc(f['format'])}</p><h2><a href="{self.href('findings/'+f['id']+'/')}">{esc(f['title'])}</a></h2><p class="story-dek">{esc(f['summary'])}</p><div class="story-meta"><span>{esc(f.get("event_label", "Event"))}: <time datetime="{self.event_date(f)}">{esc(date_label(self.event_date(f)))}</time></span><span>Reported {esc(date_label(f['published_at']))}</span>{self.share(f)}</div></header><div class="watch-story-layout"><div>{self.photo(f['image_id'],full=True,eager=eager)}</div><div class="prose watch-copy">{text}{self.watch_notes(f)}{self.references(self.source_ids(f),'watch-'+f['id'],f['image_id'],f)}<a class="text-link" href="{self.href('findings/'+f['id']+'/')}">Story permalink & sharing →</a></div></div></article>'''

    def indicator_notes(self,item):
        note='<strong>'+esc(item['label'])+':</strong> '+esc(item['note'])
        if item['source_url']:note+=' <a href="'+esc(item['source_url'])+'" rel="noreferrer">Official source ↗</a>'
        if item['id']=='dhs':note+=' <a href="https://www.dhs.gov/national-terrorism-advisory-system" rel="noreferrer">DHS advisory page ↗</a>'
        if item.get('review_due'):note+='<p>Source review due: '+esc(datetime.fromisoformat(item['review_due']).astimezone(ZoneInfo('America/New_York')).strftime('%b %d, %Y, %I:%M %p %Z'))+'. This is an editorial review deadline, not official policy expiration.</p>'
        if item.get('last_verified'):
            old=item['last_verified'];note+='<p>Last verified: '+esc(old['value'])+' ('+esc(datetime.fromisoformat(old['verified_at']).astimezone(ZoneInfo('America/New_York')).strftime('%b %d, %Y, %I:%M %p %Z'))+'). This is historical, not a current reading.</p>'
        for advisory in item.get('advisories',[]):
            note+='<p><a href="'+esc(advisory['url'])+'" rel="noreferrer">'+esc(advisory['summary'])+'</a> · '+esc(advisory['type'])+' · expires '+esc(datetime.fromisoformat(advisory['expires_at']).astimezone(ZoneInfo('America/New_York')).strftime('%b %d, %Y, %I:%M %p %Z'))+'.</p>'
        return note

    def status_panel(self):
        status=json.loads((self.root/'site/status.json').read_text())
        items=''
        for item in status['items']:
            key=item['id'];state,value=display_indicator(item,status)
            graphic='<span class="status-glyph" aria-hidden="true">◌</span>'
            if key=='clock':
                graphic='<svg class="clock-glyph" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="20"/><path d="M24 9v15l-2-16M24 3v5M45 24h-5M24 45v-5M3 24h5"/></svg>'
            elif state=='verified' and key=='uk':
                level={'LOW':1,'MODERATE':2,'SUBSTANTIAL':3,'SEVERE':4,'CRITICAL':5}.get(item['value'],0)
                graphic='<span class="status-bars" aria-hidden="true">'+''.join('<i'+(' class="on"' if n<level else '')+'></i>' for n in range(5))+'</span>'
            items+=f'<div class="indicator {esc(state)}" data-indicator="{esc(key)}">{graphic}<div><span class="indicator-label">{esc(item["label"])}</span><strong class="indicator-value">{esc(value)}</strong></div></div>'
        notes=''.join('<li data-indicator-note="'+esc(i['id'])+'">'+self.indicator_notes(i)+'</li>' for i in status['items'])
        stamp=datetime.fromisoformat(status['checked_at']).astimezone(ZoneInfo('America/New_York')).strftime('%b %d, %Y, %I:%M %p %Z')
        return f'<aside class="status-panel" aria-label="Published security indicators" data-status-url="{self.href("status.json")}"><p class="eyebrow">Published indicators</p><div class="indicator-grid">{items}</div><details class="indicator-notes"><summary>Sources, scope & freshness</summary><p>Daily source checks. Latest attempt: <time data-status-checked datetime="{esc(status["checked_at"])}">{esc(stamp)}</time>. Checks older than 36 hours are marked stale. Advisory dates and source-review deadlines can require an earlier update.</p><p>Separate systems, not a combined risk score. The Clock is a symbolic expert assessment, not a government alert or countdown. European indicators refer to individual countries. This is not a live warning service.</p><ul>{notes}</ul></details></aside>'

    def dossier_card(self, dossier):
        d=dossier
        ids=sorted({sid for fid in d['finding_ids'] for sid in self.source_ids(self.by_id[fid])})
        return f'''<article class="dossier-card">{self.photo(d['image_id'])}<div class="story-copy"><p class="eyebrow">{esc(d['status'])}</p><h3><a href="{self.href('investigations/'+d['slug']+'/')}">{esc(d['title'])}</a></h3><p>{esc(d['summary'])}</p><a class="text-link" href="{self.href('investigations/'+d['slug']+'/')}">Read the file →</a>{self.references(ids,d['id'],d['image_id'])}</div></article>'''

    def source(self, sid):
        s=self.sources[sid];check=self.checks[sid]
        return f'''<section class="source" id="{sid}"><p class="eyebrow">{sid} / {esc(s['publisher'])}</p><h3><a href="{esc(s['url'])}" rel="noreferrer">{esc(s['title'])} ↗</a></h3><p>Published {esc(s['published_at'] or 'date not recorded')} · Link checked {esc(check['checked_at'][:10])}</p><p>{esc(s['locator'])}</p></section>'''

    def build(self):
        if self.out.resolve()==self.root.resolve() or self.root.resolve().is_relative_to(self.out.resolve()):
            raise ValueError('Build output cannot replace the repository or its parent')
        if self.out.exists() and any(self.out.iterdir()):
            if not (self.out/'.preparedness-build').exists() and self.out.resolve()!=(self.root/'_site').resolve():
                raise ValueError('Refusing to clear an unrecognized output directory')
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True,exist_ok=True)
        (self.out/'.preparedness-build').write_text('Generated public artifact; safe to rebuild.\n')
        shutil.copytree(self.root/'site/assets',self.out/'assets',dirs_exist_ok=True)
        ordered=sorted(self.findings,key=lambda f:(f['published_at'],self.event_date(f),f['id']),reverse=True)
        timeline='<div class="watch-timeline" aria-label="Watch List event timeline"><div class="timeline-label"><strong>Watch timeline</strong><span>Event & record dates · select a story →</span></div><div class="timeline-track">'+''.join(f'<a href="#watch-{f["id"]}" data-watch-link="{f["id"]}"><time datetime="{self.event_date(f)}">{esc(date_label(self.event_date(f)))}</time><span>{esc(f["kicker"])}</span></a>' for f in sorted(self.findings,key=lambda f:(self.event_date(f),f['id'])))+'</div></div>'
        body=self.heading('Watch List','Tracking unusual changes in military readiness, government security and private preparedness. Each report examines what changed, the historical context and the evidence needed to establish whether activity is abnormal.','Independent investigations')+timeline+'<div class="watch-stories">'+''.join(self.watch_article(f,i==0) for i,f in enumerate(ordered))+'</div>'
        self.page('','Watch List','Independent reporting on military activity, government preparations, cyber threats and civil resilience.',body)
        # Preserve bookmarks without maintaining duplicate index pages.
        for retired in ('investigations/', 'findings/', 'timeline/'):
            path=self.out/retired/'index.html';path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investigations · Doomsday Watch</title><meta name="robots" content="noindex"><link rel="canonical" href="{self.absolute()}"><meta http-equiv="refresh" content="0;url={self.href()}"></head><body><p><a href="{self.href()}">Continue to the Watch List</a></p></body></html>''')
        public_claims=set();public_sources=set()
        for f in self.findings:
            ids=self.source_ids(f);public_claims.update(f['claim_ids']);public_sources.update(ids)
            public_sources.add(self.media[f['image_id']]['source_id'])
            body=f'<p class="crumb"><a href="{self.href()}">Watch List</a> / {esc(f["kicker"])}</p>'+self.heading(f['title'],f['summary'],f['kicker']+' / '+f['format'])
            body+=f'<div class="article-byline"><span>Doomsday Watch</span><time datetime="{f["published_at"]}">Published {esc(date_label(f["published_at"]))}</time>{self.share(f)}</div>'+self.photo(f['image_id'],full=True,eager=True)
            text=''.join(f'<section><h2>{esc(section["heading"])}</h2>'+''.join(f'<p>{esc(paragraph)}</p>' for paragraph in section['paragraphs'])+'</section>' for section in f['sections'])
            body+=f'<div class="article-layout"><article class="prose story-body">{text}{self.watch_notes(f)}{self.references(ids,f["id"],f["image_id"],f)}<div class="article-share">{self.share(f)} <a href="{self.href("assets/"+f["id"]+".png")}" download>Download image card</a><button id="print-finding" type="button" class="share-trigger">Print / save PDF</button></div></article><aside class="sidebar"><h2>In this reporting file</h2><p>{esc(f["kicker"])}</p><p>Record {f["id"]}</p><a href="{self.href("methods/")}">Reporting standards →</a><a href="{self.href("corrections/")}">Corrections →</a></aside></div>'
            self.page('findings/'+f['id']+'/',f['title'],f['summary'],body,'findings/','assets/'+f['id']+'.png')
        for d in self.investigations:
            ids=sorted({sid for fid in d['finding_ids'] for sid in self.source_ids(self.by_id[fid])})
            body=f'<p class="crumb"><a href="{self.href()}">Watch List</a> / {d["id"]}</p>'+self.heading(d['title'],d['summary'],d['status'])+self.photo(d['image_id'],full=True,eager=True)
            body+=f'<div class="article-layout"><article class="prose"><h2>The reporting focus</h2><p>{esc(d["focus"])}</p><h2>Questions we are pursuing</h2><ul>'+''.join('<li>'+esc(q)+'</li>' for q in d['questions'])+'</ul>'+self.references(ids,d['id'],d['image_id'])+'</article><aside class="sidebar"><h2>Related coverage</h2>'+''.join(f'<a href="{self.href("findings/"+fid+"/")}">{esc(self.by_id[fid]["title"])}</a>' for fid in d['finding_ids'])+'</aside></div>'
            self.page('investigations/'+d['slug']+'/',d['title'],d['summary'],body,'investigations/')
        body=self.heading('Source registry','The records cited in our published reporting. Each story also carries its own expandable reference section.','Reporting resources')+'<section class="editorial-section prose">'+''.join(self.source(sid) for sid in sorted(public_sources))+'</section>'
        self.page('sources/','Source registry','Source documents and image records for published coverage.',body)
        for route,title,filename,desc in [
            ('methods/','Reporting standards','METHODOLOGY.md','How we verify records, assess claims and compare developments with earlier activity.'),
            ('corrections/','Corrections & updates','CORRECTIONS.md','Substantive corrections, qualifications and revisions to the research record.')]:
            self.page(route,title,desc,self.heading(title,desc,'Editorial standards')+'<article class="prose document-page">'+markdown((self.root/'docs'/filename).read_text())+'</article>',route)
        assessment='''<h2>The current picture</h2><p>The reporting assembled so far has not established a shared, undisclosed imminent global threat. The coverage is limited: several operational questions remain unresolved, and complete historical comparisons are still being assembled.</p><h2>Policy history matters</h2><p>Household preparedness guidance and large military exercises have documented precedents. Our coverage also examines changes in presidential protection, private shelter projects and reports of command-aircraft activity. Each requires its own historical comparison.</p><h2>Unfinished reporting</h2><p>The investigation still needs comparable transport, procurement and delivery records across the eight research sectors. A policy announcement or contract ceiling cannot substitute for evidence of actual activity.</p><h2>What could change the assessment</h2><p>Verified operational activations, emergency deliveries or a reproducible departure from comparable earlier activity would warrant further reporting. Current astronomical and space-weather conditions have not been established by this publication.</p>'''
        assessment+=self.references(sorted({self.claims[cid]['source_id'] for cid in public_claims}),'assessment')
        self.page('assessment/','Current assessment','The findings and outstanding questions in the preparedness investigation.',self.heading('Current assessment','A review of the reporting published in this edition.','Analysis')+'<article class="prose document-page">'+assessment+'</article>')
        about='''<h2>Our remit</h2><p>Doomsday Watch investigates how governments, institutions and private actors prepare for war, infrastructure disruption and major emergencies. Our coverage examines military logistics, emergency procurement, geopolitics, civilian infrastructure, medical readiness, financial and insurance indicators, continuity of government, and astronomical hazards.</p><h2>The reporting</h2><p>We examine public documents, follow reported developments back to their sources and compare new activity with historical records. Each published story carries source links and reporting notes. Unverified research leads are not presented as established events.</p><h2>Editorial independence</h2><p>This is an independent publication, not a government warning service. The project uses AI assistance for research organization, drafting and software development. AI output is not a source of evidence; claims require verification against underlying records.</p><h2>Corrections</h2><p>Substantive qualifications and corrections remain part of the research record. To propose a correction, identify the story or finding ID, the relevant passage and a supporting primary source through the public research repository. Keep private personal information out of public submissions.</p><h2>Privacy</h2><p>The site has no accounts, forms, analytics scripts or tracking pixels. GitHub Pages processes ordinary hosting requests under its own policies. Source and sharing destinations have their own privacy policies; social scripts are not embedded on these pages.</p><h2>Photography</h2><p>Images are obtained from the cited source organizations and credited with their reuse terms. Historical and illustrative material is identified in captions. Photographs do not establish facts beyond their documented context.</p>'''
        self.page('about/','About Doomsday Watch','Independent investigative reporting on government preparedness, military readiness and civil resilience.',self.heading('About Doomsday Watch','Independent reporting on the decisions behind preparations for crisis.','The publication')+'<article class="prose document-page">'+about+'</article>')
        self.page('404/','Page not found','The requested page is unavailable.',self.heading('Page not found','Browse our reporting or investigation files.')+f'<p class="editorial-section"><a href="{self.href()}">Return to the homepage →</a></p>')
        shutil.copy2(self.out/'404/index.html',self.out/'404.html')
        (self.out/'.nojekyll').touch()
        self.feed()
        urlset=Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for route in self.routes:
            if route=='404/':continue
            url=SubElement(urlset,'url');SubElement(url,'loc').text=self.absolute(route)
        (self.out/'sitemap.xml').write_bytes(tostring(urlset,encoding='utf-8',xml_declaration=True))
        (self.out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+self.absolute('sitemap.xml')+'\n')
        shutil.copy2(self.root/'site/status.json',self.out/'status.json')
        (self.out/'findings.json').write_text(json.dumps(self.findings,ensure_ascii=False,indent=2)+'\n')
        (self.out/'publication-manifest.json').write_text(json.dumps({'cutoff':self.config['research_cutoff'],'finding_ids':[f['id'] for f in self.findings],'claim_ids':sorted(public_claims),'source_ids':sorted(public_sources),'investigation_ids':[d['id'] for d in self.investigations]},indent=2)+'\n')

    def feed(self):
        feed=Element('feed',xmlns='http://www.w3.org/2005/Atom')
        SubElement(feed,'title').text='Doomsday Watch · Reporting'
        SubElement(feed,'id').text=self.absolute()
        SubElement(feed,'updated').text=max((f['updated_at'] for f in self.findings),default=self.config['research_cutoff'])+'T12:00:00-05:00'
        SubElement(feed,'link',href=self.absolute('feed.xml'),rel='self');SubElement(feed,'link',href=self.absolute())
        author=SubElement(feed,'author');SubElement(author,'name').text='Doomsday Watch'
        for f in sorted(self.findings,key=lambda f:(f['updated_at'],f['id']),reverse=True):
            entry=SubElement(feed,'entry');SubElement(entry,'id').text=self.absolute('findings/'+f['id']+'/')
            SubElement(entry,'title').text=f['title'];SubElement(entry,'link',href=self.absolute('findings/'+f['id']+'/'))
            SubElement(entry,'updated').text=f['updated_at']+'T12:00:00-05:00';SubElement(entry,'summary').text=f['summary']
        (self.out/'feed.xml').write_bytes(tostring(feed,encoding='utf-8',xml_declaration=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'_site');args=parser.parse_args()
    site=Site(ROOT,args.output);site.build()
    print(f'Built {len(site.routes)} pages with {len(site.findings)} published stories in {args.output}')
