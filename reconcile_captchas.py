#!/usr/bin/env python3
"""Build captcha_subjects.json: the committed subject_id -> expected-answer map
for the attention-check set. Run once after uploading the qc bundle (the
uploader records gids, not Panoptes subject ids — this closes that gap).

    python3 reconcile_captchas.py [--set cluster-buster-qc] [--expect 200] [--force]

Anonymous public API reads only (no credentials). Refuses to overwrite an
existing map with fewer subjects unless --force.
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
    ap.add_argument("--set", default="cluster-buster-qc")
    ap.add_argument("--expect", type=int, default=200)
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
            if gid.startswith("qcyes"):
                answer, expected = "yes", 0
            elif gid.startswith("qcno"):
                answer, expected = "no", 1
            else:
                print(f"subject {s['id']} has unexpected #gid {gid!r} — aborting")
                return 2
            subjects[s["id"]] = {"gid": gid, "answer": answer, "expected_value": expected}
        nxt = page["meta"]["subjects"].get("next_href")
        url = f"{API}{nxt}" if nxt else None

    n_yes = sum(1 for v in subjects.values() if v["answer"] == "yes")
    n_no = len(subjects) - n_yes
    print(f"subjects found: {len(subjects)} ({n_yes} yes / {n_no} no)")
    if len(subjects) != args.expect:
        print(f"EXPECTED {args.expect} — aborting (pass --expect to override)")
        return 2
    if OUT.exists() and not args.force:
        old = json.loads(OUT.read_text())
        if len(old.get("subjects", {})) > len(subjects):
            print(f"{OUT.name} already has more subjects — refusing without --force")
            return 2

    OUT.write_text(json.dumps({
        "_meta": {
            "subject_set": args.set,
            "subject_set_id": set_id,
            "workflow_id": WORKFLOW_ID,
            "reconciled": date.today().isoformat(),
            "yes": n_yes,
            "no": n_no,
        },
        "subjects": subjects,
    }, indent=1) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
