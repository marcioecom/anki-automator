from src.main import _bold_in_sentence


def test_bold_simple_word():
    assert _bold_in_sentence("She loves apples.", "apples") == "She loves <b>apples</b>."


def test_bold_preserves_original_case():
    assert _bold_in_sentence("Apples are good.", "apples") == "<b>Apples</b> are good."


def test_bold_multi_word_expression():
    assert (
        _bold_in_sentence("He turned around quickly.", "turned around")
        == "He <b>turned around</b> quickly."
    )


def test_bold_no_match_returns_unchanged():
    assert _bold_in_sentence("She likes fruit.", "apple") == "She likes fruit."


def test_bold_word_boundary_avoids_partial_match():
    assert _bold_in_sentence("She likes pineapples.", "apple") == "She likes pineapples."


def test_bold_bolds_all_occurrences():
    assert (
        _bold_in_sentence("Apple, apple, APPLE everywhere.", "apple")
        == "<b>Apple</b>, <b>apple</b>, <b>APPLE</b> everywhere."
    )
