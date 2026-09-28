# Classification quality review — methods

How the Cluster Buster team checks that volunteer classifications carry real
information, finds automated or careless contributions, and measures what they
cost the labels. This document describes the *method*; it deliberately contains
no findings about individual volunteers (this repository is public). Dated
reviews that name accounts are kept privately.

## Why this is needed

Cluster Buster asks one yes/no question per subject: *is this clustering
good?* A binary task is the most exposed kind of crowdsourcing:

- a script needs to submit a single integer per classification;
- half of any random or fixed answer agrees with the truth by luck, so junk
  looks like a legitimate minority opinion rather than an obvious error;
- Zooniverse's default aggregation is an unweighted vote count, so every vote
  counts equally.

Two incidents shaped the method: a scripted account that submitted 25,000
constant answers in 90 minutes (July 2026), and accounts that pass attention
checks while answering science subjects at chance (August 2026).

## Data

| Source | What it gives | Tool |
|---|---|---|
| Panoptes classifications API (authenticated) | every classification with its answer, timestamps, client, session hash, front-end build, whether the images loaded | `harvest.py` → `state/raw/` |
| Zooniverse subjects export | subject → subject set (i.e. hyperparameter configuration) | downloaded to `state/` |
| Zooniverse classification export | a hashed IP per classification (not available from the API) | downloaded to `state/` |
| eras statistics API (anonymous) | daily totals | `watch.py` |

`state/` is gitignored. The raw store is harvested once and extended
incrementally; a full re-harvest of ~800k classifications takes about four
minutes with six parallel workers.

Scope: the Cluster Buster era only (from the first classification on a
Cluster Buster science subject, 2026-06-23). Attention-check subjects are
excluded from every content score.

## The layers

Evidence is ordered by how hard it is to fake.

### 1. Content: does the account's answer depend on the image?

This is the primary layer. It needs no attention checks and cannot be passed
by imitating human timing, because it asks whether the answers track the
subjects.

**Dawid–Skene consensus** (Dawid & Skene 1979). A two-coin model estimates,
jointly and iteratively, each subject's probability of being a bad clustering
and each account's *sensitivity* (says "bad" when it is bad) and
*specificity* (says "good" when it is good). Unlike a vote count, it learns
who is reliable and how each account leans, and weights accordingly. A light
Beta prior pulls accounts with few votes towards the population.

**Leave-one-out scoring.** Each account is scored against the consensus built
*without its own votes*, so a heavy contributor cannot define the truth it is
judged against.

**J = sensitivity + specificity − 1** (Youden's J; identical to the
"spammer score" of Raykar & Yu 2012). J is the information an account
carries: 0 for any strategy that ignores the image — a coin flip, always
"yes", always "no" — and positive only if the account's answers depend on the
subject. Every J comes with a 95% band.

**Signal detection** splits J into two parts that mean very different
things:

- **d′ (discrimination):** can the account tell good from bad at all?
- **c (criterion):** does it grade leniently (says "good" easily) or harshly?

A volunteer with high d′ and a strongly lenient c is careful but generous —
informative, and Dawid–Skene corrects for the lean. A volunteer with d′ ≈ 0
is not distinguishing subjects. J alone cannot tell these apart.

**BAL** (leave-one-out balanced accuracy on subjects where ≥90% of other
volunteers agree) is kept alongside for continuity with the August 2026
reviews.

#### Why not plain agreement with the majority?

Because it is fooled by the base rate. About half of the subjects are "good",
so an account answering "good" to everything agrees with the majority about
60% of the time without looking. In validation, plain majority accuracy and
the GLAD model (below) both failed to flag known fixed-answer accounts,
including the July 2026 bot. J, d′ and BAL are immune by construction.

#### Validation

On the 2026-09-28 data (764k distinct votes, 4,625 identities):

| Check | Result |
|---|---|
| Positive controls (the July bot, known fixed-answer accounts) | J = 0.00 for every one |
| Negative controls (accounts independently confirmed careful) | J 0.55–0.61, well above the median of 0.49 |
| Sensitivity to the Dawid–Skene prior (strength 2 vs 6 vs 20) | largest change in any J: 0.01; rank correlation 0.9998 |
| Split-half reliability of J (odd vs even subjects, accounts with ≥400 votes) | r = 0.98 |
| Consensus built only from trusted "anchor" accounts vs full consensus | rank correlation 0.89 |
| Agreement with GLAD ability (Whitehill et al. 2009) | 0.96 |
| Agreement with d′ | 0.91 |
| Unsupervised robust-outlier ranking over seven features, no thresholds | recovers the known bad accounts in its top 15 |

