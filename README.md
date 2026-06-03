# RuleForge

**AI-Powered Business Rule Extraction from Legacy COBOL Programs**

## What It Does

RuleForge automatically extracts business rules from undocumented COBOL programs, converts them into formal decision tables, and generates natural language specifications using locally-deployed LLMs.

## Current Status

| Module | Status |
|--------|--------|
| COBOL Parser (AST) | Working — parses IBM fixed & free format (44/44 files) |
| Rule Detector | Working — 712 rules across corpus |
| Decision Table Generator | Working — 503 tables generated |
| LLM NL Generator | Working — Ollama/Mistral + anti-hallucination validation |
| Export Engine | Working — JSON, DMN 1.3, Markdown, CSV, HTML (44/44 files) |
| Web Dashboard | Working — Streamlit UI (upload, rules, tables, AI docs, export) |
| Evaluation Framework | Working — corpus metrics + grounding report (44 programs, 712 rules, 100% PROGRAM-ID) |
| Test Suite | Working — 58 pytest tests, 62% coverage |

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

# Run the test suite
pytest                       # 58 tests, no Ollama/corpus needed (all mocked)
pytest --cov=src             # with coverage report
```

## Tech Stack

Python 3.11+ | tree-sitter (planned) | Ollama (Mistral 7B) | LangChain | FastAPI | Streamlit | SQLite | NetworkX

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
                              Validator → Export (DMN/JSON/Excel/PDF)
```

## License

MIT
