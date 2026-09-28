#!/usr/bin/env python
"""Which accounts are run by the same operator? Evidence from timing, not IPs.

    ~/Desktop/projects/arm_grouping/.venv/bin/python linkage.py [--window 180]

A shared IP is weak evidence: VPN exit nodes, school networks and mobile
carriers put unrelated people behind one address, and one person moves between
addresses. Time is harder to share by accident. One operator running two
accounts produces a signature two independent volunteers almost never do:

  HANDOFFS   account A stops and account B starts within --window seconds
             (log out, log in), repeatedly.
  EXCLUSIVE  despite being active on the same days and hours, A and B are
             almost never active in the same 5-minute slot -- one pair of hands.

Both are compared with a null that keeps each account's own daily rhythm: B's
timeline is shifted by whole days (+-1..7) and the counts recomputed, so two
people who simply both classify on weekday evenings do not look linked.
A classroom shows the opposite: high co-activity, no handoffs.

Device fingerprints (browser family and OS without version numbers, window
size, time zone, language) and hashed IPs from the classification export are
printed as corroboration only. Results go to the gitignored
state/linkage_<date>.json; nothing about an identifiable account is committed.
"""

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date

import numpy as np

import forensics as F

BOUT_GAP = 600      # seconds without a classification that ends a bout
SLOT = 300          # co-activity resolution
MIN_ROWS = 50
SHIFTS = [d for d in range(-7, 8) if d]


