"""Random integer generator."""

import random


def generate_number(min_value: int, max_value: int) -> int:
    """Generate a random integer within the inclusive range."""

    if isinstance(min_value, bool) or not isinstance(min_value, int):
        raise TypeError("min_value must be an integer")

    if isinstance(max_value, bool) or not isinstance(max_value, int):
        raise TypeError("max_value must be an integer")

    if min_value > max_value:
        raise ValueError("min_value must not exceed max_value")

    return random.randint(min_value, max_value)