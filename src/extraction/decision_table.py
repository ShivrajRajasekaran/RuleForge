"""Decision Table Generator — Module 4 of RuleForge.

Converts detected conditional rules (IF/EVALUATE) into formal decision tables.

A Decision Table has:
- CONDITIONS: What is being tested (rows)
- ACTIONS: What happens when conditions are met (rows)
- RULES: Each column represents one path through the logic

Example:
    IF AGE > 65 → SENIOR discount
    IF AGE > 21 AND SCORE >= 750 → APPROVED
    ELSE → REJECTED

Becomes:
    ┌──────────────┬─────────┬─────────┬─────────┐
    │ CONDITIONS   │ Rule 1  │ Rule 2  │ Rule 3  │
    ├──────────────┼─────────┼─────────┼─────────┤
    │ AGE > 65     │ Y       │ N       │ N       │
    │ AGE > 21     │ -       │ Y       │ N       │
    │ SCORE >= 750 │ -       │ Y       │ -       │
    ├──────────────┼─────────┼─────────┼─────────┤
    │ ACTIONS      │         │         │         │
    ├──────────────┼─────────┼─────────┼─────────┤
    │ Result       │ SENIOR  │ APPROVED│ REJECTED│
    └──────────────┴─────────┴─────────┴─────────┘
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

from src.extraction.rule_detector import DetectedRule, RuleType


@dataclass
class Condition:
    """A single condition in a decision table."""
    variable: str
    operator: str
    value: str
    raw_text: str = ""

    def __str__(self):
        return f"{self.variable} {self.operator} {self.value}"


@dataclass
class Action:
    """A single action in a decision table."""
    action_type: str        # MOVE, PERFORM, SET, COMPUTE, ADD, DISPLAY
    target_variable: str    # Variable being modified
    value: str              # Value being assigned/computed
    raw_text: str = ""

    def __str__(self):
        return f"{self.target_variable} = {self.value}"


@dataclass
class RuleColumn:
    """One column (path) in a decision table."""
    condition_values: Dict[int, str] = field(default_factory=dict)  # condition_index → Y/N/-
    actions: List[Action] = field(default_factory=list)
    label: str = ""


@dataclass
class DecisionTable:
    """A complete decision table extracted from a COBOL rule."""
    source_rule: Optional[DetectedRule] = None
    table_type: str = ""        # "EVALUATE" or "IF-ELSE"
    subject: str = ""           # What's being evaluated (e.g., "INPUT-REC-TYPE")
    conditions: List[Condition] = field(default_factory=list)
    actions_header: List[str] = field(default_factory=list)  # Action row labels
    rules: List[RuleColumn] = field(default_factory=list)
    completeness: str = ""      # "complete" or "incomplete" (has ELSE/OTHER?)

    @property
    def num_rules(self) -> int:
        return len(self.rules)

    @property
    def num_conditions(self) -> int:
        return len(self.conditions)

    def to_text(self) -> str:
        """Render decision table as formatted text."""
        if not self.rules:
            return "(Empty decision table)"

        # Calculate column widths
        cond_width = max(
            (len(str(c)) for c in self.conditions),
            default=15
        )
        cond_width = max(cond_width, 15)
        rule_width = 12

        lines = []
        separator = "+" + "-" * (cond_width + 2) + ("+" + "-" * (rule_width + 2)) * len(self.rules) + "+"

        # Header
        lines.append(separator)
        header = f"| {'CONDITIONS':<{cond_width}} |"
        for i, rule in enumerate(self.rules, 1):
            label = rule.label or f"Rule {i}"
            header += f" {label:^{rule_width}} |"
        lines.append(header)
        lines.append(separator)

        # Condition rows
        for ci, cond in enumerate(self.conditions):
            row = f"| {str(cond):<{cond_width}} |"
            for rule in self.rules:
                val = rule.condition_values.get(ci, "-")
                row += f" {val:^{rule_width}} |"
            lines.append(row)

        # Action separator
        lines.append(separator)
        action_header = f"| {'ACTIONS':<{cond_width}} |"
        for _ in self.rules:
            action_header += f" {'':^{rule_width}} |"
        lines.append(action_header)
        lines.append(separator)

        # Action rows
        if self.rules and self.rules[0].actions:
            # Collect all unique action targets
            all_targets = []
            for rule in self.rules:
                for action in rule.actions:
                    if action.target_variable not in all_targets:
                        all_targets.append(action.target_variable)

            for target in all_targets[:5]:  # Max 5 action rows
                row = f"| {target:<{cond_width}} |"
                for rule in self.rules:
                    val = ""
                    for action in rule.actions:
                        if action.target_variable == target:
                            val = action.value[:rule_width]
                            break
                    row += f" {val:^{rule_width}} |"
                lines.append(row)

        lines.append(separator)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary (for JSON export)."""
        return {
            "type": self.table_type,
            "subject": self.subject,
            "completeness": self.completeness,
            "conditions": [
                {"variable": c.variable, "operator": c.operator, "value": c.value}
                for c in self.conditions
            ],
            "rules": [
                {
                    "label": r.label,
                    "condition_values": r.condition_values,
                    "actions": [
                        {"type": a.action_type, "target": a.target_variable, "value": a.value}
                        for a in r.actions
                    ]
                }
                for r in self.rules
            ]
        }


