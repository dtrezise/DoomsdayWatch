# Public website and publishing

Canonical URL: https://dtrezise.github.io/DoomsdayWatch/
Public repository: https://github.com/dtrezise/DoomsdayWatch
Local repository: the project checkout

## Architecture

Python builds a static site from structured research records plus `site/findings.json`. GitHub Actions validates the research, tests the publication boundary and archive, builds `_site/`, and deploys only that directory to GitHub Pages. No paid API, server, account system, or database service is required for visitors.

The public repository also contains research notebooks and the program chronology. Open research records are clearly distinguished from published findings. Private material belongs only in ignored `private/`, `archive/` or `backups/` paths; never put family information in tracked research files.

Run:

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/build_site.py
```

Site builds use only standard Python. Social preview PNGs are committed assets; optional regeneration with `scripts/generate_share_cards.py` requires Pillow. Findings have stable `/findings/F001/` URLs, canonical and Open Graph metadata, image downloads, native sharing, a copyable post including status/limits, and print styles. An Atom feed is at `/feed.xml`.

## Publishing a finding

1. Verify atomic claims and record full-text source provenance. Preserve contrary evidence and the historical comparison.
2. Add a stable finding ID to `site/findings.json`, with linked claim IDs, title, bounded summary, why it matters, alternatives, next question, publication/update dates and status.
3. Keep it `draft` while unresolved. The current published-finding schema permits only verified documentary facts; reported claims, speculation and broader analytical judgments remain in separately labeled research/assessment pages. Extending this policy requires an explicit schema and test change.
4. Review every statement against the linked sources; automated record validation does not verify prose. Confirm that source support and confidence do not imply threat probability. For consequential new claims, independently corroborate before publishing.
5. Generate an image card, validate, test, preview and archive the change. Update corrections for material revisions. Commit and push to main; the Pages workflow publishes after passing checks.

`research_cutoff` is editorial metadata, not the date a build happened. Advance it only after actual research review. Website builders remove old generated pages on rebuild; maintain old finding IDs and disclose material retractions in corrections. Do not delete a published record merely to conceal an error. A withdrawn-page implementation will be needed before introducing withdrawn findings to the current public catalog.

## Scheduling

After successful launch, the recurring local Codex research task is configured for Mondays at 9:00 a.m. America/New_York. It should check sources for meaningful changes, investigate context, record contrary evidence, preserve the local archive and prepare/publish only changes that meet the publication standards. Failed or incomplete checks remain leads. There is no external model API key or GitHub Actions research agent in this design.

The workflow currently deploys reviewed repository changes; it does not itself conduct research. See MONITORING.md for the recurring research scope and operational limits.


## Editorial presentation and reference checks

The landing page explains the publication's remit and leads with sourced photography and reporting. Stories have stable finding URLs, direct headlines and narrative sections. Expandable source sections include inspected document links, the date each link was checked, reporting limits and image reuse terms. Public investigation dossiers derive their reference lists from published reporting; the wider unverified lead queue is not displayed as public investigation entries.

Before changing published references, run `python3 scripts/verify_public_sources.py` with network access, inspect source content, and then run the normal validation/tests/build. The checker preserves retrieved bytes in the local archive and records HTTP results in `site/reference_checks.json`. HTTP success is a link check, not a factual-verification decision; the existing claim review remains required. New findings require linked verified claims and checked sources. Images and credits are cataloged in `site/media.json`.

Product planning documents are local internal material, excluded from the public artifact. New coverage must not advertise deferred features.

## Navigation and Watch List

The canonical homepage is the Watch List. It contains published stories with permanent sharing URLs and expandable references. There is no top menu. Methods and About the publication remain in the footer. The sticky horizontal timeline uses event dates, not publication dates, and links to story anchors on the same page. Preserve story IDs and anchors when updating coverage.

## Published indicator panel

`scripts/refresh_status.py` checks allowlisted official publications, with strict text parsers and no model inference. GitHub Actions runs daily at 06:17 UTC and on publication builds. It builds the checked snapshot into Pages and retains the dated JSON as an Actions artifact for 90 days; it does not create daily Git commits. Scheduling and deployment can be delayed or fail. The browser rechecks the same-origin published snapshot every five minutes; this is not a direct live feed.

The Bulletin’s Doomsday Clock is its official symbolic expert setting, not a government warning or ticking countdown. DEFCON has no authenticated official current-level feed available to this publication and stays unverified. DHS NTAS is an advisory system, not the retired color scale: only an explicit current-source statement of no active advisories is parsed automatically. Active or ambiguous bulletins require editorial review, including expiry. European levels remain country-specific; UK JTAC and France Vigipirate are not directly comparable scales. Failed retrievals and unrecognized content show “Not verified,” never an inferred all-clear. Previously verified values are marked stale after 36 hours. Source text or schema changes require parser review and tests.

Weekly research reviews should download dated `indicator-snapshot-*` Actions artifacts into ignored local storage, capture/import them into the local archive, and check failed indicator sources. The committed snapshot records the reviewed development state; deployed daily snapshots can be newer. Private source captures stay local. No credentials are sent to visitors.
