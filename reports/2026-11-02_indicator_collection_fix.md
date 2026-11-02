# Public indicator collection repair — November 2, 2026

The previous “Not verified” display combined several different cases: an undisclosed official military readiness condition, blocked automated requests, and source text the parser could not interpret. These are now distinct states. No API credentials were required or used.

## DHS NTAS

The official API documentation (S057) identifies two public XML endpoints. The consolidated feed (S056) is now the first collection source; the discrete feed (S059) and official landing page are fallbacks. Direct inspection retrieved an empty alerts element from both feed endpoints. The landing page separately stated that there were no current advisories. The reviewed local snapshot therefore reads “No active advisory.” If the landing page is blocked, an empty feed is only “No active feed alerts”; the notes explain that feed coverage alone cannot exclude other bulletin coverage or imply a general threat all-clear.

Active structured entries require known types, complete summaries, official links and valid effective/end times. Future and expired entries do not enter active counts. Identical duplicate entries are deduplicated; conflicting, malformed, reference-only or undated entries require review. Feed/page disagreement cannot become a no-advisory result. The browser and static renderer invalidate the badge at the earliest known transition; they do not wait until the next daily run to keep labeling an expired advisory active. Synthetic tests cover these cases; no real active alert was invented for testing.

## France

SGDSN remains the preferred national source, but its direct response was a security-validation page. The collector now uses the Foreign Ministry’s explicit statement of the national posture as an official fallback (S058): published September 10, 2026, describing the posture in effect since June 22. The displayed value is Vigilance renforcée. The source publication date and a 90-day editorial review deadline are shown. This review deadline is not an official policy expiration. Descriptive lists of possible levels, local posture pages and advice for travelers alone cannot set the national badge.

## Presentation and provenance

DEFCON is separately labeled “Not publicly disclosed”; no official current-level feed was identified. The collector does not substitute independent estimates. Retrieval failures, access blocks, content needing review, stale checks and expired validity periods have distinct labels. A last-verified reading can be retained only as historical notes. UK bar graphics now follow the actual level, rather than always filling four bars. Reader-facing timestamps use America/New_York.

Status schema version 2 records source URLs, response hashes, attempted fallbacks, structured advisory validity and scope. Exact captured responses remain in ignored local storage and the offline archive. Small but valid XML responses are accepted by the source-link verifier; HTML security shells remain rejected. Daily Pages checks and retained JSON artifacts continue without API keys.

## Validation

Fifteen tests passed, including XML validity/expiration, duplicate handling, blocked-page feed fallback, French national-scope/date guards, last-verified handling, publication boundaries and archive restoration. Browser checks confirmed JavaScript expiration and review-due states using a clearly labeled temporary synthetic fixture, five bars for a synthetic Critical UK level, normal source notes, Eastern timestamps, mobile width and no console errors. Synthetic assets were outside the repository and publication output.

## Deployment finding and fallback correction

Pages run 41498416352 succeeded, and France was verified from the hosted network. All three DHS candidates returned 403 on the hosted runner, while local retrieval succeeded. The correction therefore also preserves reviewed snapshots on push builds, leaves scheduled/manual remote collection enabled, and adds a narrow daily local fallback at 8:30 a.m. America/New_York. The fallback requires the computer and app running and has a failures-only notification policy. It uses existing Codex allowance, not a separately billed model API or a source API key.

Failed updates now display the last successful value only with an explicit last-verified label, a failure flag and timestamped provenance. Its original advisory transition/source-review deadlines are preserved; a failed request never renews freshness or permits an expired alert to remain an active badge. After 36 hours it is marked stale. Static and browser handling were tested for this case as well. The verified local snapshot is published rather than overwritten by an immediate failed hosted recheck.
