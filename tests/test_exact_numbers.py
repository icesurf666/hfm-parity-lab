"""F1: integers are compared exactly; tolerance never rescues distinct integers."""
from __future__ import annotations

import pytest
from builders import feat, obs, run
from hypothesis import given
from hypothesis import strategies as st

BIG = 2**53


def verdict(left: object, right: object, **tolerance: float) -> str:
    return run([obs(features={"f": feat(left)})], [obs(features={"f": feat(right)})], **tolerance).state.value


@pytest.mark.parametrize(("left", "right"), [(BIG + 1, BIG), (-(BIG + 1), -BIG), (10**30 + 1, 10**30),
                                             (10**400, 10**400 + 1), (BIG + 1, float(BIG))])
def test_distinct_numbers_never_pass(left: object, right: object) -> None:
    assert verdict(left, right) == "FAIL"


@pytest.mark.parametrize("value", [BIG + 1, -(10**30), 10**400, 0])
def test_equal_integers_pass_even_when_not_representable_as_float(value: int) -> None:
    assert verdict(value, value) == "PASS"


def test_integer_comparison_is_exact_even_with_tolerance() -> None:
    assert verdict(BIG + 1, BIG, absolute_tolerance=0.5, relative_tolerance=0.5) == "FAIL"
    assert verdict(100, 101, absolute_tolerance=5.0) == "FAIL"


def test_tolerance_applies_only_when_both_values_are_floats() -> None:
    assert verdict(1.0, 1.125, absolute_tolerance=0.25) == "PASS"
    assert verdict(1.0, 1.25, absolute_tolerance=0.25) == "PASS"  # boundary is inclusive
    assert verdict(1.0, 1.5, absolute_tolerance=0.25) == "FAIL"
    assert verdict(1, 1.25, absolute_tolerance=0.25) == "FAIL"


def test_huge_int_with_tolerance_does_not_crash() -> None:
    assert verdict(10**400, 1.0, absolute_tolerance=0.1) == "FAIL"
    assert verdict(10**400, 10**400, absolute_tolerance=0.1) == "PASS"


def test_zero_signed_zero_and_int_float_type_mismatch() -> None:
    assert verdict(0, 0.0) == "FAIL" and verdict(0.0, -0.0) == "PASS" and verdict(1, 1.0) == "FAIL"


@pytest.mark.parametrize(("left", "right"), [(True, 1), (False, 0), (1, True)])
def test_bool_is_not_an_integer(left: object, right: object) -> None:
    assert verdict(left, right) == "FAIL"


@given(st.integers(min_value=-(2**80), max_value=2**80), st.integers(min_value=1, max_value=5))
def test_property_distinct_integers_never_pass(base: int, step: int) -> None:
    assert verdict(base, base + step, absolute_tolerance=2.0, relative_tolerance=0.1) == "FAIL"
    assert verdict(base, base) == "PASS"
