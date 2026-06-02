"""Tests for the NL generator (Module 5b).

Focus: the anti-hallucination grounding validator — the project's core
contribution. The LLM itself is mocked so these tests are fast/deterministic.
"""

from src.generation.nl_generator import NLGenerator, GeneratedDescription
from src.generation.llm_client import LLMResponse


class _FakeClient:
    """A stand-in LLM client that returns a fixed string."""
    model = "fake"

    def __init__(self, text):
        self._text = text

    def is_available(self):
        return True

    def generate(self, prompt, system=""):
        return LLMResponse(text=self._text, model="fake", success=True,
                           elapsed_seconds=0.0)


def test_grounding_perfect_for_real_vars(program):
    gen = NLGenerator(program)
    # Mentions only real variables from the sample program.
    text = "The rule checks WS-CUST-AGE and updates WS-APPROVAL-STATUS."
    score, invented = gen._validate_grounding(
        text, ["WS-CUST-AGE", "WS-APPROVAL-STATUS"])
    assert score == 1.0
    assert invented == []


def test_grounding_flags_invented_var(program):
    gen = NLGenerator(program)
    text = "The rule sets WS-FAKE-FLAG based on WS-CUST-AGE."
    score, invented = gen._validate_grounding(text, ["WS-CUST-AGE"])
    assert "WS-FAKE-FLAG" in invented
    assert score < 1.0


def test_grounding_ignores_plain_english(program):
    gen = NLGenerator(program)
    text = "This rule approves the customer when they are old enough."
    score, invented = gen._validate_grounding(text, [])
    # No COBOL-style identifiers → fully grounded by definition.
    assert score == 1.0
    assert invented == []


def test_glossary_includes_pic_info(program):
    gen = NLGenerator(program)
    glossary = gen._build_glossary(["WS-ACCT-BALANCE"])
    assert "WS-ACCT-BALANCE" in glossary
    assert "PIC" in glossary


def test_describe_rule_with_mocked_llm(program, rules):
    gen = NLGenerator(program, client=_FakeClient(
        "Checks WS-CUST-AGE and sets WS-APPROVAL-STATUS accordingly."))
    rule = next(r for r in rules if r.variables_involved)
    result = gen.describe_rule(rule)
    assert isinstance(result, GeneratedDescription)
    assert result.success is True
    assert result.description
    assert 0.0 <= result.grounding_score <= 1.0


def test_describe_rule_failure_path(program, rules):
    class _Down:
        model = "fake"
        def is_available(self): return False
        def generate(self, prompt, system=""):
            return LLMResponse(text="", model="fake", success=False,
                               error="offline")
    gen = NLGenerator(program, client=_Down())
    result = gen.describe_rule(rules[0])
    assert result.success is False
    assert result.error == "offline"


def test_trustworthy_threshold(program):
    gen = NLGenerator(program, client=_FakeClient("x"))
    good = GeneratedDescription("P", "conditional", "VALIDATION", "d",
                                source_confidence=0.9, grounding_score=0.9)
    bad = GeneratedDescription("P", "conditional", "VALIDATION", "d",
                               source_confidence=0.9, grounding_score=0.5)
    assert good.trustworthy is True
    assert bad.trustworthy is False
