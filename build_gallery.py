#!/usr/bin/env python3
"""Build the committed gallery assets for a Cluster Buster set.

For each subject in a set's bundle this emits, into the status site repo:
  - docs/public/sets/<NNN>/<gid>.webp   the overlay view, re-encoded to WebP
  - docs/.vitepress/data/set-<NNN>.json  per-subject metadata (gid, arms, links)

Overlay only (the headline clusters-on-tracings view, image1). Lower-quality
WebP keeps the repo small; resolution is preserved so the lightbox stays sharp.

    python3 build_gallery.py 001            # default quality 60
    python3 build_gallery.py 001 --quality 55
    python3 build_gallery.py 001 002 003    # several sets at once
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ARTIFACTS = (HERE / ".." / "cluster-buster" / "artifacts" / "set_runs").resolve()
IMG_ROOT = HERE / "docs" / "public" / "sets"
DATA_ROOT = HERE / "docs" / ".vitepress" / "data"


def resolve_set(set_arg: str) -> tuple[str, str, Path, Path]:
    """Return (set_name, num, bundle_dir, manifest_path)."""
    if set_arg.startswith("cluster-buster-"):
        name, num = set_arg, set_arg.rsplit("-", 1)[-1]
    else:
        num = f"{int(set_arg):03d}"
        name = f"cluster-buster-{num}"
    set_dir = ARTIFACTS / name
    if not set_dir.is_dir():
        sys.exit(f"set dir not found: {set_dir}")
    bundles = sorted(d for d in set_dir.glob(f"{name}_*") if d.is_dir())
    if not bundles:
        sys.exit(f"no bundle (expected {name}_<hash>/) under {set_dir}")
    manifest = bundles[-1] / "manifest.csv"
    if not manifest.is_file():
        sys.exit(f"no manifest.csv in {bundles[-1]}")
    return name, num, bundles[-1], manifest


def build_set(set_arg: str, quality: int) -> None:
    name, num, bundle, manifest_path = resolve_set(set_arg)
    out_imgs = IMG_ROOT / num
    out_imgs.mkdir(parents=True, exist_ok=True)

    subjects = []
    config = None
    written = skipped = 0
    total_bytes = 0
    with manifest_path.open(newline="") as fh:
        for raw in csv.DictReader(fh):
            row = {k.lstrip("#"): v for k, v in raw.items()}
            gid = row.get("dr7objid") or Path(row.get("image1", "")).stem.rsplit("_", 1)[0]
            src = bundle / row["image1"]
            if not src.is_file():
                skipped += 1
                continue
            dst = out_imgs / f"{gid}.webp"
            Image.open(src).convert("RGB").save(dst, "WEBP", quality=quality, method=6)
            total_bytes += dst.stat().st_size
            written += 1
            if config is None:
                config = {
                    "agreement": row.get("agreement_threshold", ""),
                    "correction": row.get("correction_agreement", ""),
                    "trace_support": row.get("trace_support", ""),
                    "longest_arm_support": row.get("longest_arm_support", ""),
                    "ratio_limit": row.get("ratio_limit", ""),
                }
            subjects.append(
                {
                    "gid": gid,
                    "arms": int(row["number_of_clustered_arms"] or 0),
                    "sdss": row.get("SDSS_data", ""),
                    "legacy": row.get("Legacy_Survey_image", ""),
                    "leda": row.get("LEDA_data", ""),
                }
            )

    subjects.sort(key=lambda s: (s["arms"], s["gid"]))
    payload = {
        "set": name,
        "num": num,
        "hash": bundle.name.rsplit("_", 1)[-1],
        "config": config or {},
        "subjects": subjects,
    }
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / f"set-{num}.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")

    mb = total_bytes / 1024 / 1024
    note = f" ({skipped} skipped, no image)" if skipped else ""
    print(f"{name}: {written} overlays -> {out_imgs.relative_to(HERE)}  {mb:.1f} MB @ q{quality}{note}")
    print(f"         data -> {(DATA_ROOT / f'set-{num}.json').relative_to(HERE)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build committed gallery assets for a set.")
    ap.add_argument("sets", nargs="+", help="set number(s) or name(s), e.g. 001 or cluster-buster-001")
    ap.add_argument("--quality", type=int, default=60, help="WebP quality 1-100 (default 60)")
    args = ap.parse_args()
    for s in args.sets:
        build_set(s, args.quality)


if __name__ == "__main__":
    main()
