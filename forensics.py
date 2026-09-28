#!/usr/bin/env python
"""Forensic review: who is contributing information, and what do the rest cost?

    ~/Desktop/projects/arm_grouping/.venv/bin/python harvest.py      # refresh store
    ~/Desktop/projects/arm_grouping/.venv/bin/python forensics.py [--since YYYY-MM-DD]

Reads the local raw store (harvest.py) and reports on the Cluster Buster era
only (from the first classification on a science subject). No API calls except
a one-off cached lookup of subject-set names. Per-account results go to the
gitignored state/forensics_<date>.json; optional notes on already-investigated
accounts are read from state/known_accounts.json (also gitignored -- this
repository is public, so no judgement about an identifiable volunteer belongs
in it).

What it measures, strongest evidence first (METHODS.md has the rationale and
the validation behind every threshold):

  CONTENT   Dawid-Skene two-coin EM over every science subject; each account is
            scored leave-one-out against that consensus. J = sens + spec - 1
            (Raykar & Yu's spammer score) is the information an account carries:
            0 for any fixed answer or coin flip. d' and c (signal detection)
            split that into discrimination and leniency, so a strict-but-careful
            volunteer is not mistaken for a guesser.
  TIERS     AUTOMATION   client evidence only: automation user agent, zero
                         recorded viewing time, sub-0.5 s median over >= 500 rows,
                         or mass re-voting of already-seen subjects (>= 20%)
            FIXED        >= 97% one answer
            AT CHANCE    two independent base-rate-immune models agree the
                         account cannot tell good from bad (J and d')
            LOW INFO     J < 0.25 otherwise
            BIASED       informative but grades far more leniently or harshly
                         than the crowd (Dawid-Skene corrects for it)
            OK
  DRIFT     weekly J and answer share per heavy account.
  CAPTCHA   reliable attention checks by polarity, with failure RATES tested
            against the population; exposure by client.
  LINKS     browser sessions and hashed IPs (classification export) shared by
            several accounts, with a device-fingerprint comparison.
  IMPACT    how many retired labels depend on the aggregation rule and on the
            flagged accounts.

Consensus is agreement with the crowd, not ground truth; read J as
information-relative-to-the-crowd, not correctness.
"""

import argparse
import csv
import gzip
import json
import math
import re
import statistics
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import NormalDist

import numpy as np

from harvest import WORKFLOW_ID, iter_rows

HERE = Path(__file__).resolve().parent
STATE = HERE / "state"
API = "https://panoptes.zooniverse.org/api"
PROJECT_ID = "23492"
CAPTCHA_SETS = {"137851", "138095"}
PHI_INV = NormalDist().inv_cdf
AUTOMATION_UA = re.compile(
    r"headless|phantom|selenium|webdriver|puppeteer|playwright|python|curl|wget|"
    r"httpclient|okhttp|node-fetch|axios|go-http|java/|electron|bot\b|spider|crawl|"
    r"zooniverse-cli", re.IGNORECASE)


def _known():
    """Optional {account_id: note} labels for accounts already investigated.

    Kept in the gitignored state/ so no judgement about an identifiable
    volunteer is ever committed to this (public) repository.
    """
    path = STATE / "known_accounts.json"
    return json.loads(path.read_text()) if path.exists() else {}


KNOWN = _known()

MIN_SCORED = 100       # science votes before an account is scored
FIXED_SHARE = 0.97     # one answer this often = fixed answering
CHANCE_J = 0.10        # upper 95% bound of J below this ...
CHANCE_D = 0.80        # ... and upper 95% bound of d' below this = at chance
LOW_J = 0.25
BIASED_C = 0.80        # |criterion| beyond this, with d' >= 1, = strongly biased
DS_STRENGTH = 6.0      # pseudo-votes pulling light accounts toward the population
RETIRE = 15


# ---------------------------------------------------------------- loading ---

