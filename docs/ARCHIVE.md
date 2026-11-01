# Local archive and offline backup

Archive location: `<project-root>/archive/`.
Portable exports: `<project-root>/backups/`.
Both are ignored by Git and excluded from the site artifact.

## What is preserved

- `archive.sqlite3`: snapshot metadata, versioned research records and findings, file references, and imported original-source capture metadata.
- `objects/`: SHA-256-addressed original bytes, deduplicated across snapshots.
- `manifests/`: per-snapshot file inventories and hashes.
- ZIP exports: a consistent SQLite database backup, all objects and manifests, plus a separate SHA-256 checksum file.

Snapshots preserve the research chronology, data, findings, source scripts, reports, notebooks, site source, images, project documentation and local internal planning documents. They exclude Git internals, credentials, the archive itself and generated `_site/`. They are local historical backups, not a second physical copy. Source URLs are preserved as research records; original website bytes are archived only after an explicit capture import.

```sh
python3 scripts/archive.py snapshot --note 'Before research update'
python3 scripts/archive.py status
python3 scripts/archive.py verify
python3 scripts/archive.py export --output backups/preparedness-YYYY-MM-DD.zip
python3 scripts/archive.py restore --snapshot SNAPSHOT_ID --destination /tmp/preparedness-restore
```

Restore refuses a nonempty destination and checks file hashes. To recover from a ZIP, verify its checksum, extract it into an empty local directory, then use `--archive-dir /absolute/path/to/extracted` before the `verify` or `restore` command. Run a restore drill periodically.

## Original-source captures

After saving an original source using an authorized retrieval method, import its actual bytes and real capture time:

```sh
python3 scripts/archive.py capture --source-id S003 --file /absolute/path/to/saved-source.html --captured-at '2026-11-01T17:00:00-05:00' --media-type text/html --note 'Original HTML retrieval; dynamic dependencies not bundled'
```

This command does not fetch, authenticate, verify truth, or automatically promote a claim. Preserve access outcomes and indicate incomplete pages. Capture time is not the source publication date. Do not label a portal shell as a full evidentiary capture.

## Evolution

Next: encrypted backup to an independent device/service, automated checksum checks, retention policy and restore drills. Later: separate private archival storage from the public publishing catalog, use managed PostgreSQL or equivalent for metadata and versioned object storage for files, migrate stable IDs and hashes intact, define encryption/access controls and source-copyright rules, and test recovery before switching. GitHub Pages remains a public reader of curated static output.

Private household identities, contacts, addresses and location details are outside this public research archive.
