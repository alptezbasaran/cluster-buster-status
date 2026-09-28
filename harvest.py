#!/usr/bin/env python
"""Raw classification store: harvest once, analyse forever.

    source ~/.zooniverse_env
    ~/Desktop/projects/arm_grouping/.venv/bin/python harvest.py            # incremental
    ~/Desktop/projects/arm_grouping/.venv/bin/python harvest.py --full     # whole history

Every forensic question so far (consensus scoring, timing, sessions, captcha
exposure) needed per-classification rows, and each investigation re-harvested
them into a scratch directory that was later wiped -- twice. This keeps one
compact copy of every project classification under the gitignored
state/raw/, so analyses read local files and only new rows are ever fetched.

--full splits the id space into chunks and pulls them with --workers parallel
processes; each chunk file is append-only and resumes from its own last id, so
an interrupted run (API 504s happen) just re-runs. Incremental mode fetches
everything after the highest stored id into one new chunk.

Rows keep the fields the analyses use, under short keys (see ROW_KEYS below);
load them with `load_rows()`. Classifications are not modified, only read.
"""

import argparse
import gzip
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "state" / "raw"
PROJECT_ID = "23492"
WORKFLOW_ID = "26736"
PAGE = 200

# Dense region (the Cluster Buster era, June 2026 on) gets fine chunks so the
# workers stay balanced; the sparse 2024-25 history gets coarse ones.
SPARSE = [(548_000_000, 640_000_000), (640_000_000, 700_000_000),
          (700_000_000, 735_000_000)]
DENSE_FROM, DENSE_STEP, DENSE_TO = 735_000_000, 2_500_000, 790_000_000

ROW_KEYS = {
    "id": "classification id (int)", "u": "user id or None (anonymous)",
    "s": "first subject id", "ns": "number of subjects", "v": "answer 0/1 or None",
    "w": "workflow id", "c": "created_at", "a": "started_at", "b": "finished_at",
    "sess": "session hash", "ua": "user agent", "vp": "viewport WxH",
    "off": "utc_offset (s)", "lang": "user_language", "rev": "front-end revision",
    "cv": "classifier_version", "wv": "workflow_version", "src": "source",
    "live": "live_project", "sel": "designator selected_at", "seen": "already_seen",
    "ret": "subject retired when served", "ss": "selection_state",
    "dims": "frames with a loaded image (None = key absent)",
    "flag": "subject_flagged", "fb": "feedback present",
}


