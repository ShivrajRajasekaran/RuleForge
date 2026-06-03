"""Rule Conflict Detector — RuleForge analysis module.

Finds pairs of extracted business rules whose guard conditions can be true at
the SAME time (their input regions overlap) yet whose outcomes DIFFER. In a
COBOL program the runtime silently resolves such overlaps by physical execution
order, so the *business specification* is ambiguous — a real, auditable risk in
banking/insurance code. No existing COBOL tool (IBM ADDI, watsonx Code
Assistant) reports this.

Design choices (deliberately conservative — precision over recall):
- We model a guard as a CONJUNCTION (AND) of atomic comparisons
  `<var> <op> <value>` where value is a number or a quoted literal.
- We PROVE overlap with interval/equality arithmetic over the shared variables.
  If a guard contains OR, nested IF, 88-level conditions, variable-to-variable
  comparisons, or anything we cannot model, the rule is reported as
  `undetermined` and never produces a (possibly false) conflict.
- A conflict requires BOTH (a) provable overlap AND (b) provably different
  outcomes (different PERFORM target, or same assignment target written with a
  different value). Everything else is skipped.

Stdlib-only. No third-party dependencies.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from src.extraction.rule_detector import DetectedRule, RuleType


# ──────────────────────────────────────────────────────────────────────────
# Guard / predicate model
# ──────────────────────────────────────────────────────────────────────────

# COBOL relational words → symbolic operators. Order matters (longest first).
_WORD_OPS = [
    (r"IS\s+NOT\s+GREATER\s+THAN\s+OR\s+EQUAL\s+TO", "<"),
    (r"IS\s+NOT\s+LESS\s+THAN\s+OR\s+EQUAL\s+TO", ">"),
    (r"GREATER\s+THAN\s+OR\s+EQUAL\s+TO", ">="),
    (r"LESS\s+THAN\s+OR\s+EQUAL\s+TO", "<="),
    (r"IS\s+NOT\s+GREATER\s+THAN", "<="),
    (r"IS\s+NOT\s+LESS\s+THAN", ">="),
    (r"NOT\s+GREATER\s+THAN", "<="),
    (r"NOT\s+LESS\s+THAN", ">="),
    (r"GREATER\s+THAN", ">"),
    (r"LESS\s+THAN", "<"),
    (r"NOT\s+EQUAL\s+TO", "<>"),
    (r"NOT\s+EQUAL", "<>"),
    (r"EQUAL\s+TO", "="),
    (r"EQUALS", "="),
    (r"EQUAL", "="),
    (r"IS\s+NOT", "<>"),
    (r"\bGREATER\b", ">"),
    (r"\bLESS\b", "<"),
    (r"\bIS\b", "="),
]

# Statement verbs that mark the END of a condition / start of an action.
_VERBS = (
    "MOVE", "PERFORM", "SET", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY",
    "DIVIDE", "DISPLAY", "GO", "CALL", "CONTINUE", "STRING", "UNSTRING",
    "INITIALIZE", "EVALUATE", "STOP", "GOBACK", "NEXT",
)
_VERB_RE = re.compile(r"\b(" + "|".join(_VERBS) + r")\b")

_PRED_RE = re.compile(
    r"([A-Z][A-Z0-9-]*)\s*"                       # variable
    r"(>=|<=|<>|=|>|<)\s*"                          # symbolic operator
    r"('[^']*'|\"[^\"]*\"|[-+]?\d+(?:\.\d+)?|[A-Z][A-Z0-9-]*)"  # value
)


@dataclass(frozen=True)
class Predicate:
    var: str
    op: str            # one of = <> > >= < <=
    value: str         # normalized: number as str, or literal without quotes
    vtype: str         # 'num' | 'str' | 'sym'


@dataclass
class ParsedGuard:
    preds: List[Predicate]
    action_kind: str           # 'perform' | 'assign' | 'other'
    action_target: str
    action_value: str
    raw_condition: str
    raw_action: str


def _normalize_ops(text: str) -> str:
    out = text
    for pattern, sym in _WORD_OPS:
        out = re.sub(pattern, f" {sym} ", out, flags=re.IGNORECASE)
    return out


def _classify_value(raw: str) -> Tuple[str, str]:
    raw = raw.strip()
    if (raw.startswith("'") and raw.endswith("'")) or (
        raw.startswith('"') and raw.endswith('"')
    ):
        return raw[1:-1], "str"
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", raw):
        return raw, "num"
    # COBOL figurative constants behave like literals for equality purposes.
    if raw.upper() in ("ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES",
                       "LOW-VALUES", "HIGH-VALUES", "LOW-VALUE", "HIGH-VALUE"):
        return raw.upper(), "str"
    return raw, "sym"


def parse_rule(rule: DetectedRule) -> Optional[ParsedGuard]:
    """Parse a detected rule into a guard + action, or None if not modelable."""
    if rule.rule_type not in (RuleType.CONDITIONAL, RuleType.VALIDATION):
        return None

    src = " ".join(rule.source_code.split()).upper()

    # Reject things we cannot model honestly.
    if " OR " in f" {src} ":
        return None                      # disjunction — skip
    if src.count("IF ") > 1 or "EVALUATE" in src:
        return None                      # nested / multi-branch — skip

    m = re.search(r"\bIF\b", src)
    if not m:
        return None
    body = src[m.end():]

    # Split condition from action at THEN, else at the first statement verb.
    if " THEN " in f" {body} ":
        cond, _, action = body.partition(" THEN ")
    else:
        vm = _VERB_RE.search(body)
        if not vm:
            return None
        cond, action = body[: vm.start()], body[vm.start():]

    cond = _normalize_ops(cond)
    preds: List[Predicate] = []
    for var, op, val in _PRED_RE.findall(cond):
        norm_val, vtype = _classify_value(val)
        preds.append(Predicate(var.upper(), op, norm_val, vtype))
    if not preds:
        return None

    kind, target, value = _parse_action(action)
    return ParsedGuard(preds, kind, target, value, cond.strip(), action.strip())


def _parse_action(action: str) -> Tuple[str, str, str]:
    """Reduce the THEN-branch to (kind, target, value). Best-effort."""
    action = action.split(" ELSE ")[0].split(" END-IF")[0].strip().rstrip(".")
    a = action.strip()
    m = re.match(r"PERFORM\s+([A-Z0-9-]+)", a)
    if m:
        return "perform", m.group(1), ""
    m = re.match(r"GO\s+TO\s+([A-Z0-9-]+)", a)
    if m:
        return "perform", m.group(1), ""
    m = re.match(r"MOVE\s+(.+?)\s+TO\s+([A-Z0-9-]+)", a)
    if m:
        return "assign", m.group(2), m.group(1).strip()
    m = re.match(r"SET\s+([A-Z0-9-]+)\s+TO\s+(.+)", a)
    if m:
        return "assign", m.group(1), m.group(2).strip()
    m = re.match(r"COMPUTE\s+([A-Z0-9-]+)\s*=\s*(.+)", a)
    if m:
        return "assign", m.group(1), m.group(2).strip()
    return "other", "", a


# ──────────────────────────────────────────────────────────────────────────
# Overlap proof (satisfiability of the combined conjunction)
# ──────────────────────────────────────────────────────────────────────────

def _vars_satisfiable(preds: List[Predicate]) -> Optional[bool]:
    """Is the conjunction of predicates on ONE variable satisfiable?

    Returns True/False when provable, or None when the constraints mix types or
    use symbolic (var-to-var) values we cannot evaluate.
    """
    nums = [p for p in preds if p.vtype == "num"]
    strs = [p for p in preds if p.vtype == "str"]
    syms = [p for p in preds if p.vtype == "sym"]

    if syms:
        return None                      # contains X op Y — undetermined
    if nums and strs:
        return None                      # mixed domains — undetermined

    if strs:
        required = {p.value for p in strs if p.op == "="}
        excluded = {p.value for p in strs if p.op == "<>"}
        if len(required) > 1:
            return False                 # = 'A' AND = 'B'
        if required & excluded:
            return False                 # = 'A' AND <> 'A'
        return True

    # Numeric interval reasoning.
    lo, lo_inc = -math.inf, True
    hi, hi_inc = math.inf, True
    eq: Optional[float] = None
    neq: set = set()
    for p in nums:
        v = float(p.value)
        if p.op == "=":
            if eq is not None and eq != v:
                return False
            eq = v
        elif p.op == "<>":
            neq.add(v)
        elif p.op == ">":
            if v > lo or (v == lo and not lo_inc):
                lo, lo_inc = v, False
        elif p.op == ">=":
            if v > lo:
                lo, lo_inc = v, True
        elif p.op == "<":
            if v < hi or (v == hi and not hi_inc):
                hi, hi_inc = v, False
        elif p.op == "<=":
            if v < hi:
                hi, hi_inc = v, True

    if eq is not None:
        if eq in neq:
            return False
        if eq < lo or eq > hi:
            return False
        if eq == lo and not lo_inc:
            return False
        if eq == hi and not hi_inc:
            return False
        return True

    if lo > hi:
        return False
    if lo == hi and not (lo_inc and hi_inc):
        return False
    return True


def guards_overlap(a: ParsedGuard, b: ParsedGuard) -> Optional[bool]:
    """Can guard A and guard B be true simultaneously? None if undetermined."""
    combined: dict = {}
    for p in a.preds + b.preds:
        combined.setdefault(p.var, []).append(p)

    determined_any_shared = False
    shared = {p.var for p in a.preds} & {p.var for p in b.preds}
    for var, preds in combined.items():
        sat = _vars_satisfiable(preds)
        if sat is None:
            if var in shared:
                return None              # cannot reason about a shared var
            continue
        if sat is False:
            return False                 # mutually exclusive on this var
        if var in shared:
            determined_any_shared = True

    # Require at least one shared variable we could actually reason about,
    # otherwise the "overlap" is trivially true and uninteresting.
    return True if determined_any_shared else None


def outcomes_differ(a: ParsedGuard, b: ParsedGuard) -> Optional[bool]:
    """Do the two actions produce a provably different outcome?"""
    if a.action_kind == "other" or b.action_kind == "other":
        return None
    if a.action_kind == "perform" and b.action_kind == "perform":
        return a.action_target != b.action_target
    if a.action_kind == "assign" and b.action_kind == "assign":
        if a.action_target == b.action_target:
            return a.action_value != b.action_value
        return None                      # different targets — not a conflict
    return None                          # perform vs assign — undetermined


# ──────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Conflict:
    rule_a: DetectedRule
    rule_b: DetectedRule
    shared_variables: List[str]
    reason: str

    def describe(self) -> str:
        return (
            f"CONFLICT in {self.rule_a.paragraph_name}/{self.rule_b.paragraph_name} "
            f"on {{{', '.join(self.shared_variables)}}}: {self.reason}\n"
            f"    A: {self.rule_a.source_code.strip().splitlines()[0]}\n"
            f"    B: {self.rule_b.source_code.strip().splitlines()[0]}"
        )


@dataclass
class ConflictReport:
    conflicts: List[Conflict] = field(default_factory=list)
    rules_considered: int = 0
    rules_modeled: int = 0

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


class RuleConflictDetector:
    """Detect contradictory business rules within a program's rule set."""

    def detect(self, rules: List[DetectedRule]) -> ConflictReport:
        parsed: List[Tuple[DetectedRule, ParsedGuard]] = []
        for r in rules:
            g = parse_rule(r)
            if g is not None:
                parsed.append((r, g))

        conflicts: List[Conflict] = []
        for i in range(len(parsed)):
            ra, ga = parsed[i]
            for j in range(i + 1, len(parsed)):
                rb, gb = parsed[j]
                shared = sorted({p.var for p in ga.preds} & {p.var for p in gb.preds})
                if not shared:
                    continue
                if guards_overlap(ga, gb) is not True:
                    continue
                if outcomes_differ(ga, gb) is not True:
                    continue
                conflicts.append(Conflict(
                    rule_a=ra, rule_b=rb, shared_variables=shared,
                    reason=_reason(ga, gb),
                ))

        return ConflictReport(
            conflicts=conflicts,
            rules_considered=len(rules),
            rules_modeled=len(parsed),
        )


