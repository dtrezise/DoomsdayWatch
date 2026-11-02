import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from refresh_status import parse,plain,collect
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
        self.assertTrue(all(i['state']=='unavailable' for i in result['items']))
        self.assertEqual(next(i for i in result['items'] if i['id']=='defcon')['value'],'Not publicly verified')
        self.assertEqual(result['stale_after_hours'],36)
    def test_static_old_snapshot_is_marked_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'site').mkdir()
            status=json.loads((ROOT/'site/status.json').read_text())
            for item in status['items']:
                if item['state']=='verified':item['verified_at']='2020-01-01T00:00:00+00:00'
            (root/'site/status.json').write_text(json.dumps(status))
            site=Site(ROOT,root/'public');site.root=root
            self.assertIn('Stale · 85 seconds',site.status_panel())

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
