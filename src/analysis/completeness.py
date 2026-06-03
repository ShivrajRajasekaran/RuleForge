"""Decision-Table Completeness Scorer — RuleForge analysis module.

A decision table is *complete* when every possible combination of its input
conditions maps to at least one defined outcome. Gaps mean the COBOL program
has input situations with undefined business behaviour — a real audit/compliance
risk. Completeness checking is a classic formal-methods technique (Hurley, King,
Pollard, 1960s); here it is applied to decision tables that were extracted
*automatically* from legacy COBOL.

Method:
- Boolean tables (IF/ELSE, EVALUATE TRUE): enumerate all 2^N combinations of the
  N conditions and count how many are covered by some rule column. A column with
  a Y/N pins that condition; "-" is don't-care; a WHEN OTHER / ELSE catch-all
  covers everything.
- Value tables (EVALUATE <var>): the variable's domain is open, so coverage is
  categorical — complete iff a WHEN OTHER catch-all exists, otherwise the
  "any other value" case is undefined.

Honest limitation (state it in the paper): the boolean method treats conditions
as logically INDEPENDENT. Correlated conditions (e.g. AGE>65 implies AGE>21) can
make some enumerated combinations logically infeasible, so a reported gap is a
*candidate* — an upper bound on missing behaviour that a human confirms. The
score never silently hides a real gap; it may over-report, never under-report.

Stdlib-only. No third-party dependencies.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import List, Optional

from src.extraction.decision_table import DecisionTable

_CATCH_ALL = {"OTHERWISE", "OTHER"}
_MAX_CONDITIONS = 10          # 2^10 = 1024 combinations; refuse to enumerate more


@dataclass
class TableCompleteness:
    table_name: str
    table_type: str
    num_conditions: int
    total_combinations: Optional[int]      # None for open-domain value tables
    covered_combinations: Optional[int]
    coverage: Optional[float]              # covered / total, or None
    verdict: str                           # 'complete' | 'incomplete' | 'unscored'
    missing: List[str] = field(default_factory=list)
    note: str = ""

    @property
    def is_high_risk(self) -> bool:
        return self.coverage is not None and self.coverage < 0.8


@dataclass
class CompletenessReport:
    tables: List[TableCompleteness] = field(default_factory=list)

    @property
    def scored(self) -> List[TableCompleteness]:
        return [t for t in self.tables if t.coverage is not None]

    @property
    def num_complete(self) -> int:
        return sum(1 for t in self.tables if t.verdict == "complete")

    @property
    def num_incomplete(self) -> int:
        return sum(1 for t in self.tables if t.verdict == "incomplete")

    @property
    def mean_coverage(self) -> Optional[float]:
        scored = self.scored
        if not scored:
            return None
        return sum(t.coverage for t in scored) / len(scored)

    @property
    def high_risk(self) -> List[TableCompleteness]:
        return [t for t in self.tables if t.is_high_risk]


class CompletenessScorer:
    """Score the input-space completeness of extracted decision tables."""

    def score_all(self, tables: List[DecisionTable]) -> CompletenessReport:
        return CompletenessReport(tables=[self.score(t) for t in tables])

    def score(self, table: DecisionTable) -> TableCompleteness:
        name = table.source_rule.paragraph_name if table.source_rule else "(anon)"
        is_value_table = (
            table.table_type == "EVALUATE"
            and table.subject not in ("TRUE", "")
        )
        if is_value_table:
            return self._score_value_table(table, name)
        return self._score_boolean_table(table, name)

    # ── boolean (IF / EVALUATE TRUE) ──────────────────────────────────────
    def _score_boolean_table(self, table: DecisionTable, name: str) -> TableCompleteness:
        n = table.num_conditions
        if n == 0:
            return TableCompleteness(
                name, table.table_type, 0, None, None, None, "unscored",
                note="no parsed conditions to enumerate",
            )
        if n > _MAX_CONDITIONS:
            return TableCompleteness(
                name, table.table_type, n, None, None, None, "unscored",
                note=f"{n} conditions — too many to enumerate (2^{n})",
            )

        has_catch_all = any(
            (col.label or "").strip().upper() in _CATCH_ALL for col in table.rules
        )

        total = 2 ** n
        covered = 0
        missing: List[str] = []
        for combo in itertools.product([False, True], repeat=n):
            if has_catch_all or self._combo_covered(table, combo):
                covered += 1
            else:
                missing.append(self._render_combo(table, combo))

        coverage = covered / total
        verdict = "complete" if covered == total else "incomplete"
        note = ""
        if missing:
            note = ("condition independence assumed — verify flagged "
                    "combinations are reachable")
        return TableCompleteness(
            name, table.table_type, n, total, covered, coverage, verdict,
            missing=missing[:8], note=note,
        )

    @staticmethod
    def _combo_covered(table: DecisionTable, combo) -> bool:
        for col in table.rules:
            ok = True
            for ci, bit in enumerate(combo):
                v = col.condition_values.get(ci, "-")
                if v == "Y" and not bit:
                    ok = False
                    break
                if v == "N" and bit:
                    ok = False
                    break
            if ok:
                return True
        return False

    @staticmethod
    def _render_combo(table: DecisionTable, combo) -> str:
        parts = []
        for ci, bit in enumerate(combo):
            cond = table.conditions[ci]
            parts.append(f"{cond}={'Y' if bit else 'N'}")
        return ", ".join(parts)

    # ── value (EVALUATE <var>) ────────────────────────────────────────────
    def _score_value_table(self, table: DecisionTable, name: str) -> TableCompleteness:
        labels = [(col.label or "").strip().upper() for col in table.rules]
        has_catch_all = any(lbl in _CATCH_ALL for lbl in labels)
        explicit = [lbl for lbl in labels if lbl not in _CATCH_ALL]
        verdict = "complete" if has_catch_all else "incomplete"
        note = (
            f"open domain on {table.subject}; {len(explicit)} explicit value(s)"
            + ("" if has_catch_all
               else " and NO catch-all — other values are undefined")
        )
        missing = [] if has_catch_all else [f"{table.subject} = <any other value>"]
        return TableCompleteness(
            name, table.table_type, 1, None, None, None, verdict,
            missing=missing, note=note,
        )


def render_report(report: CompletenessReport, program_name: str) -> str:
    lines = [
        "=" * 70,
        "  RULEFORGE — DECISION TABLE COMPLETENESS",
        "=" * 70,
        f"  Program          : {program_name}",
        f"  Tables scored    : {len(report.tables)}",
        f"  Complete         : {report.num_complete}",
        f"  Incomplete       : {report.num_incomplete}",
    ]
    mc = report.mean_coverage
    if mc is not None:
        lines.append(f"  Mean coverage    : {mc:.0%} (boolean tables)")
    lines.append("=" * 70)
    for t in report.tables:
        cov = f"{t.coverage:.0%}" if t.coverage is not None else "n/a"
        flag = "  <-- HIGH RISK" if t.is_high_risk else ""
        lines.append(f"\n  {t.table_name} [{t.table_type}] — {t.verdict}, coverage {cov}{flag}")
        if t.note:
            lines.append(f"    note: {t.note}")
        for m in t.missing:
            lines.append(f"    UNDEFINED: {m}")
    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from src.parser.cobol_parser import CobolParser
    from src.extraction.rule_detector import RuleDetector
    from src.extraction.decision_table import DecisionTableGenerator

    if len(sys.argv) < 2:
        print("Usage: python -m src.analysis.completeness <file.cbl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    program = CobolParser().parse_file(path)
    rules = RuleDetector(program).detect_all_rules()
    tables = DecisionTableGenerator().generate_all(rules)
    report = CompletenessScorer().score_all(tables)
    print(render_report(report, program.name))
