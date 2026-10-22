"""Write no-arm-galaxies.csv: every (set, galaxy) whose clustering produced no
arm. Those galaxies are never uploaded and count as unsuccessful clusterings
in the hyperparameter -> verdict map, with no volunteer needed.

    python3 collect_no_arms.py

Reads each built set's bundle skipped.txt (reason no_arms) under
artifacts/set_runs for every set in phase1-configs.csv and phase2-configs.csv,
and refreshes the `no_arms` count per set in set-status.json.
"""

import csv
import json
from pathlib import Path

from configs import CONFIG_FILES

HERE = Path(__file__).resolve().parent
SET_RUNS = Path.home() / "Desktop/projects/astro/cluster-buster/artifacts/set_runs"
OUT = HERE / "no-arm-galaxies.csv"
SET_STATUS = HERE / "docs/.vitepress/data/set-status.json"


def main():
    sets = [r["set"] for f in CONFIG_FILES if f.exists() for r in csv.DictReader(f.open())]
    status = json.loads(SET_STATUS.read_text())
    rows, built = [], 0
    for set_name in sets:
        bundles = sorted((SET_RUNS / set_name).glob(f"{set_name}_*/skipped.txt"))
        if not bundles:
            continue
        built += 1
        no_arms = [line.split("\t")[0] for line in bundles[-1].read_text().splitlines()
                   if line.endswith("\tno_arms")]
        rows += [(set_name, gid) for gid in sorted(no_arms)]
        status.setdefault(set_name, {})["no_arms"] = len(no_arms)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["set", "gid"])
        w.writerows(rows)
    SET_STATUS.write_text(json.dumps(status, indent=2) + "\n")
    print(f"wrote {OUT.name}: {len(rows)} galaxy/config pairs with no arm, "
          f"across {built} built sets")


if __name__ == "__main__":
    main()