class DecisionTableGenerator:
    """Convert detected COBOL rules into formal decision tables."""

    def generate_all(self, rules: List[DetectedRule]) -> List[DecisionTable]:
        """Generate decision tables for all conditional rules."""
        tables = []
        for rule in rules:
            if rule.rule_type == RuleType.CONDITIONAL:
                table = self.generate_table(rule)
                if table and table.num_rules > 0:
                    tables.append(table)
        return tables

    def generate_table(self, rule: DetectedRule) -> Optional[DecisionTable]:
        """Generate a decision table from a single conditional rule."""
        code_upper = rule.source_code.upper().strip()

        if code_upper.startswith('EVALUATE'):
            return self._generate_from_evaluate(rule)
        elif code_upper.startswith('IF'):
            return self._generate_from_if(rule)
        else:
            return None

    def _generate_from_evaluate(self, rule: DetectedRule) -> Optional[DecisionTable]:
        """Convert EVALUATE statement to decision table."""
        code = rule.source_code
        code_upper = code.upper()

        # Determine what's being evaluated
        eval_match = re.match(r'EVALUATE\s+(.+?)(?:\s*$|\s+ALSO)', code_upper.split('\n')[0])
        subject = eval_match.group(1).strip() if eval_match else "TRUE"

        # Extract WHEN clauses
        when_blocks = self._extract_when_blocks(code)

        if not when_blocks:
            return None

        table = DecisionTable(
            source_rule=rule,
            table_type="EVALUATE",
            subject=subject,
            completeness="complete" if any(
                'OTHER' in wb['condition'].upper() for wb in when_blocks
            ) else "incomplete"
        )

        # For EVALUATE, each WHEN becomes one condition and one rule column
        if subject == "TRUE":
            # EVALUATE TRUE: each WHEN has its own condition
            for i, wb in enumerate(when_blocks):
                cond_text = wb['condition'].strip()
                if cond_text.upper() == 'OTHER':
                    cond_text = "OTHERWISE"

                # Parse condition
                condition = self._parse_condition(cond_text)
                table.conditions.append(condition)

                # Create rule column
                rule_col = RuleColumn(
                    label=f"Rule {i+1}",
                    condition_values={i: "Y"},
                    actions=self._extract_actions(wb['body'])
                )
                # Set all other conditions to "-" (don't care)
                for j in range(len(when_blocks)):
                    if j != i:
                        rule_col.condition_values[j] = "-"

                table.rules.append(rule_col)
        else:
            # EVALUATE VARIABLE: single condition, multiple values
            condition = Condition(
                variable=subject,
                operator="=",
                value="(see rules)",
                raw_text=f"EVALUATE {subject}"
            )
            table.conditions.append(condition)

            for i, wb in enumerate(when_blocks):
                cond_value = wb['condition'].strip().strip("'\"")
                rule_col = RuleColumn(
                    label=cond_value if cond_value.upper() != 'OTHER' else "OTHERWISE",
                    condition_values={0: cond_value},
                    actions=self._extract_actions(wb['body'])
                )
                table.rules.append(rule_col)

        return table

    def _generate_from_if(self, rule: DetectedRule) -> Optional[DecisionTable]:
        """Convert IF-ELSE statement to decision table."""
        code = rule.source_code
        code_upper = code.upper()

        table = DecisionTable(
            source_rule=rule,
            table_type="IF-ELSE",
            subject="",
        )

        # Extract the condition from the IF statement
        if_match = re.match(r'IF\s+(.+?)(?:\s*$|\s+THEN)', code_upper.split('\n')[0])
        if not if_match:
            # Try multiline condition
            if_match = re.match(r'IF\s+(.+?)(?:\n\s+(?:MOVE|SET|PERFORM|COMPUTE|ADD|DISPLAY|CONTINUE))', code_upper, re.DOTALL)

        if not if_match:
            return None

        condition_text = if_match.group(1).strip()
        condition = self._parse_condition(condition_text)
        table.conditions.append(condition)

        # Extract TRUE branch (between IF and ELSE)
        true_actions = self._extract_if_true_actions(code)
        false_actions = self._extract_if_false_actions(code)

        # TRUE rule column
        true_col = RuleColumn(
            label="TRUE",
            condition_values={0: "Y"},
            actions=true_actions
        )
        table.rules.append(true_col)

        # FALSE rule column (if ELSE exists)
        if false_actions:
            false_col = RuleColumn(
                label="FALSE",
                condition_values={0: "N"},
                actions=false_actions
            )
            table.rules.append(false_col)
            table.completeness = "complete"
        else:
            table.completeness = "incomplete"

        return table

    # ═══════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════

    def _extract_when_blocks(self, code: str) -> List[dict]:
        """Extract WHEN clause blocks from EVALUATE statement."""
        blocks = []
        lines = code.split('\n')
        current_when = None
        current_body = []

        for line in lines:
            line_upper = line.upper().strip()

            if line_upper.startswith('WHEN '):
                # Save previous WHEN block
                if current_when is not None:
                    blocks.append({
                        'condition': current_when,
                        'body': '\n'.join(current_body)
                    })
                # Start new WHEN
                current_when = line_upper[5:].strip()
                current_body = []
            elif line_upper.startswith('EVALUATE') or line_upper.startswith('END-EVALUATE'):
                continue
            elif current_when is not None:
                current_body.append(line)

        # Save last WHEN
        if current_when is not None:
            blocks.append({
                'condition': current_when,
                'body': '\n'.join(current_body)
            })

        return blocks

    def _parse_condition(self, condition_text: str) -> Condition:
        """Parse a condition string into structured Condition object."""
        condition_text = condition_text.strip()

        # Pattern: VARIABLE OPERATOR VALUE
        match = re.match(
            r"([\w-]+)\s*(>=|<=|>|<|=|NOT\s*=|EQUAL|NOT\s+EQUAL|GREATER|LESS)\s*(.+)",
            condition_text,
            re.IGNORECASE
        )
        if match:
            return Condition(
                variable=match.group(1).strip(),
                operator=self._normalize_operator(match.group(2).strip()),
                value=match.group(3).strip().rstrip('.'),
                raw_text=condition_text
            )

        # If can't parse, return as-is
        return Condition(
            variable=condition_text,
            operator="",
            value="",
            raw_text=condition_text
        )

    def _normalize_operator(self, op: str) -> str:
        """Normalize COBOL operators to symbols."""
        op_upper = op.upper().strip()
        mapping = {
            'EQUAL': '=',
            'NOT EQUAL': '!=',
            'GREATER': '>',
            'LESS': '<',
            'NOT=': '!=',
            'NOT =': '!=',
        }
        return mapping.get(op_upper, op)

    def _extract_actions(self, body: str) -> List[Action]:
        """Extract actions from a WHEN/IF body block."""
        actions = []
        body_upper = body.upper()

        # MOVE statements
        for match in re.finditer(r'MOVE\s+(.+?)\s+TO\s+([\w-]+)', body_upper):
            actions.append(Action(
                action_type="MOVE",
                target_variable=match.group(2).strip(),
                value=match.group(1).strip().strip("'\""),
                raw_text=match.group(0)
            ))

        # PERFORM statements
        for match in re.finditer(r'PERFORM\s+([\w-]+)', body_upper):
            actions.append(Action(
                action_type="PERFORM",
                target_variable="(call)",
                value=match.group(1).strip(),
                raw_text=match.group(0)
            ))

        # SET statements
        for match in re.finditer(r'SET\s+([\w-]+)\s+TO\s+(TRUE|FALSE|[\w-]+)', body_upper):
            actions.append(Action(
                action_type="SET",
                target_variable=match.group(1).strip(),
                value=match.group(2).strip(),
                raw_text=match.group(0)
            ))

        # COMPUTE statements
        for match in re.finditer(r'COMPUTE\s+([\w-]+)\s*=\s*(.+?)(?:\.|$)', body_upper):
            actions.append(Action(
                action_type="COMPUTE",
                target_variable=match.group(1).strip(),
                value=match.group(2).strip()[:40],
                raw_text=match.group(0)
            ))

        # ADD statements
        for match in re.finditer(r'ADD\s+([\w-]+)\s+TO\s+([\w-]+)', body_upper):
            actions.append(Action(
                action_type="ADD",
                target_variable=match.group(2).strip(),
                value=f"+{match.group(1).strip()}",
                raw_text=match.group(0)
            ))

        return actions

    def _extract_if_true_actions(self, code: str) -> List[Action]:
        """Extract actions from the TRUE (then) branch of an IF."""
        code_upper = code.upper()
        # Find content between IF condition and ELSE (or END-IF)
        else_pos = self._find_else_position(code_upper)
        if else_pos > 0:
            true_body = code[code.find('\n'):else_pos]
        else:
            end_if_pos = code_upper.rfind('END-IF')
            if end_if_pos > 0:
                true_body = code[code.find('\n'):end_if_pos]
            else:
                true_body = code[code.find('\n'):]

        return self._extract_actions(true_body)

    def _extract_if_false_actions(self, code: str) -> List[Action]:
        """Extract actions from the FALSE (else) branch of an IF."""
        code_upper = code.upper()
        else_pos = self._find_else_position(code_upper)
        if else_pos <= 0:
            return []

        end_if_pos = code_upper.rfind('END-IF')
        if end_if_pos > else_pos:
            false_body = code[else_pos + 4:end_if_pos]
        else:
            false_body = code[else_pos + 4:]

        return self._extract_actions(false_body)

    def _find_else_position(self, code_upper: str) -> int:
        """Find the ELSE that matches the outermost IF."""
        depth = 0
        lines = code_upper.split('\n')
        pos = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('IF '):
                depth += 1
            elif 'END-IF' in stripped:
                depth -= 1
            elif stripped.startswith('ELSE') and depth == 1:
                return pos
            pos += len(line) + 1
        return -1


