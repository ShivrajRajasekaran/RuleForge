"""Evaluation Framework — Module 8 of RuleForge.

Runs the complete pipeline across an entire COBOL corpus and computes the
quantitative metrics a research paper needs in its Results section:

  Coverage      — how much of the corpus parses without error, PROGRAM-ID
                  detection rate, fixed vs free format split.
  Extraction    — rules detected per file, breakdown by rule type and
                  business domain, confidence distribution.
  Decision tbls — tables generated, completeness rate (do they cover the
                  ELSE/OTHER path?), average size.
  Grounding     — (optional, sampled because LLM inference is slow) the
                  fraction of LLM-mentioned identifiers that are real, i.e.
                  the measured hallucination rate of the generator.

Outputs three artifacts into ./evaluation:
  - per_file.csv       one row per program (for appendix / spreadsheet)
  - summary.json       aggregate metrics (for programmatic use)
  - REPORT.md          paper-ready tables and prose

Run:
    python -m src.analysis.evaluator                  # whole corpus, no LLM
    python -m src.analysis.evaluator --llm-sample 5   # + grounding on 5 rules
"""

import csv
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from src.parser.cobol_parser import CobolParser
from src.extraction.rule_detector import RuleDetector, RuleType
from src.extraction.decision_table import DecisionTableGenerator


@dataclass
class FileMetrics:
    """Metrics for a single analyzed program."""
    filename: str
    parsed: bool
    program_id_found: bool = False
    fixed_format: bool = False
    loc: int = 0
    paragraphs: int = 0
    data_items: int = 0
    rules_total: int = 0
    rules_conditional: int = 0
    rules_computational: int = 0
    rules_validation: int = 0
    avg_confidence: float = 0.0
    tables_total: int = 0
    tables_complete: int = 0
    domain_counts: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class CorpusReport:
    """Aggregate metrics across the whole corpus."""
    files_found: int = 0
    files_parsed: int = 0
    program_ids_found: int = 0
    fixed_format: int = 0
    free_format: int = 0
    total_loc: int = 0
    total_rules: int = 0
    total_tables: int = 0
    tables_complete: int = 0
    rules_by_type: dict = field(default_factory=dict)
    rules_by_domain: dict = field(default_factory=dict)
    rules_per_file: List[int] = field(default_factory=list)
    confidences: List[float] = field(default_factory=list)
    # Grounding (optional)
    grounding_samples: int = 0
    grounding_scores: List[float] = field(default_factory=list)
    grounding_trustworthy: int = 0


