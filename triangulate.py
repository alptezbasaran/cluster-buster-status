#!/usr/bin/env python
"""Cross-check forensics.py with independent analysis families.

    ~/Desktop/projects/arm_grouping/.venv/bin/python triangulate.py [--since YYYY-MM-DD]

No single score should convict an account. This runs the established methods
for crowdsourced binary labels side by side on the same votes and reports where
they agree. Each family answers a different question, and each has a failure
mode the others do not share:

  MAJ    leave-one-out agreement with the plain majority (the naive baseline;
         Zooniverse's default question reducer is an unweighted vote count).
  DS     Dawid & Skene (1979) two-coin EM; J = sens + spec - 1 is Raykar & Yu's
         (2012) spammer score. Sensitivity to its prior is checked.
  ANCHOR DS re-scored against a consensus built ONLY from accounts that pass
         their captchas and score well -- so a large low-quality bloc cannot
         define the truth it is judged against.
  GLAD   Whitehill et al. (2009): per-subject difficulty x per-account ability;
         ability < 0 means systematically inverted (adversarial) answers.
  SDT    signal detection on decided subjects: d' = discrimination (can they
         tell good from bad at all?), c = criterion (do they grade leniently or
         harshly?). Separates a biased-but-careful volunteer from a guesser --
         J alone conflates the two.
  FIT    person-fit / difficulty coupling: humans are more accurate on subjects
         the crowd finds easy (Drasgow-style aberrance: guessers are flat).
  TIME   do they spend longer on subjects the crowd finds hard? A responder
         that is not looking has timing independent of difficulty.
  RUNS   Wald-Wolfowitz runs test on the answer sequence (long-string /
         straight-lining index from careless-responding research, Meade &
         Craig 2012).
  RELIAB split-half reliability of J across accounts -- is it a stable trait?
  OUTLIER robust multivariate outlier score over behaviour + content features,
         with no hand-set thresholds (the watch.py rules were calibrated on one
         incident).
  PAIRS  difficulty-aware excess agreement between heavy accounts (a pair is
         compared with each member's agreement with a random crowd member on
         the same subjects, so shared "hard subject" disagreement is controlled).
  LABELS how many retired labels change across aggregators (majority, DS,
         GLAD, Galaxy Zoo 2 consistency weighting, majority minus at-chance
         accounts).
"""

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import NormalDist

import numpy as np

import forensics as F

PHI_INV = NormalDist().inv_cdf


def build(rows, science):
    first_vote, first_row = {}, {}
    for r in rows:
        if r[F.SUBJ] not in science or r[F.VAL] not in (0, 1):
            continue
        key = (r[F.WHO], r[F.SUBJ])
        if key not in first_vote:
            first_vote[key] = r[F.VAL]
            first_row[key] = r
    accts = sorted({a for a, _ in first_vote})
    subs = sorted({s for _, s in first_vote})
    ai = {a: i for i, a in enumerate(accts)}
    si = {s: i for i, s in enumerate(subs)}
    keys = list(first_vote)
    aidx = np.array([ai[a] for a, _ in keys])
    sidx = np.array([si[s] for _, s in keys])
    v = np.array([first_vote[k] for k in keys], dtype=float)
    dur = np.array([first_row[k][F.DUR] if first_row[k][F.DUR] is not None
                    and 0 <= first_row[k][F.DUR] < 600 else np.nan for k in keys])
    t = np.array([first_row[k][F.ID] for k in keys])
    return accts, subs, ai, si, aidx, sidx, v, dur, t, keys


def loo_majority(sidx, v, n_s):
    ones = np.bincount(sidx, weights=v, minlength=n_s)
    cnt = np.bincount(sidx, minlength=n_s)
    lo_n = cnt[sidx] - 1
    p = np.where(lo_n > 0, (ones[sidx] - v) / np.maximum(lo_n, 1), np.nan)
    return p, lo_n


