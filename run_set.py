"""Run one phase-1 set end-to-end: cluster the 500-galaxy Cluster Buster set with
a config from phase1-configs.csv, render with Set1, and build the Zooniverse
bundle (split PNGs + manifest). Does NOT upload (set PANOPTES_* + use the
standalone uploader, or flip upload.enabled).

    python run_set.py cluster-buster-001 [num_processes]

Outputs land in artifacts/set_runs/<set>/ (bundle = <set>_<hash>/).
"""

import csv
import os
import sys
from pathlib import Path

REPO = Path("/Users/atezbas/Desktop/projects/arm_grouping")
MANIFEST = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster-status/phase1-configs.csv")
SET_RUNS = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster/artifacts/set_runs")
METADATA = REPO / "set_004_manifest_proposed.csv"


def main() -> None:
    os.environ.setdefault("LOGURU_LEVEL", "INFO")
    from arm_grouping.config import load_config
    from arm_grouping.pipeline import run

    set_name = sys.argv[1]
    nproc = int(sys.argv[2]) if len(sys.argv) > 2 else max(1, (os.cpu_count() or 4) - 2)

    row = next(r for r in csv.DictReader(MANIFEST.open()) if r["set"] == set_name)

    cfg = load_config(str(REPO / "input.toml"))
    cfg["vanilla"]["agreement_threshold"] = int(row["agreement_threshold"])
    cfg["arm_correction"]["correction_agreement"] = float(row["correction_agreement"])
    cfg["decide_longest_arm"]["ratio_limit"] = float(row["ratio_limit"])
    cfg["decide_longest_arm"]["longest_arm_support"] = int(row["longest_arm_support"])
    cfg["vanilla"]["trace_support"] = int(row["trace_support"])
    cfg["filter_outliers"]["lower_perc"] = int(row["lower_perc"])
    cfg["filter_outliers"]["upper_perc"] = int(row["upper_perc"])
    cfg["vanilla"]["blur"] = int(row["vanilla_blur"])
    cfg["arm_correction"]["blur"] = int(row["arm_correction_blur"])

    cfg["zooniverse"]["enabled"] = True
    cfg["zooniverse"]["metadata_csv"] = str(METADATA)
    cfg["zooniverse"]["bundle_prefix"] = set_name
    cfg["zooniverse"]["upload"]["enabled"] = False  # no PANOPTES creds; build only
    cfg["zooniverse"]["upload"]["subject_set_name"] = set_name

    cfg["parallel"]["num_processes"] = nproc
    cfg["combine_pics"]["split_output"] = True
    cfg["combine_pics"]["gif_output"] = False
    cfg["combine_pics"]["keep_combined_image"] = False

    outdir = SET_RUNS / set_name
    outdir.mkdir(parents=True, exist_ok=True)
    os.chdir(outdir)

    print(
        f"[{set_name}] agree={row['agreement_threshold']} corr={row['correction_agreement']} "
        f"ratio={row['ratio_limit']} trace_support={row['trace_support']} nproc={nproc}"
    )
    print(f"[{set_name}] output dir: {outdir}")
    run(cfg)
    print(f"[{set_name}] DONE")


if __name__ == "__main__":
    main()
