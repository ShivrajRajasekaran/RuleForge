# RuleForge

**AI-Powered Business Rule Extraction from Legacy COBOL Programs**

## What It Does

RuleForge automatically extracts business rules from undocumented COBOL programs, converts them into formal decision tables, and generates natural language specifications using locally-deployed LLMs.

## Current Status

| Module | Status |
|--------|--------|
| COBOL Parser (AST) | Working — parses IBM fixed & free format |
| Rule Detector | In Progress |
| Decision Table Generator | Planned |
| LLM NL Generator | Planned |
| Export Engine (DMN/JSON/PDF) | Planned |
| Web Dashboard | Planned |

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

# Run parser
python src/parser/cobol_parser.py  # Demo mode
python src/parser/cobol_parser.py data/cobol_corpus/aws_card_demo/app/app-vsam-mq/cbl/COACCT01.cbl
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
