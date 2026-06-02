"""Export Engine — Module 6 of RuleForge.

Takes the full analysis of a COBOL program (AST + detected rules + decision
tables + optional LLM descriptions) and writes it out in formats that
different audiences actually use:

  - JSON     → machine-readable, for downstream tools / APIs
  - DMN 1.3  → Decision Model & Notation XML (the OMG industry standard for
               business rules; importable into Camunda, IBM ODM, Drools)
  - Markdown → human-readable spec a business analyst can read/version
  - CSV      → opens directly in Excel; one row per rule
  - HTML     → styled report, "Print → Save as PDF" for a polished deliverable

Deliberately dependency-free: uses only the Python standard library (json,
csv, xml, html) so the project runs after a bare `git clone` with no extra
`pip install`. PDF/Excel binaries would need heavyweight packages; HTML+CSV
cover the same need with zero dependencies.

Run:
    python -m src.export.export_engine <file.cbl> [--with-llm N]
"""

import json
import csv
import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from xml.dom import minidom
from xml.etree import ElementTree as ET

from src.parser.cobol_parser import CobolProgram
from src.extraction.rule_detector import DetectedRule
from src.extraction.decision_table import DecisionTable


@dataclass
class ExportBundle:
    """Everything we know about one analyzed program, ready to serialize."""
    program: CobolProgram
    rules: List[DetectedRule] = field(default_factory=list)
    tables: List[DecisionTable] = field(default_factory=list)
    descriptions: List = field(default_factory=list)  # GeneratedDescription objects


