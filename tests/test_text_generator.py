"""Tests for the random text generator."""

import pytest

from app.generators.text import generate_text


def test_generate_text_with_requested_length() -> None:
    result = generate_text(
        20,
        use_russian=True,
        use_english=True,
        use_digits=True,
        case="mixed",
    )

    assert len(result) == 20


def test_generate_text_with_digits_only() -> None:
    result = generate_text(
        100,
        use_russian=False,
        use_english=False,
        use_digits=True,
        case="lower",
    )

    assert result.isdigit()


def test_generate_text_with_russian_lowercase() -> None:
    result = generate_text(
        100,
        use_russian=True,
        use_english=False,
        use_digits=False,
        case="lower",
    )

    assert all(char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя" for char in result)


def test_generate_text_with_english_uppercase() -> None:
    result = generate_text(
        100,
        use_russian=False,
        use_english=True,
        use_digits=False,
        case="upper",
    )

    assert result.isalpha()
    assert result.isascii()
    assert result.isupper()


def test_generate_text_with_invalid_length_type() -> None:
    with pytest.raises(TypeError):
        generate_text(
            10.5,
            use_russian=True,
            use_english=False,
            use_digits=False,
            case="lower",
        )


def test_generate_text_with_boolean_length() -> None:
    with pytest.raises(TypeError):
        generate_text(
            True,
            use_russian=True,
            use_english=False,
            use_digits=False,
            case="lower",
        )


@pytest.mark.parametrize("length", [0, -1])
def test_generate_text_with_invalid_length(length: int) -> None:
    with pytest.raises(ValueError):
        generate_text(
            length,
            use_russian=True,
            use_english=False,
            use_digits=False,
            case="lower",
        )


def test_generate_text_without_selected_groups() -> None:
    with pytest.raises(ValueError):
        generate_text(
            10,
            use_russian=False,
            use_english=False,
            use_digits=False,
            case="lower",
        )


def test_generate_text_with_invalid_case() -> None:
    with pytest.raises(ValueError):
        generate_text(
            10,
            use_russian=True,
            use_english=False,
            use_digits=False,
            case="capitalize",
        )
