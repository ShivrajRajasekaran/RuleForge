# RuleForge — Rule Detection Accuracy (Hand-Labelled Benchmark)

- Benchmark programs: **5**
- Labelled rules (ground truth): **10**
- Detected rules: **10**

## Headline

| Metric | Value |
|--------|-------|
| Precision | **90.0%** |
| Recall | **90.0%** |
| F1 | **90.0%** |
| True positives | 9 |
| False positives | 1 |
| False negatives | 1 |

Matching unit: `(paragraph, rule_type)`. See `ground_truth.py` for method.

## Per-program

| Program | TP | FP | FN |
|---------|----|----|----|
| compute_finance | 3 | 0 | 0 |
| evaluate_account | 1 | 0 | 0 |
| infra_only | 0 | 0 | 0 |
| overdraft_check | 4 | 1 | 1 |
| simple_if | 1 | 0 | 0 |

## Error analysis

**False positives (detected, not a real rule):**
- `overdraft_check` → CHECK-WITHDRAWAL:conditional

**False negatives (real rule, missed):**
- `overdraft_check` → CHECK-WITHDRAWAL:validation
