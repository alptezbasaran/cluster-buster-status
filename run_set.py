"""Run one Cluster Buster set end-to-end: cluster the 500-galaxy set with the
set's config (phase1-configs.csv or phase2-configs.csv), render with Set1, and
build the Zooniverse bundle (split PNGs + manifest). Does NOT upload.

    python run_set.py cluster-buster-NNN [num_processes]

Runs start from base-config.json, the frozen Phase-1 base config, with the
set's nine knobs applied (configs.py); arm_grouping's input.toml is not read.
Outputs land in artifacts/set_runs/<set>/: the bundle (<set>_<hash>/),
outputs_*/run.json and outputs_*/outputs/ (per-galaxy JSON + split PNGs). The
per-galaxy FITS under outputs_*/outputs_arms (~5 GB a set) are deleted once
the bundle is built; they regenerate deterministically. provenance.txt records
the code and environment, and set-status.json marks the set clustered with its
subject and no-arm counts (a galaxy whose clustering has no arm counts as
unsuccessful without being uploaded; see collect_no_arms.py).
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from configs import KNOBS, config_row, set_config

REPO = Path("/Users/atezbas/Desktop/projects/arm_grouping")
SET_RUNS = Path("/Users/atezbas/Desktop/projects/astro/cluster-buster/artifacts/set_runs")
SET_STATUS = Path(__file__).resolve().parent / "docs/.vitepress/data/set-status.json"


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def version(dist):
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return "-"


def provenance(nproc):
    import cv2

    dirty = git("status", "--porcelain", "--untracked-files=no").splitlines()
    diff = hashlib.sha256(git("diff", "HEAD").encode()).hexdigest()[:12]
    return (
        f"arm_grouping: {git('rev-parse', 'HEAD')} ({git('rev-parse', '--abbrev-ref', 'HEAD')})\n"
        f"uncommitted: {', '.join(line[3:] for line in dirty) or 'none'}"
        f" (git diff HEAD sha256 {diff})\n"
        f"python {platform.python_version()}, numpy {version('numpy')}, opencv {cv2.__version__}, "
        f"fitsio {version('fitsio')}, astropy {version('astropy')}\n"
        f"platform: {platform.platform()}\n"
        f"processes: {nproc}\n"
    )


def main() -> None:
    os.environ.setdefault("LOGURU_LEVEL", "INFO")
    from arm_grouping.config import validate_config
    from arm_grouping.pipeline import run

    set_name = sys.argv[1]
    nproc = int(sys.argv[2]) if len(sys.argv) > 2 else max(1, (os.cpu_count() or 4) - 2)

    row = config_row(set_name)
    cfg = set_config(row)
    cfg["zooniverse"]["enabled"] = True
    cfg["zooniverse"]["bundle_prefix"] = set_name
    cfg["zooniverse"]["upload"]["enabled"] = False  # uploads go through upload_set.py
    cfg["zooniverse"]["upload"]["subject_set_name"] = set_name
    cfg["parallel"]["num_processes"] = nproc
    cfg["combine_pics"]["split_output"] = True
    cfg["combine_pics"]["gif_output"] = False
    cfg["combine_pics"]["keep_combined_image"] = False
    validate_config(cfg)

    outdir = SET_RUNS / set_name
    if list(outdir.glob(f"{set_name}_*")):
        sys.exit(f"[{set_name}] {outdir} already holds a bundle; move it aside to re-run")
    outdir.mkdir(parents=True, exist_ok=True)
    os.chdir(outdir)

    # Corpus provenance: sets 001-020 clustered the pre-cleaning corpus;
    # 021+ run on the cleaned set (2026-07-06 pass — outliers parked as
    # .fits.excluded are invisible to the arms/*.fits glob). Record what
    # this run actually saw, both on stdout and durably in the run dir.
    active = excluded = 0
    for folder in cfg["parallel"]["folder_list"]:
        for arms in Path(folder).glob("*/arms"):
            active += sum(1 for _ in arms.glob("*.fits"))
            excluded += sum(1 for _ in arms.glob("*.fits.excluded"))
    corpus_note = (
        f"[{set_name}] corpus: {active} active tracings, {excluded} parked "
        "(.fits.excluded; cleaned set — see cleaning/excluded_manifest_2026-07-06.csv "
        "in cluster-buster-status)"
    )
    print(corpus_note)
    (outdir / "corpus_state.txt").write_text(corpus_note + "\n")
    (outdir / "provenance.txt").write_text(provenance(nproc))

    print(f"[{set_name}] " + " ".join(f"{col}={row[col]}" for col in KNOBS) + f" nproc={nproc}")
    print(f"[{set_name}] output dir: {outdir}")
    run(cfg)

    bundle = next(outdir.glob(f"{set_name}_*"))
    for arms in outdir.glob("outputs_*/outputs_arms"):
        shutil.rmtree(arms)
    with (bundle / "manifest.csv").open() as fh:
        subjects = sum(1 for _ in fh) - 1
    skipped = [line.split("\t") for line in (bundle / "skipped.txt").read_text().splitlines()
               if line.strip()]
    no_arms = sum(1 for _, reason in skipped if reason == "no_arms")
    status = json.loads(SET_STATUS.read_text())
    status.setdefault(set_name, {}).update(
        clustered=True, hash=bundle.name.split("_")[-1], subjects=subjects, no_arms=no_arms)
    SET_STATUS.write_text(json.dumps(status, indent=2) + "\n")
    (outdir / ".clustered_ok").touch()
    print(f"[{set_name}] DONE: {subjects} subjects, {no_arms} galaxies with no arm "
          f"(counted unsuccessful), {len(skipped) - no_arms} other skips")


if __name__ == "__main__":
    main()