`triangulate.py` reruns every one of these.

### 2. Tiers

Each scored account (≥100 science votes) lands in exactly one tier, in this
order of precedence:

| Tier | Rule | Meaning |
|---|---|---|
| AUTOMATION | automation user agent (headless browser, scripting libraries, CLI tools), zero recorded viewing time on ≥20 rows, sub-0.5 s median over ≥500 rows, re-voting already-seen subjects on ≥20% of rows, or a superhuman sustained rate on the server's clock (≥1,500 classifications in 10 minutes) | submitted by software. Says nothing about label quality: one scripted account in this project gives good labels |
| FIXED | ≥97% one answer | answers do not depend on the subject |
| AT CHANCE | upper 95% bound of J < 0.10 **and** upper 95% bound of d′ < 0.8 | two independent models agree it cannot tell good from bad |
| LOW INFO | J < 0.25 | some information, well below typical |
| BIASED | d′ ≥ 1 and \|c\| ≥ 0.8 | informative but grades far more leniently or harshly than the crowd |
| OK | otherwise | |

Thresholds were set against the validation controls above. The at-chance rule
deliberately requires two models so that one model's quirk cannot convict an
account.

### 3. Drift

Lifetime scores lag. Weekly J and the weekly share of "good" answers are
tracked for every heavy account; a volunteer whose standard or attention
changes over weeks shows up here before the lifetime number moves.

### 4. Attention checks ("captchas")

200 synthetic subjects instruct the answer. They are scored **separately by
polarity**: an account that always answers "good" passes every "good" card and
fails every "bad" one. A single pooled pass rate hides that. Failure *rates*
are tested against the population rate, so a heavy account with a few misclicks
is not flagged.

What captchas can and cannot establish:

- A failure shows that a card was not read. A pass does **not** show that
  science subjects are read: gold questions that look different from real
  work can be recognised and handled separately — a documented attack on
  crowdsourcing quality control (Checco, Bates & Demartini 2020). Several
  accounts here pass every card while answering science subjects at chance.
- The first card design (v1) failed careful volunteers: its "answer NO" cards
  showed a clustering that looked correct, so people doing the real task
  answered "yes". Validate a card design by checking that failure rates do
  not *rise* with time spent per subject.
- Exposure is not uniform: the iOS app serves cards at about a quarter of the
  web rate, and at least one app installation has been served essentially
  none. The checker reports accounts served far fewer cards than their client
  predicts.

Captchas are therefore an **inattention** check, not an automation check, and
a secondary layer behind content scoring.

### 5. Client and behaviour

Cheap signals that catch lazy automation: automation markers in the user
agent, zero or sub-second viewing times, re-voting subjects the designator
would not re-serve, unusually regular gaps between submissions, front-end
builds nobody else runs. They catch careless scripts only — every metadata
field is set by the client and a careful script can fake all of them — which
is why they are corroborating evidence, not the verdict.

**Speed is measured on the server's clock.** The viewing time a classification
reports (`finished_at − started_at`) is set by the client, so a script can claim
four seconds. The time the server *received* each classification cannot be
faked, so the review also reports, per account:

- peak classifications in any minute, 10 minutes and hour. The superhuman line
  is 1,500 in 10 minutes (2.5 per second sustained); on 2026-09-28 the fastest
  human peak was 658 and the July 2026 bot's was 4,456;
- claimed viewing times longer than the time that actually passed since the
  previous submission (impossible for one window);
- viewing windows that overlap another browser session's — several windows
  worked side by side, which no one can do while actually judging each image.

### 6. Linked accounts

Question: is anyone running several accounts?

**Timing is the primary evidence** (`linkage.py`). One operator with two
accounts produces *handoffs* (one account stops, the other starts within
minutes, repeatedly) and *mutual exclusivity* (never active in the same five
minutes despite being active on the same days). Both are compared with a null
that shifts one account's timeline by whole days, which preserves each
account's own daily rhythm, so two people who both classify on weekday evenings
do not look linked. A class or household shows the opposite: high co-activity,
no handoffs.

**IP addresses and device fingerprints are corroboration only.** VPN exit
nodes, school networks and mobile carriers put unrelated people behind one
address; managed school devices share identical fingerprints. A shared IP or
device, without a timing signature, is read as "same place", not "same person".

### 7. Impact on the labels

The question that matters for the science is what any of this does to the
training labels. The review reports:

- how many retired labels differ between plain majority vote and
  Dawid–Skene, and in which direction;