def canon(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    return None


def compact(c):
    raw = c.raw
    links = raw.get("links") or {}
    m = raw.get("metadata") or {}
    subs = [str(s) for s in (links.get("subjects") or [])]
    anns = raw.get("annotations") or []
    sel = m.get("subject_selection_state") or {}
    vp = m.get("viewport") or {}
    dims = m.get("subject_dimensions")
    if isinstance(dims, list):
        dims = sum(1 for d in dims if isinstance(d, dict) and d.get("naturalWidth"))
    else:
        dims = None
    row = {
        "id": int(raw["id"]), "u": links.get("user"), "s": subs[0] if subs else None,
        "v": canon(anns[0].get("value")) if anns else None,
        "w": links.get("workflow"), "c": raw.get("created_at"),
        "a": m.get("started_at"), "b": m.get("finished_at"),
        "sess": m.get("session"), "ua": m.get("user_agent"),
        "vp": f"{vp.get('width')}x{vp.get('height')}" if vp else None,
        "off": m.get("utc_offset"), "lang": m.get("user_language"),
        "rev": (m.get("revision") or "")[:10] or None,
        "cv": m.get("classifier_version"), "wv": m.get("workflow_version"),
        "src": m.get("source"), "live": m.get("live_project"),
        "sel": sel.get("selected_at"), "seen": sel.get("already_seen"),
        "ret": sel.get("retired"), "ss": sel.get("selection_state"),
        "dims": dims, "flag": m.get("subject_flagged"), "fb": bool(m.get("feedback")),
    }
    if len(subs) > 1:
        row["ns"] = len(subs)
    return row


def connect():
    from panoptes_client import Panoptes

    user, pw = os.environ.get("PANOPTES_USERNAME"), os.environ.get("PANOPTES_PASSWORD")
    if not user or not pw:
        print("PANOPTES_USERNAME / PANOPTES_PASSWORD not set (source ~/.zooniverse_env)")
        sys.exit(2)
    Panoptes.connect(username=user, password=pw)


def last_id_in(path):
    """Highest id already written to a (plain, append-only) chunk file."""
    if not path.exists():
        return None
    last = None
    with path.open() as fh:
        for line in fh:
            try:
                last = json.loads(line)["id"]
            except (ValueError, KeyError):
                break  # torn final line from a killed run; resume before it
    return last


def pull_chunk(bounds):
    """Fetch ids in (lo, hi] into state/raw/chunk_<lo>_<hi>.jsonl. hi=None = open."""
    lo, hi = bounds
    from panoptes_client import Classification

    connect()
    path = RAW_DIR / f"chunk_{lo}_{hi or 'open'}.jsonl"
    done = RAW_DIR / (path.name + ".done")
    if done.exists():
        return path.name, 0, "skipped (done)"
    start = last_id_in(path) or lo
    n, tries = 0, 0
    while True:
        try:
            with path.open("a") as fh:
                for c in Classification.where(scope="project", project_id=PROJECT_ID,
                                              page_size=PAGE, last_id=str(start)):
                    cid = int(c.id)
                    if hi is not None and cid > hi:
                        done.touch()
                        return path.name, n, "complete"
                    fh.write(json.dumps(compact(c), separators=(",", ":")) + "\n")
                    n += 1
                    start = cid
                    if n % 5000 == 0:
                        fh.flush()
            done.touch()  # generator exhausted: reached the newest classification
            return path.name, n, "complete (end of history)"
        except Exception as exc:  # 504s and resets: back off, resume from `start`
            tries += 1
            if tries > 8:
                return path.name, n, f"GAVE UP after {tries} errors: {exc!r}"
            time.sleep(min(60, 2 ** tries))


def full_plan():
    plan = list(SPARSE)
    x = DENSE_FROM
    while x < DENSE_TO:
        plan.append((x, x + DENSE_STEP))
        x += DENSE_STEP
    plan.append((DENSE_TO, None))
    return plan


def stored_max():
    best = 0
    for p in RAW_DIR.glob("chunk_*.jsonl*"):
        if p.suffix == ".done":
            continue
        opener = gzip.open if p.suffix == ".gz" else open
        with opener(p, "rt") as fh:
            for line in fh:
                try:
                    best = max(best, json.loads(line)["id"])
                except (ValueError, KeyError):
                    pass
    return best


def iter_rows(workflow=WORKFLOW_ID, raw_dir=RAW_DIR):
    """Stream stored rows for one workflow (None = all), de-duplicated by id.

    Chunk order, not id order -- sort downstream if order matters.
    """
    seen = set()
    for p in sorted(raw_dir.glob("chunk_*.jsonl*")):
        if p.name.endswith(".done"):
            continue
        opener = gzip.open if p.suffix == ".gz" else open
        with opener(p, "rt") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r["id"] in seen or (workflow and r.get("w") != workflow):
                    continue
                seen.add(r["id"])
                yield r


def load_rows(workflow=WORKFLOW_ID, raw_dir=RAW_DIR):
    """All stored rows for one workflow (None = all), de-duplicated, id-ordered."""
    return sorted(iter_rows(workflow, raw_dir), key=lambda r: r["id"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--full", action="store_true", help="(re)harvest the whole history")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.full:
        plan = full_plan()
    else:
        top = stored_max()
        if not top:
            print("no stored rows yet -- run with --full first")
            return 2
        plan = [(top, None)]
        # an open chunk from a previous incremental run is finished business
        for p in RAW_DIR.glob("chunk_*_open.jsonl"):
            p.rename(p.with_name(p.name.replace("_open", f"_{top}")))

    t0 = time.time()
    total = 0
    with Pool(min(args.workers, len(plan))) as pool:
        for name, n, status in pool.imap_unordered(pull_chunk, plan):
            total += n
            print(f"  {name:40s} {n:>8,}  {status}  [{time.time()-t0:5.0f}s]", flush=True)
    print(f"harvest: {total:,} new rows in {time.time()-t0:.0f}s; "
          f"store max id {stored_max():,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
