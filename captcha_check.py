#!/usr/bin/env python
"""Captcha tripwire: who answered the attention-check subjects wrong?

    source ~/.zooniverse_env
    ~/Desktop/projects/arm_grouping/.venv/bin/python captcha_check.py
        [--full] [--since-id N] [--no-harvest] [--quiet]
        [--write-incident] [--unretire]

Incrementally harvests project classifications (authenticated; bookmark in
state/captcha_check_state.json, matching rows appended to
state/captcha_hits.jsonl), keeps only votes on subjects listed in
captcha_subjects.json, and reports per-user: captchas seen / passed / failed.

Verdicts: FLAG = >=2 fails, or a fail on each polarity (yes+no); WATCH =
1 fail (humans misclick occasionally); OK otherwise. Anonymous votes are
aggregated into a counts-only bucket (cannot be account-flagged).

The first run has no bookmark and scans the full history (~20 min for ~300k
classifications); run it BEFORE linking the qc set so it finishes with zero
hits and a primed bookmark. Later runs take seconds.

--unretire re-arms retired captchas (interactive confirmation; Zooniverse
mutation — operator only). --write-incident emits
incidents/<date>-captcha-flags.{md,json} for any FLAG accounts.

Exit codes: 0 clean, 2 config/auth error, 3 new FLAG accounts.
"""

import argparse
import json
import os
import statistics
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
MAP_FILE = HERE / "captcha_subjects.json"
STATE_DIR = HERE / "state"
STATE_FILE = STATE_DIR / "captcha_check_state.json"
HITS_FILE = STATE_DIR / "captcha_hits.jsonl"
API = "https://panoptes.zooniverse.org/api"
PROJECT_ID = "23492"
WORKFLOW_ID = "26736"


