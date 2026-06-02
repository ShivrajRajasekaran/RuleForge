"""Shared pytest fixtures for RuleForge.

A small, self-contained COBOL program is used so the unit tests are fast and
do NOT depend on the downloaded corpus or a running Ollama server.
"""

import sys
from pathlib import Path

# Make the project root importable when pytest is run from anywhere.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.parser.cobol_parser import CobolParser
from src.extraction.rule_detector import RuleDetector
from src.extraction.decision_table import DecisionTableGenerator


# A compact but realistic free-format COBOL program exercising:
#   - PROGRAM-ID extraction
#   - PIC / VALUE clauses and an 88-level condition name
#   - an IF/ELSE conditional rule
#   - a COMPUTE computational rule
#   - an EVALUATE decision
SAMPLE_COBOL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTCALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCT-BALANCE      PIC 9(7)V99 VALUE ZERO.
       01 WS-CREDIT-LIMIT      PIC 9(7)V99 VALUE 5000.00.
       01 WS-INTEREST-RATE     PIC 9V999   VALUE 0.015.
       01 WS-CUST-AGE          PIC 9(3)    VALUE ZERO.
       01 WS-APPROVAL-STATUS   PIC X(8)    VALUE SPACES.
          88 APPROVED          VALUE 'APPROVED'.
          88 REJECTED          VALUE 'REJECTED'.
       01 WS-FEE-AMOUNT        PIC 9(5)V99 VALUE ZERO.
       PROCEDURE DIVISION.
       1000-MAIN.
           PERFORM 2000-CHECK-ELIGIBILITY
           PERFORM 3000-CALCULATE-FEE
           STOP RUN.
       2000-CHECK-ELIGIBILITY.
           IF WS-CUST-AGE > 21 AND WS-ACCT-BALANCE > 1000
               MOVE 'APPROVED' TO WS-APPROVAL-STATUS
           ELSE
               MOVE 'REJECTED' TO WS-APPROVAL-STATUS
           END-IF.
       3000-CALCULATE-FEE.
           COMPUTE WS-FEE-AMOUNT = WS-ACCT-BALANCE * WS-INTEREST-RATE
           EVALUATE TRUE
               WHEN WS-ACCT-BALANCE > WS-CREDIT-LIMIT
                   MOVE 'REJECTED' TO WS-APPROVAL-STATUS
               WHEN OTHER
                   CONTINUE
           END-EVALUATE.
"""


@pytest.fixture
def sample_cbl(tmp_path):
    """Write the sample program to a temp .cbl file and return its path."""
    p = tmp_path / "TESTCALC.cbl"
    p.write_text(SAMPLE_COBOL, encoding="utf-8")
    return p


@pytest.fixture
def program(sample_cbl):
    """Parsed CobolProgram for the sample."""
    return CobolParser().parse_file(sample_cbl)


@pytest.fixture
def rules(program):
    """Detected rules for the sample."""
    return RuleDetector(program).detect_all_rules()


@pytest.fixture
def tables(rules):
    """Decision tables for the sample."""
    return DecisionTableGenerator().generate_all(rules)
