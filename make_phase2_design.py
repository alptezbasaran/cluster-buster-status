"""Write phase2-configs.csv: the Phase-2 sample of the hyperparameter space.

    ~/Desktop/projects/arm_grouping/.venv/bin/python make_phase2_design.py

Phase 1 was a full grid over three knobs (agreement x correction x ratio) with
trace_support and both blurs held fixed. Phase 2 varies all six together, so
the grid gives way to a space-filling sample: a scrambled Sobol sequence
(fixed seed, so the file is reproducible) mapped onto each knob's levels.

64 sets, cluster-buster-127..190, uploaded in waves of 16. Every wave spans
each knob's full range on its own, and the design stays balanced after waves
1, 1-2 and 1-4 (Sobol balance holds at powers of two). Phase 1's 126 sets are
the slice trace_support 2 / blurs 51-31 of the same space, so the two phases
read as one map.

Columns match phase1-configs.csv (run_set.py / upload_set.py read either file)
plus `wave`. Held as in Phase 1: longest_arm_support 1, outlier filter (5, 99).
"""

import csv
from pathlib import Path

from scipy.stats import qmc

HERE = Path(__file__).resolve().parent
OUT = HERE / "phase2-configs.csv"
SEED = 20261021
N_SETS = 64
WAVE = 16
FIRST_SET = 127

LEVELS = {
    "agreement_threshold": list(range(50, 91)),
    "correction_agreement": list(range(50, 81)),
    "ratio_limit": [round(1.0 + 0.05 * i, 2) for i in range(11)],
    "trace_support": [2, 3, 4, 5],
    "vanilla_blur": list(range(21, 82, 2)),  # Gaussian kernels must be odd
    "arm_correction_blur": list(range(11, 62, 2)),
}
HELD = {"longest_arm_support": 1, "lower_perc": 5, "upper_perc": 99}
COLUMNS = ["set", "agreement_threshold", "correction_agreement", "ratio_limit",
           "trace_support", "longest_arm_support", "lower_perc", "upper_perc",
           "vanilla_blur", "arm_correction_blur", "wave"]


def main():
    u = qmc.Sobol(d=len(LEVELS), scramble=True, seed=SEED).random(N_SETS)
    rows = []
    for i, point in enumerate(u):
        row = {"set": f"cluster-buster-{FIRST_SET + i:03d}", **HELD, "wave": i // WAVE + 1}
        for x, (knob, levels) in zip(point, LEVELS.items()):
            row[knob] = levels[min(int(x * len(levels)), len(levels) - 1)]
        rows.append(row)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.name}: {len(rows)} sets "
          f"({rows[0]['set']}..{rows[-1]['set']}), {N_SETS // WAVE} waves of {WAVE}")


if __name__ == "__main__":
    main()