def device(ua):
    ua = ua or ""
    if ua.startswith("ios"):
        return "iOS app"
    if ua.startswith("android"):
        return "Android app"
    os_ = next((o for o, k in (("Windows", "Windows"), ("macOS", "Macintosh"), ("ChromeOS", "CrOS"),
                               ("Android", "Android"), ("iOS", "iPhone"), ("iPadOS", "iPad"),
                               ("Linux", "Linux")) if k in ua), "?")
    br = next((b for b, k in (("Edge", "Edg/"), ("Opera", "OPR/"), ("Firefox", "Firefox/"),
                              ("Headless", "HeadlessChrome"), ("Chrome", "Chrome/"),
                              ("Safari", "Safari/")) if k in ua), ua[:20])
    return f"{br}/{os_}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", type=int, default=180, help="handoff window, seconds")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    sets = F.subject_sets()
    cmap = F.captcha_map()
    science = {s for s, k in sets.items() if k not in F.CAPTCHA_SETS}
    rows = F.load(sets, cmap)
    launch = min(r[F.CREATED] for r in rows if r[F.SUBJ] in science)
    rows = [r for r in rows if r[F.CREATED] >= launch]
    t0 = launch.timestamp()

    times = defaultdict(list)
    fps = defaultdict(Counter)
    for r in rows:
        times[r[F.WHO]].append(r[F.CREATED].timestamp() - t0)
        fps[r[F.WHO]][(device(r[F.UA]), r[F.VP], r[F.OFF])] += 1
    ids = [u for u, t in times.items() if len(t) >= MIN_ROWS]
    idx = {u: i for i, u in enumerate(ids)}
    print(f"{len(ids)} identities with >= {MIN_ROWS} classifications "
          f"({sum(1 for u in ids if u.startswith('anon'))} anonymous sessions)")

    starts, ends, s_id, e_id = [], [], [], []
    slots = {}
    days = {}
    for u in ids:
        t = np.sort(np.array(times[u]))
        brk = np.where(np.diff(t) > BOUT_GAP)[0]
        b_start = np.concatenate([[t[0]], t[brk + 1]])
        b_end = np.concatenate([t[brk], [t[-1]]])
        starts.append(b_start)
        ends.append(b_end)
        s_id.append(np.full(len(b_start), idx[u]))
        e_id.append(np.full(len(b_end), idx[u]))
        slots[u] = set((t // SLOT).astype(np.int64).tolist())
        days[u] = set((t // 86400).astype(np.int64).tolist())
    starts = np.concatenate(starts)
    ends = np.concatenate(ends)
    s_id = np.concatenate(s_id)
    e_id = np.concatenate(e_id)
    o = np.argsort(starts)
    starts, s_id = starts[o], s_id[o]
    print(f"{len(ends):,} activity bouts (gap > {BOUT_GAP // 60} min ends a bout)")

    def handoffs(shift_days):
        q = ends + shift_days * 86400
        lo = np.searchsorted(starts, q, "left")
        hi = np.searchsorted(starts, q + args.window, "right")
        c = Counter()
        for i in np.nonzero(hi > lo)[0]:
            a = e_id[i]
            for b in s_id[lo[i]:hi[i]]:
                if b != a:
                    c[(a, b)] += 1
        return c

    obs = handoffs(0)
    null = [handoffs(d) for d in SHIFTS]
    cand = [(k, n) for k, n in obs.items() if n >= 3]
    null_pairs = [sum(1 for n in c.values() if n >= 3) for c in null]
    print(f"ordered pairs with >= 3 handoffs: observed {len(cand)}, expected by chance "
          f"{np.mean(null_pairs):.1f} (range {min(null_pairs)}-{max(null_pairs)} over "
          f"{len(SHIFTS)} day-shifted timelines)")
    res = []
    for (a, b), n in cand:
        nulls = np.array([c.get((a, b), 0) for c in null], dtype=float)
        mu, sd = nulls.mean(), nulls.std()
        z = (n - mu) / max(sd, math.sqrt(max(mu, 0.25)))
        ua, ub = ids[a], ids[b]
        both_days = days[ua] & days[ub]
        if len(both_days) < 2:
            continue
        # co-activity: shared 5-minute slots, observed vs the same day-shift null
        sa, sb = slots[ua], slots[ub]
        co = len(sa & sb)
        per_day = 86400 // SLOT
        co_null = np.mean([len(sa & {x + d * per_day for x in sb}) for d in SHIFTS])
        res.append({"a": ua, "b": ub, "handoffs": n, "null_mean": round(mu, 2), "z": round(z, 1),
                    "days_both": len(both_days), "co_slots": co, "co_null": round(co_null, 1)})
    # merge A->B and B->A
    pair = {}
    for r in res:
        key = tuple(sorted((r["a"], r["b"])))
        p = pair.setdefault(key, {"a": key[0], "b": key[1], "handoffs": 0, "null_mean": 0.0,
                                  "z": -99, "days_both": r["days_both"], "co_slots": r["co_slots"],
                                  "co_null": r["co_null"]})
        p["handoffs"] += r["handoffs"]
        p["null_mean"] += r["null_mean"]
        p["z"] = max(p["z"], r["z"])
    pairs = sorted(pair.values(), key=lambda p: -p["z"])

    tiers = {}
    fr = F.STATE / f"forensics_{date.today().isoformat()}.json"
    if fr.exists():
        tiers = {u: x.get("tier") for u, x in json.loads(fr.read_text())["accounts"].items()}
    ips, through = F.ip_map()
    ip_of = defaultdict(set)
    for r in rows:
        m = ips.get(r[F.ID])
        if m:
            ip_of[r[F.WHO]].add(m[1])

    zs = np.array([p["z"] for p in pairs]) if pairs else np.array([0.0])
    print(f"{len(pairs):,} pairs with >= 3 handoffs; handoff z: median {np.median(zs):.1f}, "
          f"99th pct {np.percentile(zs, 99):.1f}")
    print(f"\n  {'pair':<36}{'handoffs':>9}{'null':>7}{'z':>6}{'days':>6}{'co-act':>8}{'null':>7}  "
          f"device match / shared IP (export to {through})")
    for p in pairs[:args.top]:
        fa = fps[p["a"]].most_common(1)[0][0]
        fb = fps[p["b"]].most_common(1)[0][0]
        same = [k for k, x, y in zip(("device", "window", "tz"), fa, fb) if x == y]
        shared_ip = len(ip_of[p["a"]] & ip_of[p["b"]])
        label = f"{p['a']}[{tiers.get(p['a'], '-')}] {p['b']}[{tiers.get(p['b'], '-')}]"
        print(f"  {label:<36}{p['handoffs']:>9}{p['null_mean']:>7.1f}{p['z']:>6.1f}{p['days_both']:>6}"
              f"{p['co_slots']:>8}{p['co_null']:>7.1f}  {'+'.join(same) or 'none'}"
              f"{'; ' + str(shared_ip) + ' IP(s)' if shared_ip else ''}")
        p.update({"device_match": same, "shared_ips": shared_ip,
                  "fp_a": list(map(str, fa)), "fp_b": list(map(str, fb))})

    out = F.STATE / f"linkage_{date.today().isoformat()}.json"
    out.write_text(json.dumps(pairs[:200], indent=1))
    print(f"\npairs -> {out.relative_to(F.HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
