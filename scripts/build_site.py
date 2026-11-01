#!/usr/bin/env python3
"""Build the public, allowlisted GitHub Pages artifact using standard Python only."""
import argparse
import html
import json
import re
import shutil
import textwrap
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring
from validate import ROOT, validate

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
    return config, tables, [f for f in all_findings if f['publication_status'] == 'published']


class Site:
    def __init__(self, root, out):
        self.root, self.out = root, out
        self.config, self.tables, self.findings = load_public(root)
        self.base = urlsplit(self.config['url']).path.rstrip('/')
        self.claims = {c['claim_id']: c for c in self.tables['claims']}
        self.sources = {s['source_id']: s for s in self.tables['sources']}
        self.events = {e['event_id']: e for e in self.tables['events']}
        self.routes = []

    def href(self, path=''):
        return self.base + '/' + path.lstrip('/')

    def absolute(self, path=''):
        return self.config['url'].rstrip('/') + '/' + path.lstrip('/')

    def share(self, f):
        payload = dict(title=f['title'], summary=f['summary'], status='Verified record · confidence in source support: high',
                       boundary=f['boundary'], url=self.absolute(f"findings/{f['id']}/"))
        return f'<button type="button" class="share-trigger" data-share="{esc(json.dumps(payload))}">Share finding ↗</button>'

    def page(self, route, title, description, body, active='', image='assets/share.png'):
        cfg = self.config
        nav = [('findings/', 'Findings'), ('investigations/', 'Investigations'), ('timeline/', 'Timeline'), ('methods/', 'Methods'), ('roadmap/', 'Roadmap')]
        navigation = ''.join(f'<a href="{self.href(path)}"'+(' aria-current="page"' if active==path else '')+f'>{name}</a>' for path,name in nav)
        canonical = self.absolute(route)
        content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Preparedness Observatory</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}"><meta property="og:type" content="article"><meta property="og:site_name" content="Preparedness Observatory">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(self.absolute(image))}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{esc(title)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(description)}"><meta name="twitter:image" content="{esc(self.absolute(image))}">
