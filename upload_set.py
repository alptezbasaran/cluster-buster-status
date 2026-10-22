"""Guard + upload one already-built set.

The guard (per the documented workflow): the uploaded manifest's hyperparameters
must match BOTH the run that produced the bundle (run.json) AND the intended config
(phase1-configs.csv or phase2-configs.csv, via configs.py). Only on a full match do
we verify the bundle and upload, then record the status change in set-status.json.

    source ~/.zooniverse_env
    python upload_set.py cluster-buster-002 [--dry-run]
    python upload_set.py cluster-buster-127 --check   # guard + offline verify only

--check stops before anything touches the network (no credentials needed): use
it to pre-flight a whole wave right after building it.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

from configs import KNOBS, config_row

REPO = Path("/Users/atezbas/Desktop/projects/arm_grouping")
STATUS = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster-status")
SET_RUNS = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster/artifacts/set_runs")
SET_STATUS = STATUS / "docs/.vitepress/data/set-status.json"
PY = REPO / ".venv/bin/python"
PROJECT = "astro-lab-ncmns/spiral-graph-cluster-buster"

set_name = sys.argv[1]
dry = "--dry-run" in sys.argv
check_only = "--check" in sys.argv
run_dir = SET_RUNS / set_name

bundle = max(run_dir.glob(f"{set_name}_*"), key=lambda p: p.stat().st_mtime)
run_json = max(run_dir.glob("outputs_*/run.json"), key=lambda p: p.stat().st_mtime)
file_hash = bundle.name.split("_")[-1]

# --- hyperparameter guard: EVERY knob, every time ---
# 3-way (configs ↔ run.json ↔ bundle manifest) for every knob the manifest
# records — all nine since 2026-10-22; 2-way (configs ↔ run.json) for the four
# that bundles built before then lack (blurs + outlier percentiles). run.json
# holds the config the run ACTUALLY used, so a 2-way match still proves correct
# assignment end-to-end.
exp = config_row(set_name)
cfg = json.load(run_json.open())["config"]
with (bundle / "manifest.csv").open() as f:
    mrow = next(csv.DictReader(f))

print(f"[{set_name}] guard (expected | run.json | manifest):")
ok = True
for col, (sec, key, _cast, mcol) in KNOBS.items():
    e = exp[col]
    r = cfg[sec][key]
    m = mrow.get(mcol)
    vals = {float(e), float(r)} | ({float(m)} if m is not None else set())
    match = len(vals) == 1
    ok = ok and match
    print(f"  {col:22s} {e} | {r} | {m if m is not None else '-'}   {'OK' if match else 'MISMATCH'}")
if not ok:
    sys.exit(f"GUARD FAILED for {set_name}: manifest / run.json / configs disagree — NOT uploading")
print(f"[{set_name}] guard PASSED, all 9 knobs ({bundle.name})")

# --- verify bundle (offline) ---
subprocess.run([str(PY), str(REPO / "zooniverse_upload.py"), "--verify-only", str(bundle)], check=True)
if check_only:
    sys.exit(0)

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
    SET_STATUS.write_text(json.dumps(d, indent=2) + "\n")
    print(f"[{set_name}] status -> uploaded ({n_subjects} subjects, id in upload log)")
