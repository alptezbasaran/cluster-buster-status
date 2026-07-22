# Incident: automated classifications, 2026-07-12

> Follow-up 2026-07-23: an attention-check tripwire was deployed in response to
> this incident — see `2026-07-23-captcha-deploy.md` and `captcha_check.py`.

## Summary

Zooniverse user **3055564 (`_.naitik09`)** submitted **25,427 classifications**
on workflow 26736 in ~90 minutes on 2026-07-12 (13:10–14:40 UTC) — 75% of that
day's 34,108 total. The account was created at 12:52 UTC the same day, 18
minutes before the run started.

Detection: daily-count spike (34k vs the usual 6–11k) via the eras stats API,
then per-classification forensics over the Panoptes API (harvest of
2026-07-11..13, 51,551 rows).

## Evidence of automation

- Median classification duration **0.2 s** (`finished_at - started_at`);
  99.6% under 2 s. Genuine volunteers on this workflow run 3–7 s medians.
- Median gap between submissions **0.1 s**; sustained ~16,800/hour.
  (~4.7 verdicts/second for 90 minutes.)
- **Every one of the 25,427 annotations voted value `0`** — the human split
  that window was 55/45 between 0 and 1. Zero information content.
- **12,721 distinct subjects touched; 11,576 of them multiple times (max 6)**
  — the client-side seen-subject dedup was bypassed; duplicate votes still
  count toward Panoptes retirement.
- Single user agent (Chrome/150 on Linux), single session, one account.

## Impact

- Subject retirement (15 verdicts) was accelerated with junk votes: subjects
  retiring around 2026-07-12 may carry several bot votes among their 15, i.e.
  fewer real human verdicts than the count implies. Site "retired" numbers
  synced 2026-07-13 include this inflation.
- The good/bad label corpus is NOT ruined: the classification export carries
  user ids, so **exclude user_id 3055564 during aggregation**. Subjects then
  left with too few human verdicts can be re-queued or accepted at a lower
  verdict threshold.

## Artifacts

- `incidents/bot_subject_ids_2026-07-12.json` — the 12,721 affected subject
  ids (for label filtering / re-queue decisions).

## Recommended actions

1. Report the account to the Zooniverse team (contact@zooniverse.org) with
   user id 3055564, project 23492, workflow 26736, and the 13:10–14:40 UTC
   window — they can deactivate the account and can advise on purging its
   classifications / resetting retirement server-side.
2. Exclude user 3055564 from every label aggregation regardless of (1).
3. After any server-side cleanup, rerun `sync_progress.py` so the site's
   retirement numbers deflate to reality.
4. Watch for recurrence: the daily eras check is cheap —
   `curl "https://eras.zooniverse.org/classifications?workflow_id=26736&period=day&start_date=<recent>"`;
   anything >3x the baseline warrants the per-classification look.