def glad(sidx, aidx, v, n_s, n_a, q0, em_iters=25, grad_iters=15, lr=0.02):
    """Whitehill et al. 2009. Returns ability alpha (per account) and posterior q."""
    alpha = np.ones(n_a)
    b = np.zeros(n_s)  # beta = exp(b) > 0, the subject's easiness
    q = q0.copy()
    pi = q.mean()
    cnt_a = np.maximum(np.bincount(aidx, minlength=n_a), 1)
    cnt_s = np.maximum(np.bincount(sidx, minlength=n_s), 1)
    for _ in range(em_iters):
        corr = np.where(v == 1, q[sidx], 1 - q[sidx])  # P(vote is correct)
        for _ in range(grad_iters):
            beta = np.exp(b)
            s = 1 / (1 + np.exp(-alpha[aidx] * beta[sidx]))
            g = corr - s
            ga = np.bincount(aidx, weights=g * beta[sidx], minlength=n_a) - (alpha - 1)
            gb = np.bincount(sidx, weights=g * alpha[aidx] * beta[sidx], minlength=n_s) - b
            alpha += lr * ga / np.sqrt(cnt_a)
            b += lr * gb / np.sqrt(cnt_s)
            b = np.clip(b, -4, 4)
        beta = np.exp(b)
        s = np.clip(1 / (1 + np.exp(-alpha[aidx] * beta[sidx])), 1e-6, 1 - 1e-6)
        l1 = np.where(v == 1, np.log(s), np.log(1 - s))
        l0 = np.where(v == 0, np.log(s), np.log(1 - s))
        lo = (math.log(pi / (1 - pi)) + np.bincount(sidx, weights=l1, minlength=n_s)
              - np.bincount(sidx, weights=l0, minlength=n_s))
        q = 1 / (1 + np.exp(-lo))
        pi = float(np.clip(q.mean(), 0.01, 0.99))
    return alpha, b, q