<link rel="icon" href="{self.href('assets/favicon.svg')}" type="image/svg+xml"><link rel="stylesheet" href="{self.href('assets/style.css')}">
<link rel="alternate" type="application/atom+xml" title="Preparedness findings" href="{self.href('feed.xml')}"><script defer src="{self.href('assets/app.js')}"></script></head><body>
<a class="skip" href="#main">Skip to content</a><div class="topline"><div class="wrap"><span>Independent public-source research</span><span>{esc(cfg['edition'])} / Research through {esc(cfg['research_cutoff'])}</span></div></div>
<header class="masthead wrap"><a class="brand" href="{self.href()}"><span class="mark" aria-hidden="true">◎</span><span class="brand-name">PREPAREDNESS<small>Observatory</small></span></a><nav aria-label="Main navigation">{navigation}</nav></header>
<main id="main" class="wrap">{body}</main>
<footer><div class="wrap"><div>Preparedness Observatory<br>Evidence and uncertainty, kept together.</div><div><a href="{self.href('sources/')}">Sources</a><a href="{self.href('corrections/')}">Corrections</a><a href="{self.href('about/')}">About & privacy</a><a href="{esc(cfg['repository'])}">GitHub ↗</a></div></div></footer>
<dialog id="share-dialog" aria-labelledby="share-title"><div class="dialog-top"><p class="eyebrow">Share the evidence</p><button type="button" id="close-share" class="dialog-close" aria-label="Close share composer">×</button></div><h2 id="share-title">Keep the evidence in context.</h2><label for="share-text">Suggested post · edit before sharing</label><textarea id="share-text" rows="8"></textarea><div class="actions"><button class="primary" id="copy-post" type="button">Copy post</button><button class="button secondary" id="copy-link" type="button">Copy link</button><button class="button secondary" id="native-share" type="button">Share…</button></div><div class="share-destinations"><a data-destination="email">Email</a><a data-destination="facebook" target="_blank" rel="noopener noreferrer">Facebook ↗</a><a data-destination="linkedin" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a></div><p class="message" id="share-message" role="status"></p><p class="subtle">Your post is sent only when you choose a destination. Link previews use the published finding title, image, and description; custom post text may need to be pasted.</p></dialog>
</body></html>'''
        path = self.out/route/'index.html' if route else self.out/'index.html'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)
        self.routes.append(route)

    def heading(self, title, desc, label='Research desk'):
        return f'<header class="page-heading"><p class="eyebrow">{esc(label)}</p><h1>{esc(title)}</h1><p>{esc(desc)}</p></header>'

    def card(self, f):
        return f'''<article class="finding-card" data-finding data-sector="{f['sector']}"><div class="card-top"><span>{f['id']} / {esc(SECTORS[f['sector']][0])}</span><span>{f['published_at']}</span></div><h3><a href="{self.href('findings/'+f['id']+'/')}">{esc(f['title'])}</a></h3><p>{esc(f['summary'])}</p><p class="boundary"><strong>Limit:</strong> {esc(f['boundary'])}</p><div class="card-foot"><span class="badge">Verified record</span>{self.share(f)}</div></article>'''

    def source(self, sid):
        s = self.sources[sid]
        return f'''<section class="source" id="{sid}"><p class="eyebrow">{sid} · {esc(s['source_type'].replace('_',' '))}</p><h3><a href="{esc(s['url'])}" rel="noreferrer">{esc(s['title'])} ↗</a></h3><p>{esc(s['publisher'])} · Published {esc(s['published_at'] or 'date not recorded')} · Inspected {esc(s['accessed_at'])}</p><p><strong>Record locator:</strong> {esc(s['locator'])}<br><strong>Independence group:</strong> {esc(s['independence_group'])}</p></section>'''

    def build(self):
        if self.out.resolve() == self.root.resolve() or self.root.resolve().is_relative_to(self.out.resolve()):
            raise ValueError('Build output cannot replace the repository or its parent')
        if self.out.exists() and any(self.out.iterdir()):
            if not (self.out/'.preparedness-build').exists():
                # Accept the initial generated build only in the known ignored output folder.
                if self.out.resolve() != (self.root/'_site').resolve():
                    raise ValueError('Refusing to clear an unrecognized output directory')
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True,exist_ok=True)
        (self.out/'.preparedness-build').write_text('Generated public artifact; safe to rebuild.\n')
        shutil.copytree(self.root/'site/assets',self.out/'assets',dirs_exist_ok=True)
        sectors = ''.join(f'<a class="sector" href="{self.href("investigations/#"+key)}"><span>0{i}</span><h3>{title}</h3><p>{desc}</p></a>' for i,(key,(title,desc)) in enumerate(SECTORS.items(),1))
        visual = '''<div class="hero-visual" role="img" aria-label="Illustrative observation grid; not live threat data"><svg viewBox="0 0 420 340" fill="none" aria-hidden="true"><defs><pattern id="grid" width="35" height="35" patternUnits="userSpaceOnUse"><path d="M35 0H0V35" stroke="#acc2a7" stroke-width=".4"/></pattern></defs><rect width="420" height="340" fill="url(#grid)"/><g stroke="#cad8b9"><circle cx="290" cy="120" r="100"/><circle cx="290" cy="120" r="70"/><circle cx="290" cy="120" r="35"/><path d="M160 120H420M290 0V250M218 49L361 191M219 190L360 50"/></g><circle cx="335" cy="75" r="5" fill="#f3cb84"/><path d="M290 120L335 75" stroke="#f3cb84"/></svg><div class="caption"><strong>Observe.<br>Verify. Understand.</strong>Eight research lenses.<br>One transparent evidence trail.</div></div>'''
        home = f'''<section class="hero"><div><p class="eyebrow">The preparedness research project / 001</p><h1>Read the signals.<br><em>Question the pattern.</em></h1><p class="lede">An open investigation into government preparedness and potential global threats. We trace claims to their sources, compare them with history, and make the limits visible.</p><div class="actions"><a class="button" href="{self.href('findings/')}">Explore the findings ↗</a><a class="button secondary" href="{self.href('assessment/')}">Read the assessment</a></div></div>{visual}</section>
