"""Tests for the ground-truth precision/recall harness."""

import json

from src.analysis.ground_truth import (
    Benchmark,
    FileScore,
    GroundTruthEvaluator,
)


def _fs(name, expected, detected):
    return FileScore(name, set(expected), set(detected))


def test_fixture_set_arithmetic():
    fs = _fs(
        "x",
        expected={("P1", "conditional"), ("P2", "computational")},
        detected={("P1", "conditional"), ("P3", "validation")},
    )
    assert fs.tp == 1            # P1:conditional in both
    assert fs.fp == 1            # P3:validation detected, not expected
    assert fs.fn == 1            # P2:computational expected, missed


def test_benchmark_metrics_math():
    b = Benchmark(files=[
        _fs("a", {("P", "conditional")}, {("P", "conditional")}),   # TP
        _fs("b", {("Q", "computational")}, set()),                  # FN
        _fs("c", set(), {("R", "validation")}),                     # FP
    ])
    assert b.tp == 1 and b.fp == 1 and b.fn == 1
    assert b.precision == 0.5
    assert b.recall == 0.5
    assert b.f1 == 0.5


def test_empty_benchmark_no_zero_division():
    b = Benchmark(files=[])
    assert b.precision == 0.0
    assert b.recall == 0.0
    assert b.f1 == 0.0


def test_perfect_negative_control():
    # infra-only style: nothing expected, nothing detected -> no penalty.
    fs = _fs("infra", set(), set())
    assert fs.tp == 0 and fs.fp == 0 and fs.fn == 0


def test_runs_against_real_benchmark():
    """The shipped benchmark must load, parse, and score without crashing."""
    ev = GroundTruthEvaluator()
    bench = ev.run()
    assert len(bench.files) >= 5
    # Recall should be high on these clean, readable programs.
    assert bench.recall >= 0.9
    # Negative control contributes no false positives.
    infra = next(f for f in bench.files if f.name == "infra_only")
    assert infra.fp == 0
    assert infra.tp == 0


def test_writes_artifacts(tmp_path):
    ev = GroundTruthEvaluator(out_dir=str(tmp_path / "gt"))
    ev.run()
    jp = ev.write_json()
    rp = ev.write_report()
    assert jp.exists() and rp.exists()
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert "precision" in data["summary"]
    assert "recall" in data["summary"]
    assert data["summary"]["false_negatives"] >= 0
