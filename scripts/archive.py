#!/usr/bin/env python3
"""Local-only, content-addressed research archive and portable offline backup."""
import argparse
import csv
import hashlib
import json
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'archive'
DIRS=('data','docs','research','reports','templates','scripts','site','.github','evidence','tests','private/internal')
FILES=('README.md','AGENTS.md','.gitignore')
SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS snapshots(snapshot_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS objects(sha256 TEXT PRIMARY KEY, bytes INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS files(snapshot_id TEXT REFERENCES snapshots(snapshot_id), path TEXT NOT NULL, sha256 TEXT REFERENCES objects(sha256), PRIMARY KEY(snapshot_id,path));
CREATE TABLE IF NOT EXISTS record_versions(snapshot_id TEXT REFERENCES snapshots(snapshot_id), collection TEXT NOT NULL, record_id TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY(snapshot_id,collection,record_id));
CREATE TABLE IF NOT EXISTS source_captures(capture_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL, captured_at TEXT NOT NULL, imported_at TEXT NOT NULL, media_type TEXT NOT NULL, sha256 TEXT REFERENCES objects(sha256), note TEXT NOT NULL);
PRAGMA user_version=1;
'''

def now():return datetime.now(timezone.utc).isoformat()
def connect(home):
    home.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(home/'archive.sqlite3')
    db.executescript(SCHEMA)
    return db

def store(home,db,data):
    digest=hashlib.sha256(data).hexdigest()
    target=home/'objects'/digest[:2]/digest
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if target.read_bytes()!=data:raise ValueError('Hash object collision or corruption')
    else:target.write_bytes(data)
    db.execute('INSERT OR IGNORE INTO objects VALUES (?,?)',(digest,len(data)))
    return digest

def candidates(root):
    for name in FILES:
        path=root/name
        if path.is_file() and not path.is_symlink():yield path
    for directory in DIRS:
        for path in sorted((root/directory).rglob('*')):
            if (path.is_file() and not path.is_symlink() and not any(part in {'__pycache__','.git','node_modules'} for part in path.parts)
                and path.suffix not in {'.pyc','.sqlite3'} and path.name!='.DS_Store' and not path.name.startswith('.env')):
                yield path

def snapshot(root,home,note):
    sid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    with connect(home) as db:
        db.execute('INSERT INTO snapshots VALUES (?,?,?)',(sid,now(),note))
        manifest=[]
        for path in candidates(root):
            relative=path.relative_to(root).as_posix()
            digest=store(home,db,path.read_bytes())
            db.execute('INSERT INTO files VALUES (?,?,?)',(sid,relative,digest))
            manifest.append({'path':relative,'sha256':digest})
        for path in sorted((root/'data').glob('*.csv')):
            with path.open(newline='') as handle:
                reader=csv.DictReader(handle)
                first=(reader.fieldnames or ['id'])[0]
                for row in reader:
                    db.execute('INSERT INTO record_versions VALUES (?,?,?,?)',(sid,path.stem,row[first],json.dumps(row,ensure_ascii=False)))
        for row in json.loads((root/'site/findings.json').read_text()):
            db.execute('INSERT INTO record_versions VALUES (?,?,?,?)',(sid,'findings',row['id'],json.dumps(row,ensure_ascii=False)))
        directory=home/'manifests';directory.mkdir(exist_ok=True)
        (directory/(sid+'.json')).write_text(json.dumps({'snapshot_id':sid,'note':note,'files':manifest},indent=2)+'\n')
    return sid

def verify(home):
    failures=[]
    with connect(home) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':failures.append('SQLite integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():failures.append('Foreign key check failed')
        for digest,size in db.execute('SELECT sha256,bytes FROM objects'):
            path=home/'objects'/digest[:2]/digest
            if not path.exists():failures.append('Missing object '+digest);continue
            data=path.read_bytes()
            if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:failures.append('Corrupt object '+digest)
    return failures

def export(home,destination):
    if destination.exists():raise ValueError('Export path already exists; choose a new filename')
    failures=verify(home)
    if failures:raise ValueError('\n'.join(failures))
    destination.parent.mkdir(parents=True,exist_ok=True)
    # SQLite backup API captures a consistent database, even if the archive gains WAL mode later.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        copy=Path(td)/'archive.sqlite3'
        with connect(home) as source,sqlite3.connect(copy) as target:source.backup(target)
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(copy,'archive.sqlite3')
            for directory in ('objects','manifests'):
                for path in sorted((home/directory).rglob('*')):
                    if path.is_file():bundle.write(path,path.relative_to(home))
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix+'.sha256').write_text(digest+'  '+destination.name+'\n')
    return digest

def restore(home,snapshot_id,destination):
    if destination.exists() and any(destination.iterdir()):raise ValueError('Restore destination must be empty')
    destination.mkdir(parents=True,exist_ok=True)
    with connect(home) as db:
        rows=db.execute('SELECT path,sha256 FROM files WHERE snapshot_id=?',(snapshot_id,)).fetchall()
        if not rows:raise ValueError('Snapshot not found')
        for name,digest in rows:
            path=(destination/name).resolve()
            if not path.is_relative_to(destination.resolve()):raise ValueError('Unsafe archive path')
            data=(home/'objects'/digest[:2]/digest).read_bytes()
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Corrupt object '+digest)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return len(rows)

def capture(root,home,source_id,path,captured_at,media_type,note):
    datetime.fromisoformat(captured_at.replace('Z','+00:00'))
    with (root/'data/sources.csv').open(newline='') as f:
        sources={s['source_id']:s for s in csv.DictReader(f)}
    if source_id not in sources:raise ValueError('Unknown source ID')
    with connect(home) as db:
        digest=store(home,db,path.read_bytes());cid='CAP-'+uuid.uuid4().hex
        db.execute('INSERT INTO source_captures VALUES (?,?,?,?,?,?,?,?)',(cid,source_id,sources[source_id]['url'],captured_at,now(),media_type,digest,note))
    return cid

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive-dir',type=Path,default=DEFAULT)
    sub=parser.add_subparsers(dest='command',required=True)
    snap=sub.add_parser('snapshot');snap.add_argument('--note',required=True)
    sub.add_parser('verify');sub.add_parser('status')
    ex=sub.add_parser('export');ex.add_argument('--output',type=Path,required=True)
    re=sub.add_parser('restore');re.add_argument('--snapshot',required=True);re.add_argument('--destination',type=Path,required=True)
    ca=sub.add_parser('capture');ca.add_argument('--source-id',required=True);ca.add_argument('--file',type=Path,required=True);ca.add_argument('--captured-at',required=True);ca.add_argument('--media-type',required=True);ca.add_argument('--note',default='')
    args=parser.parse_args();home=args.archive_dir
    if args.command=='snapshot':print(snapshot(ROOT,home,args.note))
    elif args.command=='verify':
        failures=verify(home)
        if failures:raise SystemExit('\n'.join(failures))
        print('Archive database and all content hashes verified.')
    elif args.command=='export':print(export(home,args.output))
    elif args.command=='restore':print(f'Restored {restore(home,args.snapshot,args.destination)} files.')
    elif args.command=='capture':print(capture(ROOT,home,args.source_id,args.file,args.captured_at,args.media_type,args.note))
    else:
        with connect(home) as db:
            print(json.dumps({name:db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('snapshots','objects','files','record_versions','source_captures')},indent=2))