class Evaluator:
    """Run the pipeline over a corpus and compute metrics."""

    def __init__(self, corpus_dir: str = "data/cobol_corpus",
                 out_dir: str = "evaluation"):
        self.corpus_dir = Path(corpus_dir)
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.file_metrics: List[FileMetrics] = []
        self.report = CorpusReport()

    # ─────────────────────────────────────────────────────────
    def evaluate(self, llm_sample: int = 0) -> CorpusReport:
        """Run the full evaluation. llm_sample = #rules to grounding-test."""
        files = sorted(self.corpus_dir.rglob("*.cbl"))
        self.report.files_found = len(files)

        # Collect rules for an optional LLM grounding sample.
        grounding_pool = []  # list of (program, rule)

        for f in files:
            fm = self._evaluate_file(f, grounding_pool)
            self.file_metrics.append(fm)

        self._aggregate()

        if llm_sample > 0:
            self._grounding_sample(grounding_pool, llm_sample)

        return self.report

    # ─────────────────────────────────────────────────────────
    def _evaluate_file(self, path: Path, grounding_pool: list) -> FileMetrics:
        fm = FileMetrics(filename=path.name, parsed=False)
        try:
            parser = CobolParser()
            program = parser.parse_file(path)
            fm.parsed = True
            fm.program_id_found = bool(program.name and program.name != "UNKNOWN")
            fm.fixed_format = parser.is_fixed_format
            fm.loc = program.loc
            fm.paragraphs = len(program.paragraphs)
            fm.data_items = len(program.data_items)

            rules = RuleDetector(program).detect_all_rules()
            fm.rules_total = len(rules)
            fm.rules_conditional = sum(
                1 for r in rules if r.rule_type == RuleType.CONDITIONAL)
            fm.rules_computational = sum(
                1 for r in rules if r.rule_type == RuleType.COMPUTATIONAL)
            fm.rules_validation = sum(
                1 for r in rules if r.rule_type == RuleType.VALIDATION)
            if rules:
                fm.avg_confidence = statistics.mean(r.confidence for r in rules)
            for r in rules:
                d = r.domain.value
                fm.domain_counts[d] = fm.domain_counts.get(d, 0) + 1

            tables = DecisionTableGenerator().generate_all(rules)
            fm.tables_total = len(tables)
            fm.tables_complete = sum(
                1 for t in tables if t.completeness == "complete")

            # Stash high-confidence rules for the LLM grounding sample.
            for r in sorted(rules, key=lambda x: x.confidence, reverse=True)[:3]:
                grounding_pool.append((program, r))

        except Exception as e:  # parser/extraction robustness is itself a metric
            fm.error = f"{type(e).__name__}: {e}"
        return fm

    # ─────────────────────────────────────────────────────────
    def _aggregate(self):
        r = self.report
        for fm in self.file_metrics:
            if not fm.parsed:
                continue
            r.files_parsed += 1
            if fm.program_id_found:
                r.program_ids_found += 1
            if fm.fixed_format:
                r.fixed_format += 1
            else:
                r.free_format += 1
            r.total_loc += fm.loc
            r.total_rules += fm.rules_total
            r.total_tables += fm.tables_total
            r.tables_complete += fm.tables_complete
            r.rules_per_file.append(fm.rules_total)
            r.rules_by_type["conditional"] = (
                r.rules_by_type.get("conditional", 0) + fm.rules_conditional)
            r.rules_by_type["computational"] = (
                r.rules_by_type.get("computational", 0) + fm.rules_computational)
            r.rules_by_type["validation"] = (
                r.rules_by_type.get("validation", 0) + fm.rules_validation)
            for domain, count in fm.domain_counts.items():
                r.rules_by_domain[domain] = (
                    r.rules_by_domain.get(domain, 0) + count)

        # Per-file mean confidences (only files that actually had rules).
        r.confidences = [
            fm.avg_confidence for fm in self.file_metrics
            if fm.parsed and fm.rules_total > 0
        ]

    # ─────────────────────────────────────────────────────────
    def _grounding_sample(self, pool: list, n: int):
        """Run the LLM on a sample of rules and measure grounding."""
        from src.generation.nl_generator import NLGenerator
        from src.generation.llm_client import LLMClient

        client = LLMClient()
        if not client.is_available():
            print("  (Ollama offline — skipping grounding sample)")
            return

        # Spread the sample across different programs for representativeness.
        sample = pool[:: max(1, len(pool) // n)][:n] if pool else []
        print(f"  Running grounding sample on {len(sample)} rules (slow)...")
        for i, (program, rule) in enumerate(sample, 1):
            gen = NLGenerator(program, client=client)
            print(f"    [{i}/{len(sample)}] {program.name}:{rule.paragraph_name}")
            d = gen.describe_rule(rule)
            if d.success:
                self.report.grounding_samples += 1
                self.report.grounding_scores.append(d.grounding_score)
                if d.trustworthy:
                    self.report.grounding_trustworthy += 1

    # ─────────────────────────────────────────────────────────
    # Output writers
    # ─────────────────────────────────────────────────────────
    def write_csv(self) -> Path:
        path = self.out_dir / "per_file.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "File", "Parsed", "ProgramID", "Format", "LOC", "Paragraphs",
                "DataItems", "Rules", "Conditional", "Computational",
                "Validation", "AvgConfidence", "Tables", "TablesComplete", "Error",
            ])
            for m in self.file_metrics:
                w.writerow([
                    m.filename, m.parsed, m.program_id_found,
                    "fixed" if m.fixed_format else "free", m.loc, m.paragraphs,
                    m.data_items, m.rules_total, m.rules_conditional,
                    m.rules_computational, m.rules_validation,
                    f"{m.avg_confidence:.3f}", m.tables_total,
                    m.tables_complete, m.error,
                ])
        return path

    def write_json(self) -> Path:
        r = self.report
        path = self.out_dir / "summary.json"
        data = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "corpus_dir": str(self.corpus_dir),
            "coverage": {
                "files_found": r.files_found,
                "files_parsed": r.files_parsed,
                "parse_rate": self._pct(r.files_parsed, r.files_found),
                "program_id_rate": self._pct(r.program_ids_found, r.files_parsed),
                "fixed_format": r.fixed_format,
                "free_format": r.free_format,
            },
            "extraction": {
                "total_loc": r.total_loc,
                "total_rules": r.total_rules,
                "rules_per_file_mean": self._mean(r.rules_per_file),
                "rules_per_file_median": self._median(r.rules_per_file),
                "rules_per_file_max": max(r.rules_per_file) if r.rules_per_file else 0,
                "rules_by_type": r.rules_by_type,
                "rules_by_domain": r.rules_by_domain,
                "mean_confidence": self._mean(r.confidences),
            },
            "decision_tables": {
                "total": r.total_tables,
                "complete": r.tables_complete,
                "completeness_rate": self._pct(r.tables_complete, r.total_tables),
            },
            "grounding": {
                "samples": r.grounding_samples,
                "mean_grounding": self._mean(r.grounding_scores),
                "trustworthy_rate": self._pct(
                    r.grounding_trustworthy, r.grounding_samples),
            } if r.grounding_samples else None,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def write_report(self) -> Path:
        r = self.report
        L = []
        L.append("# RuleForge — Evaluation Report")
        L.append("")
        L.append(f"*Generated {datetime.now():%Y-%m-%d %H:%M} over "
                 f"`{self.corpus_dir}`*")
        L.append("")
        L.append("## 1. Corpus Coverage")
        L.append("")
        L.append("| Metric | Value |")
        L.append("|--------|-------|")
        L.append(f"| COBOL files found | {r.files_found} |")
        L.append(f"| Parsed without error | {r.files_parsed} "
                 f"({self._pct(r.files_parsed, r.files_found):.1f}%) |")
        L.append(f"| PROGRAM-ID detected | {r.program_ids_found} "
                 f"({self._pct(r.program_ids_found, r.files_parsed):.1f}%) |")
        L.append(f"| Fixed-format programs | {r.fixed_format} |")
        L.append(f"| Free-format programs | {r.free_format} |")
        L.append(f"| Total lines of COBOL | {r.total_loc:,} |")
        L.append("")

        L.append("## 2. Business Rule Extraction")
        L.append("")
        L.append("| Metric | Value |")
        L.append("|--------|-------|")
        L.append(f"| Total rules detected | {r.total_rules} |")
        L.append(f"| Rules per program (mean) | {self._mean(r.rules_per_file):.1f} |")
        L.append(f"| Rules per program (median) | {self._median(r.rules_per_file):.1f} |")
        L.append(f"| Rules per program (max) | "
                 f"{max(r.rules_per_file) if r.rules_per_file else 0} |")
        L.append(f"| Mean rule confidence | {self._mean(r.confidences):.2f} |")
        L.append("")
        L.append("### Rules by type")
        L.append("")
        L.append("| Type | Count | Share |")
        L.append("|------|-------|-------|")
        for t, c in sorted(r.rules_by_type.items(), key=lambda x: -x[1]):
            L.append(f"| {t} | {c} | {self._pct(c, r.total_rules):.1f}% |")
        L.append("")
        L.append("### Rules by business domain")
        L.append("")
        L.append("| Domain | Count | Share |")
        L.append("|--------|-------|-------|")
        for d, c in sorted(r.rules_by_domain.items(), key=lambda x: -x[1]):
            L.append(f"| {d} | {c} | {self._pct(c, r.total_rules):.1f}% |")
        L.append("")

        L.append("## 3. Decision Tables")
        L.append("")
        L.append("| Metric | Value |")
        L.append("|--------|-------|")
        L.append(f"| Tables generated | {r.total_tables} |")
        L.append(f"| Complete (cover ELSE/OTHER) | {r.tables_complete} "
                 f"({self._pct(r.tables_complete, r.total_tables):.1f}%) |")
        L.append("")

        if r.grounding_samples:
            L.append("## 4. LLM Grounding (Anti-Hallucination)")
            L.append("")
            L.append("| Metric | Value |")
            L.append("|--------|-------|")
            L.append(f"| Rules sampled | {r.grounding_samples} |")
            L.append(f"| Mean grounding score | {self._mean(r.grounding_scores):.2f} |")
            L.append(f"| Trustworthy (≥80% grounded) | {r.grounding_trustworthy} "
                     f"({self._pct(r.grounding_trustworthy, r.grounding_samples):.1f}%) |")
            L.append("")
            L.append("> Grounding score = fraction of COBOL identifiers the LLM "
                     "mentioned that actually exist in the source program. A low "
                     "score flags potential hallucination for human review.")
            L.append("")

        L.append("## Interpretation")
        L.append("")
        L.append(f"RuleForge parsed **{self._pct(r.files_parsed, r.files_found):.0f}%** "
                 f"of a real-world COBOL banking corpus ({r.files_found} programs, "
                 f"{r.total_loc:,} LOC) and extracted **{r.total_rules} business "
                 f"rules**, generating **{r.total_tables} formal decision tables** "
                 f"of which {self._pct(r.tables_complete, r.total_tables):.0f}% are "
                 f"logically complete. All processing is local and dependency-free.")
        L.append("")

        path = self.out_dir / "REPORT.md"
        path.write_text("\n".join(L), encoding="utf-8")
        return path

    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _pct(num, den):
        return (100.0 * num / den) if den else 0.0

    @staticmethod
    def _mean(xs):
        return statistics.mean(xs) if xs else 0.0

    @staticmethod
    def _median(xs):
        return statistics.median(xs) if xs else 0.0


