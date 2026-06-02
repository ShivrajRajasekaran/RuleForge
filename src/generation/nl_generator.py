"""Natural-Language Generator — Module 5b of RuleForge.

Turns the *structured* output of the earlier modules (DetectedRule +
DecisionTable) into plain-English business documentation a non-programmer
analyst can read, using a locally-deployed LLM (Ollama / Mistral).

The hard part is NOT calling the LLM — it is trusting it. LLMs hallucinate.
For documentation of banking rules that is unacceptable. So every generated
description passes through an anti-hallucination validator that cross-checks
the variable / paragraph names the model mentions against the real COBOL AST.
Anything the model invented is flagged, lowering the confidence of the output.

Pipeline position:
    Parser → RuleDetector → DecisionTable → [THIS MODULE] → Export

Run:
    python -m src.generation.nl_generator <file.cbl>
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from src.parser.cobol_parser import CobolProgram, DataItem
from src.extraction.rule_detector import DetectedRule, RuleType
from src.extraction.decision_table import DecisionTable
from src.generation.llm_client import LLMClient


# ═══════════════════════════════════════════════════
# PROMPT TEMPLATES
# ═══════════════════════════════════════════════════
SYSTEM_PROMPT = (
    "You are a senior business analyst documenting legacy COBOL banking "
    "software for modernization. You explain code logic in plain business "
    "English. You ONLY describe what the provided code actually does. You "
    "NEVER invent variables, values, or behavior that is not in the code. "
    "If something is unclear, you say so rather than guessing."
)

RULE_PROMPT = """Below is a business rule extracted from a COBOL program.

Program     : {program}
Paragraph   : {paragraph}
Rule type   : {rule_type}
Business area: {domain}
Variables used: {variables}

