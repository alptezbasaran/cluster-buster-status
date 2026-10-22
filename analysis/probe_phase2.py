"""Phase-2 dry run: cluster one wave of phase2-configs.csv in memory over the
500-galaxy set, before any set is built.

    ~/Desktop/projects/arm_grouping/.venv/bin/python analysis/phase1_morphology.py   # once
    ~/Desktop/projects/arm_grouping/.venv/bin/python analysis/probe_phase2.py --wave 1

Reports per config: failures, arm-count spread, and how many images repeat one
volunteers already judged -- exactly (same galaxy, same arm memberships in the
same order = byte-identical image; blurs only steer membership, the render
draws the member tracings) or only up to colour (same grouping, arms in a
different order). Earlier waves count as already judged. Writes nothing but
state/phase2/probe_wave<N>.json.

In-memory clustering matches the disk pipeline on ~99.7% of galaxy/config
pairs (cluster-buster/REGENERATE_TRACINGS.md), so the counts are close, not
exact; sets themselves are built with the disk path (run_set.py).
"""

import argparse
import copy
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ARM_GROUPING = Path.home() / "Desktop/projects/arm_grouping"
GSET = Path.home() / "Desktop/projects/astro/cluster-buster/artifacts/cluster_buster_galaxy_set"
OUT_DIR = HERE / "state/phase2"
KNOBS = {  # phase2-configs column -> (config section, key, type)
    "agreement_threshold": ("vanilla", "agreement_threshold", int),
    "correction_agreement": ("arm_correction", "correction_agreement", float),
    "ratio_limit": ("decide_longest_arm", "ratio_limit", float),
    "longest_arm_support": ("decide_longest_arm", "longest_arm_support", int),
    "trace_support": ("vanilla", "trace_support", int),
    "lower_perc": ("filter_outliers", "lower_perc", int),
    "upper_perc": ("filter_outliers", "upper_perc", int),
    "vanilla_blur": ("vanilla", "blur", int),
    "arm_correction_blur": ("arm_correction", "blur", int),
}


def config_for(row, base):
    cfg = copy.deepcopy(base)
    for col, (section, key, cast) in KNOBS.items():
        cfg[section][key] = cast(row[col])
    cfg["skeletonization"]["skeletonize"] = False
    cfg["zooniverse"]["enabled"] = False
    return cfg


def cluster(job):
    set_name, gid, cfg = job
    from arm_grouping.events import null_bus
    from arm_grouping.galaxy import Galaxy

    res = Galaxy(str(GSET / gid / "arms") + "/", cfg, bus=null_bus, in_memory=True).run()
    arms = []
    if res.return_code == 0:
        arms = [sorted(int(t.split("_")[1]) for t in m[1:]) for m in res.arm_members]
    return set_name, gid, res.return_code, arms


def init_worker():
    os.environ.setdefault("LOGURU_LEVEL", "ERROR")
    sys.path.insert(0, str(ARM_GROUPING))


