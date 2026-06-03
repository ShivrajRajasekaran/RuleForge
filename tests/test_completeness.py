"""Tests for the decision-table completeness scorer."""

from pathlib import Path

from src.parser.cobol_parser import CobolParser
from src.extraction.rule_detector import RuleDetector
from src.extraction.decision_table import (
    DecisionTable, Condition, RuleColumn, DecisionTableGenerator,
)
from src.analysis.completeness import CompletenessScorer, CompletenessReport

SAMPLES = Path("data/completeness_samples")


def _ifelse_table(with_else: bool) -> DecisionTable:
    t = DecisionTable(table_type="IF-ELSE")
    t.conditions.append(Condition("WS-BAL", ">", "1000"))
    t.rules.append(RuleColumn(label="TRUE", condition_values={0: "Y"}))
    if with_else:
        t.rules.append(RuleColumn(label="FALSE", condition_values={0: "N"}))
    return t


def _value_table(with_other: bool) -> DecisionTable:
    t = DecisionTable(table_type="EVALUATE", subject="WS-ACCT-TYPE")
    t.conditions.append(Condition("WS-ACCT-TYPE", "=", "(see rules)"))
    t.rules.append(RuleColumn(label="SAV", condition_values={0: "SAV"}))
    t.rules.append(RuleColumn(label="CUR", condition_values={0: "CUR"}))
    if with_other:
        t.rules.append(RuleColumn(label="OTHERWISE", condition_values={0: "OTHER"}))
    return t


# ── boolean tables ─────────────────────────────────────────────────────────

def test_complete_if_else_full_coverage():
    r = CompletenessScorer().score(_ifelse_table(with_else=True))
    assert r.coverage == 1.0
    assert r.verdict == "complete"
    assert r.missing == []


def test_incomplete_if_missing_false_branch():
    r = CompletenessScorer().score(_ifelse_table(with_else=False))
    assert r.coverage == 0.5
    assert r.verdict == "incomplete"
    assert r.is_high_risk
    assert len(r.missing) == 1


def test_two_condition_table_enumerates_four():
    t = DecisionTable(table_type="EVALUATE", subject="TRUE")
    t.conditions.append(Condition("A", ">", "1"))
    t.conditions.append(Condition("B", ">", "2"))
    t.rules.append(RuleColumn(label="Rule 1", condition_values={0: "Y", 1: "-"}))
    r = CompletenessScorer().score(t)
    assert r.total_combinations == 4
    # Rule 1 covers A=Y (B either) -> 2 of 4 combos.
    assert r.covered_combinations == 2
    assert r.coverage == 0.5


def test_catch_all_column_makes_complete():
    t = DecisionTable(table_type="EVALUATE", subject="TRUE")
    t.conditions.append(Condition("A", ">", "1"))
    t.rules.append(RuleColumn(label="Rule 1", condition_values={0: "Y"}))
    t.rules.append(RuleColumn(label="OTHERWISE", condition_values={0: "-"}))
    r = CompletenessScorer().score(t)
    assert r.verdict == "complete"
    assert r.coverage == 1.0


# ── value (open-domain) tables ──────────────────────────────────────────────

def test_value_table_without_catch_all_incomplete():
    r = CompletenessScorer().score(_value_table(with_other=False))
    assert r.verdict == "incomplete"
    assert r.coverage is None          # open domain, not a fraction
    assert r.missing


def test_value_table_with_catch_all_complete():
    r = CompletenessScorer().score(_value_table(with_other=True))
    assert r.verdict == "complete"
    assert r.missing == []


# ── report aggregation ──────────────────────────────────────────────────────

def test_report_aggregates():
    scorer = CompletenessScorer()
    report = CompletenessReport(tables=[
        scorer.score(_ifelse_table(with_else=True)),    # complete, 1.0
        scorer.score(_ifelse_table(with_else=False)),   # incomplete, 0.5
    ])
    assert report.num_complete == 1
    assert report.num_incomplete == 1
    assert report.mean_coverage == 0.75
    assert len(report.high_risk) == 1


# ── end-to-end on fixtures ──────────────────────────────────────────────────

def _score_file(name):
    program = CobolParser().parse_file(SAMPLES / name)
    rules = RuleDetector(program).detect_all_rules()
    tables = DecisionTableGenerator().generate_all(rules)
    return CompletenessScorer().score_all(tables)


def test_fixture_incomplete_eval():
    report = _score_file("incomplete_eval.cbl")
    assert report.num_incomplete >= 1


def test_fixture_complete_eval():
    report = _score_file("complete_eval.cbl")
    assert report.num_complete >= 1
    assert report.num_incomplete == 0


def test_fixture_incomplete_if_high_risk():
    report = _score_file("incomplete_if.cbl")
    assert any(t.is_high_risk for t in report.tables)