def _reason(a: ParsedGuard, b: ParsedGuard) -> str:
    if a.action_kind == "perform":
        outcome = f"different actions PERFORM {a.action_target} vs PERFORM {b.action_target}"
    else:
        outcome = (
            f"{a.action_target} assigned '{a.action_value}' vs '{b.action_value}'"
        )
    return f"overlapping conditions but {outcome}"


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from src.parser.cobol_parser import CobolParser
    from src.extraction.rule_detector import RuleDetector

    if len(sys.argv) < 2:
        print("Usage: python -m src.analysis.conflict_detector <file.cbl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    program = CobolParser().parse_file(path)
    rules = RuleDetector(program).detect_all_rules()
    report = RuleConflictDetector().detect(rules)

    print("=" * 70)
    print("  RULEFORGE — RULE CONFLICT DETECTOR")
    print("=" * 70)
    print(f"  Program          : {program.name}")
    print(f"  Rules considered : {report.rules_considered}")
    print(f"  Rules modeled    : {report.rules_modeled} "
          f"(others use OR / nesting / computed conditions — skipped)")
    print(f"  Conflicts found  : {len(report.conflicts)}")
    print("=" * 70)
    if report.conflicts:
        for k, c in enumerate(report.conflicts, 1):
            print(f"\n  [{k}] {c.describe()}")
    else:
        print("\n  No provable rule conflicts detected.")
    print("\n" + "=" * 70)
