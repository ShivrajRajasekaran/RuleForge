"""Tests for the rule detector (Module 3)."""

from src.extraction.rule_detector import (
    RuleDetector, RuleType, BusinessDomain, DetectedRule,
)


def test_detects_some_rules(rules):
    assert len(rules) >= 3


def test_detects_conditional_rule(rules):
    conditionals = [r for r in rules if r.rule_type == RuleType.CONDITIONAL]
    assert len(conditionals) >= 1


def test_detects_computational_rule(rules):
    comps = [r for r in rules if r.rule_type == RuleType.COMPUTATIONAL]
    assert len(comps) >= 1


def test_business_variables_identified(program):
    detector = RuleDetector(program)
    assert "WS-ACCT-BALANCE" in detector.business_vars
    assert "WS-CREDIT-LIMIT" in detector.business_vars


def test_confidence_in_valid_range(rules):
    for r in rules:
        assert 0.0 <= r.confidence <= 1.0


def test_rules_above_threshold(rules):
    # Detector filters rules below 0.4 confidence.
    assert all(r.confidence >= 0.4 for r in rules)


def test_rule_has_paragraph_name(rules):
    for r in rules:
        assert r.paragraph_name


def test_domains_are_assigned(rules):
    for r in rules:
        assert isinstance(r.domain, BusinessDomain)


def test_variables_involved_populated(rules):
    conditional = next(r for r in rules if r.rule_type == RuleType.CONDITIONAL)
    assert len(conditional.variables_involved) >= 1


def test_detected_rule_dataclass_shape():
    r = DetectedRule(
        rule_type=RuleType.VALIDATION,
        paragraph_name="P",
        source_code="IF X = 1",
        start_line=1,
        end_line=1,
    )
    assert r.confidence == 0.0
    assert r.domain == BusinessDomain.UNKNOWN
