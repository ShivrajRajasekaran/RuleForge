# RuleForge — Evaluation Report

*Generated 2026-06-03 11:08 over `data\cobol_corpus`*

## 1. Corpus Coverage

| Metric | Value |
|--------|-------|
| COBOL files found | 44 |
| Parsed without error | 44 (100.0%) |
| PROGRAM-ID detected | 44 (100.0%) |
| Fixed-format programs | 10 |
| Free-format programs | 34 |
| Total lines of COBOL | 30,175 |

## 2. Business Rule Extraction

| Metric | Value |
|--------|-------|
| Total rules detected | 531 |
| Rules per program (mean) | 12.1 |
| Rules per program (median) | 8.0 |
| Rules per program (max) | 66 |
| Mean rule confidence | 0.65 |

### Rules by type

| Type | Count | Share |
|------|-------|-------|
| conditional | 458 | 86.3% |
| computational | 66 | 12.4% |
| validation | 7 | 1.3% |

### Rules by business domain

| Domain | Count | Share |
|--------|-------|-------|
| UNKNOWN | 252 | 47.5% |
| ELIGIBILITY | 80 | 15.1% |
| CALCULATION | 76 | 14.3% |
| VALIDATION | 75 | 14.1% |
| ROUTING | 43 | 8.1% |
| COMPLIANCE | 3 | 0.6% |
| PRICING | 2 | 0.4% |

## 3. Decision Tables

| Metric | Value |
|--------|-------|
| Tables generated | 426 |
| Complete (cover ELSE/OTHER) | 276 (64.8%) |

## Interpretation

RuleForge parsed **100%** of a real-world COBOL banking corpus (44 programs, 30,175 LOC) and extracted **531 business rules**, generating **426 formal decision tables** of which 65% are logically complete. All processing is local and dependency-free.