def ts(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def subject_sets():
    """{subject_id: set_id} for the workflow, from the cached subjects export."""
    path = STATE / "export_subjects.csv.gz"
    if not path.exists():
        sys.exit("state/export_subjects.csv.gz missing (download the subjects export)")
    csv.field_size_limit(sys.maxsize)
    out = {}
    with gzip.open(path, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["workflow_id"] == WORKFLOW_ID or r["subject_set_id"] in CAPTCHA_SETS:
                out[r["subject_id"]] = r["subject_set_id"]
    return out


def set_names():
    cache = STATE / "set_names.json"
    if cache.exists():
        return json.loads(cache.read_text())
    names, page = {}, 1
    while page:
        req = urllib.request.Request(
            f"{API}/subject_sets?project_id={PROJECT_ID}&page_size=100&page={page}",
            headers={"Accept": "application/vnd.api+json; version=1"})
        with urllib.request.urlopen(req, timeout=60) as fh:
            d = json.load(fh)
        for s in d["subject_sets"]:
            names[s["id"]] = s["display_name"]
        page = d["meta"]["subject_sets"].get("next_page")
    cache.write_text(json.dumps(names, indent=1))
    return names


def captcha_map():
    doc = json.loads((HERE / "captcha_subjects.json").read_text())
    return {sid: (v["expected_value"], v.get("reliable", True))
            for sid, v in doc["subjects"].items()}


def ip_map():
    """{classification_id: (user_id, ip_hash)} from the export (covers its date only)."""
    path = STATE / "ip_map.tsv.gz"
    if not path.exists():
        return {}, None
    out, last = {}, ""
    with gzip.open(path, "rt") as fh:
        for line in fh:
            cid, uid, ip, created = line.rstrip("\n").split("\t")
            out[int(cid)] = (uid or None, ip)
            last = max(last, created)
    return out, last[:10]


def ua_family(ua):
    ua = (ua or "").lower()
    if not ua:
        return "none"
    if ua.startswith("ios"):
        return "ios-app"
    if ua.startswith("android"):
        return "android-app"
    if AUTOMATION_UA.search(ua):
        return "automation"
    if "mozilla" in ua:
        return "browser"
    return "other"


ID, WHO, SUBJ, VAL, CREATED, DUR, LAT, SESS, CLIENT, DIMS, SEEN, REV, LOGGED, UA, VP, OFF = range(16)


def load(sets, cmap):
    """Science + captcha rows, as compact id-ordered tuples (fields above)."""
    rows = []
    for r in iter_rows():
        s = r.get("s")
        if s not in sets and s not in cmap:
            continue
        u = r.get("u")
        who = str(u) if u else "anon:" + (r.get("sess") or "?")[:16]
        a, b = ts(r.get("a")), ts(r.get("b"))
        dur = (b - a).total_seconds() if a and b else None
        sel = ts(r.get("sel"))
        lat = (a - sel).total_seconds() if a and sel else None
        ua = sys.intern(r.get("ua") or "")
        rows.append((r["id"], who, s, r.get("v"), ts(r.get("c")), dur, lat,
                     r.get("sess"), sys.intern(ua_family(ua)), r.get("dims"),
                     bool(r.get("seen")), r.get("rev"), bool(u), ua,
                     sys.intern(r.get("vp") or ""), r.get("off")))
    rows.sort(key=lambda x: x[0])
    return rows


# ------------------------------------------------------------ Dawid-Skene ---

def dawid_skene(sidx, aidx, v, n_s, n_a, iters=100):
    """Two-coin EM with a population-mean Beta prior. Returns per-vote weights,
    per-subject log-odds of value 1, per-account (sens, spec) and the prior."""
    cnt = np.bincount(sidx, minlength=n_s)
    q = np.bincount(sidx, weights=v, minlength=n_s) / np.maximum(cnt, 1)
    for _ in range(iters):
        pos = np.bincount(aidx, weights=q[sidx], minlength=n_a)
        neg = np.bincount(aidx, weights=1 - q[sidx], minlength=n_a)
        tp = np.bincount(aidx, weights=v * q[sidx], minlength=n_a)
        tn = np.bincount(aidx, weights=(1 - v) * (1 - q[sidx]), minlength=n_a)
        ps, pp = tp.sum() / pos.sum(), tn.sum() / neg.sum()
        sens = np.clip((tp + DS_STRENGTH * ps) / (pos + DS_STRENGTH), 0.01, 0.99)
        spec = np.clip((tn + DS_STRENGTH * pp) / (neg + DS_STRENGTH), 0.01, 0.99)
        pi = float(np.clip(q[cnt > 0].mean(), 0.01, 0.99))
        w = np.where(v == 1, np.log(sens / (1 - spec))[aidx],
                     np.log((1 - sens) / spec)[aidx])
        lo = math.log(pi / (1 - pi)) + np.bincount(sidx, weights=w, minlength=n_s)
        qn = 1 / (1 + np.exp(-lo))
        done = np.max(np.abs(qn - q)) < 1e-7
        q = qn
        if done:
            break
    return w, lo, sens, spec, pi


def score_accounts(sidx, aidx, v, w, lo, n_a):
    """Leave-one-out soft confusion per account -> sens, spec, J and a 95% band."""
    ql = 1 / (1 + np.exp(-(lo[sidx] - w)))
    tp = np.bincount(aidx, weights=v * ql, minlength=n_a)
    fn = np.bincount(aidx, weights=(1 - v) * ql, minlength=n_a)
    tn = np.bincount(aidx, weights=(1 - v) * (1 - ql), minlength=n_a)
    fp = np.bincount(aidx, weights=v * (1 - ql), minlength=n_a)
    n1, n0 = tp + fn, tn + fp
    se_ = (tp + 0.5) / (n1 + 1)
    sp_ = (tn + 0.5) / (n0 + 1)
    j = se_ + sp_ - 1
    band = 1.96 * np.sqrt(se_ * (1 - se_) / (n1 + 1) + sp_ * (1 - sp_) / (n0 + 1))
    return se_, sp_, j, j - band, j + band, ql


def sdt(aidx, v, ql, n_a):
    """d' and criterion on subjects the leave-one-out consensus has decided.

    Value 1 ("No, bad clustering") is the signal; c > 0 = lenient (says good
    easily), c < 0 = harsh. Returns d', its 95% upper bound, and c."""
    d1, d0 = ql > 0.9, ql < 0.1
    hn = np.bincount(aidx[d1], minlength=n_a)
    hk = np.bincount(aidx[d1], weights=v[d1], minlength=n_a)
    fn = np.bincount(aidx[d0], minlength=n_a)
    fk = np.bincount(aidx[d0], weights=v[d0], minlength=n_a)
    hit, fa = (hk + .5) / (hn + 1), (fk + .5) / (fn + 1)
    zh = np.array([PHI_INV(x) for x in hit])
    zf = np.array([PHI_INV(x) for x in fa])

    def phi(z):
        return np.exp(-z * z / 2) / math.sqrt(2 * math.pi)

    se = np.sqrt(hit * (1 - hit) / ((hn + 1) * phi(zh) ** 2)
                 + fa * (1 - fa) / ((fn + 1) * phi(zf) ** 2))
    d = zh - zf
    return d, d + 1.96 * se, -(zh + zf) / 2


def bal_obvious(sidx, aidx, v, n_s, n_a, obvious=0.10, min_other=5):
    """The Aug 2026 score: leave-one-out accuracy on obvious subjects, per class."""
    ones = np.bincount(sidx, weights=v, minlength=n_s)
    cnt = np.bincount(sidx, minlength=n_s)
    lo_n = cnt[sidx] - 1
    p = np.where(lo_n > 0, (ones[sidx] - v) / np.maximum(lo_n, 1), 0.5)
    ok = lo_n >= min_other
    c0 = ok & (p <= obvious)
    c1 = ok & (p >= 1 - obvious)
    n0 = np.bincount(aidx[c0], minlength=n_a)
    k0 = np.bincount(aidx[c0], weights=(v[c0] == 0), minlength=n_a)
    n1 = np.bincount(aidx[c1], minlength=n_a)
    k1 = np.bincount(aidx[c1], weights=(v[c1] == 1), minlength=n_a)
    return n0, k0, n1, k1


def poisson_cdf(k, lam):
    """P(X <= k), X ~ Poisson(lam), in log space so large lam cannot overflow."""
    return sum(math.exp(i * math.log(lam) - lam - math.lgamma(i + 1)) for i in range(k + 1))


def binom_sf(k, n, p):
    """P(X >= k), X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


# ----------------------------------------------------------------- report ---

def pct(x):
    return f"{100 * x:5.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-08-19",
                    help="start of the 'recent' window (default: day after last review)")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()
    since = datetime.fromisoformat(args.since + "T00:00:00+00:00")

    sets = subject_sets()
    cmap = captcha_map()
    science = {s for s, k in sets.items() if k not in CAPTCHA_SETS}
    rows = load(sets, cmap)
    launch = min(r[CREATED] for r in rows if r[SUBJ] in science)
    rows = [r for r in rows if r[CREATED] >= launch]
    sci_rows = [r for r in rows if r[SUBJ] in science]
    end = max(r[CREATED] for r in rows)
    print(f"Cluster Buster era: {launch:%Y-%m-%d %H:%M} .. {end:%Y-%m-%d %H:%M} UTC")
    print(f"{len(rows):,} classifications ({len(sci_rows):,} science, "
          f"{len(rows) - len(sci_rows):,} captcha) | {len(science):,} science subjects "
          f"| recent window from {args.since}")

    # ---- per-account behaviour
    per = defaultdict(lambda: {"n": 0, "recent": 0, "dur": [], "zero": 0, "seen": 0,
                               "clients": Counter(), "uas": Counter(), "fp": Counter(),
                               "cy": 0, "cyo": 0, "cn": 0, "cno": 0, "cap_after": 0,
                               "first": None, "last": None, "times": [], "sessions": set()})
    qc2_live = min((r[CREATED] for r in rows if sets.get(r[SUBJ]) == "138095"), default=None)
    for r in rows:
        p = per[r[WHO]]
        p["n"] += 1
        p["recent"] += r[CREATED] >= since
        p["first"] = p["first"] or r[CREATED]
        p["last"] = r[CREATED]
        p["times"].append(r[CREATED])
        p["sessions"].add(r[SESS])
        p["cap_after"] += bool(qc2_live and r[CREATED] >= qc2_live)
        if r[DUR] is not None and 0 <= r[DUR] < 600:
            p["dur"].append(r[DUR])
            p["zero"] += r[DUR] == 0
        p["seen"] += r[SEEN]
        p["clients"][r[CLIENT]] += 1
        p["uas"][r[UA]] += 1
        p["fp"][(r[UA], r[VP], r[OFF])] += 1
        c = cmap.get(r[SUBJ])
        if c and c[1] and r[VAL] in (0, 1):
            if c[0] == 0:
                p["cy"] += 1
                p["cyo"] += r[VAL] == 0
            else:
                p["cn"] += 1
                p["cno"] += r[VAL] == 1

    # ---- volume
    print("\n== VOLUME ==")
    wk = defaultdict(lambda: {"n": 0, "anon": 0, "acc": Counter(), "new": 0})
    for r in rows:
        k = (r[CREATED] - timedelta(days=r[CREATED].weekday())).strftime("%Y-%m-%d")
        wk[k]["n"] += 1
        if r[LOGGED]:
            wk[k]["acc"][r[WHO]] += 1
        else:
            wk[k]["anon"] += 1
    for u, p in per.items():
        if not u.startswith("anon"):
            t = p["first"]
            wk[(t - timedelta(days=t.weekday())).strftime("%Y-%m-%d")]["new"] += 1
    print(f"  {'week of':<11}{'class.':>9}{'anon':>7}{'accts':>7}{'new':>6}{'top1':>7}{'top5':>7}")
    for k in sorted(wk):
        b = wk[k]
        tops = b["acc"].most_common(5)
        print(f"  {k:<11}{b['n']:>9,}{pct(b['anon'] / b['n']):>7}{len(b['acc']):>7}{b['new']:>6}"
              f"{pct(tops[0][1] / b['n'] if tops else 0):>7}"
              f"{pct(sum(c for _, c in tops) / b['n'] if tops else 0):>7}")

    # ---- content: Dawid-Skene over deduplicated science votes
    first_vote, dupes = {}, Counter()
    vote_week = {}
    for r in sci_rows:
        if r[VAL] not in (0, 1):
            continue
        key = (r[WHO], r[SUBJ])
        if key in first_vote:
            dupes[r[WHO]] += 1
            continue
        first_vote[key] = r[VAL]
        vote_week[key] = (r[CREATED] - timedelta(days=r[CREATED].weekday())).date()
    accts = sorted({a for a, _ in first_vote})
    subs = sorted({s for _, s in first_vote})
    ai = {a: i for i, a in enumerate(accts)}
    si = {s: i for i, s in enumerate(subs)}
    n_a, n_s = len(accts), len(subs)
    aidx = np.fromiter((ai[a] for a, _ in first_vote), dtype=np.int64, count=len(first_vote))
    sidx = np.fromiter((si[s] for _, s in first_vote), dtype=np.int64, count=len(first_vote))
    v = np.fromiter(first_vote.values(), dtype=np.float64, count=len(first_vote))
    w, lo, _sens, _spec, pi = dawid_skene(sidx, aidx, v, n_s, n_a)
    _se, _sp, j, jlo, jhi, ql = score_accounts(sidx, aidx, v, w, lo, n_a)
    dprime, d_hi, crit = sdt(aidx, v, ql, n_a)
    n0, k0, n1, k1 = bal_obvious(sidx, aidx, v, n_s, n_a)
    nvotes = np.bincount(aidx, minlength=n_a)
    yes_rate = np.bincount(aidx, weights=(v == 0), minlength=n_a) / np.maximum(nvotes, 1)

    def gap_cv(times):
        g = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
        g = [x for x in g if 0 < x < 600]
        if len(g) < 50:
            return float("nan")
        m = statistics.mean(g)
        return statistics.pstdev(g) / m if m else float("nan")

    report, tier = {}, {}
    for u, p in per.items():
        i = ai.get(u)
        d = p["dur"]
        auto_ua = sum(n for ua, n in p["uas"].items() if AUTOMATION_UA.search(ua))
        x = {
            "rows": p["n"], "recent": p["recent"],
            "first": p["first"].isoformat()[:10], "last": p["last"].isoformat()[:10],
            "votes": int(nvotes[i]) if i is not None else 0, "dupes": dupes.get(u, 0),
            "sessions": len(p["sessions"]),
            "client": p["clients"].most_common(1)[0][0],
            "automation_ua_rows": auto_ua,
            "med_dur": round(statistics.median(d), 2) if d else None,
            "lt1s": round(sum(t < 1 for t in d) / len(d), 3) if d else None,
            "zero_dur": p["zero"], "gap_cv": round(gap_cv(p["times"]), 2),
            "seen": round(p["seen"] / p["n"], 3),
            "captcha": [p["cyo"], p["cy"], p["cno"], p["cn"]],
            "rows_since_qc2": p["cap_after"],
        }
        if i is not None:
            x.update({
                "J": round(float(j[i]), 3), "J_lo": round(float(jlo[i]), 3),
                "J_hi": round(float(jhi[i]), 3), "dprime": round(float(dprime[i]), 2),
                "dprime_hi": round(float(d_hi[i]), 2), "criterion": round(float(crit[i]), 2),
                "yes_rate": round(float(yes_rate[i]), 3),
                "BAL": (round(50 * (k0[i] / n0[i] + k1[i] / n1[i]), 1)
                        if n0[i] >= 15 and n1[i] >= 15 else None),
            })
        report[u] = x
        # tiers, in order of evidence strength
        if auto_ua >= 20 or x["zero_dur"] >= 20 or (x["med_dur"] is not None and x["med_dur"] < 0.5
                                                     and p["n"] >= 500) \
                or (x["dupes"] >= 500 and x["dupes"] / p["n"] >= 0.20):
            t = "AUTOMATION"
        elif i is None or nvotes[i] < MIN_SCORED:
            t = "UNSCORED"
        elif max(yes_rate[i], 1 - yes_rate[i]) >= FIXED_SHARE:
            t = "FIXED"
        elif jhi[i] < CHANCE_J and d_hi[i] < CHANCE_D:
            t = "AT CHANCE"
        elif j[i] < LOW_J:
            t = "LOW INFO"
        elif dprime[i] >= 1.0 and abs(crit[i]) >= BIASED_C:
            t = "BIASED"
        else:
            t = "OK"
        tier[u] = x["tier"] = t

    print("\n== CONTENT (Dawid-Skene, leave-one-out; signal detection) ==")
    scored = [i for i in range(n_a) if nvotes[i] >= MIN_SCORED]
    js = np.array([j[i] for i in scored])
    wts = np.array([nvotes[i] for i in scored], dtype=float)
    post = 1 / (1 + np.exp(-lo))
    print(f"  {len(v):,} distinct (account, subject) votes from {n_a:,} identities; "
          f"prior P(bad) = {pi:.3f}; {np.mean(np.abs(post - 0.5) > 0.4):.1%} of subjects decided")
    print(f"  {len(scored)} identities with >={MIN_SCORED} votes: J median {np.median(js):.2f}, "
          f"volume-weighted {np.average(js, weights=wts):.2f}")

    order = ["AUTOMATION", "FIXED", "AT CHANCE", "LOW INFO", "BIASED", "OK", "UNSCORED"]
    print(f"\n  {'tier':<12}{'accounts':>9}{'rows':>10}{'share':>8}{'recent':>9}{'share':>8}")
    for t in order:
        us = [u for u in tier if tier[u] == t]
        nr = sum(report[u]["rows"] for u in us)
        rr = sum(report[u]["recent"] for u in us)
        print(f"  {t:<12}{len(us):>9,}{nr:>10,}{pct(nr / len(rows)):>8}{rr:>9,}"
              f"{pct(rr / max(1, sum(p['recent'] for p in per.values()))):>8}")

    hdr = (f"  {'account':>22}{'rows':>8}{'recent':>8}{'J':>6}{'dprime':>7}{'crit':>6}"
           f"{'yes%':>6}{'dur':>6}  captcha(yes,no)  client")

    def row(u, extra=""):
        x = report[u]
        cap = x["captcha"]
        jj = f"{x['J']:6.2f}" if "J" in x else "     -"
        dd = f"{x['dprime']:7.2f}{x['criterion']:6.2f}{100 * x['yes_rate']:5.0f}%" if "J" in x else " " * 19
        md = f"{x['med_dur']:.1f}" if x["med_dur"] is not None else "-"
        return (f"  {u:>22}{x['rows']:>8,}{x['recent']:>8,}{jj}{dd}{md:>6}"
                f"  y{cap[0]}/{cap[1]} n{cap[2]}/{cap[3]}  {x['client']:<10} {extra}")

    for t in ["AUTOMATION", "FIXED", "AT CHANCE", "LOW INFO", "BIASED"]:
        us = sorted((u for u in tier if tier[u] == t), key=lambda u: -report[u]["rows"])
        if not us:
            continue
        print(f"\n  {t} ({len(us)})")
        print(hdr)
        for u in us[:args.top]:
            why = []
            x = report[u]
            if t == "AUTOMATION":
                if x["automation_ua_rows"]:
                    ua = next(ua for ua in per[u]["uas"] if AUTOMATION_UA.search(ua))
                    why.append(f"{x['automation_ua_rows']:,} rows UA '{AUTOMATION_UA.search(ua).group(0)}'")
                if x["zero_dur"] >= 20:
                    why.append(f"{x['zero_dur']:,} zero-duration")
                if x["dupes"] >= 50:
                    why.append(f"{x['dupes']:,} re-votes")
                if x["med_dur"] is not None and x["med_dur"] < 0.5:
                    why.append(f"median {x['med_dur']}s")
            print(row(u, "; ".join(why) + ("  " + KNOWN[u] if u in KNOWN else "")))

    rec = sorted((u for u in report if report[u]["recent"] > 0), key=lambda u: -report[u]["recent"])
    print(f"\n  TOP RECENT CONTRIBUTORS (since {args.since}): {len(rec)} identities active")
    print(hdr)
    for u in rec[:args.top]:
        print(row(u, f"[{tier[u]}] {KNOWN.get(u, '')}"))

    # ---- drift
    print("\n== DRIFT (weekly leave-one-out J / share answering Yes) ==")
    weeks = np.array([vote_week[k].toordinal() for k in first_vote], dtype=np.int64)
    heavy = [u for u in rec[:40] if report[u]["recent"] >= 500 and u in ai]
    wlist = sorted({d for d in vote_week.values() if d >= since.date() - timedelta(days=35)})
    print("  " + f"{'account':>22}" + "".join(f"{d:%m-%d}".rjust(11) for d in wlist))
    drifters = []
    for u in heavy:
        i = ai[u]
        cells, js_ = [], []
        for d in wlist:
            m = (aidx == i) & (weeks == d.toordinal())
            if m.sum() < 80:
                cells.append(" " * 11)
                continue
            vv, qq = v[m], ql[m]
            tp, fn = (vv * qq).sum(), ((1 - vv) * qq).sum()
            tn, fp = ((1 - vv) * (1 - qq)).sum(), (vv * (1 - qq)).sum()
            jw = (tp + .5) / (tp + fn + 1) + (tn + .5) / (tn + fp + 1) - 1
            js_.append(jw)
            cells.append(f"{jw:5.2f}/{100 * (1 - vv.mean()):3.0f}%".rjust(11))
        print(f"  {u:>22}" + "".join(cells) + f"  {tier[u]}")
        if len(js_) >= 3 and js_[-1] < LOW_J and js_[0] - js_[-1] > 0.15:
            drifters.append(u)
    print(f"  declining (first->last week drop > 0.15, ending below {LOW_J}): "
          f"{', '.join(drifters) or 'none'}")

    # ---- captcha
    print("\n== CAPTCHA (reliable cards) ==")
    byc = defaultdict(lambda: [0, 0])
    for r in rows:
        if qc2_live and r[CREATED] >= qc2_live:
            byc[r[CLIENT]][0] += 1
            byc[r[CLIENT]][1] += sets.get(r[SUBJ]) == "138095"
    rate = {c: k / n for c, (n, k) in byc.items() if n}
    for c, (n, k) in sorted(byc.items(), key=lambda kv: -kv[1][0]):
        if n >= 1000:
            print(f"  served since qc2 link ({qc2_live:%Y-%m-%d}), {c:<12} {k:>5,} / {n:>8,} = {k / n:.3%}")
    logged = [x for u, x in report.items() if not u.startswith("anon")]
    yk, yn = sum(x["captcha"][0] for x in logged), sum(x["captcha"][1] for x in logged)
    nk, nn = sum(x["captcha"][2] for x in logged), sum(x["captcha"][3] for x in logged)
    fy, fn_ = 1 - yk / max(yn, 1), 1 - nk / max(nn, 1)
    print(f"  logged-in pass rate: YES {yk}/{yn} ({yk / max(yn, 1):.1%}), NO {nk}/{nn} ({nk / max(nn, 1):.1%})")
    print("  NOTE: a pass shows the account read the card, not that it reads science subjects;")
    print("  see METHODS.md on what captchas can and cannot establish.")
    flags = []
    for u, x in report.items():
        if u.startswith("anon"):
            continue
        cy, ny_, cn, nn_ = x["captcha"]
        py = binom_sf(ny_ - cy, ny_, fy) if ny_ - cy else 1.0
        pn = binom_sf(nn_ - cn, nn_, fn_) if nn_ - cn else 1.0
        onesided = (ny_ >= 2 and cy == ny_ and nn_ >= 2 and cn == 0) or \
                   (nn_ >= 2 and cn == nn_ and ny_ >= 2 and cy == 0)
        if onesided or min(py, pn) < 1e-3:
            flags.append((u, "one-sided" if onesided else f"fail rate p={min(py, pn):.0e}"))
    print(f"  accounts failing one polarity entirely, or failing far above the population rate: {len(flags)}")
    for u, why in sorted(flags, key=lambda t: -report[t[0]]["rows"]):
        print(row(u, f"{why} [{tier[u]}]"))
    under = []
    for u, x in report.items():
        r_ = rate.get(x["client"], 0)
        served = x["captcha"][1] + x["captcha"][3]
        if u.startswith("anon") or x["rows_since_qc2"] < 1000 or not r_:
            continue
        lam = x["rows_since_qc2"] * r_
        if served >= lam:
            continue
        p0 = poisson_cdf(served, lam)
        if p0 < 1e-4:
            under.append((u, served, lam, p0))
    print(f"  accounts served far fewer captchas than their client's rate predicts: {len(under)}")
    for u, s_, lam, p0 in under:
        print(row(u, f"served {s_}, expected {lam:.0f}, P={p0:.0e}"))

    # ---- links
    print("\n== LINKED ACCOUNTS ==")
    sess_users = defaultdict(Counter)
    for r in rows:
        if r[LOGGED] and r[SESS]:
            sess_users[r[SESS]][r[WHO]] += 1
    shared = {s: c for s, c in sess_users.items() if len(c) >= 2}
    print(f"  browser sessions used by >=2 logged-in accounts: {len(shared)}")
    for s, c in sorted(shared.items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        print("   ", s[:12], ", ".join(f"{u}({n:,}, {tier[u]})" for u, n in c.most_common()))
    ips, ip_through = ip_map()
    if ips:
        ip_users = defaultdict(lambda: defaultdict(list))
        for r in rows:
            m = ips.get(r[ID])
            if m and m[0]:
                ip_users[m[1]][r[WHO]].append(r)
        multi = [(ip, us) for ip, us in ip_users.items() if len(us) >= 2]
        print(f"  hashed IPs (export through {ip_through}) shared by >=2 accounts: {len(multi)}")
        print("  device = same user agent + window size + time zone; 'together' = two accounts")
        print("  active within 10 min of each other on that IP (a class or household, not one person)")
        flagged = {"AUTOMATION", "FIXED", "AT CHANCE", "LOW INFO"}
        for ip, us in sorted(multi, key=lambda kv: -sum(len(x) for x in kv[1].values())):
            ids = sorted(us, key=lambda u: int(u))
            if not ({tier[u] for u in ids} & flagged):
                continue
            fps = {u: Counter((r[UA], r[VP], r[OFF]) for r in us[u]).most_common(1)[0][0] for u in ids}
            dev = len(set(fps.values())) < len(ids)
            ev = sorted((r[CREATED], u) for u in ids for r in us[u])
            together = sum(1 for a, b in zip(ev, ev[1:])
                           if a[1] != b[1] and (b[0] - a[0]).total_seconds() < 600)
            print(f"   {ip[:10]} ids {ids[0]}..{ids[-1]} device-shared {'YES' if dev else 'no':<3} "
                  f"together {together:>4}: "
                  + ", ".join(f"{u}({len(us[u])}, {tier[u]})" for u in ids[:8]))

    # ---- impact on labels
    print("\n== IMPACT ON LABELS ==")
    raw_cnt = Counter(r[SUBJ] for r in sci_rows)
    R = np.array([raw_cnt[s] >= RETIRE for s in subs])
    ones = np.bincount(sidx, weights=v, minlength=n_s)
    cnt = np.bincount(sidx, minlength=n_s)
    maj = np.where(ones * 2 > cnt, 1, np.where(ones * 2 < cnt, 0, -1))
    ds = (lo > 0).astype(int)
    m = R & (maj >= 0)
    print(f"  retired science subjects (>= {RETIRE} classifications): {int(R.sum()):,}")
    print(f"  Dawid-Skene vs plain majority: {np.mean(ds[m] != maj[m]):.1%} differ "
          f"({int(((maj == 0) & (ds == 1) & m).sum()):,} majority-good -> DS-bad, "
          f"{int(((maj == 1) & (ds == 0) & m).sum()):,} the other way); "
          f"share labelled good: majority {np.mean(maj[m] == 0):.1%}, DS {np.mean(ds[m] == 0):.1%}")
    # automation that still carries information (a scripted client giving good
    # labels) is a method question, not a quality one -- keep its votes
    bad_t = {"AUTOMATION", "FIXED", "AT CHANCE"}
    bad = np.array([tier.get(a) in bad_t and report[a].get("J", 0) < LOW_J for a in accts])
    keep = ~bad[aidx]
    o2 = np.bincount(sidx[keep], weights=v[keep], minlength=n_s)
    c2 = np.bincount(sidx[keep], minlength=n_s)
    maj2 = np.where(o2 * 2 > c2, 1, np.where(o2 * 2 < c2, 0, -1))
    mm = m & (maj2 >= 0)
    print(f"  majority label flips when no-information votes (AUTOMATION/FIXED/AT CHANCE with J < {LOW_J}) are removed: "
          f"{int((maj2[mm] != maj[mm]).sum()):,} ({np.mean(maj2[mm] != maj[mm]):.1%}); "
          f"{int((m & (maj2 < 0)).sum()):,} become ties")
    nbad = np.bincount(sidx, weights=bad[aidx].astype(float), minlength=n_s)
    for k in (2, 3, 5):
        print(f"  retired subjects with >= {k} of their votes from those accounts: "
              f"{int((nbad[R] >= k).sum()):,} ({np.mean(nbad[R] >= k):.1%})")
    lenient = np.array([report[a].get("criterion", 0) >= BIASED_C and nvotes[ai[a]] >= 300
                        for a in accts])
    nlen = np.bincount(sidx, weights=lenient[aidx].astype(float), minlength=n_s)
    print("  DS-vs-majority disagreement by number of strongly lenient heavy voters on the subject:")
    for k in range(6):
        sel = m & ((nlen == k) if k < 5 else (nlen >= 5))
        if sel.sum() >= 100:
            print(f"    {k}{'+' if k == 5 else ' '} lenient voters: {int(sel.sum()):>6,} subjects, "
                  f"differ {np.mean(ds[sel] != maj[sel]):.1%}")
    cover = sorted(((nvotes[i] / n_s, accts[i]) for i in range(n_a)), reverse=True)[:5]
    print("  largest single-account coverage of all science subjects: "
          + ", ".join(f"{u} {c:.0%} [{tier[u]}]" for c, u in cover))

    # ---- anonymous
    an = [u for u in report if u.startswith("anon")]
    an_rows = sum(report[u]["rows"] for u in an)
    print(f"\n== ANONYMOUS ==\n  {an_rows:,} rows ({an_rows / len(rows):.1%}) across {len(an):,} sessions; "
          f"anonymous captcha pass: YES {sum(report[u]['captcha'][0] for u in an)}/"
          f"{sum(report[u]['captcha'][1] for u in an)}, NO {sum(report[u]['captcha'][2] for u in an)}/"
          f"{sum(report[u]['captcha'][3] for u in an)}")
    for u in sorted((u for u in an if report[u]["votes"] >= MIN_SCORED),
                    key=lambda u: -report[u]["rows"])[:8]:
        print(row(u, f"[{tier[u]}]"))

    out = STATE / f"forensics_{date.today().isoformat()}.json"
    out.write_text(json.dumps({"_meta": {"launch": launch.isoformat(), "end": end.isoformat(),
                                         "since": args.since, "rows": len(rows),
                                         "tiers": {t: sorted(u for u in tier if tier[u] == t)
                                                   for t in order if t != "OK" and t != "UNSCORED"},
                                         "drifting": drifters,
                                         "captcha_flags": [u for u, _ in flags]},
                               "accounts": report}, indent=0))
    print(f"\nper-account results -> {out.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
