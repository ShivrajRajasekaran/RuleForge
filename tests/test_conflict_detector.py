"""Tests for the rule conflict detector."""

from pathlib import Path

from src.parser.cobol_parser import CobolParser
from src.extraction.rule_detector import RuleDetector, DetectedRule, RuleType
from src.analysis.conflict_detector import (
    Predicate,
    ParsedGuard,
    RuleConflictDetector,
    parse_rule,
    guards_overlap,
    outcomes_differ,
    _vars_satisfiable,
)

SAMPLES = Path("data/conflict_samples")


def _rule(src, rtype=RuleType.CONDITIONAL, para="P"):
    return DetectedRule(
        rule_type=rtype, paragraph_name=para, source_code=src,
        start_line=1, end_line=1,
    )


# ── predicate-level satisfiability ─────────────────────────────────────────

def test_numeric_intervals_overlap():
    preds = [Predicate("X", ">", "1000", "num"), Predicate("X", ">", "5000", "num")]
    assert _vars_satisfiable(preds) is True


def test_numeric_intervals_disjoint():
    preds = [Predicate("X", ">", "5000", "num"), Predicate("X", "<", "1000", "num")]
    assert _vars_satisfiable(preds) is False


def test_numeric_equality_outside_interval():
    preds = [Predicate("X", "=", "10", "num"), Predicate("X", ">", "50", "num")]
    assert _vars_satisfiable(preds) is False


def test_string_equality_conflict():
    preds = [Predicate("T", "=", "SAV", "str"), Predicate("T", "=", "CUR", "str")]
    assert _vars_satisfiable(preds) is False


def test_string_equality_compatible():
    preds = [Predicate("T", "=", "SAV", "str"), Predicate("T", "=", "SAV", "str")]
    assert _vars_satisfiable(preds) is True


def test_symbolic_value_undetermined():
    preds = [Predicate("X", ">", "Y", "sym")]
    assert _vars_satisfiable(preds) is None


def test_mixed_domains_undetermined():
    preds = [Predicate("X", "=", "5", "num"), Predicate("X", "=", "SAV", "str")]
    assert _vars_satisfiable(preds) is None


# ── guard / action parsing ─────────────────────────────────────────────────

def test_parse_simple_conditional():
    g = parse_rule(_rule("IF WS-ACCT-BALANCE > 5000 PERFORM PREMIUM END-IF"))
    assert g is not None
    assert g.action_kind == "perform"
    assert g.action_target == "PREMIUM"
    assert any(p.var == "WS-ACCT-BALANCE" and p.op == ">" for p in g.preds)


def test_or_condition_is_skipped():
    g = parse_rule(_rule("IF A > 1 OR B > 2 PERFORM X END-IF"))
    assert g is None


def test_computational_rule_not_modeled():
    g = parse_rule(_rule("COMPUTE WS-FEE = WS-BAL * 2", rtype=RuleType.COMPUTATIONAL))
    assert g is None


def test_word_operator_normalized():
    g = parse_rule(_rule("IF WS-AGE GREATER THAN 65 PERFORM SENIOR END-IF"))
    assert g is not None
    assert any(p.op == ">" and p.value == "65" for p in g.preds)


# ── overlap + outcome logic ────────────────────────────────────────────────

def test_guards_overlap_true_on_shared_var():
    a = parse_rule(_rule("IF T = 'SAV' AND B > 5000 PERFORM P1 END-IF"))
    b = parse_rule(_rule("IF T = 'SAV' AND B > 1000 PERFORM P2 END-IF"))
    assert guards_overlap(a, b) is True
    assert outcomes_differ(a, b) is True


def test_guards_mutually_exclusive():
    a = parse_rule(_rule("IF B > 5000 PERFORM P1 END-IF"))
    b = parse_rule(_rule("IF B < 1000 PERFORM P2 END-IF"))
    assert guards_overlap(a, b) is False


def test_same_perform_target_not_a_conflict():
    a = parse_rule(_rule("IF B > 5000 PERFORM SAME END-IF"))
    b = parse_rule(_rule("IF B > 1000 PERFORM SAME END-IF"))
    assert guards_overlap(a, b) is True
    assert outcomes_differ(a, b) is False


# ── end-to-end on fixtures ─────────────────────────────────────────────────

def _detect(cbl_name):
    program = CobolParser().parse_file(SAMPLES / cbl_name)
    rules = RuleDetector(program).detect_all_rules()
    return RuleConflictDetector().detect(rules)


def test_conflict_fixture_flags_one():
    report = _detect("rate_conflict.cbl")
    assert len(report.conflicts) == 1
    c = report.conflicts[0]
    assert "WS-ACCT-BALANCE" in c.shared_variables
    assert "WS-ACCT-TYPE" in c.shared_variables


def test_negative_control_flags_none():
    report = _detect("rate_noconflict.cbl")
    assert report.conflicts == []
    assert report.rules_modeled >= 2
