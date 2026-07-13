"""Per-subject classification progress for one Cluster Buster set.
Usage: set_progress.py cluster-buster-005"""
import json
import sys
import urllib.request
from collections import Counter

API = "https://panoptes.zooniverse.org/api"
WORKFLOW, PROJECT = "26736", "23492"


def get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.api+json; version=1"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


name = sys.argv[1]

# subject set id by display name
set_id = None
url = f"{API}/subject_sets?project_id={PROJECT}&page_size=100"
while url and not set_id:
    page = get(url)
    for ss in page["subject_sets"]:
        if ss["display_name"] == name:
            set_id = ss["id"]
    nxt = page["meta"]["subject_sets"].get("next_href")
    url = f"{API}{nxt}" if nxt else None
print(f"{name} -> subject set {set_id}")

# subject ids in the set
subject_ids = []
url = f"{API}/set_member_subjects?subject_set_id={set_id}&page_size=100"
while url:
    page = get(url)
    subject_ids += [m["links"]["subject"] for m in page["set_member_subjects"]]
    nxt = page["meta"]["set_member_subjects"].get("next_href")
    url = f"{API}{nxt}" if nxt else None
print(f"subjects in set: {len(subject_ids)}")

# per-subject workflow status, batched
counts, retired = {}, set()
for i in range(0, len(subject_ids), 50):
    batch = ",".join(subject_ids[i : i + 50])
    page = get(
        f"{API}/subject_workflow_statuses?workflow_id={WORKFLOW}"
        f"&subject_ids={batch}&page_size=50"
    )
    for s in page["subject_workflow_statuses"]:
        counts[s["links"]["subject"]] = s["classifications_count"]
        if s["retired_at"]:
            retired.add(s["links"]["subject"])

seen = len(counts)
total = sum(counts.values())
dist = Counter(counts.values())
print(f"\nstatuses found: {seen}/{len(subject_ids)} "
      f"(missing = never classified: {len(subject_ids) - seen})")
print(f"total classifications in this set: {total:,}")
print(f"retired: {len(retired)}")
print("\nclassifications-per-subject distribution:")
for k in sorted(dist):
    print(f"  {k:3d} verdicts: {dist[k]:4d} subjects {'#' * (dist[k] // 8 or 1)}")
pending = sorted((v, k) for k, v in counts.items() if k not in retired)
print(f"\nstill collecting ({len(pending)}):",
      [f"subj {k}@{v}/15" for v, k in pending[:10]])
