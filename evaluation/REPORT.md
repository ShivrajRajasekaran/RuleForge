# RuleForge — Evaluation Report

*Generated 2026-06-03 10:36 over `data\cobol_corpus`*

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
| Total rules detected | 712 |
| Rules per program (mean) | 16.2 |
| Rules per program (median) | 10.5 |
| Rules per program (max) | 80 |
| Mean rule confidence | 0.63 |

### Rules by type

| Type | Count | Share |
|------|-------|-------|
| conditional | 560 | 78.7% |
| computational | 114 | 16.0% |
| validation | 38 | 5.3% |

### Rules by business domain

| Domain | Count | Share |
|--------|-------|-------|
| UNKNOWN | 332 | 46.6% |
| ELIGIBILITY | 113 | 15.9% |
| CALCULATION | 108 | 15.2% |
| VALIDATION | 103 | 14.5% |
| ROUTING | 50 | 7.0% |
| COMPLIANCE | 4 | 0.6% |
| PRICING | 2 | 0.3% |

## 3. Decision Tables

| Metric | Value |
|--------|-------|
| Tables generated | 528 |
| Complete (cover ELSE/OTHER) | 320 (60.6%) |

## Interpretation

RuleForge parsed **100%** of a real-world COBOL banking corpus (44 programs, 30,175 LOC) and extracted **712 business rules**, generating **528 formal decision tables** of which 61% are logically complete. All processing is local and dependency-free.
