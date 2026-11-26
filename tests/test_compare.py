import pytest

from chinook_agent.compare import CompareConfig, compare_answer, extract_numbers

CFG = CompareConfig(abs_tol=0.005, rel_tol=1e-6)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Всього 275 треків", [275.0]),
        ("Сума 1 234,56 грн", [1234.56]),
        ("Значення 1,234.56", [1234.56]),
        ("Ціна 0,99", [0.99]),
        ("Було 1.234 одиниць", [1234.0]),
        ("Гурт U2 має 3 альбоми", [3.0]),
        ("Немає чисел", []),
    ],
)
def test_extract_numbers(text, expected):
    assert extract_numbers(text) == expected


def test_numeric_match_with_rounding():
    result = compare_answer("Загальна сума 39.62", [[39.62]], cfg=CFG)
    assert result.solved is True and result.value_recall == 1.0


def test_numeric_mismatch():
    result = compare_answer("Сума 40.00", [[39.62]], cfg=CFG)
    assert result.solved is False and result.missing == [39.62]


def test_string_match_ignores_case_and_quotes():
    result = compare_answer('Артист «ac/dc» має 2 альбоми', [["AC/DC"]], cfg=CFG)
    assert result.solved is True


def test_all_gold_values_required():
    result = compare_answer("Iron Maiden", [["Iron Maiden"], ["Accept"]], cfg=CFG)
    assert result.solved is False and result.value_recall == 0.5


def test_mixed_values():
    result = compare_answer("Клієнт Luís Gonçalves витратив 108.7", [["Luís", "Gonçalves", 108.7]], cfg=CFG)
    assert result.solved is True


def test_extra_number_breaks_strict_only():
    result = compare_answer("2 артисти, і ще 17 жанрів", [[2]], cfg=CFG)
    assert result.solved is True and result.strict_solved is False
    assert result.extra_numbers == [17.0]


def test_number_from_question_is_allowed():
    result = compare_answer("Топ-5 треків: 5 позицій", [[5]], question="Назви топ-5 треків", cfg=CFG)
    assert result.strict_solved is True


def test_short_string_needs_word_boundary():
    assert compare_answer("ABBA", [["AB"]], cfg=CFG).solved is False
    assert compare_answer("жанр AB окремо", [["AB"]], cfg=CFG).solved is True


def test_none_answer():
    result = compare_answer(None, [[1]], cfg=CFG)
    assert result.solved is False and result.value_recall == 0.0


def test_empty_gold():
    result = compare_answer("будь-що", [], cfg=CFG)
    assert result.solved is False and result.value_recall is None


def test_null_cells_are_ignored():
    result = compare_answer("Відповідь 5", [[5, None]], cfg=CFG)
    assert result.total == 1 and result.solved is True


def test_tolerance_boundary():
    assert compare_answer("39.63", [[39.62]], cfg=CFG).solved is False
    wide = CompareConfig(abs_tol=0.02, rel_tol=0.0)
    assert compare_answer("39.63", [[39.62]], cfg=wide).solved is True


def test_three_decimals_are_read_as_thousands():
    # Задокументована межа евристики: «39.624» читається як 39624.
    assert extract_numbers("39.624") == [39624.0]