class ExportEngine:
    """Serialize an ExportBundle into multiple file formats."""

    DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"

    def __init__(self, bundle: ExportBundle, out_dir: str = "exports"):
        self.bundle = bundle
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        # Safe base filename derived from the program name.
        prog = bundle.program.name or "PROGRAM"
        self.stem = "".join(c if c.isalnum() else "_" for c in prog) or "PROGRAM"

    # ─────────────────────────────────────────────────────────
    # Orchestration
    # ─────────────────────────────────────────────────────────
    def export_all(self) -> dict:
        """Write every format. Returns {format: path}."""
        return {
            "json": self.to_json(),
            "dmn": self.to_dmn(),
            "markdown": self.to_markdown(),
            "csv": self.to_csv(),
            "html": self.to_html(),
        }

    # ─────────────────────────────────────────────────────────
    # JSON
    # ─────────────────────────────────────────────────────────
    def to_json(self) -> Path:
        prog = self.bundle.program
        # Index descriptions by paragraph for easy attachment.
        desc_by_para = {}
        for d in self.bundle.descriptions:
            desc_by_para.setdefault(d.paragraph_name, []).append(d)

        data = {
            "program": {
                "name": prog.name,
                "source_path": prog.source_path,
                "loc": prog.loc,
                "paragraphs": len(prog.paragraphs),
                "data_items": len(prog.data_items),
            },
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "generator": "RuleForge Export Engine v0.1",
            "rules": [
                {
                    "type": r.rule_type.value,
                    "paragraph": r.paragraph_name,
                    "domain": r.domain.value,
                    "confidence": round(r.confidence, 3),
                    "description": r.description,
                    "variables": r.variables_involved,
                    "lines": [r.start_line, r.end_line],
                    "source_code": r.source_code,
                }
                for r in self.bundle.rules
            ],
            "decision_tables": [t.to_dict() for t in self.bundle.tables],
            "llm_descriptions": [
                {
                    "paragraph": d.paragraph_name,
                    "rule_type": d.rule_type,
                    "domain": d.domain,
                    "description": d.description,
                    "grounding_score": round(d.grounding_score, 3),
                    "trustworthy": d.trustworthy,
                    "flagged_terms": d.hallucinated_terms,
                }
                for d in self.bundle.descriptions
            ],
        }
        path = self.out_dir / f"{self.stem}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    # ─────────────────────────────────────────────────────────
    # DMN 1.3 XML
    # ─────────────────────────────────────────────────────────
    def to_dmn(self) -> Path:
        """Emit decision tables as a DMN 1.3 model.

        Each RuleForge DecisionTable becomes a <decision> containing a
        <decisionTable> with <input>/<output> columns and <rule> rows. This is
        the format business-rules engines (Camunda, IBM ODM, Drools) import.
        """
        ET.register_namespace("", self.DMN_NS)
        definitions = ET.Element(
            f"{{{self.DMN_NS}}}definitions",
            {
                "id": f"RuleForge_{self.stem}",
                "name": self.bundle.program.name or "RuleForge",
                "namespace": "http://ruleforge/dmn",
            },
        )

        for idx, table in enumerate(self.bundle.tables, 1):
            para = table.source_rule.paragraph_name if table.source_rule else f"T{idx}"
            decision = ET.SubElement(
                definitions,
                f"{{{self.DMN_NS}}}decision",
                {"id": f"decision_{idx}", "name": f"{para}_{idx}"},
            )
            dt = ET.SubElement(
                decision,
                f"{{{self.DMN_NS}}}decisionTable",
                {"id": f"dt_{idx}", "hitPolicy": "FIRST"},
            )

            # Inputs = conditions
            for ci, cond in enumerate(table.conditions, 1):
                inp = ET.SubElement(
                    dt, f"{{{self.DMN_NS}}}input",
                    {"id": f"in_{idx}_{ci}", "label": str(cond)},
                )
                expr = ET.SubElement(
                    inp, f"{{{self.DMN_NS}}}inputExpression",
                    {"id": f"ine_{idx}_{ci}", "typeRef": "string"},
                )
                text = ET.SubElement(expr, f"{{{self.DMN_NS}}}text")
                text.text = cond.variable or str(cond)

            # Single output = the chosen action/outcome
            out = ET.SubElement(
                dt, f"{{{self.DMN_NS}}}output",
                {"id": f"out_{idx}", "label": "Outcome", "typeRef": "string"},
            )

            # Rules = columns
            for ri, col in enumerate(table.rules, 1):
                rule_el = ET.SubElement(
                    dt, f"{{{self.DMN_NS}}}rule", {"id": f"rule_{idx}_{ri}"}
                )
                for ci, _cond in enumerate(table.conditions):
                    ie = ET.SubElement(rule_el, f"{{{self.DMN_NS}}}inputEntry",
                                       {"id": f"ie_{idx}_{ri}_{ci}"})
                    t = ET.SubElement(ie, f"{{{self.DMN_NS}}}text")
                    val = col.condition_values.get(ci, "-")
                    t.text = "" if val == "-" else val
                oe = ET.SubElement(rule_el, f"{{{self.DMN_NS}}}outputEntry",
                                   {"id": f"oe_{idx}_{ri}"})
                ot = ET.SubElement(oe, f"{{{self.DMN_NS}}}text")
                outcome = col.label
                if col.actions:
                    outcome = "; ".join(str(a) for a in col.actions[:3])
                ot.text = outcome

        rough = ET.tostring(definitions, encoding="unicode")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ")
        path = self.out_dir / f"{self.stem}.dmn"
        path.write_text(pretty, encoding="utf-8")
        return path

    # ─────────────────────────────────────────────────────────
    # Markdown
    # ─────────────────────────────────────────────────────────
    def to_markdown(self) -> Path:
        prog = self.bundle.program
        L = []
        L.append(f"# Business Rules Specification — {prog.name}")
        L.append("")
        L.append(f"*Generated by RuleForge on "
                 f"{datetime.now():%Y-%m-%d %H:%M}*")
        L.append("")
        L.append("## Program Overview")
        L.append("")
        L.append(f"- **Source:** `{prog.source_path}`")
        L.append(f"- **Lines of code:** {prog.loc}")
        L.append(f"- **Paragraphs:** {len(prog.paragraphs)}")
        L.append(f"- **Data items:** {len(prog.data_items)}")
        L.append(f"- **Business rules found:** {len(self.bundle.rules)}")
        L.append(f"- **Decision tables:** {len(self.bundle.tables)}")
        L.append("")

        # Rules grouped by domain
        L.append("## Business Rules")
        L.append("")
        by_domain = {}
        for r in self.bundle.rules:
            by_domain.setdefault(r.domain.value, []).append(r)
        for domain, rlist in sorted(by_domain.items()):
            L.append(f"### {domain} ({len(rlist)})")
            L.append("")
            for r in rlist:
                L.append(f"- **{r.paragraph_name}** "
                         f"({r.rule_type.value}, confidence {r.confidence:.0%}) "
                         f"— {r.description}")
            L.append("")

        # LLM descriptions
        if self.bundle.descriptions:
            L.append("## Plain-English Descriptions (LLM)")
            L.append("")
            for d in self.bundle.descriptions:
                badge = "✅ trustworthy" if d.trustworthy else "⚠️ needs review"
                L.append(f"### {d.paragraph_name} — {badge} "
                         f"(grounding {d.grounding_score:.0%})")
                L.append("")
                L.append(d.description)
                if d.hallucinated_terms:
                    L.append("")
                    L.append(f"> **Flagged terms:** {', '.join(d.hallucinated_terms)}")
                L.append("")

        # Decision tables
        if self.bundle.tables:
            L.append("## Decision Tables")
            L.append("")
            for i, t in enumerate(self.bundle.tables, 1):
                para = t.source_rule.paragraph_name if t.source_rule else f"Table {i}"
                L.append(f"### Table {i}: {para} ({t.table_type})")
                L.append("")
                L.append("```")
                L.append(t.to_text())
                L.append("```")
                L.append("")

        path = self.out_dir / f"{self.stem}.md"
        path.write_text("\n".join(L), encoding="utf-8")
        return path

    # ─────────────────────────────────────────────────────────
    # CSV (one row per rule)
    # ─────────────────────────────────────────────────────────
    def to_csv(self) -> Path:
        path = self.out_dir / f"{self.stem}_rules.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "Paragraph", "Type", "Domain", "Confidence",
                "Variables", "Start Line", "End Line", "Description",
            ])
            for r in self.bundle.rules:
                w.writerow([
                    r.paragraph_name,
                    r.rule_type.value,
                    r.domain.value,
                    f"{r.confidence:.2f}",
                    "; ".join(r.variables_involved[:8]),
                    r.start_line,
                    r.end_line,
                    r.description,
                ])
        return path

    # ─────────────────────────────────────────────────────────
    # HTML (print-to-PDF friendly)
    # ─────────────────────────────────────────────────────────
    def to_html(self) -> Path:
        prog = self.bundle.program
        e = html.escape
        parts = [f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>RuleForge Report — {e(prog.name)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ border-bottom: 3px solid #0b5cad; padding-bottom: .3rem; }}
  h2 {{ color: #0b5cad; margin-top: 2rem; }}
  .meta {{ color: #666; font-size: .9rem; }}
  .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
  .card {{ background: #f3f7fb; border: 1px solid #d6e4f0; border-radius: 8px;
          padding: .8rem 1.2rem; min-width: 120px; }}
  .card b {{ font-size: 1.6rem; display: block; color: #0b5cad; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9rem; }}
  th, td {{ border: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }}
  th {{ background: #0b5cad; color: #fff; }}
  tr:nth-child(even) {{ background: #f7f9fb; }}
  .trust {{ color: #137333; font-weight: bold; }}
  .review {{ color: #b06000; font-weight: bold; }}
  pre {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 6px;
         overflow-x: auto; font-size: .8rem; }}
  .badge {{ font-size: .75rem; padding: .1rem .5rem; border-radius: 10px;
            background: #e0e0e0; }}
</style></head><body>"""]

        parts.append(f"<h1>Business Rules Specification</h1>")
        parts.append(f"<p class='meta'>Program <b>{e(prog.name)}</b> &middot; "
                     f"generated by RuleForge on {datetime.now():%Y-%m-%d %H:%M}</p>")

        # Stat cards
        parts.append("<div class='cards'>")
        for label, val in [
            ("Lines", prog.loc), ("Paragraphs", len(prog.paragraphs)),
            ("Data items", len(prog.data_items)),
            ("Rules", len(self.bundle.rules)),
            ("Tables", len(self.bundle.tables)),
        ]:
            parts.append(f"<div class='card'><b>{val}</b>{e(str(label))}</div>")
        parts.append("</div>")

        # Rules table
        parts.append("<h2>Detected Business Rules</h2>")
        parts.append("<table><tr><th>Paragraph</th><th>Type</th><th>Domain</th>"
                     "<th>Confidence</th><th>Description</th></tr>")
        for r in self.bundle.rules:
            parts.append(
                f"<tr><td>{e(r.paragraph_name)}</td><td>{e(r.rule_type.value)}</td>"
                f"<td>{e(r.domain.value)}</td><td>{r.confidence:.0%}</td>"
                f"<td>{e(r.description)}</td></tr>"
            )
        parts.append("</table>")

        # LLM descriptions
        if self.bundle.descriptions:
            parts.append("<h2>Plain-English Descriptions (LLM)</h2>")
            for d in self.bundle.descriptions:
                cls = "trust" if d.trustworthy else "review"
                tag = "TRUSTWORTHY" if d.trustworthy else "NEEDS REVIEW"
                parts.append(f"<h3>{e(d.paragraph_name)} "
                             f"<span class='{cls}'>[{tag} · grounding "
                             f"{d.grounding_score:.0%}]</span></h3>")
                parts.append(f"<p>{e(d.description)}</p>")
                if d.hallucinated_terms:
                    parts.append(f"<p class='review'>Flagged: "
                                 f"{e(', '.join(d.hallucinated_terms))}</p>")

        # Decision tables
        if self.bundle.tables:
            parts.append("<h2>Decision Tables</h2>")
            for i, t in enumerate(self.bundle.tables, 1):
                para = t.source_rule.paragraph_name if t.source_rule else f"Table {i}"
                parts.append(f"<h3>Table {i}: {e(para)} "
                             f"<span class='badge'>{e(t.table_type)}</span></h3>")
                parts.append(f"<pre>{e(t.to_text())}</pre>")

        parts.append("</body></html>")
        path = self.out_dir / f"{self.stem}.html"
        path.write_text("\n".join(parts), encoding="utf-8")
        return path


# ═══════════════════════════════════════════════════
# RUN DIRECTLY TO TEST
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from src.parser.cobol_parser import CobolParser
    from src.extraction.rule_detector import RuleDetector
    from src.extraction.decision_table import DecisionTableGenerator

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    with_llm = 0
    if "--with-llm" in sys.argv:
        i = sys.argv.index("--with-llm")
        if i + 1 < len(sys.argv):
            with_llm = int(sys.argv[i + 1])

    if args:
        file_path = Path(args[0])
    else:
        file_path = Path(
            "data/cobol_corpus/aws_card_demo/app/"
            "app-transaction-type-db2/cbl/COBTUPDT.cbl"
        )

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        print("Usage: python -m src.export.export_engine <file.cbl> [--with-llm N]")
        sys.exit(1)

    # Pipeline
    program = CobolParser().parse_file(file_path)
    rules = RuleDetector(program).detect_all_rules()
    tables = DecisionTableGenerator().generate_all(rules)

    descriptions = []
    if with_llm > 0:
        from src.generation.nl_generator import NLGenerator
        gen = NLGenerator(program)
        if gen.client.is_available():
            top = sorted(rules, key=lambda r: r.confidence, reverse=True)[:with_llm]
            print(f"  Generating {len(top)} LLM descriptions (slow)...")
            for r in top:
                descriptions.append(gen.describe_rule(r))
        else:
            print("  (Ollama offline — skipping LLM descriptions)")

    bundle = ExportBundle(program, rules, tables, descriptions)
    engine = ExportEngine(bundle)
    outputs = engine.export_all()

    print("=" * 70)
    print("  RULEFORGE — EXPORT ENGINE v0.1")
    print("=" * 70)
    print(f"  Program : {program.name}")
    print(f"  Rules   : {len(rules)} | Tables: {len(tables)} | "
          f"LLM docs: {len(descriptions)}")
    print("-" * 70)
    for fmt, path in outputs.items():
        size = path.stat().st_size
        print(f"  {fmt.upper():<9} -> {path}  ({size:,} bytes)")
    print("=" * 70)
    print("  EXPORT COMPLETE")
    print("=" * 70)