<section class="assessment"><p class="eyebrow">Current assessment</p><div><h2>A shared, undisclosed imminent global threat has not been established by this research.</h2><p>Some apparent signals have older policy precedents. Other leads still need primary records and comparable baselines. This is a limited evidence assessment, not an all-clear. <a href="{self.href('assessment/')}">Read the reasoning and gaps →</a></p></div></section>
<div class="stats"><div class="stat"><strong>{len(self.findings):02}</strong><span>Published findings</span></div><div class="stat"><strong>08</strong><span>Research workstreams</span></div><div class="stat"><strong>{len(self.tables['leads']):02}</strong><span>Open research leads</span></div><div class="stat"><strong>2023–25</strong><span>Baseline collection window</span></div></div>
<section class="section"><div class="section-head"><div><p class="eyebrow">The evidence, in context</p><h2>Start with what we can document.</h2></div><a href="{self.href('findings/')}">Browse all findings →</a></div><div class="finding-grid">{''.join(self.card(f) for f in self.findings)}</div></section>
<section class="section"><div class="section-head"><div><p class="eyebrow">Follow the investigation</p><h2>Eight lenses. No assumed conclusion.</h2></div><p>Open questions are leads, not findings.</p></div><div class="sectors">{sectors}</div></section>
<aside class="roadmap-strip"><div><p class="eyebrow">On the horizon</p><h2>From understanding<br>to practical readiness.</h2></div><div><p>A future family preparedness planner will help households think through supplies, communication, destinations, shelter, and evacuation routes. It is in planning; no family information is collected here.</p><a href="{self.href('roadmap/')}">See the project roadmap →</a></div></aside>'''
        self.page('', 'Read the signals. Question the pattern.', self.config['tagline'], home)
        opts = ''.join(f'<option value="{key}">{title}</option>' for key,(title,_) in SECTORS.items())
        body = self.heading('Findings you can inspect. Context you can share.', 'Each finding has a permanent record, its supporting sources, and an explicit limit. Published findings currently cover verified documentary facts; unresolved leads remain in the investigation queue.', 'Evidence library')
        body += f'<section class="section"><div class="filters"><label for="search">Search findings<input id="search" type="search" placeholder="Try household advice, medical, NATO…"></label><label for="sector">Research lens<select id="sector"><option value="">All workstreams</option>{opts}</select></label></div><p id="filter-count" class="filter-count" role="status">{len(self.findings)} findings shown</p><div class="finding-grid">'+''.join(self.card(f) for f in self.findings)+'</div><p id="no-results" class="no-results" hidden>No matching findings yet. Try another term, or explore the open investigation leads.</p></section>'
        self.page('findings/', 'Evidence library', 'Search sourced preparedness findings and share their permanent records.', body, 'findings/')
        public_claims, public_sources = set(), set()
        for f in self.findings:
            cs = [self.claims[cid] for cid in f['claim_ids']]
            public_claims.update(f['claim_ids'])
            source_ids = sorted({c['source_id'] for c in cs})
            public_sources.update(source_ids)
            claim_rows = ''.join(f'<tr><td>{c["claim_id"]}</td><td>{esc(c["proposition"])}</td><td><a href="#{c["source_id"]}">{c["source_id"]}</a></td></tr>' for c in cs)
            body = f'<p class="crumb"><a href="{self.href("findings/")}">Findings</a> / {f["id"]}</p>'+self.heading(f['title'],f['summary'],f'{f["id"]} / {SECTORS[f["sector"]][0]}')
            body += f'''<div class="article-layout"><article class="prose"><span class="badge">Confirmed documentary fact</span><h2>Why this matters</h2><p>{esc(f['why_it_matters'])}</p><h2>What this does — and does not — establish</h2><blockquote>{esc(f['boundary'])}</blockquote><h2>Alternative explanations</h2><p>{esc(f['alternatives'])}</p><h2>The next question</h2><p>{esc(f['next_question'])}</p><h2>The underlying record</h2><div class="table-wrap"><table><thead><tr><th>Claim</th><th>Proposition</th><th>Source</th></tr></thead><tbody>{claim_rows}</tbody></table></div><h2>Sources & citation trail</h2>{''.join(self.source(sid) for sid in source_ids)}<h2>Share with the boundary attached</h2>{self.share(f)}<p class="subtle"><a href="{self.href('assets/'+f['id']+'.png')}" download>Download the share card (PNG)</a> · <button type="button" class="share-trigger" id="print-finding">Print / save as PDF</button></p></article><aside class="sidebar"><h2>Record details</h2><dl><div><dt>Permanent ID</dt><dd>{f['id']}</dd></div><div><dt>Verification</dt><dd>Verified</dd></div><div><dt>Source support confidence</dt><dd>High · not a threat probability</dd></div><div><dt>Published / updated</dt><dd>{f['published_at']} / {f['updated_at']}</dd></div><div><dt>Review boundary</dt><dd>Documented facts only</dd></div></dl><p><a href="{self.href('methods/')}">How we verify →</a></p><p><a href="{self.href('corrections/')}">Corrections & revisions →</a></p></aside></div>'''
            self.page(f"findings/{f['id']}/", f['title'],f['summary']+' Limit: '+f['boundary'],body,'findings/',f"assets/{f['id']}.png")
        body = self.heading('An investigation organized around questions.', 'These research leads are research tasks. A lead’s priority reflects the importance of verification, not the likelihood of danger. No candidate anomaly has a completed quantitative baseline.', 'Research workstreams')
        body += '<div class="prose section"><p class="notice">Status: source-integrity review and baseline collection are ongoing. Leads below are unverified or incompletely verified unless linked to a published finding. Repetition across sources is not independent corroboration.</p>'
        for key,(title,desc) in SECTORS.items():
            body += f'<section id="{key}"><h2>{title}</h2><p>{desc}</p>'
            # L10 is also the financial workstream's source lead; avoid an empty lane.
            leads = [l for l in self.tables['leads'] if l['sector']==key or (key=='financial_insurance' and l['lead_id']=='L10')]
            for lead in leads:
                body += f'<article class="lead"><span class="badge pending">Open lead · {lead["lead_id"]}</span><h3>{esc(lead["subject"])}</h3><p><strong>Verification task:</strong> {esc(lead["next_action"])}</p></article>'
            body += f'<p><a href="{self.href("findings/?sector="+key)}">Published findings in this workstream →</a></p></section>'
        body += '</div>'
        self.page('investigations/','Open investigations','Eight preparedness research workstreams, unresolved questions, and verification tasks.',body,'investigations/')
        body = self.heading('Chronology before correlation.', 'Only verified events supporting published findings appear here. The internal event database also retains alleged events, clearly marked and held apart.', 'Verified timeline')+'<section class="section">'
        event_claims = {}
        for cid in sorted(public_claims):
            c=self.claims[cid];event_claims.setdefault(c['event_id'],[]).append(c)
        for eid in sorted(event_claims,key=lambda eid:self.events[eid]['event_date']):
            e=self.events[eid]
            refs=' · '.join(f'<a href="{self.href("sources/#"+c["source_id"])}">{c["claim_id"]} / {c["source_id"]}</a>' for c in event_claims[eid])
            body += f'<article class="timeline-item"><time>{e["event_date"]}</time><div><h2>{esc(e["description"])}</h2><p>{esc(e["location"])} · Verified documentary record · {refs}</p></div></article>'
        self.page('timeline/','Verified timeline','Dated records behind published preparedness findings.',body+'</section>','timeline/')
        body=self.heading('Follow every published finding back to its source.', 'Publication date, access date, record locator, and shared source origins travel with the evidence. Archived local research backups are separate from these external source links.', 'Citation registry')+'<section class="section prose">'+''.join(self.source(sid) for sid in sorted(public_sources))+'</section>'
        self.page('sources/','Source registry','Exact source links and provenance for published findings.',body)
        for route,title,filename,desc in [
            ('methods/','How we investigate','METHODOLOGY.md','Verification standards, competing hypotheses, confidence, and historical comparisons.'),
            ('corrections/','Corrections stay on the record','CORRECTIONS.md','Material qualifications to earlier research, preserved for accountability.')]:
            self.page(route,title,desc,self.heading(title,desc,'Research standards')+'<article class="prose section">'+markdown((self.root/'docs'/filename).read_text())+'</article>',route)
        assessment='''<h2>The question</h2><p>Do independent, measurable departures from normal preparedness point to a specific approaching threat beyond publicly documented risks?</p><h2>Current judgment</h2><p>The evidence assembled in this initial research does not establish a shared, undisclosed imminent global threat. Confidence in a comprehensive cross-sector conclusion is low: most operational leads and comparable measurements remain incomplete. This is not a finding that all risks are absent.</p><h2>What the published records establish</h2><p>Some public-preparedness measures have older precedents, and legal notices need to be read within their actual scope. The findings library documents these narrow propositions. They weaken some novelty claims but do not explain every reported development.</p><h2>Competing explanations</h2><ul><li>Routine resilience policy, scheduled exercises, and procurement cycles.</li><li>Responses to known conflicts and infrastructure vulnerabilities.</li><li>Selection effects or inaccurate earlier claims creating an apparent pattern.</li><li>A new shared threat: still an unsubstantiated hypothesis requiring specific, independent operational evidence.</li></ul><h2>Baseline status</h2><p>Selected 2023–2025 policy and exercise milestones are documented. All eight workstreams still need complete matched quantitative series. No candidate deviation has been established as an anomaly, and no numerical threat probability is assigned.</p><h2>What would change the assessment</h2><p>Verified unusual activations or emergency deliveries, reproducible deviations from a comparable baseline, or dated authoritative hazard notices. Repeated headlines and contract ceilings alone are insufficient.</p><h2>Coverage limits</h2><p>The initial sample is selective. Source-integrity work remains open. Current asteroid and solar conditions have not been established by this project; dynamic or missing portal data cannot support an all-clear. Published documentary facts should not be generalized into a global threat forecast.</p>'''
        assessment+=f'<p><a href="{self.href("findings/")}">Inspect the published findings →</a> · <a href="{self.href("investigations/")}">See unresolved leads →</a></p>'
        self.page('assessment/','The working assessment','What this investigation currently supports, where it is uncertain, and what would change it.',self.heading('Evidence first. Conclusions proportional.',f'Initial public assessment · Research cutoff {self.config["research_cutoff"]}','Master assessment')+'<article class="prose section">'+assessment+'</article>')
        roadmap='''<h2>1 / Establish the public record</h2><p>Build a public GitHub Pages site with permanent finding URLs, clear evidence status, source citations, share tools, and corrections. Only curated published findings are included in the site artifact.</p><h2>2 / Expand the watchdog investigation</h2><p>Continue verification of research leads and build historical denominators. Look for evidence that supports, refines, expands, or contradicts current ideas. New signals enter a review queue before becoming findings.</p><h2>3 / Recurring investigative updates</h2><p>After launch, a recurring research task will check priority sources, investigate meaningful changes, preserve records, and prepare reviewed site updates. Collection failures must not become threat alerts. The update schedule and activation status will be disclosed here.</p><h2>4 / Preserve a durable archive</h2><p>The local project keeps a private SQLite archive, content-addressed files, and portable backup exports. A backup on the same computer protects revision history but does not protect against device loss. A later independent, encrypted copy and restore-tested archival service will add that protection.</p><h2>5 / A family preparedness planner</h2><p>Planned only; no questionnaire or family data collection has been implemented. The intended guide covers core family members, trusted contacts, household needs, supplies, communications, shelter and evacuation choices, meeting points, destinations, addresses, and alternate routes.</p><p>Supply planning will eventually cover food, water, medicine, energy, clothing, transport, fuel, and lawful personal safety. Quantities and recommendations will need appropriate public-authority sources and household-specific constraints.</p><p>The planner should support private, browser-local answers, a printable family plan, an offline export, and an explicit delete/reset control. Names, home addresses, children’s details, routes, shelter locations, and access information must never enter the public research repository or analytics. Account sync, map routing, or a private backend would require a separate design.</p>'''
        roadmap+=f'<p class="notice"><strong>Monitoring status:</strong> {esc(self.config["monitoring_status"])}. The family planner remains a future phase.</p>'
        self.page('roadmap/','Where this project is heading','Public findings, recurring investigation, durable archiving, and a future private family planner.',self.heading('A public record that can keep growing.','The investigation comes first. Practical planning follows a considered design.','Project roadmap')+'<article class="prose section">'+roadmap+'</article>','roadmap/')
        about='''<h2>Purpose and editorial independence</h2><p>Preparedness Observatory is an independent public-source research project. It is not an official warning service or a government publication. Its purpose is to investigate preparedness claims, compare them with historical context, and preserve uncertainty alongside evidence.</p><h2>How the site is made</h2><p>The project uses AI assistance for research organization, drafting, and software development. AI output is not primary evidence. Every research claim requires verification against its underlying sources. Published findings are curated from the structured research records and include their documentary boundaries.</p><h2>Privacy</h2><p>This static site has no accounts, forms, analytics scripts, tracking pixels, or family-plan storage. GitHub Pages and external source sites may process ordinary request information under their own policies. Social destinations are contacted only after you choose them. Share-composer edits remain in the current page until you choose to copy or send them.</p><h2>Corrections and contributions</h2><p>Use the public research repository to propose a correction with an exact finding ID, primary source link, and explanation. Do not include private personal details in public issues. Corrections remain visible rather than silently replacing earlier judgments.</p><h2>Archival limits</h2><p>The project’s local archive preserves research files and versioned findings offline. A registered source URL is not proof that a copy of that source has been archived. Original-source capture coverage is tracked separately.</p>'''
        self.page('about/','About & privacy','Purpose, editorial standards, AI assistance, privacy and archival limits.',self.heading('An accountable, inspectable research project.','The methods and limits should be as easy to find as the findings.','About & privacy')+'<article class="prose section">'+about+'</article>')
        self.page('404/','Page not found','The requested research page could not be found.',self.heading('This page is not in the record.','Use the findings library or research workstreams to continue.')+f'<p class="section"><a href="{self.href()}">Return to the Observatory →</a></p>')
        shutil.copy2(self.out/'404/index.html',self.out/'404.html')
        (self.out/'.nojekyll').touch()
        self.feed()
        urlset=Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for route in self.routes:
            if route=='404/': continue
            u=SubElement(urlset,'url');SubElement(u,'loc').text=self.absolute(route)
        (self.out/'sitemap.xml').write_bytes(tostring(urlset,encoding='utf-8',xml_declaration=True))
        (self.out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+self.absolute('sitemap.xml')+'\n')
        # Public data is deliberately allowlisted; never copy the research root or local archive.
        (self.out/'findings.json').write_text(json.dumps(self.findings,ensure_ascii=False,indent=2)+'\n')
        (self.out/'publication-manifest.json').write_text(json.dumps({'cutoff':self.config['research_cutoff'],'finding_ids':[f['id'] for f in self.findings],'claim_ids':sorted(public_claims),'source_ids':sorted(public_sources)},indent=2)+'\n')

    def feed(self):
        ns='http://www.w3.org/2005/Atom'
        feed=Element('feed',xmlns=ns)
        SubElement(feed,'title').text='Preparedness Observatory · Findings'
        SubElement(feed,'id').text=self.absolute()
        SubElement(feed,'updated').text=max((f['updated_at'] for f in self.findings),default=self.config['research_cutoff'])+'T12:00:00-05:00'
        SubElement(feed,'link',href=self.absolute('feed.xml'),rel='self')
        SubElement(feed,'link',href=self.absolute())
        author=SubElement(feed,'author');SubElement(author,'name').text='Preparedness Observatory'
        for f in sorted(self.findings,key=lambda f:(f['updated_at'],f['id']),reverse=True):
            entry=SubElement(feed,'entry');SubElement(entry,'id').text=self.absolute('findings/'+f['id']+'/')
            SubElement(entry,'title').text=f['title']
            SubElement(entry,'link',href=self.absolute('findings/'+f['id']+'/'))
            SubElement(entry,'updated').text=f['updated_at']+'T12:00:00-05:00'
            SubElement(entry,'summary').text=f['summary']+' Limit: '+f['boundary']
        (self.out/'feed.xml').write_bytes(tostring(feed,encoding='utf-8',xml_declaration=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'_site');args=parser.parse_args()
    site=Site(ROOT,args.output)
    site.build()
    print(f'Built {len(site.routes)} pages with {len(site.findings)} published findings in {args.output}')
