#!/usr/bin/env python
"""Generate the attention-check ("captcha") subject bundle for Cluster Buster.

Each subject is three 592x592 frames mimicking a real subject (gray tracing
squiggles, Set1-colored clusters, composite overlay) with an unmissable
instruction on every frame: "TEST SUBJECT / Please answer: / YES|NO". Volunteers
who read the image answer correctly; automation and blind clickers do not.
Deployed after the 2026-07-12 bot incident (see incidents/).

    ~/Desktop/projects/arm_grouping/.venv/bin/python make_captcha_bundle.py \
        [--n-yes 100] [--n-no 100] [--seed 20260723] [--size 592] \
        [--out ~/Desktop/projects/astro/cluster-buster/artifacts/set_runs/cluster-buster-qc]

Output bundle <out>/cluster-buster-qc_<seed>/ contains <gid>_{1,2,3}.png per
subject (1=overlay, 2=clusters, 3=tracings — the live-set frame order), a
strict 18-column manifest.csv (only #image1/2/3 + #data_set=attention_check
populated; answer is encoded in the gid prefix qcyes/qcno), captcha_answers.csv
and info.txt. Generation is deterministic per (seed, gid) and finishes by
running the uploader's verify_bundle, so a completed run is upload-ready.

NEVER upload this set with upload_set.py (its hyperparameter guard aborts on
the empty knob columns) — use zooniverse_upload.py directly:

    source ~/.zooniverse_env
    ~/Desktop/projects/arm_grouping/.venv/bin/python \
        ~/Desktop/projects/arm_grouping/zooniverse_upload.py <bundle_dir> \
        --project-slug astro-lab-ncmns/spiral-graph-cluster-buster \
        --subject-set-name cluster-buster-qc
"""

import argparse
import csv
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ARM_GROUPING = Path.home() / "Desktop/projects/arm_grouping"
sys.path.insert(0, str(ARM_GROUPING))
from arm_grouping.zooniverse import MANIFEST_FIELDNAMES  # noqa: E402
from zooniverse_upload import verify_bundle  # noqa: E402

