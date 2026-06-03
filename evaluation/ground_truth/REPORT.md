# RuleForge — Rule Detection Accuracy (Hand-Labelled Benchmark)

- Benchmark programs: **5**
- Labelled rules (ground truth): **10**
- Detected rules: **13**

## Headline

| Metric | Value |
|--------|-------|
| Precision | **76.9%** |
| Recall | **100.0%** |
| F1 | **87.0%** |
| True positives | 10 |
| False positives | 3 |
| False negatives | 0 |

Matching unit: `(paragraph, rule_type)`. See `ground_truth.py` for method.

## Per-program

| Program | TP | FP | FN |
|---------|----|----|----|
| compute_finance | 3 | 0 | 0 |
| evaluate_account | 1 | 0 | 0 |
| infra_only | 0 | 0 | 0 |
| overdraft_check | 5 | 2 | 0 |
| simple_if | 1 | 1 | 0 |

## Error analysis

**False positives (detected, not a real rule):**
- `overdraft_check` → CALCULATE-BALANCE:validation
- `overdraft_check` → CHECK-WITHDRAWAL:conditional
- `simple_if` → CALCULATE-DISCOUNT:validation