# ═══════════════════════════════════════════════════
# RUN DIRECTLY TO TEST
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from src.parser.cobol_parser import CobolParser
    from src.extraction.rule_detector import RuleDetector

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        default = Path("data/cobol_corpus/aws_card_demo/app/app-transaction-type-db2/cbl/COBTUPDT.cbl")
        if default.exists():
            file_path = default
        else:
            print("Usage: python -m src.extraction.decision_table <file.cbl>")
            sys.exit(1)

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    # Pipeline: Parse → Detect → Generate Decision Tables
    parser = CobolParser()
    program = parser.parse_file(file_path)

    detector = RuleDetector(program)
    rules = detector.detect_all_rules()

    generator = DecisionTableGenerator()
    tables = generator.generate_all(rules)

    # Display
    print("=" * 70)
    print("  RULEFORGE — DECISION TABLE GENERATOR v0.1")
    print("=" * 70)
    print(f"  Program          : {program.name}")
    print(f"  Rules Detected   : {len(rules)}")
    print(f"  Conditional Rules: {sum(1 for r in rules if r.rule_type == RuleType.CONDITIONAL)}")
    print(f"  Tables Generated : {len(tables)}")
    print("=" * 70)

    for i, table in enumerate(tables, 1):
        print(f"\n  TABLE #{i}: {table.source_rule.paragraph_name}")
        print(f"  Type: {table.table_type} | Subject: {table.subject}")
        print(f"  Conditions: {table.num_conditions} | Rules: {table.num_rules}")
        print(f"  Completeness: {table.completeness}")
        print()
        print(table.to_text())
        print()

    if not tables:
        print("\n  No decision tables generated.")
        print("  (Rules may be computational or too simple for tabular form)")

    print("=" * 70)
    print("  GENERATION COMPLETE")
    print("=" * 70)