- how many flip when AUTOMATION / FIXED / AT CHANCE votes are removed;
- how disagreement between the two scales with the number of strongly lenient
  heavy contributors on each subject.

Two structural facts make this important for this project. Heavy contributors
have classified a large fraction of *all* subjects, so the "15 independent
verdicts" behind each retirement are not independent: the same few accounts
recur on most subjects. And a label that changes depending on *which*
volunteers happened to see a subject reflects voter composition rather than
the image. Model-based aggregation removes that dependence; this is the reason
to prefer it over a raw vote count for the training set.

## Limitations

- **Consensus is not ground truth.** All content scores measure information
  relative to the crowd. An account better than the crowd would score lower.
  There are no expert or gold-standard labels on this workflow.
- **Disagreement is not spam.** Filtering annotators who disagree erodes
  legitimate label variation; conservative removal (a few percent of
  annotators) is recommended (arXiv:2509.08217), and the same work finds that
  real spammers mostly give *fixed* answers, which matches what is seen here.
  Strict or lenient volunteers belong in the BIASED tier and are corrected by
  weighting, not removed.
- **These are volunteers.** Most low-information accounts are people who
  misunderstood the task, lost attention, or were set a classroom assignment.
  The appropriate response is usually better guidance and down-weighting,
  not exclusion or public judgement.

## How this compares with other Zooniverse projects

| Project | Approach |
|---|---|
| Galaxy Zoo 2 (Willett et al. 2013) | iterative consistency weighting, w = min(1, (κ/0.6)^8.5); about 1% of volunteers end near zero weight |
| Galaxy Zoo DECaLS (Walmsley et al. 2022) | weighting mainly removes volunteers who used a shortcut answer to skip through subjects — the fixed-answer pattern |
| Space Warps (Marshall et al. 2016) | a Bayesian agent per volunteer with a 2×2 confusion matrix trained on known subjects |
| Gravity Spy (Zevin et al. 2017) | confusion matrices from gold-standard subjects; volunteers promoted by skill |
| Cluster Buster (this) | unsupervised Dawid–Skene confusion matrices (no gold set exists), content scores leave-one-out, attention checks as a secondary layer |

Galaxy Zoo 2–style weighting is computed in `triangulate.py` for comparison.

## Running a review

```bash
source ~/.zooniverse_env
PY=~/Desktop/projects/arm_grouping/.venv/bin/python
$PY harvest.py            # fetch new classifications (seconds; --full rebuilds)
$PY forensics.py          # tiers, drift, captchas, links, impact -> state/forensics_<date>.json
$PY linkage.py            # timing-based account linkage        -> state/linkage_<date>.json
$PY triangulate.py        # method cross-validation             -> state/triangulate_<date>.json
$PY watch.py              # daily-count spike check (no credentials)
$PY captcha_check.py      # attention-check tripwire
```

Refresh the subjects and classification exports from the project Lab before a
review if new subject sets were added or IP corroboration is needed.
Suggested cadence: `watch.py` daily, the full review every two weeks.

## References

- Checco, A., Bates, J. & Demartini, G. (2020). Adversarial attacks on crowdsourcing quality control. *JAIR* 67, 375–408.
- Dawid, A. P. & Skene, A. M. (1979). Maximum likelihood estimation of observer error-rates using the EM algorithm. *Applied Statistics* 28, 20–28.
- Drasgow, F., Levine, M. V. & Williams, E. A. (1985). Appropriateness measurement with polychotomous item response models and standardized indices. *Br. J. Math. Stat. Psychol.* 38, 67–86.
- Hovy, D., Berg-Kirkpatrick, T., Vaswani, A. & Hovy, E. (2013). Learning whom to trust with MACE. *NAACL*.
- Marshall, P. J. et al. (2016). Space Warps I: crowdsourcing the discovery of gravitational lenses. *MNRAS* 455, 1171.
- Meade, A. W. & Craig, S. B. (2012). Identifying careless responses in survey data. *Psychological Methods* 17, 437–455.
- Raykar, V. C. & Yu, S. (2012). Eliminating spammers and ranking annotators for crowdsourced labeling tasks. *JMLR* 13, 491–518.
- Walmsley, M. et al. (2022). Galaxy Zoo DECaLS. *MNRAS* 509, 3966.
- Whitehill, J. et al. (2009). Whose vote should count more. *NIPS*.
- Willett, K. W. et al. (2013). Galaxy Zoo 2. *MNRAS* 435, 2835.
- Zevin, M. et al. (2017). Gravity Spy. *CQG* 34, 064003.
- *Balancing quality and variation: spam filtering distorts data label distributions* (2025). arXiv:2509.08217.
