# RuleForge

**AI-Powered Business Rule Extraction from Legacy COBOL Programs**

## What It Does

RuleForge automatically extracts business rules from undocumented COBOL programs, converts them into formal decision tables, and generates natural language specifications using locally-deployed LLMs.

## Current Status

| Module | Status |
|--------|--------|
| COBOL Parser (AST) | Working — parses IBM fixed & free format (44/44 files) |
| Rule Detector | Working — 531 rules across corpus (overlapping duplicates collapsed) |
| Decision Table Generator | Working — 426 tables generated |
| LLM NL Generator | Working — Ollama/Mistral + anti-hallucination validation |
| Export Engine | Working — JSON, DMN 1.3, Markdown, CSV, HTML (44/44 files) |
| Web Dashboard | Working — Streamlit UI (upload, rules, tables, audit: conflicts + completeness, AI docs, export) |
| Evaluation Framework | Working — corpus metrics + grounding report (44 programs, 531 rules, 100% PROGRAM-ID) |
| Accuracy Benchmark | Working — hand-labelled precision/recall (P 90%, R 90%, F1 90% on 5 programs) |
| Rule Conflict Detector | Working — proves overlapping guards with different outcomes (interval/equality reasoning, stdlib-only) |
| Completeness Scorer | Working — enumerates condition combinations, flags decision tables with undefined inputs (47% of corpus tables incomplete) |
| Test Suite | Working — 90 pytest tests, ~62% coverage |

## Quick Start

```bash
# Clone
git clone https://github.com/ShivrajRajasekaran/RuleForge.git
cd RuleForge

# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Download test data
git clone https://github.com/aws-samples/aws-mainframe-modernization-carddemo data/cobol_corpus/aws_card_demo

# Run the pipeline (each module is runnable standalone)
python -m src.parser.cobol_parser <file.cbl>          # Parse → AST
python -m src.extraction.rule_detector <file.cbl>     # Detect business rules
python -m src.extraction.decision_table <file.cbl>    # Build decision tables

# Generate plain-English docs with a local LLM (needs Ollama running)
ollama pull mistral
python -m src.generation.llm_client                   # Health check
python -m src.generation.nl_generator <file.cbl> 3    # Document top 3 rules

# Export everything (JSON, DMN, Markdown, CSV, HTML) → exports/
python -m src.export.export_engine <file.cbl>             # without LLM (fast)
python -m src.export.export_engine <file.cbl> --with-llm 3 # include LLM docs

# Launch the web dashboard (browser UI for the whole pipeline)
streamlit run src/dashboard/app.py

# Evaluate the whole corpus → evaluation/REPORT.md + summary.json + per_file.csv
python -m src.analysis.evaluator                  # metrics only (fast)
python -m src.analysis.evaluator --llm-sample 3   # + grounding sample (slow)

# Measure detection accuracy against the hand-labelled benchmark
# → evaluation/ground_truth/REPORT.md (precision / recall / F1)
python -m src.analysis.ground_truth

# Detect contradictory business rules (overlapping conditions, different outcomes)
python -m src.analysis.conflict_detector data/conflict_samples/rate_conflict.cbl   # 1 conflict
python -m src.analysis.conflict_detector data/conflict_samples/rate_noconflict.cbl # 0 (control)

# Score decision-table completeness (flag inputs with undefined behaviour)
python -m src.analysis.completeness data/completeness_samples/incomplete_if.cbl    # 50%, HIGH RISK
python -m src.analysis.completeness data/completeness_samples/complete_eval.cbl    # complete

# Run the test suite
pytest                       # 64 tests, no Ollama/corpus needed (all mocked)
pytest --cov=src             # with coverage report
```

## Tech Stack

Python 3.11+ (stdlib-only core: regex COBOL parser + `urllib`-based LLM client, no heavy deps) | Ollama (Mistral 7B, local) | Streamlit + pandas (dashboard) | pytest (tests)

## The Problem

- 800 billion lines of COBOL in production globally
- 70% has NO documentation
- 75% of COBOL programmers retiring by 2030
- Business rules buried in nested IF-ELSE chains are being permanently lost

## Architecture

```
COBOL Source → Parser → AST → Rule Detector → Decision Tables
                                     ↓
                              Context Builder → LLM → NL Description
                                     ↓
                              Validator → Export (DMN 1.3 / JSON / CSV / Markdown / HTML)
```

## License

MIT