def soft_j(aidx, v, ql, n_a):
    tp = np.bincount(aidx, weights=v * ql, minlength=n_a)
    fn = np.bincount(aidx, weights=(1 - v) * ql, minlength=n_a)
    tn = np.bincount(aidx, weights=(1 - v) * (1 - ql), minlength=n_a)
    fp = np.bincount(aidx, weights=v * (1 - ql), minlength=n_a)
    return (tp + .5) / (tp + fn + 1) + (tn + .5) / (tn + fp + 1) - 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-08-19")
    args = ap.parse_args()
    since = datetime.fromisoformat(args.since + "T00:00:00+00:00")

    sets = F.subject_sets()
    cmap = F.captcha_map()
    science = {s for s, k in sets.items() if k not in F.CAPTCHA_SETS}
    rows = F.load(sets, cmap)
    launch = min(r[F.CREATED] for r in rows if r[F.SUBJ] in science)
    rows = [r for r in rows if r[F.CREATED] >= launch]
    accts, subs, ai, _si, aidx, sidx, v, dur, tid, _keys = build(rows, science)
    n_a, n_s = len(accts), len(subs)
    nv = np.bincount(aidx, minlength=n_a)
    heavy = nv >= 300
    print(f"{len(v):,} votes, {n_a:,} identities ({int(heavy.sum())} with >=300 votes), "
          f"{n_s:,} subjects")

    # captcha record per account (reliable cards)
    cap = defaultdict(lambda: [0, 0, 0, 0])
    recent = Counter()
    for r in rows:
        if r[F.CREATED] >= since:
            recent[r[F.WHO]] += 1
        c = cmap.get(r[F.SUBJ])
        if c and c[1] and r[F.VAL] in (0, 1):
            x = cap[r[F.WHO]]
            if c[0] == 0:
                x[0] += 1
                x[1] += r[F.VAL] == 0
            else:
                x[2] += 1
                x[3] += r[F.VAL] == 1

    # ---- MAJ
    p, lo_n = loo_majority(sidx, v, n_s)
    ok = lo_n >= 5
    maj = np.where(p > 0.5, 1.0, np.where(p < 0.5, 0.0, np.nan))
    agree = (v == maj)
    valid = ok & ~np.isnan(maj)
    acc_maj = (np.bincount(aidx[valid], weights=agree[valid], minlength=n_a)
               / np.maximum(np.bincount(aidx[valid], minlength=n_a), 1))

    # ---- DS at three prior strengths + anchor consensus
    res = {}
    for k in (2.0, 6.0, 20.0):
        F.DS_STRENGTH = k
        w, lo, sens, spec, _pi = F.dawid_skene(sidx, aidx, v, n_s, n_a)
        _se, _sp, j, jlo, jhi, ql = F.score_accounts(sidx, aidx, v, w, lo, n_a)
        res[k] = (j, jlo, jhi, ql, w, lo, sens, spec)
    F.DS_STRENGTH = 6.0
    j, jlo, jhi, ql, w, lo, sens, spec = res[6.0]
    print("\n== DS prior sensitivity (J, accounts with >=300 votes) ==")
    for k in (2.0, 20.0):
        d = np.abs(res[k][0][heavy] - j[heavy])
        print(f"  strength {k:>4}: max |dJ| {d.max():.3f}, mean {d.mean():.4f}, "
              f"rank corr {np.corrcoef(np.argsort(np.argsort(res[k][0][heavy])), np.argsort(np.argsort(j[heavy])))[0, 1]:.4f}")

    anchor = np.zeros(n_a, bool)
    for u, i in ai.items():
        c = cap.get(u)
        passes = c and c[0] + c[2] >= 4 and c[1] + c[3] == c[0] + c[2]
        anchor[i] = bool(passes) and j[i] >= 0.45 and nv[i] >= 300
    am = anchor[aidx]
    wa, loa, *_ = F.dawid_skene(sidx[am], aidx[am], v[am], n_s, n_a)
    has = np.bincount(sidx[am], minlength=n_s) >= 3
    # anchor posterior for every vote; anchors themselves are scored leave-one-out
    wfull = np.zeros(len(v))
    wfull[am] = wa
    q_anchor = 1 / (1 + np.exp(-(loa[sidx] - wfull)))
    m_anchor = has[sidx]
    j_anchor = soft_j(aidx[m_anchor], v[m_anchor], q_anchor[m_anchor], n_a)
    n_anchor = np.bincount(aidx[m_anchor], minlength=n_a)
    print(f"\n== ANCHOR consensus: {int(anchor.sum())} anchor accounts "
          f"({int(np.bincount(aidx[am]).sum()):,} votes), {int(has.sum()):,} subjects with >=3 anchor votes ==")

    # ---- GLAD
    alpha, _b, q_glad = glad(sidx, aidx, v, n_s, n_a, 1 / (1 + np.exp(-lo)))

    # ---- SDT on decided subjects (leave-one-out DS posterior)
    dec1 = ql > 0.9
    dec0 = ql < 0.1
    h_n = np.bincount(aidx[dec1], minlength=n_a)
    h_k = np.bincount(aidx[dec1], weights=v[dec1], minlength=n_a)
    f_n = np.bincount(aidx[dec0], minlength=n_a)
    f_k = np.bincount(aidx[dec0], weights=v[dec0], minlength=n_a)
    hit = (h_k + .5) / (h_n + 1)
    fa = (f_k + .5) / (f_n + 1)
    zh = np.array([PHI_INV(x) for x in hit])
    zf = np.array([PHI_INV(x) for x in fa])
    dprime = zh - zf
    crit = -(zh + zf) / 2
    # d' standard error (Gourevitch & Galanter)
    phi = lambda z: np.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    dse = np.sqrt(hit * (1 - hit) / ((h_n + 1) * phi(zh) ** 2) + fa * (1 - fa) / ((f_n + 1) * phi(zf) ** 2))

    # ---- FIT: accuracy vs subject easiness (LOO majority margin)
    margin = np.abs(p - 0.5) * 2
    easy = valid & (margin >= 0.8)
    hard = valid & (margin < 0.3)
    acc_e = np.bincount(aidx[easy], weights=agree[easy], minlength=n_a) / np.maximum(np.bincount(aidx[easy], minlength=n_a), 1)
    acc_h = np.bincount(aidx[hard], weights=agree[hard], minlength=n_a) / np.maximum(np.bincount(aidx[hard], minlength=n_a), 1)
    n_e = np.bincount(aidx[easy], minlength=n_a)
    fit = acc_e - acc_h

    # ---- TIME coupling and RUNS
    couple = np.full(n_a, np.nan)
    runs_z = np.full(n_a, np.nan)
    order = np.argsort(tid)
    by_a = defaultdict(list)
    for k in order:
        by_a[aidx[k]].append(k)
    for i, ks in by_a.items():
        if len(ks) < 300:
            continue
        ks = np.array(ks)
        de, dh = dur[ks][easy[ks]], dur[ks][hard[ks]]
        de, dh = de[~np.isnan(de)], dh[~np.isnan(dh)]
        if len(de) >= 30 and len(dh) >= 30 and np.median(de) > 0:
            couple[i] = np.median(dh) / np.median(de)
        seq = v[ks]
        n1_ = seq.sum()
        n0_ = len(seq) - n1_
        if n0_ >= 20 and n1_ >= 20:
            r = 1 + np.count_nonzero(seq[1:] != seq[:-1])
            n = len(seq)
            e = 1 + 2 * n0_ * n1_ / n
            var = 2 * n0_ * n1_ * (2 * n0_ * n1_ - n) / (n * n * (n - 1))
            runs_z[i] = (r - e) / math.sqrt(var)

    # ---- RELIAB: split-half J
    half = (sidx % 2 == 0)
    j_a = soft_j(aidx[half], v[half], ql[half], n_a)
    j_b = soft_j(aidx[~half], v[~half], ql[~half], n_a)
    m = nv >= 400
    rel = np.corrcoef(j_a[m], j_b[m])[0, 1]
    print(f"\n== RELIABILITY: split-half J correlation over {int(m.sum())} accounts "
          f"(>=400 votes): r = {rel:.3f}; Spearman-Brown full-length {2 * rel / (1 + rel):.3f} ==")

    # ---- method agreement table
    def rank(x):
        return np.argsort(np.argsort(x))

    H = np.where(heavy)[0]
    fam = {"MAJ acc": acc_maj, "DS J": j, "ANCHOR J": j_anchor, "GLAD alpha": alpha,
           "SDT d'": dprime, "FIT": fit}
    names = list(fam)
    print("\n== METHOD AGREEMENT (Spearman rank correlation, accounts with >=300 votes) ==")
    print("  " + " " * 12 + "".join(f"{n:>12}" for n in names))
    for a_ in names:
        print(f"  {a_:<12}" + "".join(
            f"{np.corrcoef(rank(fam[a_][H]), rank(fam[b_][H]))[0, 1]:>12.2f}" for b_ in names))

    # ---- per-account verdict matrix
    fixed = np.bincount(aidx, weights=v, minlength=n_a) / np.maximum(nv, 1)
    fixed = np.maximum(fixed, 1 - fixed)
    votes_chance = {
        "DS": jhi < 0.10,
        "ANCHOR": (j_anchor < 0.10) & (n_anchor >= 100),
        "GLAD": alpha < 0.25,
        "SDT": (dprime + 1.96 * dse < 0.6) | (fixed >= 0.97),
        "FIT": (fit < 0.10) & (n_e >= 30),
        "MAJ": acc_maj < 0.60,
    }
    n_methods = sum(x.astype(int) for x in votes_chance.values())
    print("\n== AT-CHANCE VERDICTS: how many of 6 independent families call it (>=300 votes) ==")
    tot_votes = nv[H].sum()
    for kk in range(7):
        sel = H[n_methods[H] == kk]
        print(f"  {kk} of 6: {len(sel):>4} accounts, {int(nv[sel].sum()):>8,} votes "
              f"({nv[sel].sum() / tot_votes:.1%} of heavy-account votes)")

    hdr = (f"  {'account':>10}{'votes':>8}{'recent':>8}{'DS J':>7}{'anchJ':>7}{'GLADa':>7}"
           f"{'MAJacc':>7}{'dprime':>7}{'crit':>6}{'FIT':>6}{'TIME':>6}{'RUNSz':>7}"
           f"{'one%':>6}  cap(y,n)   calls")
    def line(i):
        u = accts[i]
        c = cap.get(u, [0, 0, 0, 0])
        calls = "".join(k[0] if votes_chance[k][i] else "." for k in votes_chance)
        return (f"  {u:>10}{nv[i]:>8,}{recent.get(u, 0):>8,}{j[i]:>7.2f}{j_anchor[i]:>7.2f}"
                f"{alpha[i]:>7.2f}{acc_maj[i]:>7.2f}{dprime[i]:>7.2f}{crit[i]:>6.2f}"
                f"{fit[i]:>6.2f}{couple[i]:>6.2f}{runs_z[i]:>7.1f}{100 * fixed[i]:>5.0f}%"
                f"  y{c[1]}/{c[0]} n{c[3]}/{c[2]}  {calls}  {F.KNOWN.get(u, '')}")

    print("\n== ACCOUNTS CALLED AT CHANCE BY >=4 FAMILIES (>=300 votes), by volume ==")
    print(hdr)
    strong = sorted(H[n_methods[H] >= 4], key=lambda i: -nv[i])
    for i in strong:
        print(line(i))
    print("\n== SPLIT DECISIONS (2-3 families) -- read these individually ==")
    print(hdr)
    for i in sorted(H[(n_methods[H] >= 2) & (n_methods[H] <= 3)], key=lambda i: -nv[i])[:30]:
        print(line(i))
    print("\n== CONTROLS / KNOWN ==")
    print(hdr)
    for u in F.KNOWN:
        if u in ai:
            print(line(ai[u]))
    print("\n== BIASED BUT DISCRIMINATING (d' >= 1.5, |c| >= 0.8, >=300 votes) ==")
    print(hdr)
    for i in sorted(H[(dprime[H] >= 1.5) & (np.abs(crit[H]) >= 0.8)], key=lambda i: -nv[i])[:20]:
        print(line(i))

    # ---- OUTLIER: robust multivariate score, no hand-set thresholds
    feats = np.column_stack([j, dprime, np.abs(crit), fit, np.nan_to_num(couple, nan=1.0),
                             np.nan_to_num(runs_z, nan=0.0), fixed])
    X = feats[H]
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0) * 1.4826 + 1e-9
    Z = (X - med) / mad
    keep = np.ones(len(Z), bool)
    for _ in range(5):  # trimmed covariance (MCD-like)
        C = np.cov(Z[keep].T) + 1e-6 * np.eye(Z.shape[1])
        mu = Z[keep].mean(axis=0)
        d2 = np.einsum("ij,jk,ik->i", Z - mu, np.linalg.inv(C), Z - mu)
        keep = d2 <= np.quantile(d2, 0.75)
    order_o = np.argsort(-d2)
    print(f"\n== OUTLIER (robust Mahalanobis over {X.shape[1]} features; top 15 of {len(H)}) ==")
    print(hdr)
    for k in order_o[:15]:
        print(line(H[k]) + f"  d2={d2[k]:.0f}")

    # ---- PAIRS with a difficulty-aware null
    heavy_p = [i for i in H if nv[i] >= 1000]
    sub_votes = defaultdict(dict)
    for k in range(len(v)):
        sub_votes[sidx[k]][aidx[k]] = v[k]
    pos = {i: {} for i in heavy_p}
    hp = set(heavy_p)
    for k in range(len(v)):
        if aidx[k] in hp:
            pos[aidx[k]][sidx[k]] = v[k]
    pairs = []
    for x in range(len(heavy_p)):
        for y in range(x + 1, len(heavy_p)):
            a1, a2 = heavy_p[x], heavy_p[y]
            common = pos[a1].keys() & pos[a2].keys()
            if len(common) < 200:
                continue
            obs = e1 = e2 = var = 0.0
            for s in common:
                va, vb = pos[a1][s], pos[a2][s]
                others = [vv for aa, vv in sub_votes[s].items() if aa not in (a1, a2)]
                if len(others) < 3:
                    continue
                f1 = sum(others) / len(others)
                pa = f1 if va == 1 else 1 - f1   # a random crowd member agrees with a1
                pb = f1 if vb == 1 else 1 - f1
                obs += va == vb
                e1 += pa
                e2 += pb
                pe = max(pa, pb)
                var += pe * (1 - pe)
            if var <= 0:
                continue
            e = max(e1, e2)
            pairs.append(((obs - e) / math.sqrt(var), accts[a1], accts[a2], len(common),
                          obs / len(common), e / len(common)))
    zz = np.array([t[0] for t in pairs])
    print(f"\n== PAIRS (difficulty-aware null; {len(pairs):,} heavy pairs) z median {np.median(zz):.1f}, "
          f"95th {np.percentile(zz, 95):.1f}, 99th {np.percentile(zz, 99):.1f} ==")
    for z, u1, u2, n, o, e in sorted(pairs, reverse=True)[:12]:
        print(f"  z={z:5.1f}  {u1:>8} & {u2:<8} {n:>6,} shared  agree {o:.1%} vs {e:.1%} "
              f"(each with a random crowd member)  J {j[ai[u1]]:.2f}/{j[ai[u2]]:.2f}  "
              f"c {crit[ai[u1]]:.2f}/{crit[ai[u2]]:.2f}")

    # ---- LABELS across aggregators on retired subjects
    raw_cnt = Counter(r[F.SUBJ] for r in rows if r[F.SUBJ] in science)
    retired = np.array([raw_cnt[s] >= F.RETIRE for s in subs])
    ones = np.bincount(sidx, weights=v, minlength=n_s)
    cnt = np.bincount(sidx, minlength=n_s)
    lab_maj = np.where(ones * 2 > cnt, 1, np.where(ones * 2 < cnt, 0, -1))
    lab_ds = (lo > 0).astype(int)
    lab_glad = (q_glad > 0.5).astype(int)
    chance = np.zeros(n_a, bool)
    chance[H[n_methods[H] >= 4]] = True
    keepv = ~chance[aidx]
    o2 = np.bincount(sidx[keepv], weights=v[keepv], minlength=n_s)
    c2 = np.bincount(sidx[keepv], minlength=n_s)
    lab_clean = np.where(o2 * 2 > c2, 1, np.where(o2 * 2 < c2, 0, -1))
    # Galaxy Zoo 2 style: consistency-weighted votes, iterated three times
    wgt = np.ones(n_a)
    for _ in range(3):
        wo = np.bincount(sidx, weights=wgt[aidx] * v, minlength=n_s)
        wt = np.bincount(sidx, weights=wgt[aidx], minlength=n_s)
        frac = (wo[sidx] - wgt[aidx] * v) / np.maximum(wt[sidx] - wgt[aidx], 1e-9)
        kappa = np.where(v == 1, frac, 1 - frac)
        kap = np.bincount(aidx, weights=kappa, minlength=n_a) / np.maximum(nv, 1)
        wgt = np.minimum(1.0, (kap / 0.6) ** 8.5)
    wo = np.bincount(sidx, weights=wgt[aidx] * v, minlength=n_s)
    wt = np.bincount(sidx, weights=wgt[aidx], minlength=n_s)
    lab_gz2 = np.where(wo * 2 > wt, 1, np.where(wo * 2 < wt, 0, -1))
    labs = {"majority": lab_maj, "maj-clean": lab_clean, "GZ2-weight": lab_gz2,
            "DS": lab_ds, "GLAD": lab_glad}
    R = retired
    print(f"\n== LABELS: {int(R.sum()):,} retired science subjects; share whose label differs ==")
    ln = list(labs)
    print("  " + " " * 12 + "".join(f"{n:>12}" for n in ln))
    for a_ in ln:
        cells = []
        for b_ in ln:
            A, B = labs[a_][R], labs[b_][R]
            mm = (A >= 0) & (B >= 0)
            cells.append(f"{np.mean(A[mm] != B[mm]):>12.2%}")
        print(f"  {a_:<12}" + "".join(cells))
    ties = {k: int((x[R] < 0).sum()) for k, x in labs.items() if (x[R] < 0).any()}
    print(f"  ties (undecided) among retired: {ties}")
    print(f"  GZ2 weights: {np.mean(wgt[H] >= 0.99):.0%} of heavy accounts at full weight, "
          f"{np.mean(wgt[H] < 0.01):.1%} below 0.01")
    cv = np.bincount(sidx, weights=chance[aidx].astype(float), minlength=n_s)
    for k in (2, 3, 5):
        print(f"  retired subjects with >= {k} of their votes from at-chance accounts: "
              f"{int((cv[R] >= k).sum()):,} ({np.mean(cv[R] >= k):.1%})")

    out = F.STATE / f"triangulate_{date.today().isoformat()}.json"
    out.write_text(json.dumps({
        accts[i]: {"votes": int(nv[i]), "J": round(float(j[i]), 3),
                   "J_anchor": round(float(j_anchor[i]), 3), "glad_alpha": round(float(alpha[i]), 3),
                   "maj_acc": round(float(acc_maj[i]), 3), "dprime": round(float(dprime[i]), 2),
                   "criterion": round(float(crit[i]), 2), "fit": round(float(fit[i]), 3),
                   "time_couple": None if np.isnan(couple[i]) else round(float(couple[i]), 2),
                   "runs_z": None if np.isnan(runs_z[i]) else round(float(runs_z[i]), 1),
                   "one_answer_share": round(float(fixed[i]), 3),
                   "at_chance_calls": int(n_methods[i]),
                   "calls": [k for k in votes_chance if votes_chance[k][i]]}
        for i in H}, indent=0))
    print(f"\nper-account method matrix -> {out.relative_to(F.HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
