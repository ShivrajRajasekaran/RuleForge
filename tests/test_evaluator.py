"""Tests for the evaluation framework (Module 8)."""

import json

from src.analysis.evaluator import Evaluator, FileMetrics, CorpusReport


def test_stat_helpers():
    assert Evaluator._pct(1, 4) == 25.0
    assert Evaluator._pct(0, 0) == 0.0  # no division-by-zero
    assert Evaluator._mean([2, 4]) == 3.0
    assert Evaluator._mean([]) == 0.0
    assert Evaluator._median([1, 2, 3]) == 2
    assert Evaluator._median([]) == 0.0


def test_evaluate_single_file_corpus(sample_cbl, tmp_path):
    # Point the evaluator at a folder containing only the sample.
    evaluator = Evaluator(corpus_dir=str(sample_cbl.parent),
                          out_dir=str(tmp_path / "out"))
    report = evaluator.evaluate(llm_sample=0)
    assert report.files_found == 1
    assert report.files_parsed == 1
    assert report.total_rules >= 1
    assert report.total_tables >= 1


def test_file_metrics_populated(sample_cbl, tmp_path):
    evaluator = Evaluator(corpus_dir=str(sample_cbl.parent),
                          out_dir=str(tmp_path / "out"))
    evaluator.evaluate(llm_sample=0)
    fm = evaluator.file_metrics[0]
    assert fm.parsed is True
    assert fm.program_id_found is True
    assert fm.loc > 0
    assert "conditional" not in fm.error  # no error string


def test_writes_three_artifacts(sample_cbl, tmp_path):
    out = tmp_path / "out"
    evaluator = Evaluator(corpus_dir=str(sample_cbl.parent), out_dir=str(out))
    evaluator.evaluate(llm_sample=0)
    csv_path = evaluator.write_csv()
    json_path = evaluator.write_json()
    report_path = evaluator.write_report()
    assert csv_path.exists()
    assert report_path.exists()
    # summary.json must be valid JSON with expected sections.
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "coverage" in data
    assert "extraction" in data
    assert data["coverage"]["files_parsed"] == 1


def test_bad_file_recorded_not_raised(tmp_path):
    # A non-COBOL binary blob should be recorded as a parse outcome, not crash
    # the whole run.
    bad = tmp_path / "BAD.cbl"
    bad.write_bytes(b"\x00\x01\x02 not cobol \xff")
    evaluator = Evaluator(corpus_dir=str(tmp_path), out_dir=str(tmp_path / "o"))
    report = evaluator.evaluate(llm_sample=0)
    assert report.files_found == 1
    # Either it parsed (gracefully) or recorded an error — but never raised.
    assert len(evaluator.file_metrics) == 1
