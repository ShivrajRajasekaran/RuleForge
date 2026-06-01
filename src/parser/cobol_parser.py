"""COBOL Parser - Module 1 of RuleForge.

Handles both free-format and IBM fixed-format COBOL (with sequence numbers).
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
import re


@dataclass
class Paragraph:
    name: str
    start_line: int
    end_line: int
    raw_code: str


@dataclass
class DataItem:
    name: str
    level: int
    pic_clause: Optional[str] = None
    value_clause: Optional[str] = None
    is_88_level: bool = False


@dataclass
class CobolProgram:
    name: str
    source_path: str
    loc: int
    paragraphs: List[Paragraph] = field(default_factory=list)
    data_items: List[DataItem] = field(default_factory=list)


class CobolParser:
    """Parse COBOL source files into structured representation.

    Handles:
    - IBM fixed-format (columns 1-6 sequence, 7 indicator, 8-72 code, 73-80 ID)
    - Free-format COBOL
    - COPY statements (noted, not expanded yet)
    """

    def __init__(self):
        self.is_fixed_format = False

    def parse_file(self, file_path: Path) -> CobolProgram:
        """Parse a .cbl file and return structured program."""
        source = file_path.read_text(encoding='utf-8')
        raw_lines = source.splitlines()

        # Detect format and clean lines
        self.is_fixed_format = self._detect_fixed_format(raw_lines)
        lines = self._clean_lines(raw_lines)

        program = CobolProgram(
            name=self._extract_program_id(lines),
            source_path=str(file_path),
            loc=len(raw_lines)
        )

        program.data_items = self._extract_data_items(lines)
        program.paragraphs = self._extract_paragraphs(lines)

        return program

    def _detect_fixed_format(self, lines: List[str]) -> bool:
        """Detect if COBOL uses IBM fixed format.

        Fixed format indicators:
        - Sequence numbers in cols 1-6 (digits)
        - OR lines are exactly 80 chars with trailing numbers in cols 73-80
        - OR code consistently starts at column 8+
        """
        for line in lines[:30]:
            if len(line) < 7:
                continue
            # Classic: digits in cols 1-6
            if line[:6].strip().isdigit() and line[:6].strip():
                return True
            # Alternative: line is 80 chars with digits in cols 73-80
            if len(line) >= 80 and line[72:80].strip().isdigit():
                return True
        return False

    def _clean_lines(self, raw_lines: List[str]) -> List[str]:
        """Strip sequence numbers and identification area.

        IBM fixed format: cols 1-6 = sequence, col 7 = indicator, cols 8-72 = code, cols 73-80 = ID
        Handles both numeric-sequence and space-padded column 1-6 variants.
        """
        cleaned = []
        for line in raw_lines:
            if self.is_fixed_format:
                if len(line) < 7:
                    cleaned.append('')
                    continue
                # Column 7 (index 6) = indicator
                indicator = line[6]
                if indicator == '*' or indicator == '/':
                    cleaned.append('')  # Comment or page break
                    continue
                # Extract columns 8-72 (index 7 to 71) = Area A + Area B
                code = line[7:72] if len(line) >= 72 else line[7:]
                cleaned.append(code)
            else:
                # Free format
                stripped = line.strip()
                if stripped.startswith('*>'):
                    cleaned.append('')
                    continue
                cleaned.append(line)
        return cleaned

    def _extract_program_id(self, lines: List[str]) -> str:
        """Find PROGRAM-ID in IDENTIFICATION DIVISION."""
        for line in lines:
            upper = line.upper().strip()
            if 'PROGRAM-ID' in upper:
                # Handle: PROGRAM-ID. COACCT01 IS INITIAL.
                match = re.search(r'PROGRAM-ID[\.\s]+(\w+)', upper)
                if match:
                    return match.group(1)
        return "UNKNOWN"

    def _extract_paragraphs(self, lines: List[str]) -> List[Paragraph]:
        """Extract paragraph names and boundaries from PROCEDURE DIVISION.

        In cleaned fixed-format COBOL:
        - Area A = columns 1-4 (where paragraphs/sections start)
        - Area B = columns 5+ (where statements live)
        A paragraph name starts in Area A, is a single token, ends with period.
        """
        paragraphs = []
        in_procedure = False
        current_para = None

        cobol_keywords = {
            'IF', 'ELSE', 'END-IF', 'EVALUATE', 'WHEN', 'END-EVALUATE',
            'PERFORM', 'MOVE', 'COMPUTE', 'ADD', 'SUBTRACT', 'MULTIPLY',
            'DIVIDE', 'DISPLAY', 'ACCEPT', 'READ', 'WRITE', 'OPEN',
            'CLOSE', 'STOP', 'GOBACK', 'EXIT', 'CALL', 'STRING',
            'UNSTRING', 'INSPECT', 'SET', 'INITIALIZE', 'NOT',
            'END-PERFORM', 'END-READ', 'END-WRITE', 'END-CALL',
            'END-STRING', 'END-UNSTRING', 'CONTINUE', 'NEXT',
            'WHEN', 'OTHER', 'ALSO', 'UNTIL', 'VARYING',
        }

        for i, line in enumerate(lines, 1):
            upper = line.upper().strip()

            if 'PROCEDURE DIVISION' in upper:
                in_procedure = True
                continue

            if not in_procedure:
                continue

            if not line.strip():
                continue

            # After cleaning, Area A = first 4 characters of the line
            # If text starts in positions 0-3, it's Area A (paragraph/section)
            # If text starts at position 4+, it's Area B (statements)

            # Check leading spaces
            if not line or not line.rstrip():
                continue

            leading_spaces = len(line) - len(line.lstrip())
            content = line.strip()

            # AREA A detection:
            # Fixed format (after clean): 0-3 leading spaces = Area A
            # Free format: 7 leading spaces = Area A (cols 8-11)
            area_a_limit = 3 if self.is_fixed_format else 7
            if leading_spaces <= area_a_limit and content:
                # Check if it's a paragraph name (single word + period)
                # Handle: "1000-CONTROL." or "MAIN-LOGIC." or "CHECK-ELIGIBILITY."
                potential_name = content.rstrip('.')

                is_paragraph = (
                    content.endswith('.') and
                    ' ' not in potential_name and
                    potential_name.upper() not in cobol_keywords and
                    len(potential_name) > 1 and
                    re.match(r'^[A-Za-z0-9][\w-]*$', potential_name) and
                    'DIVISION' not in content.upper() and
                    'SECTION' not in content.upper()
                )

                is_section = (
                    content.upper().endswith('SECTION.') and
                    len(content.split()) <= 2
                )

                if is_paragraph or is_section:
                    # Save previous paragraph
                    if current_para:
                        current_para.end_line = i - 1
                        current_para.raw_code = '\n'.join(
                            lines[current_para.start_line - 1:current_para.end_line]
                        )
                        paragraphs.append(current_para)

                    # Start new paragraph
                    name = potential_name if is_paragraph else content.replace('.', '').strip()
                    current_para = Paragraph(
                        name=name,
                        start_line=i,
                        end_line=i,
                        raw_code=""
                    )

        # Save last paragraph
        if current_para:
            current_para.end_line = len(lines)
            current_para.raw_code = '\n'.join(
                lines[current_para.start_line - 1:current_para.end_line]
            )
            paragraphs.append(current_para)

        return paragraphs

    def _extract_data_items(self, lines: List[str]) -> List[DataItem]:
        """Extract variables from DATA DIVISION."""
        items = []
        in_data = False

        for line in lines:
            upper = line.upper().strip()

            if 'DATA DIVISION' in upper:
                in_data = True
                continue
            if 'PROCEDURE DIVISION' in upper:
                break

            if not in_data:
                continue

            stripped = line.strip()
            if not stripped:
                continue

            # Match level number at start
            match = re.match(r'^(\d{1,2})\s+([\w-]+)', stripped)
            if not match:
                continue

            level = int(match.group(1))
            name = match.group(2).rstrip('.')

            # Skip section headers and filler
            if name.upper() in ('SECTION', 'FILLER', 'SECTION.'):
                continue

            pic = None
            value = None
            is_88 = (level == 88)

            # Find PIC clause
            pic_match = re.search(r'PIC(?:TURE)?\s+([^\s.]+)', stripped, re.IGNORECASE)
            if pic_match:
                pic = pic_match.group(1).rstrip('.')

            # Find VALUE clause
            value_match = re.search(r'VALUE\s+(.+?)(?:\.|$)', stripped, re.IGNORECASE)
            if value_match:
                value = value_match.group(1).strip().rstrip('.')

            items.append(DataItem(
                name=name,
                level=level,
                pic_clause=pic,
                value_clause=value,
                is_88_level=is_88
            ))

        return items


# ═══════════════════════════════════════════════════
# MAIN: Run directly to test
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}")
            sys.exit(1)

        parser = CobolParser()
        result = parser.parse_file(file_path)

        print("=" * 60)
        print("  RULEFORGE PARSER v0.2")
        print("=" * 60)
        print(f"  Program Name  : {result.name}")
        print(f"  Source File   : {result.source_path}")
        print(f"  Lines of Code : {result.loc}")
        print(f"  Format        : {'IBM Fixed' if parser.is_fixed_format else 'Free'}")
        print(f"  Paragraphs   : {len(result.paragraphs)}")
        print(f"  Data Items    : {len(result.data_items)}")
        print("=" * 60)

        if result.paragraphs:
            print("\n  PARAGRAPHS:")
            print("  " + "-" * 50)
            for p in result.paragraphs:
                lines_count = p.end_line - p.start_line + 1
                print(f"    {p.name:<35} ({lines_count} lines)")

        if result.data_items:
            print(f"\n  DATA ITEMS ({len(result.data_items)} total):")
            print("  " + "-" * 50)
            # Show first 30 items
            for d in result.data_items[:30]:
                level_str = f"{d.level:02d}"
                pic_str = d.pic_clause if d.pic_clause else ""
                val_str = f"= {d.value_clause}" if d.value_clause else ""
                flag = " [88]" if d.is_88_level else ""
                print(f"    {level_str}  {d.name:<35} {pic_str:<15} {val_str}{flag}")
            if len(result.data_items) > 30:
                print(f"    ... and {len(result.data_items) - 30} more")

        print("\n" + "=" * 60)
        print("  PARSING COMPLETE")
        print("=" * 60)

    else:
        # Demo mode
        print("=" * 60)
        print("  RULEFORGE PARSER v0.2 - DEMO MODE")
        print("=" * 60)

        demo_cobol = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOAN-CHECK.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CUSTOMER-AGE        PIC 9(3).
       01 WS-ANNUAL-INCOME       PIC 9(7)V99.
       01 WS-CREDIT-SCORE        PIC 9(3).
       01 WS-ELIGIBILITY         PIC X(10).
          88 ELIGIBLE             VALUE 'YES'.
          88 NOT-ELIGIBLE         VALUE 'NO'.
       01 WS-MAX-LOAN            PIC 9(7)V99.
       01 WS-INTEREST-RATE       PIC 9(2)V99.

       PROCEDURE DIVISION.

       MAIN-LOGIC.
           PERFORM CHECK-ELIGIBILITY.
           PERFORM CALCULATE-LOAN.
           STOP RUN.

       CHECK-ELIGIBILITY.
           IF WS-CUSTOMER-AGE < 21
               SET NOT-ELIGIBLE TO TRUE
           ELSE
               IF WS-CREDIT-SCORE >= 750
                   SET ELIGIBLE TO TRUE
               ELSE
                   MOVE 'REVIEW' TO WS-ELIGIBILITY
               END-IF
           END-IF.

       CALCULATE-LOAN.
           COMPUTE WS-MAX-LOAN =
               WS-ANNUAL-INCOME * 5.
           MOVE 8.50 TO WS-INTEREST-RATE.
"""

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cbl', delete=False, encoding='utf-8') as f:
            f.write(demo_cobol)
            temp_path = f.name

        parser = CobolParser()
        result = parser.parse_file(Path(temp_path))

        print(f"\n  Program: {result.name}")
        print(f"  LOC: {result.loc}")
        print(f"  Format: {'IBM Fixed' if parser.is_fixed_format else 'Free'}")
        print(f"\n  PARAGRAPHS ({len(result.paragraphs)}):")
        for p in result.paragraphs:
            print(f"    -> {p.name} (lines {p.start_line}-{p.end_line})")

        print(f"\n  DATA ITEMS ({len(result.data_items)}):")
        for d in result.data_items:
            pic = d.pic_clause or ""
            flag = " [CONDITION]" if d.is_88_level else ""
            print(f"    -> {d.level:02d} {d.name:<25} {pic}{flag}")

        print("\n" + "=" * 60)
        print("  SUCCESS! Run with a file: python cobol_parser.py <file.cbl>")
        print("=" * 60)

        Path(temp_path).unlink()
