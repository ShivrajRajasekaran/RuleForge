"""Tests for the COBOL parser (Module 1)."""

from src.parser.cobol_parser import CobolParser, CobolProgram


def test_program_id_extracted(program):
    assert program.name == "TESTCALC"


def test_loc_counted(program):
    assert program.loc > 0


def test_paragraphs_found(program):
    names = {p.name for p in program.paragraphs}
    assert "1000-MAIN" in names
    assert "2000-CHECK-ELIGIBILITY" in names
    assert "3000-CALCULATE-FEE" in names


def test_paragraph_line_ranges_valid(program):
    for p in program.paragraphs:
        assert p.start_line >= 1
        assert p.end_line >= p.start_line


def test_data_items_found(program):
    names = {d.name for d in program.data_items}
    assert "WS-ACCT-BALANCE" in names
    assert "WS-CREDIT-LIMIT" in names


def test_pic_clause_parsed(program):
    bal = next(d for d in program.data_items if d.name == "WS-ACCT-BALANCE")
    assert bal.pic_clause is not None
    assert "9" in bal.pic_clause


def test_88_level_detected(program):
    eighty_eights = [d for d in program.data_items if d.is_88_level]
    names = {d.name for d in eighty_eights}
    assert "APPROVED" in names
    assert "REJECTED" in names
    assert all(d.level == 88 for d in eighty_eights)


def test_returns_cobol_program_type(program):
    assert isinstance(program, CobolProgram)


def test_empty_file_does_not_crash(tmp_path):
    p = tmp_path / "EMPTY.cbl"
    p.write_text("", encoding="utf-8")
    prog = CobolParser().parse_file(p)
    assert prog.loc == 0
    assert prog.paragraphs == []


def test_fixed_vs_free_format_flag(sample_cbl):
    parser = CobolParser()
    parser.parse_file(sample_cbl)
    # Sample has no sequence numbers → free format.
    assert parser.is_fixed_format is False
