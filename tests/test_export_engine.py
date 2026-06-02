"""Tests for the export engine (Module 6)."""

import json
import csv
from xml.etree import ElementTree as ET

from src.export.export_engine import ExportBundle, ExportEngine


def _bundle(program, rules, tables):
    return ExportBundle(program, rules, tables, [])


def test_export_all_writes_five_files(program, rules, tables, tmp_path):
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    outputs = engine.export_all()
    assert set(outputs.keys()) == {"json", "dmn", "markdown", "csv", "html"}
    for path in outputs.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_json_is_valid_and_complete(program, rules, tables, tmp_path):
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    data = json.loads(engine.to_json().read_text(encoding="utf-8"))
    assert data["program"]["name"] == "TESTCALC"
    assert len(data["rules"]) == len(rules)
    assert len(data["decision_tables"]) == len(tables)


def test_dmn_is_valid_xml(program, rules, tables, tmp_path):
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    tree = ET.parse(engine.to_dmn())
    ns = "{https://www.omg.org/spec/DMN/20191111/MODEL/}"
    decisions = tree.findall(f".//{ns}decision")
    assert len(decisions) == len(tables)


def test_csv_has_header_and_rows(program, rules, tables, tmp_path):
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    with engine.to_csv().open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "Paragraph"
    assert len(rows) == len(rules) + 1  # header + one row per rule


def test_html_is_well_formed(program, rules, tables, tmp_path):
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    html = engine.to_html().read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE")
    assert html.rstrip().endswith("</html>")
    assert "TESTCALC" in html


def test_markdown_has_sections(program, rules, tables, tmp_path):
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    md = engine.to_markdown().read_text(encoding="utf-8")
    assert "# Business Rules Specification" in md
    assert "## Decision Tables" in md


def test_stem_sanitized_for_unknown(program, rules, tables, tmp_path):
    program.name = ""  # force the fallback
    engine = ExportEngine(_bundle(program, rules, tables), out_dir=str(tmp_path))
    assert engine.stem  # never empty
    assert all(c.isalnum() or c == "_" for c in engine.stem)
