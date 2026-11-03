"""Tote barcodes: "PF" + 9-digit sequence + GS1 mod-10 check digit.

The check digit lets the sorter scanner detect a misread instead of
sending the tote to the wrong pharmacy.
"""
import re

PREFIX = "PF"
_PATTERN = re.compile(rf"{PREFIX}(\d{{9}})(\d)")


def gs1_check_digit(digits: str) -> int:
    """GS1 mod-10: weights 3,1,3,1... starting from the rightmost digit."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def make_tote_barcode(sequence: int) -> str:
    body = f"{sequence:09d}"
    return f"{PREFIX}{body}{gs1_check_digit(body)}"


def is_valid_tote_barcode(code: str) -> bool:
    match = _PATTERN.fullmatch(code)
    return bool(match) and gs1_check_digit(match.group(1)) == int(match.group(2))