Variable meanings (from the program's data definitions):
{variable_glossary}

COBOL source:
```
{source_code}
```

Write a clear, plain-English description of this business rule in 2-4
sentences. Explain WHAT condition is checked and WHAT happens as a result.
Use the business meaning of the variables, not the raw COBOL names where
possible. Do NOT mention any variable that is not listed above. Do NOT invent
numbers. Output only the description, no preamble."""

TABLE_PROMPT = """Below is a decision table extracted from a COBOL program,
representing the branching logic of paragraph "{paragraph}".

{table_text}

Variable meanings:
{variable_glossary}

Write a short plain-English summary (2-3 sentences) of the decision logic this
table represents: what is being decided, and how the outcome depends on the
conditions. Do NOT invent conditions or outcomes beyond those in the table.
Output only the summary."""


# ═══════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════
@dataclass
class GeneratedDescription:
    """A natural-language description plus its validation metadata."""
    paragraph_name: str
    rule_type: str
    domain: str
    description: str
    source_confidence: float           # confidence of the underlying rule
    grounding_score: float = 1.0       # fraction of mentioned entities that are real
    hallucinated_terms: List[str] = field(default_factory=list)
    llm_seconds: float = 0.0
    success: bool = True
    error: str = ""

    @property
    def trustworthy(self) -> bool:
        """A description we are willing to ship without human review."""
        return self.success and self.grounding_score >= 0.8


# ═══════════════════════════════════════════════════
# GENERATOR
# ═══════════════════════════════════════════════════
class NLGenerator:
    """Generate validated natural-language docs for detected rules."""

    # COBOL keywords / common English words we must NOT treat as "invented
    # variables" when scanning the LLM output for hallucinations.
    _STOPWORDS = {
        "IF", "THEN", "ELSE", "END", "MOVE", "TO", "FROM", "PERFORM",
        "EVALUATE", "WHEN", "OTHER", "SET", "TRUE", "FALSE", "COMPUTE",
        "ADD", "SUBTRACT", "AND", "OR", "NOT", "THE", "AND/OR", "VALUE",
        "STATUS", "RULE", "RULES", "COBOL", "PROGRAM", "PARAGRAPH", "TABLE",
        "YES", "NO", "ZERO", "ZEROS", "SPACES", "NUMERIC",
    }

    def __init__(self, program: CobolProgram, client: Optional[LLMClient] = None):
        self.program = program
        self.client = client or LLMClient()
        # Map of UPPER variable name → DataItem, for glossary + validation.
        self.data_index: Dict[str, DataItem] = {
            d.name.upper(): d for d in program.data_items
        }
        self.paragraph_names = {p.name.upper() for p in program.paragraphs}
        self.valid_names = set(self.data_index.keys()) | self.paragraph_names

    # ─────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────
    def describe_rule(self, rule: DetectedRule) -> GeneratedDescription:
        """Generate and validate an NL description for one detected rule."""
        glossary = self._build_glossary(rule.variables_involved)
        prompt = RULE_PROMPT.format(
            program=self.program.name,
            paragraph=rule.paragraph_name,
            rule_type=rule.rule_type.value,
            domain=rule.domain.value,
            variables=", ".join(rule.variables_involved[:12]) or "(none identified)",
            variable_glossary=glossary,
            source_code=rule.source_code.strip()[:1500],
        )

        resp = self.client.generate(prompt, system=SYSTEM_PROMPT)

        if not resp.success:
            return GeneratedDescription(
                paragraph_name=rule.paragraph_name,
                rule_type=rule.rule_type.value,
                domain=rule.domain.value,
                description="",
                source_confidence=rule.confidence,
                success=False,
                error=resp.error,
            )

        grounding, invented = self._validate_grounding(
            resp.text, rule.variables_involved
        )

        return GeneratedDescription(
            paragraph_name=rule.paragraph_name,
            rule_type=rule.rule_type.value,
            domain=rule.domain.value,
            description=resp.text,
            source_confidence=rule.confidence,
            grounding_score=grounding,
            hallucinated_terms=invented,
            llm_seconds=resp.elapsed_seconds,
        )

    def describe_table(self, table: DecisionTable) -> GeneratedDescription:
        """Generate an NL summary for a decision table."""
        rule = table.source_rule
        vars_involved = rule.variables_involved if rule else []
        glossary = self._build_glossary(vars_involved)
        prompt = TABLE_PROMPT.format(
            paragraph=rule.paragraph_name if rule else "(unknown)",
            table_text=table.to_text(),
            variable_glossary=glossary,
        )

        resp = self.client.generate(prompt, system=SYSTEM_PROMPT)
        para = rule.paragraph_name if rule else "(unknown)"

        if not resp.success:
            return GeneratedDescription(
                paragraph_name=para,
                rule_type="decision-table",
                domain=rule.domain.value if rule else "UNKNOWN",
                description="",
                source_confidence=rule.confidence if rule else 0.0,
                success=False,
                error=resp.error,
            )

        grounding, invented = self._validate_grounding(resp.text, vars_involved)
        return GeneratedDescription(
            paragraph_name=para,
            rule_type="decision-table",
            domain=rule.domain.value if rule else "UNKNOWN",
            description=resp.text,
            source_confidence=rule.confidence if rule else 0.0,
            grounding_score=grounding,
            hallucinated_terms=invented,
            llm_seconds=resp.elapsed_seconds,
        )

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────
    def _build_glossary(self, variables: List[str]) -> str:
        """Build a 'NAME → PIC/VALUE hints' glossary for the prompt.

        Giving the model real data definitions both improves quality and
        anchors it to genuine names (reducing hallucination at the source).
        """
        lines = []
        for var in variables[:12]:
            item = self.data_index.get(var.upper())
            if not item:
                continue
            hint_parts = []
            if item.pic_clause:
                hint_parts.append(f"PIC {item.pic_clause}")
            if item.value_clause:
                hint_parts.append(f"VALUE {item.value_clause}")
            if item.is_88_level:
                hint_parts.append("(condition-name)")
            hint = ", ".join(hint_parts) if hint_parts else "(no PIC info)"
            lines.append(f"  - {item.name}: {hint}")
        return "\n".join(lines) if lines else "  (no data definitions found)"

    def _validate_grounding(self, text: str, expected_vars: List[str]) -> tuple:
        """Anti-hallucination check.

        Scan the LLM output for COBOL-style identifiers (UPPER-CASE-WITH-
        HYPHENS or words containing a hyphen). Any such token that is NOT a
        real variable/paragraph in the program is treated as potentially
        invented. Returns (grounding_score, invented_terms).

        grounding_score = real_mentions / total_mentions  (1.0 if no mentions).
        """
        # Candidate identifiers: 3+ char tokens, ALL CAPS or containing a hyphen.
        candidates = set(re.findall(r"\b[A-Z][A-Z0-9]{2,}(?:-[A-Z0-9]+)*\b", text))
        # Also catch lowercase hyphenated names the model may echo.
        candidates |= set(re.findall(r"\b[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9-]+\b", text))

        real, invented = [], []
        for token in candidates:
            tok_upper = token.upper()
            if tok_upper in self._STOPWORDS:
                continue
            # Only judge tokens that "look like" COBOL data names: either they
            # contain a hyphen, or they were among the expected variables.
            looks_like_cobol = "-" in token or tok_upper in {
                v.upper() for v in expected_vars
            }
            if not looks_like_cobol:
                continue
            if tok_upper in self.valid_names:
                real.append(tok_upper)
            else:
                invented.append(token)

        total = len(real) + len(invented)
        if total == 0:
            return 1.0, []
        return len(real) / total, sorted(set(invented))


def _wrap(text: str, width: int):
    """Tiny word-wrapper for terminal display."""
    import textwrap
    out = []
    for paragraph in text.split("\n"):
        out.extend(textwrap.wrap(paragraph, width) or [""])
    return out


# ═══════════════════════════════════════════════════
# RUN DIRECTLY TO TEST
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from src.parser.cobol_parser import CobolParser
    from src.extraction.rule_detector import RuleDetector
    from src.extraction.decision_table import DecisionTableGenerator

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        default = Path(
            "data/cobol_corpus/aws_card_demo/app/"
            "app-transaction-type-db2/cbl/COBTUPDT.cbl"
        )
        file_path = default

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        print("Usage: python -m src.generation.nl_generator <file.cbl>")
        sys.exit(1)

    # How many rules to document (LLM inference on CPU is slow ~1min/call).
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    # ── Pipeline: Parse → Detect → (Tables) → Describe ──
    parser = CobolParser()
    program = parser.parse_file(file_path)

    detector = RuleDetector(program)
    rules = detector.detect_all_rules()

    generator = NLGenerator(program)

    print("=" * 70)
    print("  RULEFORGE — NATURAL LANGUAGE GENERATOR v0.1")
    print("=" * 70)
    print(f"  Program   : {program.name}")
    print(f"  Rules      : {len(rules)}")
    print(f"  LLM model  : {generator.client.model}")
    print(f"  LLM online : {generator.client.is_available()}")
    print("=" * 70)

    if not generator.client.is_available():
        print("\n  Ollama is not running — start it and retry.")
        sys.exit(1)

    # Pick the highest-confidence rules first.
    rules_sorted = sorted(rules, key=lambda r: r.confidence, reverse=True)
    to_do = rules_sorted[:limit]
    print(f"\n  Documenting top {len(to_do)} rules (by confidence)...\n")

    for i, rule in enumerate(to_do, 1):
        print(f"  [{i}/{len(to_do)}] {rule.paragraph_name} "
              f"({rule.rule_type.value}, conf={rule.confidence:.2f})")
        result = generator.describe_rule(rule)
        if not result.success:
            print(f"      FAILED: {result.error}\n")
            continue
        print(f"      Grounding : {result.grounding_score:.0%} "
              f"({'TRUSTWORTHY' if result.trustworthy else 'NEEDS REVIEW'}, "
              f"{result.llm_seconds:.0f}s)")
        if result.hallucinated_terms:
            print(f"      Flagged   : {', '.join(result.hallucinated_terms)}")
        print(f"      Description:")
        for line in _wrap(result.description, 60):
            print(f"        {line}")
        print()

    print("=" * 70)
    print("  GENERATION COMPLETE")
    print("=" * 70)