# ═══════════════════════════════════════════════════
# RUN DIRECTLY
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    llm_sample = 0
    skip_next = False
    positional = []
    for idx, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if arg == "--llm-sample":
            nxt = sys.argv[2 + idx] if 2 + idx < len(sys.argv) else "0"
            llm_sample = int(nxt)
            skip_next = True
        elif not arg.startswith("--"):
            positional.append(arg)

    corpus = positional[0] if positional else "data/cobol_corpus"

    evaluator = Evaluator(corpus_dir=corpus)

    print("=" * 70)
    print("  RULEFORGE — EVALUATION FRAMEWORK v0.1")
    print("=" * 70)
    print(f"  Corpus: {corpus}")
    print("  Running pipeline over corpus...")

    report = evaluator.evaluate(llm_sample=llm_sample)

    csv_path = evaluator.write_csv()
    json_path = evaluator.write_json()
    report_path = evaluator.write_report()

    r = report
    print("-" * 70)
    print(f"  Files parsed     : {r.files_parsed}/{r.files_found} "
          f"({evaluator._pct(r.files_parsed, r.files_found):.1f}%)")
    print(f"  PROGRAM-ID found : {r.program_ids_found}/{r.files_parsed} "
          f"({evaluator._pct(r.program_ids_found, r.files_parsed):.1f}%)")
    print(f"  Total LOC        : {r.total_loc:,}")
    print(f"  Total rules      : {r.total_rules} "
          f"(mean {evaluator._mean(r.rules_per_file):.1f}/file)")
    print(f"  Rules by type    : {r.rules_by_type}")
    print(f"  Decision tables  : {r.total_tables} "
          f"({evaluator._pct(r.tables_complete, r.total_tables):.1f}% complete)")
    if r.grounding_samples:
        print(f"  Grounding (n={r.grounding_samples}): "
              f"mean {evaluator._mean(r.grounding_scores):.2f}, "
              f"{evaluator._pct(r.grounding_trustworthy, r.grounding_samples):.0f}% trustworthy")
    print("-" * 70)
    print(f"  Wrote: {csv_path}")
    print(f"  Wrote: {json_path}")
    print(f"  Wrote: {report_path}")
    print("=" * 70)
    print("  EVALUATION COMPLETE")
    print("=" * 70)
