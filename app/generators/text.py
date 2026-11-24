"""Random text generator."""

import random
import string


def generate_text(
    length: int,
    *,
    use_russian: bool,
    use_english: bool,
    use_digits: bool,
    case: str,
) -> str:
    """Generate random text using the selected character groups and case."""

    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be an integer")

    if length <= 0:
        raise ValueError("length must be greater than zero")

    for name, value in (
        ("use_russian", use_russian),
        ("use_english", use_english),
        ("use_digits", use_digits),
    ):
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a boolean")

    if case not in ("lower", "upper", "mixed"):
        raise ValueError("case must be 'lower', 'upper' or 'mixed'")

    alphabet = ""

    if use_russian:
        russian_lower = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        russian_upper = russian_lower.upper()

        if case in ("lower", "mixed"):
            alphabet += russian_lower

        if case in ("upper", "mixed"):
            alphabet += russian_upper

    if use_english:
        if case in ("lower", "mixed"):
            alphabet += string.ascii_lowercase

        if case in ("upper", "mixed"):
            alphabet += string.ascii_uppercase

    if use_digits:
        alphabet += string.digits

    if not alphabet:
        raise ValueError("at least one character group must be selected")

    return "".join(random.choices(alphabet, k=length))
