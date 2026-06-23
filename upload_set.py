"""Guard + upload one already-built set.

The guard (per the documented workflow): the uploaded manifest's hyperparameters
must match BOTH the run that produced the bundle (run.json) AND the intended config
(phase1-configs.csv). Only on a 3-way match do we verify the bundle and upload, then
record the status change in set-status.json.

    source ~/.zooniverse_env
    python upload_set.py cluster-buster-002 [--dry-run]
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO = Path("/Users/atezbas/Desktop/projects/arm_grouping")
STATUS = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster-status")
SET_RUNS = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster/artifacts/set_runs")
MANIFEST = STATUS / "phase1-configs.csv"
SET_STATUS = STATUS / "docs/.vitepress/data/set-status.json"
PY = REPO / ".venv/bin/python"
PROJECT = "astro-lab-ncmns/spiral-graph-cluster-buster"

set_name = sys.argv[1]
dry = "--dry-run" in sys.argv
run_dir = SET_RUNS / set_name

bundle = max(run_dir.glob(f"{set_name}_*"), key=lambda p: p.stat().st_mtime)
run_json = max(run_dir.glob("outputs_*/run.json"), key=lambda p: p.stat().st_mtime)
file_hash = bundle.name.split("_")[-1]

# --- 3-way hyperparameter guard ---
exp = next(r for r in csv.DictReader(MANIFEST.open()) if r["set"] == set_name)
cfg = json.load(run_json.open())["config"]
with (bundle / "manifest.csv").open() as f:
    mrow = next(csv.DictReader(f))

triples = {
    "agreement": (exp["agreement_threshold"], cfg["vanilla"]["agreement_threshold"], mrow["#agreement_threshold"]),
    "correction": (exp["correction_agreement"], cfg["arm_correction"]["correction_agreement"], mrow["#correction_agreement"]),
    "ratio": (exp["ratio_limit"], cfg["decide_longest_arm"]["ratio_limit"], mrow["#ratio_limit"]),
}
print(f"[{set_name}] guard (expected | run.json | manifest):")
ok = True
for k, (e, r, m) in triples.items():
    match = len({float(e), float(r), float(m)}) == 1
    ok = ok and match
    print(f"  {k:11s} {e} | {r} | {m}   {'OK' if match else 'MISMATCH'}")
if not ok:
    sys.exit(f"GUARD FAILED for {set_name}: manifest / run.json / phase1-configs disagree — NOT uploading")
print(f"[{set_name}] guard PASSED ({bundle.name})")

# --- verify bundle (offline) ---
subprocess.run([str(PY), str(REPO / "zooniverse_upload.py"), "--verify-only", str(bundle)], check=True)

# --- upload ---
cmd = [str(PY), str(REPO / "zooniverse_upload.py"),
       "--project-slug", PROJECT, "--subject-set-name", set_name]
if dry:
    cmd.append("--dry-run")
cmd.append(str(bundle))
subprocess.run(cmd, check=True)

# --- record status ---
if not dry:
    d = json.load(SET_STATUS.open())
    n_subjects = sum(1 for _ in (bundle / "uploaded.txt").open()) if (bundle / "uploaded.txt").exists() else 500
    d.setdefault(set_name, {})
    d[set_name].update(clustered=True, uploaded=True, live=True, hash=file_hash, subjects=n_subjects)
    SET_STATUS.write_text(json.dumps(d, indent=2))
    print(f"[{set_name}] status -> uploaded ({n_subjects} subjects, id in upload log)")