DEFAULT_OUT = (
    Path.home() / "Desktop/projects/astro/cluster-buster/artifacts/set_runs/cluster-buster-qc"
)
# Project Set1 palette (RGB, blue brightened per brand decision)
SET1 = ["#e41a1c", "#46a1eb", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33"]
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def load_font(size: int) -> ImageFont.FreeTypeFont:
    if size in _font_cache:
        return _font_cache[size]
    for path in FONT_CANDIDATES:
        try:
            _font_cache[size] = ImageFont.truetype(path, size)
            return _font_cache[size]
        except OSError:
            continue
    raise RuntimeError(
        "no usable bold TrueType font found; refusing PIL's tiny bitmap fallback"
    )


def arm_backbone(
    rng: random.Random,
    cx: float,
    cy: float,
    th0: float,
    handed: int,
    b: float,
    r_out: float,
) -> list[tuple[float, float]]:
    """One log-spiral arm skeleton sized to fill the frame like real subjects:
    outer radius is chosen first and the inner scale derived from it."""
    sweep = rng.uniform(1.6, 2.6) * math.pi
    a = r_out / math.exp(b * sweep)
    pts = []
    n = 150
    for i in range(n):
        frac = i / (n - 1)
        th = th0 + handed * sweep * frac
        r = a * math.exp(b * sweep * frac)
        pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
    return pts


def jitter_trace(rng: random.Random, backbone: list[tuple[float, float]]):
    """One 'volunteer tracing' of a backbone: offset + wobble, sometimes sparse
    (subsampled points give the polygonal hand-drawn look of real tracings)."""
    off = rng.uniform(0, 7)
    ang = rng.uniform(0, 2 * math.pi)
    ox, oy = off * math.cos(ang), off * math.sin(ang)
    pts = [(x + ox + rng.gauss(0, 2.4), y + oy + rng.gauss(0, 2.4)) for x, y in backbone]
    if rng.random() < 0.35:
        step = rng.randint(6, 14)
        pts = pts[::step] + [pts[-1]]
    return pts


def outlier_scribble(rng: random.Random, size: int):
    """Stray non-arm tracing, as seen in real aggregated subjects."""
    x = rng.uniform(size * 0.2, size * 0.8)
    y = rng.uniform(size * 0.2, size * 0.8)
    pts = [(x, y)]
    ang = rng.uniform(0, 2 * math.pi)
    for _ in range(rng.randint(15, 40)):
        ang += rng.gauss(0, 0.5)
        x += 6 * math.cos(ang)
        y += 6 * math.sin(ang)
        pts.append((x, y))
    return pts


def make_geometry(rng: random.Random, size: int):
    """A galaxy: arms share one center, handedness and winding (like a real
    spiral), offset evenly in angle with jitter; each arm = many tracings."""
    n_arms = rng.randint(2, 4)
    cx = size / 2 + rng.uniform(-15, 15)
    cy = size / 2 + rng.uniform(-15, 15)
    handed = rng.choice([-1, 1])
    b = rng.uniform(0.15, 0.28)
    base_th = rng.uniform(0, 2 * math.pi)
    arms = []
    for k in range(n_arms):
        th0 = base_th + k * (2 * math.pi / n_arms) + rng.uniform(-0.3, 0.3)
        r_out = size * rng.uniform(0.30, 0.42)
        backbone = arm_backbone(rng, cx, cy, th0, handed, b, r_out)
        traces = [jitter_trace(rng, backbone) for _ in range(rng.randint(8, 14))]
        arms.append(traces)
    outliers = [outlier_scribble(rng, size) for _ in range(rng.randint(1, 3))]
    return arms, outliers


def draw_gray(draw: ImageDraw.ImageDraw, arms, outliers, rng: random.Random):
    for traces in arms:
        for t in traces:
            g = rng.randint(110, 190)
            draw.line(t, fill=(g, g, g), width=1)
    for t in outliers:
        g = rng.randint(90, 150)
        draw.line(t, fill=(g, g, g), width=1)


def draw_clusters(draw: ImageDraw.ImageDraw, arms, colors):
    for traces, color in zip(arms, colors):
        for t in traces:
            draw.line(t, fill=color, width=1)


def draw_instruction(img: Image.Image, answer: str, jx: int, jy: int):
    """White text with black stroke: maximal contrast normal AND color-inverted;
    the word itself carries the meaning (no color-only cue)."""
    d = ImageDraw.Draw(img)
    cx = img.width / 2 + jx

    def center(text: str, font: ImageFont.FreeTypeFont, y: int):
        bb = d.textbbox((0, 0), text, font=font, stroke_width=3)
        d.text(
            (cx - (bb[2] - bb[0]) / 2, y),
            text,
            font=font,
            fill=(255, 255, 255),
            stroke_width=3,
            stroke_fill=(0, 0, 0),
        )

    center("TEST SUBJECT", load_font(44), 52 + jy)
    center("Please answer:", load_font(34), 112 + jy)
    center(answer, load_font(170), 210 + jy)


def render_subject(gid: str, answer: str, seed: int, size: int, out: Path):
    rng = random.Random(f"{seed}:{gid}")
    arms, outliers = make_geometry(rng, size)
    colors = rng.sample(SET1, len(arms))
    jx, jy = rng.randint(-20, 20), rng.randint(-15, 15)

    # frame 3: tracings only (gray)
    tracings = Image.new("RGB", (size, size), (0, 0, 0))
    draw_gray(ImageDraw.Draw(tracings), arms, outliers, random.Random(f"{seed}:{gid}:g"))
    # frame 2: clusters only (colored)
    clusters = Image.new("RGB", (size, size), (0, 0, 0))
    draw_clusters(ImageDraw.Draw(clusters), arms, colors)
    # frame 1: overlay = gray tracings + colored clusters on top
    overlay = Image.new("RGB", (size, size), (0, 0, 0))
    d1 = ImageDraw.Draw(overlay)
    draw_gray(d1, arms, outliers, random.Random(f"{seed}:{gid}:g"))
    draw_clusters(d1, arms, colors)

    for frame in (overlay, clusters, tracings):
        draw_instruction(frame, answer, jx, jy)

    overlay.save(out / f"{gid}_1.png")
    clusters.save(out / f"{gid}_2.png")
    tracings.save(out / f"{gid}_3.png")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-yes", type=int, default=100)
    ap.add_argument("--n-no", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260723)
    ap.add_argument("--size", type=int, default=592)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    bundle = args.out / f"cluster-buster-qc_{args.seed}"
    bundle.mkdir(parents=True, exist_ok=True)

    subjects = [(f"qcyes{i:03d}", "YES", 0) for i in range(1, args.n_yes + 1)]
    subjects += [(f"qcno{i:03d}", "NO", 1) for i in range(1, args.n_no + 1)]

    rows = []
    answers = []
    for gid, word, expected in subjects:
        render_subject(gid, word, args.seed, args.size, bundle)
        row = {col: "" for col in MANIFEST_FIELDNAMES}
        row["#image1"] = f"{gid}_1.png"
        row["#image2"] = f"{gid}_2.png"
        row["#image3"] = f"{gid}_3.png"
        row["#data_set"] = "attention_check"
        rows.append(row)
        answers.append({"gid": gid, "answer": word.lower(), "expected_value": expected})

    with open(bundle / "manifest.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    with open(bundle / "captcha_answers.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["gid", "answer", "expected_value"])
        writer.writeheader()
        writer.writerows(answers)
    (bundle / "info.txt").write_text(
        f"file_hash: qc{args.seed}\nkind: attention_check\n"
        f"subjects: {len(subjects)} ({args.n_yes} yes / {args.n_no} no)\n"
    )

    rows_ok, _ = verify_bundle(bundle)
    print(f"bundle: {bundle}")
    print(f"subjects: {len(subjects)} ({args.n_yes} yes / {args.n_no} no)")
    print(f"verify_bundle: {rows_ok}/{len(subjects)} rows OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
