#!/usr/bin/env python3
"""Build captcha_subjects.json: the committed subject_id -> expected-answer map
for the attention-check sets. Run once after uploading a qc bundle (the uploader
records gids, not Panoptes subject ids — this closes that gap).

    python3 reconcile_captchas.py [--set cluster-buster-qc2] [--expect 200]
                                  [--replace] [--force]

Entries from earlier sets are MERGED by default, so historical captcha hits stay
interpretable after a design change. Each subject carries a `reliable` flag:
the v1 `qcno*` subjects are marked unreliable because their images depicted a
correct clustering while instructing "NO", so careful volunteers failed them
(measured: slow users passed 47%, fast users 88% — inverted). The checker counts
only reliable subjects toward verdicts.

Anonymous public API reads only (no credentials).
"""

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

API = "https://panoptes.zooniverse.org/api"
PROJECT_ID = "23492"
WORKFLOW_ID = "26736"
OUT = Path(__file__).parent / "captcha_subjects.json"


def get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.api+json; version=1"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="cluster-buster-qc2")
    ap.add_argument("--expect", type=int, default=200)
    ap.add_argument("--replace", action="store_true",
                    help="drop existing entries instead of merging")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    set_id = None
    url = f"{API}/subject_sets?project_id={PROJECT_ID}&page_size=100"
    while url and set_id is None:
        page = get(url)
        for ss in page["subject_sets"]:
            if ss["display_name"] == args.set:
                set_id = ss["id"]
        nxt = page["meta"]["subject_sets"].get("next_href")
        url = f"{API}{nxt}" if nxt else None
    if set_id is None:
        print(f"subject set {args.set!r} not found in project {PROJECT_ID}")
        return 2
    print(f"{args.set} -> subject set {set_id}")

    subjects = {}
    url = f"{API}/subjects?subject_set_id={set_id}&page_size=100"
    while url:
        page = get(url)
        for s in page["subjects"]:
            gid = (s.get("metadata") or {}).get("#gid", "")
            if not gid.startswith("qc"):
                print(f"subject {s['id']} has unexpected #gid {gid!r} — aborting")
                return 2
            if "yes" in gid:
                answer, expected = "yes", 0
            elif "no" in gid:
                answer, expected = "no", 1
            else:
                print(f"subject {s['id']} gid {gid!r} states no polarity — aborting")
                return 2
            # v1 NO-captchas depicted a correct clustering while instructing NO,
            # so their failures are not evidence of inattention.
            reliable = not (args.set == "cluster-buster-qc" and answer == "no")
            subjects[s["id"]] = {"gid": gid, "answer": answer,
                                 "expected_value": expected, "set": args.set,
                                 "reliable": reliable}
        nxt = page["meta"]["subjects"].get("next_href")
        url = f"{API}{nxt}" if nxt else None

    n_yes = sum(1 for v in subjects.values() if v["answer"] == "yes")
    n_no = len(subjects) - n_yes
    print(f"subjects found in {args.set}: {len(subjects)} ({n_yes} yes / {n_no} no)")
    if len(subjects) != args.expect:
        print(f"EXPECTED {args.expect} — aborting (pass --expect to override)")
        return 2

    merged = dict(subjects)
    sets_meta = {args.set: {"subject_set_id": set_id, "yes": n_yes, "no": n_no,
                            "reconciled": date.today().isoformat()}}
    if OUT.exists() and not args.replace:
        old = json.loads(OUT.read_text())
        kept = {sid: v for sid, v in old.get("subjects", {}).items()
                if sid not in merged}
        merged.update(kept)
        for name, m in (old.get("_meta", {}).get("sets") or {}).items():
            sets_meta.setdefault(name, m)
        print(f"merged {len(kept)} entries from earlier set(s): "
              f"{sorted({v.get('set','?') for v in kept.values()})}")

    unreliable = sum(1 for v in merged.values() if not v.get("reliable", True))
    OUT.write_text(json.dumps({
        "_meta": {
            "workflow_id": WORKFLOW_ID,
            "sets": sets_meta,
            "total": len(merged),
            "unreliable": unreliable,
            "note": "reliable=false subjects (v1 NO-captchas) are excluded from "
                    "verdicts: their images showed a correct clustering while "
                    "instructing NO, so failures were not inattention.",
        },
        "subjects": merged,
    }, indent=1) + "\n")
    print(f"wrote {OUT}: {len(merged)} subjects total, {unreliable} marked unreliable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
