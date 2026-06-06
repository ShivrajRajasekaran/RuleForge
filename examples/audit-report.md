# RuleForge — Sample Audit Report

This is **real, reproducible output** from RuleForge's two formal-analysis tools,
run on the sample programs committed in this repo. Every command below works
straight after `git clone` — no Ollama, no external corpus, no setup beyond
`pip install -r requirements.txt`.

> Reproduce everything in this file:
> ```bash
> python -m src.analysis.conflict_detector data/conflict_samples/rate_conflict.cbl
> python -m src.analysis.conflict_detector data/conflict_samples/rate_noconflict.cbl
> python -m src.analysis.completeness     data/completeness_samples/incomplete_if.cbl
> python -m src.analysis.completeness     data/completeness_samples/incomplete_eval.cbl
> python -m src.analysis.completeness     data/completeness_samples/complete_eval.cbl
> ```

---

## 1. Rule Conflict Detection

RuleForge flags pairs of business rules whose conditions **provably overlap** but
whose **outcomes differ** — a latent contradiction that would otherwise stay
buried until production behaves unexpectedly.

### 1a. A planted conflict — `rate_conflict.cbl`

Two rules both fire for a savings account with a balance over 5000, yet one
applies the *premium* rate and the other the *standard* rate.

```
======================================================================
  RULEFORGE - RULE CONFLICT DETECTOR
======================================================================
  Program          : RATECONF
  Rules considered : 2
  Rules modeled    : 2 (others use OR / nesting / computed conditions - skipped)
  Conflicts found  : 1
======================================================================

  [1] CONFLICT in APPLY-PREMIUM/APPLY-STANDARD on {WS-ACCT-BALANCE, WS-ACCT-TYPE}:
      overlapping conditions but different actions
      PERFORM APPLY-PREMIUM-RATE vs PERFORM APPLY-STANDARD-RATE
    A: IF WS-ACCT-TYPE = 'SAV' AND WS-ACCT-BALANCE > 5000
    B: IF WS-ACCT-TYPE = 'SAV' AND WS-ACCT-BALANCE > 1000
======================================================================
```

The proof: `balance > 5000` and `balance > 1000` have a non-empty intersection
(`balance > 5000`), and on that overlap the two rules perform different actions.

### 1b. A clean negative control — `rate_noconflict.cbl`

Same shape, but the guards are mutually exclusive (`balance > 5000` vs
`balance < 1000`), so there is **no** overlap and **no** false alarm.

```
======================================================================
  RULEFORGE - RULE CONFLICT DETECTOR
======================================================================
  Program          : RATEOK
  Rules considered : 2
  Rules modeled    : 2
  Conflicts found  : 0
======================================================================

  No provable rule conflicts detected.
======================================================================
```

> **Design choice — precision over recall.** The detector only reports a conflict
> it can mathematically prove. Rules using `OR`, nesting, computed values, or
> variable-to-variable comparisons are reported as *undetermined* and skipped
> rather than guessed. "No provable conflict" therefore means *"none we can
> prove"*, **not** *"guaranteed none"*.

---

## 2. Decision-Table Completeness Scoring

For every decision table, RuleForge checks whether the inputs are **fully
covered** — i.e. whether there is an input combination with **no defined
behaviour**. It enumerates the `2^N` condition combinations for boolean tables,
and checks for a catch-all (`WHEN OTHER` / `ELSE`) on value tables.

### 2a. An `IF` with no `ELSE` — `incomplete_if.cbl` (HIGH RISK)

```
======================================================================
  RULEFORGE - DECISION TABLE COMPLETENESS
======================================================================
  Program          : INCMPIF
  Tables scored    : 1
  Complete         : 0
  Incomplete       : 1
  Mean coverage    : 50% (boolean tables)
======================================================================

  CHECK-LIMIT [IF-ELSE] - incomplete, coverage 50%  <-- HIGH RISK
    note: condition independence assumed - verify flagged combinations are reachable
    UNDEFINED: WS-ACCT-BALANCE > WS-CREDIT-LIMIT = N
======================================================================
```

When the balance is **not** over the credit limit, the program does nothing —
an undefined branch the original author may never have intended.

### 2b. An `EVALUATE` with no catch-all — `incomplete_eval.cbl`

```
  SET-RATE [EVALUATE] - incomplete, coverage n/a
    note: open domain on WS-ACCT-TYPE; 3 explicit value(s) and NO catch-all
          - other values are undefined
    UNDEFINED: WS-ACCT-TYPE = <any other value>
```

### 2c. A complete table — `complete_eval.cbl`

```
  SET-RATE [EVALUATE] - complete, coverage n/a
    note: open domain on WS-ACCT-TYPE; 2 explicit value(s)
```

> **Honest limitation.** The scorer assumes condition independence, so it can
> flag combinations that are unreachable in practice — it **over-reports, never
> under-reports**. Treat each flag as *"verify this"*, not *"definitely a bug"*.

---

## 3. At corpus scale (AWS CardDemo)

Run across the full AWS Mainframe Modernization **CardDemo** corpus
(44 programs, 531 detected rules, 426 decision tables):

| Metric | Result |
|---|---|
| Rule conflicts (provable) | 0 — the corpus is internally consistent on the modelable subset |
| Rules modelable by the conflict detector | ~40 / 531 (rest use OR / nesting / computed conditions) |
| Decision tables flagged incomplete | 201 / 426 (**47%**) |
| High-risk tables (coverage < 80%) | 153 |
| Mean boolean-table coverage | ~78% |

These corpus numbers depend on downloading CardDemo (see the README Quick Start);
the per-file samples above are self-contained and reproducible on a fresh clone.
