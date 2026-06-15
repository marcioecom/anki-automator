from src.card import bold_in_sentence, make_front_back
from src.types import EnrichedWord


def test_bold_simple_word():
    assert bold_in_sentence("She loves apples.", "apples") == "She loves <b>apples</b>."


def test_bold_preserves_original_case():
    assert bold_in_sentence("Apples are good.", "apples") == "<b>Apples</b> are good."


def test_bold_multi_word_expression():
    assert (
        bold_in_sentence("He turned around quickly.", "turned around")
        == "He <b>turned around</b> quickly."
    )


def test_bold_no_match_returns_unchanged():
    assert bold_in_sentence("She likes fruit.", "apple") == "She likes fruit."


def test_bold_word_boundary_avoids_partial_match():
    assert bold_in_sentence("She likes pineapples.", "apple") == "She likes pineapples."


def test_bold_bolds_all_occurrences():
    assert (
        bold_in_sentence("Apple, apple, APPLE everywhere.", "apple")
        == "<b>Apple</b>, <b>apple</b>, <b>APPLE</b> everywhere."
    )


def test_make_front_back_without_audio():
    ew = EnrichedWord(
        numero=1,
        palavra="play",
        explicacao="test explanation",
        traducao="Brincar",
        exemplos=["a", "b", "c", "d", "e"],
    )
    front, back = make_front_back("She loves to play.", ew, None)
    assert front == "She loves to <b>play</b>."
    assert back == "<b>Play</b>: Brincar"


def test_make_front_back_with_audio():
    ew = EnrichedWord(
        numero=1,
        palavra="play",
        explicacao="test explanation",
        traducao="Brincar",
        exemplos=["a", "b", "c", "d", "e"],
    )
    front, back = make_front_back(
        "She loves to play.", ew, "anki-automator-abc123.mp3"
    )
    assert front == "She loves to <b>play</b>. [sound:anki-automator-abc123.mp3]"
    assert back == "<b>Play</b>: Brincar"
