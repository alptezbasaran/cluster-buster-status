"""Set configs across phases: which knobs a Cluster Buster set ran with.

phase1-configs.csv (the 126-config grid) and phase2-configs.csv (the 64-config
sample) share their knob columns, and every set name appears in exactly one of
them. run_set.py, upload_set.py and analysis/probe_phase2.py all go through
here, so a knob is applied, checked and recorded the same way everywhere.
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_FILES = (HERE / "phase1-configs.csv", HERE / "phase2-configs.csv")
BASE_CONFIG = HERE / "base-config.json"

# configs column -> (config section, key, type, manifest column)
KNOBS = {
    "agreement_threshold": ("vanilla", "agreement_threshold", int, "#agreement_threshold"),
    "correction_agreement": ("arm_correction", "correction_agreement", float,
                             "#correction_agreement"),
    "ratio_limit": ("decide_longest_arm", "ratio_limit", float, "#ratio_limit"),
    "trace_support": ("vanilla", "trace_support", int, "#trace_support"),
    "longest_arm_support": ("decide_longest_arm", "longest_arm_support", int,
                            "#longest_arm_support"),
    "lower_perc": ("filter_outliers", "lower_perc", int, "#lower_perc"),
    "upper_perc": ("filter_outliers", "upper_perc", int, "#upper_perc"),
    "vanilla_blur": ("vanilla", "blur", int, "#vanilla_blur"),
    "arm_correction_blur": ("arm_correction", "blur", int, "#arm_correction_blur"),
}


def config_row(set_name):
    """The configs row for one set; exits unless exactly one file lists it."""
    rows = [r for f in CONFIG_FILES if f.exists()
            for r in csv.DictReader(f.open()) if r["set"] == set_name]
    if len(rows) != 1:
        raise SystemExit(f"{set_name}: listed {len(rows)} times across "
                         f"{', '.join(f.name for f in CONFIG_FILES)} (expected once)")
    return rows[0]


def set_config(row):
    """base-config.json with the set's nine knobs applied."""
    cfg = json.loads(BASE_CONFIG.read_text())
    for col, (section, key, cast, _) in KNOBS.items():
        cfg[section][key] = cast(row[col])
    return cfg
