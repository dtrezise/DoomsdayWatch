# Preparedness OSINT Research Project

Persistent, public-source investigation of unusual preparedness and potential global threats. Established 2026-11-01. Research cutoff: 2026-11-01, America/New_York. Initial release is a limited source-integrity review, not a completed threat survey.

Start with [master assessment](docs/MASTER_ASSESSMENT.md), [source-integrity audit](reports/00_source_integrity_audit.md), [methodology](docs/METHODOLOGY.md), and [next research steps](docs/RESEARCH_PLAN.md).

## Research workstreams

1. Military logistics
2. Emergency procurement
3. Geopolitical developments
4. Civilian infrastructure
5. Medical preparedness
6. Financial and insurance indicators
7. Continuity of government
8. Astronomical hazards (including space weather as a separate mechanism)

Each has a notebook in `research/`. Cross-sector connections require independent evidence of timing and mechanism.

## Persistent records

- `data/events.csv`: chronological events, including explicitly unverified alleged events.
- `data/claims.csv`: atomic claims, evidence class, verification status and confidence.
- `data/sources.csv`: exact citation URLs, access results and independence groups.
- `data/leads.csv`: all 19 research leads and next verification steps.
- `data/anomalies.csv`: candidate deviations, baseline gaps and alternatives.
- `data/baselines.csv`: 2023–2025 observations and explicit missing comparisons.
- `data/watchlist.csv`: proposed indicator-level collection specification; see docs/MONITORING.md for the recurring research task.
- `data/verification_log.csv`: retrieval outcomes, including failures.
- `docs/CORRECTIONS.md`: corrections and qualifications; history is retained unchanged.
- `templates/INTELLIGENCE_REPORT.md`: professional report template.

## Continue research

Read `AGENTS.md` and methodology. Check an unresolved lead against original records, add sources and atomic claims, link events, record counterevidence, then update assessment and corrections. Keep IDs stable. Empty CSV fields mean unknown or not assessed, never zero. Source dates and event dates are separate.

Run `python3 scripts/validate.py` after edits. Run `python3 scripts/build_report.py` to produce a dated evidence inventory in `reports/`; this does not generate threat judgments. No third-party packages are required. Use Git for change history; make reviewed commits as the project evolves.

The research program chronology is maintained in `docs/HISTORY.md`. Research leads are not evidence of occurrence. Current website and scheduling status is described below.

## Public website and archive

[Preparedness Observatory](https://dtrezise.github.io/Preparedness/) is the public reader of curated research. See [website and publishing](docs/WEBSITE.md), [offline archive](docs/ARCHIVE.md), [recurring research](docs/MONITORING.md).

Build with `python3 scripts/build_site.py`; test with `python3 -m unittest discover -s tests -v`. Site source is in `site/`, generated output in ignored `_site/`. GitHub Pages deploys only that output. Each published finding has a stable URL, status, citations, share composer and downloadable social card. Local SQLite snapshots and ZIP exports stay in ignored `archive/` and `backups/` folders within this work folder.

Weekly investigative maintenance is scheduled for Mondays at 9:00 a.m. Eastern in the local project. The local task needs the computer on and the app running. Indicator-specific live collectors remain disabled.
