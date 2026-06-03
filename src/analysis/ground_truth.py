"""Ground-Truth Evaluation — precision / recall / F1 for rule detection.

This is the *validation* half of the evaluation story. The corpus evaluator
(``evaluator.py``) reports how MANY rules are found; this module reports how
ACCURATE the detector is against a hand-labelled benchmark.

Benchmark design
----------------
``data/ground_truth/programs/*.cbl`` are small, fully-readable COBOL programs.
For each one, a human recorded the business rules it contains in
``data/ground_truth/labels/<name>.json`` *independently of the detector*.

Matching granularity
---------------------
A rule is identified by the pair ``(PARAGRAPH, RULE_TYPE)``. This measures the
core claim of the tool — "this paragraph contains a conditional / computational
/ validation business rule" — without depending on exactly how the regex
segments a nested IF (which would make counting brittle and unreproducible).
Both the labelled set and the detected set are reduced to unique pairs, then:

    TP = pairs in both          (correct detections)
    FP = detected, not labelled  (hallucinated / over-segmented rules)
    FN = labelled, not detected  (missed rules)

    precision = TP / (TP + FP)
    recall    = TP / (TP + FN)
    F1        = 2PR / (P + R)

The ``infra_only`` program is a negative control: it has zero labelled rules,
so anything detected there is a pure false positive (specificity check).

Stdlib only — no third-party dependencies.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

from src.parser.cobol_parser import CobolParser
from src.extraction.rule_detector import RuleDetector

# A rule is keyed by (paragraph upper-cased, rule_type value).
RuleKey = Tuple[str, str]


@dataclass
class FileScore:
    name: str
    expected: Set[RuleKey]
    detected: Set[RuleKey]
    parse_error: str = ""

    @property
    def true_positives(self) -> Set[RuleKey]:
        return self.expected & self.detected

    @property
    def false_positives(self) -> Set[RuleKey]:
        return self.detected - self.expected

    @property
    def false_negatives(self) -> Set[RuleKey]:
        return self.expected - self.detected

    @property
    def tp(self) -> int:
        return len(self.true_positives)

    @property
    def fp(self) -> int:
        return len(self.false_positives)

    @property
    def fn(self) -> int:
        return len(self.false_negatives)


@dataclass
class Benchmark:
    files: List[FileScore] = field(default_factory=list)

    @property
    def tp(self) -> int:
        return sum(f.tp for f in self.files)

    @property
    def fp(self) -> int:
        return sum(f.fp for f in self.files)

    @property
    def fn(self) -> int:
        return sum(f.fn for f in self.files)

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


class GroundTruthEvaluator:
    """Run the detector over the labelled benchmark and score it."""

    def __init__(self, gt_dir: str = "data/ground_truth", out_dir: str = "evaluation/ground_truth"):
        self.gt_dir = Path(gt_dir)
        self.programs_dir = self.gt_dir / "programs"
        self.labels_dir = self.gt_dir / "labels"
        self.out_dir = Path(out_dir)
        self.benchmark = Benchmark()

    def run(self) -> Benchmark:
        self.benchmark = Benchmark()
        for label_path in sorted(self.labels_dir.glob("*.json")):
            self.benchmark.files.append(self._score_one(label_path))
        return self.benchmark

    def _score_one(self, label_path: Path) -> FileScore:
        spec = json.loads(label_path.read_text(encoding="utf-8"))
        expected = {
            (r["paragraph"].upper(), r["rule_type"].lower())
            for r in spec.get("expected_rules", [])
        }
        cbl_path = self.programs_dir / spec["source_file"]

        if not cbl_path.exists():
            return FileScore(cbl_path.stem, expected, set(),
                             parse_error=f"missing source {cbl_path.name}")

        try:
            program = CobolParser().parse_file(cbl_path)
            rules = RuleDetector(program).detect_all_rules()
            detected = {(r.paragraph_name.upper(), r.rule_type.value) for r in rules}
        except Exception as exc:  # detector must never crash the benchmark
            return FileScore(cbl_path.stem, expected, set(), parse_error=str(exc))

        return FileScore(cbl_path.stem, expected, detected)

    # ── reporting ────────────────────────────────────────────────────

    def to_dict(self) -> Dict:
        b = self.benchmark
        return {
            "summary": {
                "files": len(b.files),
                "labelled_rules": b.tp + b.fn,
                "detected_rules": b.tp + b.fp,
                "true_positives": b.tp,
                "false_positives": b.fp,
                "false_negatives": b.fn,
                "precision": round(b.precision, 4),
                "recall": round(b.recall, 4),
                "f1": round(b.f1, 4),
            },
            "per_file": [
                {
                    "name": f.name,
                    "tp": f.tp,
                    "fp": f.fp,
                    "fn": f.fn,
                    "false_positives": sorted(f"{p}:{t}" for p, t in f.false_positives),
                    "false_negatives": sorted(f"{p}:{t}" for p, t in f.false_negatives),
                    "parse_error": f.parse_error,
                }
                for f in b.files
            ],
        }

    def write_json(self) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "ground_truth.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    def write_report(self) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        b = self.benchmark
        lines = [
            "# RuleForge — Rule Detection Accuracy (Hand-Labelled Benchmark)",
            "",
            f"- Benchmark programs: **{len(b.files)}**",
            f"- Labelled rules (ground truth): **{b.tp + b.fn}**",
            f"- Detected rules: **{b.tp + b.fp}**",
            "",
            "## Headline",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Precision | **{b.precision:.1%}** |",
            f"| Recall | **{b.recall:.1%}** |",
            f"| F1 | **{b.f1:.1%}** |",
            f"| True positives | {b.tp} |",
            f"| False positives | {b.fp} |",
            f"| False negatives | {b.fn} |",
            "",
            "Matching unit: `(paragraph, rule_type)`. See `ground_truth.py` for method.",
            "",
            "## Per-program",
            "",
            "| Program | TP | FP | FN |",
            "|---------|----|----|----|",
        ]
        for f in b.files:
            lines.append(f"| {f.name} | {f.tp} | {f.fp} | {f.fn} |")

        # Error analysis — the honest part reviewers care about.
        fps = [(f.name, k) for f in b.files for k in sorted(f"{p}:{t}" for p, t in f.false_positives)]
        fns = [(f.name, k) for f in b.files for k in sorted(f"{p}:{t}" for p, t in f.false_negatives)]
        lines += ["", "## Error analysis", ""]
        if fps:
            lines.append("**False positives (detected, not a real rule):**")
            lines += [f"- `{name}` → {k}" for name, k in fps]
            lines.append("")
        if fns:
            lines.append("**False negatives (real rule, missed):**")
            lines += [f"- `{name}` → {k}" for name, k in fns]
            lines.append("")
        if not fps and not fns:
            lines.append("No errors — perfect detection on this benchmark.")
            lines.append("")

        path = self.out_dir / "REPORT.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gt_dir = args[0] if args else "data/ground_truth"

    ev = GroundTruthEvaluator(gt_dir=gt_dir)
    bench = ev.run()
    json_path = ev.write_json()
    report_path = ev.write_report()

    print("=" * 70)
    print("  RULEFORGE - GROUND-TRUTH ACCURACY")
    print("=" * 70)
    print(f"  Programs        : {len(bench.files)}")
    print(f"  Labelled rules  : {bench.tp + bench.fn}")
    print(f"  Detected rules  : {bench.tp + bench.fp}")
    print("-" * 70)
    print(f"  Precision       : {bench.precision:.1%}  (TP={bench.tp}, FP={bench.fp})")
    print(f"  Recall          : {bench.recall:.1%}  (TP={bench.tp}, FN={bench.fn})")
    print(f"  F1              : {bench.f1:.1%}")
    print("-" * 70)
    for f in bench.files:
        flag = f"  ERROR: {f.parse_error}" if f.parse_error else ""
        print(f"  {f.name:<20} TP={f.tp} FP={f.fp} FN={f.fn}{flag}")
    print("-" * 70)
    print(f"  Wrote: {json_path}")
    print(f"  Wrote: {report_path}")
    print("=" * 70)
