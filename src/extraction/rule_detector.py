"""Rule Detector — Module 3 of RuleForge.

Detects business rules in COBOL paragraphs by analyzing:
- Conditional logic (IF/EVALUATE statements)
- Computational formulas (COMPUTE/ADD/SUBTRACT/MULTIPLY/DIVIDE)
- Validation rules (range checks, format checks)
- 88-level condition usage

Filters out infrastructure code (file I/O status checks, error handling).
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from src.parser.cobol_parser import Paragraph, DataItem, CobolProgram


class RuleType(Enum):
    CONDITIONAL = "conditional"
    COMPUTATIONAL = "computational"
    VALIDATION = "validation"
    CONSTRAINT = "constraint"


class BusinessDomain(Enum):
    PRICING = "PRICING"
    ELIGIBILITY = "ELIGIBILITY"
    VALIDATION = "VALIDATION"
    COMPLIANCE = "COMPLIANCE"
    CALCULATION = "CALCULATION"
    ROUTING = "ROUTING"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectedRule:
    rule_type: RuleType
    paragraph_name: str
    source_code: str
    start_line: int
    end_line: int
    variables_involved: List[str] = field(default_factory=list)
    confidence: float = 0.0
    domain: BusinessDomain = BusinessDomain.UNKNOWN
    description: str = ""


class RuleDetector:
    """Identify business rule patterns in COBOL paragraphs.

    Strategy:
    1. Score each paragraph for "rule-bearing" likelihood
    2. Extract specific rule patterns (IF, EVALUATE, COMPUTE)
    3. Filter infrastructure code (file status, error handling)
    4. Assign confidence scores and business domains
    """

    # Infrastructure patterns — NOT business rules
    INFRA_PATTERNS = [
        r'FILE.?STATUS',
        r'DALYTRAN-STATUS',
        r'ACCTFILE-STATUS',
        r'XREFFILE-STATUS',
        r'TCATBALF-STATUS',
        r'TRANFILE-STATUS',
        r'DALYREJS-STATUS',
        r'WS-INF-STATUS',
        r'RESP\s*\(',
        r'DFHRESP',
        r'SQLCODE',
    ]

    # Paragraph names that are infrastructure (not business logic)
    INFRA_PARA_PATTERNS = [
        r'^\d*-?OPEN',
        r'^\d*-?CLOSE',
        r'^\d*-?INIT',
        r'^\d*-?SETUP',
        r'^\d*-?TERM',
        r'^\d*-?ERROR',
        r'^\d*-?ABEND',
        r'^\d*-?EXIT',
        r'^\d*-?HOUSE',
    ]

    # Business-meaningful variable name patterns
    BUSINESS_VAR_PATTERNS = [
        r'AMT|AMOUNT',
        r'BAL|BALANCE',
        r'RATE|INTEREST',
        r'LIMIT|CREDIT',
        r'FEE|CHARGE|PENALTY',
        r'DISCOUNT|BONUS',
        r'STATUS|ELIGIB',
        r'SCORE|RATING',
        r'AGE|DOB|DATE',
        r'INCOME|SALARY',
        r'LOAN|MORTGAGE',
        r'ACCT|ACCOUNT',
        r'CUST|CUSTOMER',
        r'TRAN|TRANSACTION',
        r'TYPE|CATEGORY|CLASS',
        r'TOTAL|SUM|COUNT',
        r'TAX|DEDUCT',
        r'MIN|MAX|THRESH',
    ]

    def __init__(self, program: CobolProgram):
        self.program = program
        self.data_item_names = {d.name.upper() for d in program.data_items}
        self.business_vars = self._identify_business_variables()

    def _identify_business_variables(self) -> set:
        """Identify which variables are likely business-meaningful."""
        business = set()
        for item in self.program.data_items:
            name_upper = item.name.upper()
            for pattern in self.BUSINESS_VAR_PATTERNS:
                if re.search(pattern, name_upper):
                    business.add(name_upper)
                    break
        return business

    def detect_all_rules(self) -> List[DetectedRule]:
        """Detect rules in all paragraphs of the program."""
        all_rules = []
        for paragraph in self.program.paragraphs:
            rules = self.detect_rules_in_paragraph(paragraph)
            all_rules.extend(rules)
        return all_rules

    def detect_rules_in_paragraph(self, paragraph: Paragraph) -> List[DetectedRule]:
        """Detect business rules in a single paragraph."""
        # Skip infrastructure paragraphs
        if self._is_infrastructure_paragraph(paragraph):
            return []

        rules = []

        # Detect each rule type
        conditional_rules = self._detect_conditional_rules(paragraph)
        computational_rules = self._detect_computational_rules(paragraph)
        validation_rules = self._detect_validation_rules(paragraph)

        rules.extend(conditional_rules)
        rules.extend(computational_rules)
        rules.extend(validation_rules)

        # Remove low-confidence rules
        rules = [r for r in rules if r.confidence >= 0.4]

        # Assign business domains
        for rule in rules:
            rule.domain = self._classify_domain(rule)

        return rules

    def _is_infrastructure_paragraph(self, paragraph: Paragraph) -> bool:
        """Check if paragraph is infrastructure (not business logic)."""
        name_upper = paragraph.name.upper()

        # Check paragraph name patterns
        for pattern in self.INFRA_PARA_PATTERNS:
            if re.search(pattern, name_upper, re.IGNORECASE):
                # BUT: if it has business variables in IF conditions, keep it
                code_upper = paragraph.raw_code.upper()
                business_var_count = sum(
                    1 for v in self.business_vars if v in code_upper
                )
                if business_var_count < 2:
                    return True

        return False

    def _detect_conditional_rules(self, paragraph: Paragraph) -> List[DetectedRule]:
        """Detect IF and EVALUATE statements containing business logic."""
        rules = []
        code = paragraph.raw_code
        code_upper = code.upper()

        # --- EVALUATE detection ---
        eval_matches = list(re.finditer(
            r'EVALUATE\s+(.+?)(?:\n|\r)',
            code_upper
        ))
        for match in eval_matches:
            # Find the full EVALUATE block
            eval_start = match.start()
            eval_end = self._find_end_evaluate(code_upper, eval_start)
            eval_block = code[eval_start:eval_end]

            # Count WHEN clauses (indicates decision complexity)
            when_count = len(re.findall(r'\bWHEN\b', eval_block, re.IGNORECASE))

            # Extract variables involved
            variables = self._extract_variables_from_code(eval_block)
            business_vars = [v for v in variables if v in self.business_vars]

            # Score confidence
            confidence = self._score_conditional_confidence(
                eval_block, business_vars, when_count
            )

            if confidence >= 0.4:
                rules.append(DetectedRule(
                    rule_type=RuleType.CONDITIONAL,
                    paragraph_name=paragraph.name,
                    source_code=eval_block.strip(),
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=variables,
                    confidence=confidence,
                    description=f"EVALUATE with {when_count} WHEN clauses"
                ))

        # --- IF detection (complex business IF, not simple file status) ---
        if_blocks = self._extract_if_blocks(code, code_upper)
        for if_block in if_blocks:
            # Skip infrastructure IF statements
            if self._is_infrastructure_if(if_block):
                continue

            variables = self._extract_variables_from_code(if_block)
            business_vars = [v for v in variables if v in self.business_vars]

            # Count nesting depth
            nesting = if_block.upper().count('IF ') - if_block.upper().count('END-IF')
            nesting = max(1, if_block.upper().count('IF '))

            confidence = self._score_conditional_confidence(
                if_block, business_vars, nesting
            )

            if confidence >= 0.4 and business_vars:
                rules.append(DetectedRule(
                    rule_type=RuleType.CONDITIONAL,
                    paragraph_name=paragraph.name,
                    source_code=if_block.strip(),
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=variables,
                    confidence=confidence,
                    description=f"IF with {nesting} condition(s), {len(business_vars)} business vars"
                ))

        return rules

    def _detect_computational_rules(self, paragraph: Paragraph) -> List[DetectedRule]:
        """Detect COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE with business meaning."""
        rules = []
        code = paragraph.raw_code
        code_upper = code.upper()

        # COMPUTE statements
        compute_matches = re.finditer(
            r'COMPUTE\s+([\w-]+)\s*=\s*(.+?)(?:\.\s*$|\n\s*(?=[A-Z]))',
            code_upper,
            re.MULTILINE | re.DOTALL
        )
        for match in compute_matches:
            target_var = match.group(1).strip()
            expression = match.group(2).strip()
            full_statement = match.group(0).strip()

            variables = self._extract_variables_from_code(full_statement)
            business_vars = [v for v in variables if v in self.business_vars]

            confidence = 0.5
            if business_vars:
                confidence += 0.2 * min(len(business_vars), 3)
            if any(op in expression for op in ['*', '/', '**']):
                confidence += 0.1

            if confidence >= 0.4:
                rules.append(DetectedRule(
                    rule_type=RuleType.COMPUTATIONAL,
                    paragraph_name=paragraph.name,
                    source_code=full_statement,
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=variables,
                    confidence=min(confidence, 1.0),
                    description=f"COMPUTE: {target_var} = {expression[:50]}"
                ))

        # ADD statements with business variables
        add_matches = re.finditer(
            r'ADD\s+([\w-]+)\s+TO\s+([\w-]+)',
            code_upper
        )
        for match in add_matches:
            source_var = match.group(1)
            target_var = match.group(2)
            variables = [source_var, target_var]
            business_vars = [v for v in variables if v in self.business_vars]

            if business_vars:
                rules.append(DetectedRule(
                    rule_type=RuleType.COMPUTATIONAL,
                    paragraph_name=paragraph.name,
                    source_code=match.group(0),
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=variables,
                    confidence=0.6 if len(business_vars) >= 2 else 0.4,
                    description=f"ADD {source_var} TO {target_var}"
                ))

        # SUBTRACT statements
        sub_matches = re.finditer(
            r'SUBTRACT\s+([\w-]+)\s+FROM\s+([\w-]+)',
            code_upper
        )
        for match in sub_matches:
            source_var = match.group(1)
            target_var = match.group(2)
            variables = [source_var, target_var]
            business_vars = [v for v in variables if v in self.business_vars]

            if business_vars:
                rules.append(DetectedRule(
                    rule_type=RuleType.COMPUTATIONAL,
                    paragraph_name=paragraph.name,
                    source_code=match.group(0),
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=variables,
                    confidence=0.6 if len(business_vars) >= 2 else 0.4,
                    description=f"SUBTRACT {source_var} FROM {target_var}"
                ))

        return rules

    def _detect_validation_rules(self, paragraph: Paragraph) -> List[DetectedRule]:
        """Detect data validation patterns (range checks, format checks)."""
        rules = []
        code_upper = paragraph.raw_code.upper()

        # Pattern: IF variable < value OR variable > value (range check)
        range_checks = re.finditer(
            r'IF\s+([\w-]+)\s*(<|>|<=|>=|=|NOT\s*=|LESS|GREATER|EQUAL)\s*(\d+)',
            code_upper
        )
        for match in range_checks:
            var_name = match.group(1)
            operator = match.group(2)
            value = match.group(3)

            if var_name in self.business_vars:
                rules.append(DetectedRule(
                    rule_type=RuleType.VALIDATION,
                    paragraph_name=paragraph.name,
                    source_code=match.group(0),
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=[var_name],
                    confidence=0.7,
                    description=f"Validation: {var_name} {operator} {value}"
                ))

        # Pattern: IF variable = SPACES / ZEROS / LOW-VALUES (empty check)
        empty_checks = re.finditer(
            r'IF\s+([\w-]+)\s*=\s*(SPACES?|ZEROS?|ZEROES|LOW-VALUES?)',
            code_upper
        )
        for match in empty_checks:
            var_name = match.group(1)
            check_value = match.group(2)

            if var_name in self.business_vars:
                rules.append(DetectedRule(
                    rule_type=RuleType.VALIDATION,
                    paragraph_name=paragraph.name,
                    source_code=match.group(0),
                    start_line=paragraph.start_line,
                    end_line=paragraph.end_line,
                    variables_involved=[var_name],
                    confidence=0.6,
                    description=f"Empty check: {var_name} = {check_value}"
                ))

        # Pattern: IF variable IS (NOT) NUMERIC
        numeric_checks = re.finditer(
            r'IF\s+([\w-]+)\s+IS\s+(NOT\s+)?NUMERIC',
            code_upper
        )
        for match in numeric_checks:
            var_name = match.group(1)
            rules.append(DetectedRule(
                rule_type=RuleType.VALIDATION,
                paragraph_name=paragraph.name,
                source_code=match.group(0),
                start_line=paragraph.start_line,
                end_line=paragraph.end_line,
                variables_involved=[var_name],
                confidence=0.7,
                description=f"Numeric validation: {var_name}"
            ))

        return rules

    # ═══════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════

    def _extract_if_blocks(self, code: str, code_upper: str) -> List[str]:
        """Extract top-level IF blocks from paragraph code."""
        blocks = []
        lines = code.split('\n')
        in_if = False
        if_depth = 0
        current_block = []

        for line in lines:
            line_upper = line.upper().strip()

            if re.match(r'^IF\b', line_upper) and not in_if:
                in_if = True
                if_depth = 1
                current_block = [line]
            elif in_if:
                current_block.append(line)
                # Count nesting
                if_count = len(re.findall(r'\bIF\b', line_upper))
                end_if_count = len(re.findall(r'\bEND-IF\b', line_upper))
                if_depth += if_count - end_if_count

                if if_depth <= 0 or line_upper.rstrip('.').strip() == 'END-IF':
                    blocks.append('\n'.join(current_block))
                    in_if = False
                    if_depth = 0
                    current_block = []

        # Capture unclosed IF (period-terminated)
        if current_block:
            blocks.append('\n'.join(current_block))

        return blocks

    def _find_end_evaluate(self, code_upper: str, start: int) -> int:
        """Find the END-EVALUATE position for an EVALUATE starting at 'start'."""
        end_pos = code_upper.find('END-EVALUATE', start)
        if end_pos != -1:
            return end_pos + len('END-EVALUATE')
        # Look for period-terminated EVALUATE
        next_period = code_upper.find('.', start + 20)
        if next_period != -1:
            return next_period + 1
        return len(code_upper)

    def _is_infrastructure_if(self, if_block: str) -> bool:
        """Check if an IF block is just infrastructure (file status, error check)."""
        upper = if_block.upper()
        for pattern in self.INFRA_PATTERNS:
            if re.search(pattern, upper):
                return True
        return False

    def _extract_variables_from_code(self, code: str) -> List[str]:
        """Extract variable names referenced in a code block."""
        code_upper = code.upper()
        found = []
        for var_name in self.data_item_names:
            if var_name in code_upper and len(var_name) > 2:
                found.append(var_name)
        return list(set(found))

    def _score_conditional_confidence(self, code: str, business_vars: list, complexity: int) -> float:
        """Score confidence that a conditional block is a business rule."""
        score = 0.3  # Base score

        # More business variables = more likely a real business rule
        score += 0.15 * min(len(business_vars), 4)

        # Higher complexity (more branches) = more interesting rule
        if complexity >= 3:
            score += 0.2
        elif complexity >= 2:
            score += 0.1

        # Contains MOVE to status/result variable = decision output
        code_upper = code.upper()
        if re.search(r'MOVE\s+.+\s+TO\s+.*(STATUS|RESULT|FLAG|ELIG|APPROV|REJECT)', code_upper):
            score += 0.2

        # Contains SET ... TO TRUE (88-level decision)
        if 'SET ' in code_upper and 'TO TRUE' in code_upper:
            score += 0.15

        # Penalty: mostly DISPLAY statements (just logging)
        display_count = code_upper.count('DISPLAY ')
        if display_count > 2 and len(business_vars) < 2:
            score -= 0.2

        return min(max(score, 0.0), 1.0)

    def _classify_domain(self, rule: DetectedRule) -> BusinessDomain:
        """Classify which business domain a rule belongs to."""
        vars_upper = ' '.join(rule.variables_involved).upper()
        code_upper = rule.source_code.upper()
        combined = vars_upper + ' ' + code_upper

        if re.search(r'RATE|INTEREST|FEE|CHARGE|DISCOUNT|PRICE', combined):
            return BusinessDomain.PRICING
        elif re.search(r'ELIG|APPROV|REJECT|QUALIFY|VALID', combined):
            return BusinessDomain.ELIGIBILITY
        elif re.search(r'LIMIT|RANGE|CHECK|NUMERIC|FORMAT', combined):
            return BusinessDomain.VALIDATION
        elif re.search(r'COMPLY|REGULAT|AUDIT|REPORT', combined):
            return BusinessDomain.COMPLIANCE
        elif re.search(r'COMPUTE|CALC|TOTAL|SUM|BAL|AMT|AMOUNT', combined):
            return BusinessDomain.CALCULATION
        elif re.search(r'ROUTE|TYPE|CATEGORY|CODE|CLASS', combined):
            return BusinessDomain.ROUTING
        else:
            return BusinessDomain.UNKNOWN


# ═══════════════════════════════════════════════════
# RUN DIRECTLY TO TEST
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from src.parser.cobol_parser import CobolParser

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        # Default test file
        default = Path("data/cobol_corpus/aws_card_demo/app/app-transaction-type-db2/cbl/COBTUPDT.cbl")
        if default.exists():
            file_path = default
        else:
            print("Usage: python -m src.extraction.rule_detector <file.cbl>")
            print("Or run from project root with test corpus downloaded.")
            sys.exit(1)

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    # Parse
    parser = CobolParser()
    program = parser.parse_file(file_path)

    # Detect rules
    detector = RuleDetector(program)
    rules = detector.detect_all_rules()

    # Display results
    print("=" * 70)
    print("  RULEFORGE — RULE DETECTOR v0.1")
    print("=" * 70)
    print(f"  Program      : {program.name}")
    print(f"  Paragraphs   : {len(program.paragraphs)}")
    print(f"  Data Items   : {len(program.data_items)}")
    print(f"  Business Vars: {len(detector.business_vars)}")
    print(f"  Rules Found  : {len(rules)}")
    print("=" * 70)

    if rules:
        # Group by type
        by_type = {}
        for r in rules:
            by_type.setdefault(r.rule_type.value, []).append(r)

        print(f"\n  RULES BY TYPE:")
        print(f"  " + "-" * 60)
        for rtype, rlist in by_type.items():
            print(f"    {rtype.upper():<15} : {len(rlist)} rules")

        print(f"\n  DETAILED RULES:")
        print(f"  " + "-" * 60)
        for i, rule in enumerate(rules, 1):
            print(f"\n  Rule #{i}")
            print(f"    Type       : {rule.rule_type.value}")
            print(f"    Paragraph  : {rule.paragraph_name}")
            print(f"    Domain     : {rule.domain.value}")
            print(f"    Confidence : {rule.confidence:.2f}")
            print(f"    Description: {rule.description}")
            print(f"    Variables  : {', '.join(rule.variables_involved[:5])}")
            # Show first 3 lines of source
            src_lines = rule.source_code.strip().split('\n')[:3]
            print(f"    Code Preview:")
            for line in src_lines:
                print(f"      | {line.rstrip()}")
            if len(rule.source_code.strip().split('\n')) > 3:
                print(f"      | ... ({len(rule.source_code.strip().split(chr(10)))} lines total)")

    else:
        print("\n  No business rules detected in this program.")
        print("  (May be infrastructure-only code)")

    print("\n" + "=" * 70)
    print("  DETECTION COMPLETE")
    print("=" * 70)
