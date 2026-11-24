"""Tests for the random number generator."""

import pytest

from app.generators.number import generate_number


def test_generate_number_within_range() -> None:
    result = generate_number(1, 100)

    assert 1 <= result <= 100


def test_generate_number_with_same_bounds() -> None:
    assert generate_number(5, 5) == 5


def test_generate_number_with_negative_bounds() -> None:
    result = generate_number(-100, -1)

    assert -100 <= result <= -1


def test_generate_number_with_invalid_min_type() -> None:
    with pytest.raises(TypeError):
        generate_number(1.5, 100)


def test_generate_number_with_invalid_max_type() -> None:
    with pytest.raises(TypeError):
        generate_number(1, "100")


def test_generate_number_with_boolean_value() -> None:
    with pytest.raises(TypeError):
        generate_number(True, 100)


def test_generate_number_with_invalid_range() -> None:
    with pytest.raises(ValueError):
        generate_number(100, 1)