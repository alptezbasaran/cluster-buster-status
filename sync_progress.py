"""Sync classification progress from Zooniverse into set-status.json.

Anonymous public API reads (no credentials needed): per-set retirement via
each subject set's completeness fraction for workflow 26736, plus
workflow-level totals stored under the "_meta" key. Run any time; then
commit set-status.json and push to redeploy the site.

    python3 sync_progress.py
"""
import json
import urllib.request
from datetime import date
from pathlib import Path

API = "https://panoptes.zooniverse.org/api"
WORKFLOW_ID = "26736"
PROJECT_ID = "23492"
STATUS = Path(__file__).parent / "docs/.vitepress/data/set-status.json"


def get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.api+json; version=1"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    wf = get(f"{API}/workflows/{WORKFLOW_ID}")["workflows"][0]

    completeness = {}
    url = f"{API}/subject_sets?project_id={PROJECT_ID}&page_size=100"
    while url:
        page = get(url)
        for ss in page["subject_sets"]:
            name = ss["display_name"]
            if name.startswith("cluster-buster-"):
                completeness[name] = ss["completeness"].get(WORKFLOW_ID, 0.0)
        nxt = page["meta"]["subject_sets"].get("next_href")
        url = f"{API}{nxt}" if nxt else None

    status = json.loads(STATUS.read_text())
    missing = [k for k in status if k != "_meta" and k not in completeness]
    for name, entry in status.items():
        if name == "_meta" or name not in completeness:
            continue
        frac = completeness[name]
        entry["completeness"] = round(frac, 4)
        entry["retired"] = round(frac * (entry.get("subjects") or 0))

    status["_meta"] = {
        "workflow_id": WORKFLOW_ID,
        "workflow_active": wf["active"],
        "linked_subject_sets": len(wf["links"].get("subject_sets", [])),
        "classifications": wf["classifications_count"],
        "retired_subjects": wf["retired_set_member_subjects_count"],
        "subjects": wf["subjects_count"],
        "synced": date.today().isoformat(),
    }
    STATUS.write_text(json.dumps(status, indent=2) + "\n")

    m = status["_meta"]
    print(
        f"synced {len(completeness)}/{len(status) - 1} sets | "
        f"{m['classifications']:,} classifications | "
        f"{m['retired_subjects']:,}/{m['subjects']:,} retired "
        f"({m['retired_subjects'] / m['subjects']:.1%}) | "
        f"{m['linked_subject_sets']} sets linked to workflow"
    )
    if missing:
        print(f"WARNING: no Zooniverse subject set found for: {missing[:5]}...")


if __name__ == "__main__":
    main()