def signature(gid, arms, cleaned):
    tag = "clean" if gid in cleaned else "any"
    return hashlib.sha1(json.dumps([tag, arms]).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wave", type=int, required=True)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    base = json.loads((HERE / "base-config.json").read_text())
    rows = list(csv.DictReader((HERE / "phase2-configs.csv").open()))
    wave = [r for r in rows if int(r["wave"]) == args.wave]
    earlier = [r for r in rows if int(r["wave"]) < args.wave]
    cleaned = {r["gid"] for r in csv.DictReader(
        (HERE / "cleaning/excluded_manifest_2026-07-06.csv").open())}
    morph = json.loads((HERE / "state/phase1/morphology.json").read_text())

    def group_of(gid, arms):
        return json.dumps(["clean" if gid in cleaned else "any", sorted(arms)])

    prior_exact = defaultdict(set)   # gid -> images already judged (phase 1, earlier waves)
    prior_group = defaultdict(set)   # gid -> their groupings, colours ignored
    for _, gid, sig, _ in morph["rows"]:
        prior_exact[gid].add(sig)
    for key, img in morph["images"].items():
        gid = key.split("|")[0]
        prior_group[gid].add(group_of(gid, img["arms"]))
    for r in earlier:
        prev = OUT_DIR / f"probe_wave{r['wave']}.json"
        if prev.exists():
            for gid, arms in json.loads(prev.read_text())["results"][r["set"]].items():
                if arms:
                    prior_exact[gid].add(signature(gid, arms, cleaned))
                    prior_group[gid].add(group_of(gid, arms))

    gids = sorted(p.name for p in GSET.iterdir())
    jobs = [(r["set"], g, config_for(r, base)) for r in wave for g in gids]
    with Pool(args.workers, initializer=init_worker) as pool:
        out = pool.map(cluster, jobs, chunksize=8)
    results = defaultdict(dict)
    rcs = defaultdict(Counter)
    for set_name, gid, rc, arms in out:
        results[set_name][gid] = arms
        rcs[set_name][rc] += 1

    print(f"wave {args.wave}: {len(wave)} configs x {len(gids)} galaxies (in memory)")
    print(f"{'set':>4} {'agr':>3} {'cor':>3} {'ratio':>5} {'TS':>2} {'vb':>3} {'cb':>3} | "
          f"{'subj':>4} {'fail':>4} {'arms':>4} {'1arm':>5} {'7+':>4} | {'new':>4} {'rep1':>4} {'repW':>4} {'recol':>5}")
    totals = Counter()
    arm_hist = Counter()
    wave_exact = defaultdict(set)    # images shown by earlier sets of this wave
    wave_group = defaultdict(set)
    for r in wave:
        s = r["set"]
        n_sub = n_new = rep_p1 = rep_w = recol = 0
        arm_counts = []
        for gid in gids:
            arms = results[s][gid]
            if not arms:
                continue
            n_sub += 1
            arm_counts.append(len(arms))
            arm_hist[min(len(arms), 7)] += 1
            sig = signature(gid, arms, cleaned)
            group = group_of(gid, arms)
            if sig in prior_exact[gid]:
                rep_p1 += 1
            elif sig in wave_exact[gid]:
                rep_w += 1
            else:
                n_new += 1
                recol += group in prior_group[gid] or group in wave_group[gid]
            wave_exact[gid].add(sig)
            wave_group[gid].add(group)
        fails = sum(c for rc, c in rcs[s].items() if rc not in (0, -1))
        mean = sum(arm_counts) / max(len(arm_counts), 1)
        one = sum(1 for a in arm_counts if a == 1) / max(len(arm_counts), 1)
        many = sum(1 for a in arm_counts if a >= 7) / max(len(arm_counts), 1)
        print(f"{s[-3:]:>4} {r['agreement_threshold']:>3} {r['correction_agreement']:>3} {r['ratio_limit']:>5} "
              f"{r['trace_support']:>2} {r['vanilla_blur']:>3} {r['arm_correction_blur']:>3} | "
              f"{n_sub:>4} {fails:>4} {mean:>4.2f} {one:>5.0%} {many:>4.0%} | {n_new:>4} {rep_p1:>4} {rep_w:>4} {recol:>5}")
        totals.update(subjects=n_sub, fails=fails, new=n_new, rep_prior=rep_p1,
                      rep_wave=rep_w, recolour=recol)
    reps = totals["rep_prior"] + totals["rep_wave"]
    print(f"total: {totals['subjects']:,} subjects, {totals['fails']} failures; "
          f"{reps:,} exact repeats ({reps / max(totals['subjects'], 1):.1%}: "
          f"{totals['rep_prior']:,} of earlier phases, {totals['rep_wave']:,} within the wave); "
          f"{totals['recolour']:,} new images that repeat a grouping in other colours")
    print("columns: subj = galaxies with >=1 arm; fail = errors (rc -2/-3); new = never shown; "
          "rep1 = repeats an image from phase 1 or an earlier wave; repW = repeats an earlier "
          "set of this wave; recol = new image, same grouping as one shown in other colours")
    print("arm-count spread:", {(k if k < 7 else "7+"): v for k, v in sorted(arm_hist.items())})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"probe_wave{args.wave}.json").write_text(json.dumps(
        {"wave": args.wave, "sets": [r["set"] for r in wave], "results": results,
         "return_codes": {s: dict(c) for s, c in rcs.items()}}))


if __name__ == "__main__":
    main()
