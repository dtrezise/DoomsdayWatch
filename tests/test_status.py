import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from refresh_status import parse,plain,collect,parse_ntas,parse_france,display_indicator,DHS_PAGE,DHS_FEEDS
from datetime import datetime,timezone
from urllib.error import HTTPError
from build_site import Site

class IndicatorTests(unittest.TestCase):
    def test_only_explicit_current_values(self):
        self.assertEqual(parse('uk','The threat to the UK (England, Wales, Scotland and Northern Ireland) from terrorism is severe.')[0],'SEVERE')
        self.assertEqual(parse('clock','It is now 85 seconds to midnight')[0],'85 seconds')
        self.assertEqual(parse('dhs','There are no current advisories. Expired Advisories')[0],'No active advisory')
        for kind,text in [('uk','Threat levels: low moderate substantial severe critical'),('dhs','Expired bulletin: no advisories in 2020'),('clock','Please enable JavaScript. It is now 85 seconds to midnight')]:
            with self.assertRaises(ValueError):parse(kind,text)
        self.assertNotIn('Current Threat Level',plain('<script>Current Threat Level: SEVERE</script><p>Unavailable</p>'))
    def test_fetch_failure_is_unknown_never_clear(self):
        def fail(url):raise OSError('Test retrieval failure')
        result=collect(fetch=fail,now='2026-11-02T16:00:00+00:00')
        self.assertTrue(all(i['state'] in {'retrieval_failed'} for i in result['items']))
        self.assertNotIn('defcon',[i['id'] for i in result['items']])
        self.assertEqual(result['stale_after_hours'],36)
    def test_static_old_snapshot_is_marked_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'site').mkdir()
            status=json.loads((ROOT/'site/status.json').read_text())
            for item in status['items']:
                if item['state']=='verified':item['verified_at']='2020-01-01T00:00:00+00:00'
            (root/'site/status.json').write_text(json.dumps(status))
            site=Site(ROOT,root/'public');site.root=root
            self.assertIn('Stale · '+next(i['value'] for i in status['items'] if i['id']=='clock'),site.status_panel())

    def test_ntas_dates_scope_and_automatic_expiration(self):
        now=datetime(2026,11,2,17,tzinfo=timezone.utc)
        xml=b'''<alerts>
          <alert start="2026/11/01 00:00" end="2026/11/02 20:00" type="Imminent Threat" link="https://www.dhs.gov/ntas/advisory/test"><summary>Test advisory</summary></alert>
          <alert start="2026/10/01 00:00" end="2026/11/02 17:00" type="Bulletin" link="https://www.dhs.gov/ntas/expired"><summary>Expired</summary></alert>
          <alert start="2026/11/03 00:00" end="2026/11/04 00:00" type="ElevatedThreat" link="https://www.dhs.gov/ntas/future"><summary>Scheduled</summary></alert>
        </alerts>'''
        value,meta=parse_ntas(xml,now)
        self.assertEqual(value,'Imminent threat · 1 active')
        self.assertEqual(meta['expired_entries'],1);self.assertEqual(meta['scheduled_entries'],1)
        self.assertEqual(meta['valid_until'],'2026-11-02T20:00:00+00:00')
        item=dict(id='dhs',state='verified',value=value,verified_at=now.isoformat(),**meta)
        self.assertEqual(display_indicator(item,{'stale_after_hours':36},datetime(2026,11,2,20,tzinfo=timezone.utc)),('expired','Advisory update required'))
        value,meta=parse_ntas(b'<alerts/>',now)
        self.assertEqual(value,'No active feed alerts');self.assertEqual(meta['advisories'],[])

    def test_duplicate_alerts_do_not_inflate_count(self):
        now=datetime(2026,11,2,17,tzinfo=timezone.utc)
        entry='<alert start="2026/11/01 00:00" end="2026/11/04 00:00" type="ElevatedThreat" link="https://www.dhs.gov/ntas/example"><summary>Test advisory</summary></alert>'
        value,meta=parse_ntas(('<alerts>'+entry+entry+'</alerts>').encode(),now)
        self.assertEqual(value,'Elevated threat · 1 active');self.assertEqual(len(meta['advisories']),1)

    def test_ntas_malformed_or_incomplete_feed_never_becomes_clear(self):
        now=datetime(2026,11,2,17,tzinfo=timezone.utc)
        bad=[b'<html>There are no current advisories.</html>',b'<alerts><alert',
             b'<alerts><alert start="2026/11/01 00:00" type="Bulletin"/></alerts>',
             b'<alerts><alert start="2026/11/01 00:00" end="2026/11/04 00:00" type="Unknown"/></alerts>',
             b'<alerts><alert start="2026/11/01 00:00" end="2026/11/04 00:00" type="Bulletin" link="https://example.com/private"><summary>Unsafe</summary></alert></alerts>',
             b'<!DOCTYPE alerts [<!ENTITY x "value">]><alerts/>']
        for xml in bad:
            with self.subTest(xml=xml), self.assertRaises(ValueError):parse_ntas(xml,now)
        def conflicting(url):
            if url.endswith('.xml'):return bad[2]
            if url==DHS_PAGE:return b'<main>There are no current advisories.</main>'
            raise OSError('Test failure')
        item=next(i for i in collect(fetch=conflicting,now=now.isoformat())['items'] if i['id']=='dhs')
        self.assertEqual(item['state'],'needs_review')

    def test_ntas_feed_works_when_landing_page_is_blocked(self):
        def fetch(url):
            if url in DHS_FEEDS:return b'<alerts/>'
            raise HTTPError(url,403,'Test public-source block',None,None)
        result=collect(fetch=fetch,now='2026-11-02T17:00:00+00:00')
        item=next(i for i in result['items'] if i['id']=='dhs')
        self.assertEqual(item['state'],'verified');self.assertEqual(item['value'],'No active feed alerts')
        self.assertIn('does not independently exclude',item['note'])
        self.assertEqual(next(i for i in result['items'] if i['id']=='uk')['state'],'source_blocked')

    def test_french_fallback_requires_dated_national_scope(self):
        text='Date de mise en ligne le : 10 septembre 2026 Depuis le 22 juin 2026, le Plan Vigipirate 2026 prévoit un stade « vigilance renforcée » sur le territoire français.'
        value,meta=parse_france(text,datetime(2026,11,2,tzinfo=timezone.utc))
        self.assertEqual(value,'Vigilance renforcée');self.assertEqual(meta['source_date'],'2026-09-10')
        with self.assertRaises(ValueError):parse_france(text,datetime(2027,1,1,tzinfo=timezone.utc))
        with self.assertRaises(ValueError):parse_france('Les niveaux possibles sont vigilance, vigilance renforcée, alerte attentat.',datetime(2026,11,2,tzinfo=timezone.utc))

    def test_last_verified_value_is_historical_when_fetch_is_blocked(self):
        def blocked(url):raise HTTPError(url,403,'Test block',None,None)
        previous={'items':[dict(id='uk',state='verified',value='SEVERE',verified_at='2026-11-01T17:00:00+00:00')]}
        item=next(i for i in collect(fetch=blocked,previous=previous,now='2026-11-02T17:00:00+00:00')['items'] if i['id']=='uk')
        self.assertEqual(item['value'],'Source blocked');self.assertEqual(item['last_verified']['value'],'SEVERE')
        self.assertEqual(display_indicator(item,{'stale_after_hours':36},datetime(2026,11,2,17,tzinfo=timezone.utc)),('last_verified','SEVERE · last verified'))
        self.assertEqual(display_indicator(item,{'stale_after_hours':36},datetime(2026,11,4,17,tzinfo=timezone.utc)),('stale','Stale · SEVERE'))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'site').mkdir()
            current=json.loads(json.dumps(item));current['last_verified']['verified_at']=datetime.now(timezone.utc).isoformat()
            (root/'site/status.json').write_text(json.dumps(dict(checked_at=current['last_verified']['verified_at'],stale_after_hours=36,items=[current])))
            site=Site(ROOT,root/'out');site.root=root
            panel=site.status_panel()
            self.assertIn('SEVERE · last verified',panel);self.assertIn('Update blocked',panel)
        item['last_verified']['valid_until']='2026-11-02T16:00:00+00:00'
        self.assertEqual(display_indicator(item,{'stale_after_hours':36},datetime(2026,11,2,17,tzinfo=timezone.utc)),('expired','Advisory update required'))

    def test_watch_list_timeline_targets_and_no_menu(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);site=Site(ROOT,out);site.build();page=(out/'index.html').read_text()
            self.assertIn('<h1>Watch List</h1>',page)
            self.assertNotIn('aria-label="Main navigation"',page)
            self.assertIn('class="watch-timeline"',page)
            for f in site.findings:
                self.assertIn('href="#watch-'+f['id']+'"',page)
                self.assertIn('id="watch-'+f['id']+'"',page)
                self.assertTrue((out/'findings'/f['id']/'index.html').exists())
            self.assertTrue((out/'status.json').exists())
