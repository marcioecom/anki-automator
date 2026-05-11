from pathlib import Path

from src.parser import parse_word_list, Word


def write(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "list.txt"
    f.write_text(content, encoding="utf-8")
    return f


def test_parses_simple_line(tmp_path):
    f = write(tmp_path, "345. obviously\n")
    words, errors = parse_word_list(f)
    assert errors == []
    assert words == [Word(numero=345, palavra="obviously", contexto=None)]


def test_parses_multiword_term(tmp_path):
    f = write(tmp_path, "348. turned around\n")
    words, errors = parse_word_list(f)
    assert words == [Word(numero=348, palavra="turned around", contexto=None)]


def test_parses_context_with_smart_quotes(tmp_path):
    f = write(tmp_path, '351. considerable (context: "considerable amount of …")\n')
    words, errors = parse_word_list(f)
    assert words == [Word(numero=351, palavra="considerable", contexto="considerable amount of …")]


def test_parses_context_with_curly_quotes(tmp_path):
    f = write(tmp_path, '351. considerable (context: “considerable amount of …”)\n')
    words, errors = parse_word_list(f)
    assert words[0].contexto == "considerable amount of …"


def test_skips_blank_lines(tmp_path):
    f = write(tmp_path, "1. apple\n\n2. banana\n")
    words, errors = parse_word_list(f)
    assert [w.palavra for w in words] == ["apple", "banana"]
    assert errors == []


def test_reports_malformed_line(tmp_path):
    f = write(tmp_path, "1. apple\nnot-a-numbered-line\n2. banana\n")
    words, errors = parse_word_list(f)
    assert [w.palavra for w in words] == ["apple", "banana"]
    assert len(errors) == 1
    assert errors[0].line_number == 2
    assert "not-a-numbered-line" in errors[0].content


def test_empty_file(tmp_path):
    f = write(tmp_path, "")
    words, errors = parse_word_list(f)
    assert words == []
    assert errors == []


def test_strips_surrounding_whitespace(tmp_path):
    f = write(tmp_path, "  42.   hiking  \n")
    words, errors = parse_word_list(f)
    assert words == [Word(numero=42, palavra="hiking", contexto=None)]
