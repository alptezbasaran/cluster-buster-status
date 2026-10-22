"""Phase-1 morphology index: which uploaded subjects show the same clustering?

    python3 analysis/phase1_morphology.py

Reads the kept per-galaxy outputs (outputs_*/outputs/<gid>.json) of every
phase-1 set under artifacts/set_runs and writes state/phase1/morphology.json:
one row per uploaded (set, gid) with a morphology signature, plus the arm
membership of every distinct (gid, signature).

Signature = the member tracings of each arm, in arm order (arm order fixes the
Set1 colour), plus the corpus for galaxies that had cleaning exclusions (their
tracing panel differs between sets 001-020 and 021+). Blurs, palette and render
settings were constant across phase 1, so an identical signature means an
identical uploaded image. No API calls; the output is regenerable.
"""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SET_RUNS = Path.home() / "Desktop/projects/astro/cluster-buster/artifacts/set_runs"
OUT = HERE / "state/phase1/morphology.json"
LAST_PRE_CLEANING = 20


def trace_no(name):
    return int(name.split("_")[1])


def main():
    configs = {r["set"]: r for r in csv.DictReader((HERE / "phase1-configs.csv").open())}
    cleaned = {r["gid"] for r in csv.DictReader(
        (HERE / "cleaning/excluded_manifest_2026-07-06.csv").open())}

    rows, arms_of = [], {}
    for set_name in sorted(configs):
        run = SET_RUNS / set_name
        bundle = max(run.glob(f"{set_name}_*"), key=lambda p: p.stat().st_mtime)
        h = bundle.name.split("_")[-1]
        outputs = next(run.glob(f"outputs_*_{h}")) / "outputs"
        with (bundle / "manifest.csv").open() as fh:
            uploaded = {r["#dr7objid"] for r in csv.DictReader(fh)}
        corpus = "pre" if int(set_name.split("-")[-1]) <= LAST_PRE_CLEANING else "clean"
        for gid in sorted(uploaded):
            d = json.loads((outputs / f"{gid}.json").read_text())[gid]
            arms = [sorted(trace_no(t) for t in d[f"Arm{i}"]["traces"])
                    for i in range(1, d["Number of arms"] + 1)]
            tag = corpus if gid in cleaned else "any"
            sig = hashlib.sha1(json.dumps([tag, arms]).encode()).hexdigest()[:16]
            rows.append([set_name, gid, sig, len(arms)])
            arms_of.setdefault(f"{gid}|{sig}", {"arms": arms, "total": d["Total traces"]})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": rows, "images": arms_of}))

    per_gal = defaultdict(set)
    for _, gid, sig, _ in rows:
        per_gal[gid].add(sig)
    n = sorted(len(v) for v in per_gal.values())
    print(f"uploaded subjects: {len(rows):,}; distinct images: {len(arms_of):,} "
          f"({1 - len(arms_of) / len(rows):.1%} of subjects repeat an earlier image)")
    print(f"distinct images per galaxy: min {n[0]}, median {n[len(n) // 2]}, max {n[-1]}")

    by_set = defaultdict(dict)
    for s, gid, sig, n_arms in rows:
        by_set[s][gid] = (sig, n_arms)
    knobs = ("agreement_threshold", "correction_agreement", "ratio_limit")
    clean_sets = [s for s in configs if int(s.split("-")[-1]) > LAST_PRE_CLEANING]
    print("one adjacent step of a knob, others fixed (sets 021-126 only):")
    for knob in knobs:
        changed = arm_changed = total = 0
        for a in clean_sets:
            for b in clean_sets:
                ra, rb = configs[a], configs[b]
                if a >= b or [k for k in knobs if ra[k] != rb[k]] != [knob]:
                    continue
                if knob != "ratio_limit" and abs(float(ra[knob]) - float(rb[knob])) != 5:
                    continue
                for gid in by_set[a].keys() & by_set[b].keys():
                    (sa, na), (sb, nb) = by_set[a][gid], by_set[b][gid]
                    total += 1
                    changed += sa != sb
                    arm_changed += na != nb
        print(f"  {knob:22s} clustering changes for {changed / total:.1%} of galaxies, "
              f"arm count for {arm_changed / total:.1%} ({total:,} pairs)")
    print(f"wrote {OUT.relative_to(HERE)}")


if __name__ == "__main__":
    main()
