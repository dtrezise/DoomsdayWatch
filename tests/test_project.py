import csv
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from archive import snapshot, verify, export, restore, capture
from build_site import Site, load_public

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        for key in ('href','src'):
            if attrs.get(key):self.links.append(attrs[key])
        if attrs.get('id'):self.ids.add(attrs['id'])

class ProjectTests(unittest.TestCase):
    def test_build_subpath_links_and_private_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'public'
            Site(ROOT,out).build()
            for page in out.rglob('*.html'):
                parsed=Links();parsed.feed(page.read_text())
                for link in parsed.links:
                    parts=urlsplit(link)
                    if parts.scheme or parts.netloc or not parts.path:continue
                    path=unquote(parts.path)
                    self.assertTrue(path.startswith('/Preparedness/'),link)
                    target=out/path.removeprefix('/Preparedness/')
                    if target.is_dir():target=target/'index.html'
                    self.assertTrue(target.is_file(),f'{page}: {link}')
                    if parts.fragment and target.suffix=='.html':
                        target_parsed=Links();target_parsed.feed(target.read_text())
                        self.assertIn(parts.fragment,target_parsed.ids,f'{page}: {link}')
            manifest=json.loads((out/'publication-manifest.json').read_text())
            self.assertEqual(len(manifest['finding_ids']),4)
            for forbidden in ('archive','private','data','docs/HISTORY.md','archive.sqlite3'):
                self.assertFalse((out/forbidden).exists())
            self.assertNotIn('C006',manifest['claim_ids'])
            self.assertIn('og:image',(out/'findings/F001/index.html').read_text())
            self.assertTrue((out/'assets/F001.png').exists())
            # Rebuilding must remove old generated pages instead of leaking withdrawn content.
            stale=out/'stale.html';stale.write_text('stale')
            Site(ROOT,out).build();self.assertFalse(stale.exists())

    def test_unverified_claim_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            shutil.copytree(ROOT/'data',root/'data')
            shutil.copytree(ROOT/'site',root/'site')
            path=root/'site/findings.json';findings=json.loads(path.read_text())
            findings[0]['claim_ids']=['C006'];path.write_text(json.dumps(findings))
            with self.assertRaisesRegex(ValueError,'requires verified'):
                load_public(root)

    def test_editorial_publication_has_sources_images_and_no_internal_planning(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'public'
            site=Site(ROOT,out);site.build()
            self.assertFalse((out/'roadmap').exists())
            self.assertNotIn('/roadmap/',(out/'sitemap.xml').read_text())
            for path in out.rglob('*.html'):
                self.assertNotIn('Chronology before correlation',path.read_text())
                self.assertNotIn('/roadmap/',path.read_text())
            for finding in site.findings:
                page=(out/'findings'/finding['id']/'index.html').read_text()
                self.assertIn('<details class="references"',page)
                self.assertIn('assets/photos/',page)
                for sid in site.source_ids(finding):
                    self.assertIn(site.sources[sid]['url'],page)
            for dossier in site.investigations:
                page=(out/'investigations'/dossier['slug']/'index.html').read_text()
                self.assertIn('<details class="references"',page)
                self.assertIn('assets/photos/',page)
                self.assertTrue(dossier['finding_ids'])

    def test_unchecked_reference_or_missing_media_blocks_publication(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            shutil.copytree(ROOT/'data',root/'data')
            shutil.copytree(ROOT/'site',root/'site')
            path=root/'site/reference_checks.json';checks=json.loads(path.read_text())
            for check in checks:
                if check['source_id']=='S003':check['status']='needs_review'
            path.write_text(json.dumps(checks))
            with self.assertRaisesRegex(ValueError,'reference check'):
                load_public(root)
            shutil.copy2(ROOT/'site/reference_checks.json',path)
            image=root/'site/assets/photos/eu-response-centre.webp';image.unlink()
            with self.assertRaisesRegex(ValueError,'story image'):
                load_public(root)

    def test_archive_restore_capture_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);home=base/'archive';destination=base/'restored'
            sid=snapshot(ROOT,home,'Test preservation')
            self.assertEqual(verify(home),[])
            count=restore(home,sid,destination)
            self.assertGreater(count,20)
            self.assertEqual((destination/'data/claims.csv').read_bytes(),(ROOT/'data/claims.csv').read_bytes())
            self.assertEqual((destination/'site/findings.json').read_bytes(),(ROOT/'site/findings.json').read_bytes())
            source=base/'source.txt';source.write_text('Explicitly synthetic source capture for archive test only.')
            cid=capture(ROOT,home,'S003',source,'2026-11-01T12:00:00-05:00','text/plain','Synthetic test')
            self.assertTrue(cid.startswith('CAP-'))
            with sqlite3.connect(home/'archive.sqlite3') as db:
                self.assertEqual(db.execute('SELECT count(*) FROM source_captures').fetchone()[0],1)
                self.assertGreater(db.execute('SELECT count(*) FROM record_versions').fetchone()[0],100)
            bundle=base/'backup.zip';export(home,bundle)
            extracted=base/'offline'
            with zipfile.ZipFile(bundle) as z:z.extractall(extracted)
            self.assertEqual(verify(extracted),[])
            restore(extracted,sid,base/'offline-restored')
            self.assertTrue((base/'offline-restored/docs/HISTORY.md').is_file())
            first=next((extracted/'objects').rglob('*/*'));first.write_bytes(b'corrupt')
            self.assertTrue(verify(extracted))

if __name__=='__main__':unittest.main()
