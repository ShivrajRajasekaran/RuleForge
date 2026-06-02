"""Tests for the decision table generator (Module 4)."""

from src.extraction.decision_table import (
    DecisionTableGenerator, DecisionTable, Condition, Action, RuleColumn,
)


def test_generates_tables(tables):
    assert len(tables) >= 2


def test_table_types_present(tables):
    types = {t.table_type for t in tables}
    assert "IF-ELSE" in types
    assert "EVALUATE" in types


def test_tables_have_conditions_and_rules(tables):
    for t in tables:
        assert t.num_conditions >= 1
        assert t.num_rules >= 1


def test_to_text_renders(tables):
    text = tables[0].to_text()
    assert "CONDITIONS" in text
    assert "+" in text  # ASCII border


def test_to_dict_is_serializable(tables):
    import json
    d = tables[0].to_dict()
    json.dumps(d)  # must not raise
    assert "conditions" in d
    assert "rules" in d


def test_completeness_flagged(tables):
    for t in tables:
        assert t.completeness in ("complete", "incomplete")


def test_ifelse_has_two_columns(tables):
    ifelse = next(t for t in tables if t.table_type == "IF-ELSE")
    # IF with ELSE → TRUE + FALSE columns.
    assert ifelse.num_rules == 2


def test_empty_table_to_text():
    t = DecisionTable(table_type="IF-ELSE")
    assert t.to_text() == "(Empty decision table)"


def test_condition_str():
    c = Condition(variable="AGE", operator=">", value="21")
    assert str(c) == "AGE > 21"


def test_action_str():
    a = Action(action_type="MOVE", target_variable="STATUS", value="APPROVED")
    assert "STATUS" in str(a)
    assert "APPROVED" in str(a)


def test_only_conditional_rules_become_tables(rules):
    # Computational rules should not produce tables.
    gen = DecisionTableGenerator()
    tables = gen.generate_all(rules)
    assert all(
        t.source_rule is None or t.source_rule.rule_type.value == "conditional"
        for t in tables
    )