def get_anon(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.api+json; version=1"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def canon_value(v):
    """Annotation value -> 0/1 (Yes/No) or None."""
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().lower()
    if s in ("0", "yes"):
        return 0
    if s in ("1", "no"):
        return 1
    return None


def load_map():
    """-> (meta, {subject_id: (gid, expected_value)}, {unreliable subject_ids}).

    Unreliable subjects still get harvested and reported, but never count toward
    a verdict — see reconcile_captchas.py for why the v1 NO-captchas are so
    marked.
    """
    if not MAP_FILE.exists():
        print(f"{MAP_FILE.name} missing — run reconcile_captchas.py first")
        sys.exit(2)
    doc = json.loads(MAP_FILE.read_text())
    cmap = {sid: (v["gid"], v["expected_value"]) for sid, v in doc["subjects"].items()}
    unreliable = {sid for sid, v in doc["subjects"].items()
                  if not v.get("reliable", True)}
    return doc["_meta"], cmap, unreliable


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_id": None, "synced": None, "logins": {}, "flagged": []}


def save_state(state):
    STATE_DIR.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(STATE_FILE)


def harvest(state, cmap, quiet):
    from panoptes_client import Classification, Panoptes

    user, pw = os.environ.get("PANOPTES_USERNAME"), os.environ.get("PANOPTES_PASSWORD")
    if not user or not pw:
        print("PANOPTES_USERNAME / PANOPTES_PASSWORD not set (source ~/.zooniverse_env)")
        sys.exit(2)
    Panoptes.connect(username=user, password=pw)

    params = {"scope": "project", "project_id": PROJECT_ID, "page_size": 200}
    if state["last_id"]:
        params["last_id"] = str(state["last_id"])
    elif not quiet:
        print("no bookmark: FULL harvest (~20 min for ~300k rows)...")

    n = new_hits = 0
    last = state["last_id"] or 0
    STATE_DIR.mkdir(exist_ok=True)
    with HITS_FILE.open("a") as fh:
        for c in Classification.where(**params):
            n += 1
            last = max(last, int(c.id))
            links = c.raw.get("links", {})
            if str(links.get("workflow")) != WORKFLOW_ID:
                continue
            subs = [str(s) for s in (links.get("subjects") or [])]
            hit = [s for s in subs if s in cmap]
            if not hit:
                continue
            m = c.metadata or {}
            anns = c.raw.get("annotations") or []
            answered = canon_value(anns[0].get("value")) if anns else None
            for sid in hit:
                gid, expected = cmap[sid]
                new_hits += 1
                fh.write(json.dumps({
                    "classification_id": c.id,
                    "user": links.get("user"),
                    "subject_id": sid,
                    "gid": gid,
                    "expected": expected,
                    "answered": answered,
                    "ok": answered == expected,
                    "created": c.created_at,
                    "started": m.get("started_at"),
                    "finished": m.get("finished_at"),
                }) + "\n")
            if n % 2000 == 0:
                state["last_id"] = last
                save_state(state)
                if not quiet:
                    print(f"  {n} rows scanned, {new_hits} captcha hits, at {c.created_at}")
    state["last_id"] = last
    state["synced"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    if not quiet:
        print(f"harvest: {n} new rows scanned, {new_hits} new captcha hits")


def load_hits():
    if not HITS_FILE.exists():
        return []
    return [json.loads(l) for l in HITS_FILE.open()]


def dur_seconds(h):
    try:
        a = datetime.fromisoformat(h["started"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(h["finished"].replace("Z", "+00:00"))
        return (b - a).total_seconds()
    except (KeyError, AttributeError, ValueError, TypeError):
        return None


def report(hits, state, quiet, unreliable=frozenset()):
    per = defaultdict(list)
    for h in hits:
        per[h["user"] or "ANONYMOUS"].append(h)

    flagged = {}
    rows = []
    n_excluded = sum(1 for h in hits if str(h["subject_id"]) in unreliable)
    if n_excluded and not quiet:
        print(f"\n({n_excluded} votes on retired/unreliable captcha subjects are "
              f"shown but excluded from verdicts)")
    for u, hs in sorted(per.items(), key=lambda kv: -len(kv[1])):
        fails = [h for h in hs if not h["ok"] and h["answered"] is not None
                 and str(h["subject_id"]) not in unreliable]
        fail_pol = {h["expected"] for h in fails}
        if u == "ANONYMOUS":
            verdict = "n/a"
        elif len(fails) >= 2 or fail_pol == {0, 1}:
            verdict = "FLAG"
            flagged[u] = {"seen": len(hs), "failed": len(fails),
                          "details": [{k: h[k] for k in
                                       ("gid", "expected", "answered", "created")}
                                      for h in fails]}
        elif len(fails) == 1:
            verdict = "WATCH"
        else:
            verdict = "OK"
        durs = [d for d in (dur_seconds(h) for h in hs) if d is not None and 0 <= d < 3600]
        med = statistics.median(durs) if durs else float("nan")
        rows.append((u, len(hs), len(hs) - len(fails), len(fails), med, verdict))

    if not rows:
        if not quiet:
            print("no captcha classifications recorded yet")
        return flagged
    if not quiet or flagged:
        print(f"\n{'user':>12}{'seen':>6}{'pass':>6}{'fail':>6}{'med_s':>8}  verdict")
        for u, seen, ok, bad, med, verdict in rows:
            print(f"{u:>12}{seen:>6}{ok:>6}{bad:>6}{med:>8.1f}  {verdict}")
    return flagged


def live_status(cmap, quiet):
    ids = list(cmap)
    live = retired = 0
    votes = 0
    for i in range(0, len(ids), 50):
        batch = ",".join(ids[i:i + 50])
        page = get_anon(f"{API}/subject_workflow_statuses?workflow_id={WORKFLOW_ID}"
                        f"&subject_ids={batch}&page_size=50")
        for s in page["subject_workflow_statuses"]:
            votes += s["classifications_count"]
            if s["retired_at"]:
                retired += 1
            else:
                live += 1
    seen = live + retired
    never = len(ids) - seen
    if not quiet:
        print(f"\ncaptcha pool: {live + never}/{len(ids)} live "
              f"({never} never classified), {retired} retired, "
              f"{votes} total captcha votes")
    return retired


def unretire(meta):
    if not sys.stdin.isatty():
        print("--unretire needs an interactive terminal")
        sys.exit(2)
    resp = input(f"un-retire ALL retired captchas in set {meta['subject_set_id']}? "
                 f"type UNRETIRE to confirm: ")
    if resp.strip() != "UNRETIRE":
        print("aborted")
        return
    from panoptes_client import Panoptes, Workflow
    Panoptes.connect(username=os.environ["PANOPTES_USERNAME"],
                     password=os.environ["PANOPTES_PASSWORD"])
    wf = Workflow.find(WORKFLOW_ID)
    wf.unretire_subjects_by_subject_set([meta["subject_set_id"]])
    print("unretired — captcha pool re-armed")


def write_incident(flagged, state):
    if not flagged:
        print("no FLAG accounts — nothing to write")
        return
    day = date.today().isoformat()
    jpath = HERE / "incidents" / f"captcha_flags_{day}.json"
    mpath = HERE / "incidents" / f"{day}-captcha-flags.md"
    jpath.write_text(json.dumps(flagged, indent=1) + "\n")
    lines = [f"# Incident: captcha (attention-check) failures, {day}", "",
             "## Summary", "",
             f"{len(flagged)} account(s) answered attention-check subjects "
             "incorrectly at FLAG level (>=2 failures, or failures on both "
             "polarities). Details per account:", ""]
    for u, info in flagged.items():
        lines.append(f"- user {u}: {info['failed']} failed of {info['seen']} seen")
        for d in info["details"][:10]:
            lines.append(f"    - {d['gid']} expected {d['expected']} "
                         f"answered {d['answered']} at {d['created']}")
    lines += ["", "## Recommended actions", "",
              "1. Cross-check the account with the behavioral forensics "
              "(rate, vote entropy, obvious-subject accuracy).",
              "2. Exclude the account from label aggregation.",
              "3. Report to contact@zooniverse.org if automation is confirmed "
              "(precedent: incidents/2026-07-12-bot-classifications.md).",
              "4. Re-run sync_progress.py after any server-side cleanup.", ""]
    mpath.write_text("\n".join(lines))
    print(f"wrote {mpath.name} + {jpath.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--full", action="store_true", help="ignore bookmark, rescan all")
    ap.add_argument("--since-id", type=int, help="override bookmark")
    ap.add_argument("--no-harvest", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--write-incident", action="store_true")
    ap.add_argument("--unretire", action="store_true")
    args = ap.parse_args()

    meta, cmap, unreliable = load_map()
    state = load_state()
    if args.full:
        state["last_id"] = None
    if args.since_id:
        state["last_id"] = args.since_id

    if not args.no_harvest:
        harvest(state, cmap, args.quiet)

    hits = load_hits()
    flagged = report(hits, state, args.quiet, unreliable)
    retired = live_status(cmap, args.quiet)

    new_flags = [u for u in flagged if u not in state.get("flagged", [])]
    state["flagged"] = sorted(set(state.get("flagged", [])) | set(flagged))
    save_state(state)

    if args.write_incident:
        write_incident(flagged, state)
    if args.unretire:
        if retired == 0:
            print("nothing retired — pool fully armed")
        else:
            unretire(meta)

    if new_flags:
        print(f"\nNEW FLAG accounts: {new_flags}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
