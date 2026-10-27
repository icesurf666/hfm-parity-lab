"""P0: nested JSON values must not inherit Python's loose numeric equality."""
from __future__ import annotations

import pytest
from builders import feat, obs, run

from hfm_parity.domain.models import Classification


def report(left: object, right: object, **tolerance: float):
    return run([obs(features={"payload": feat(left)})], [obs(features={"payload": feat(right)})], **tolerance)


class ExplodingEqualityList(list[object]):
    def __eq__(self, other: object) -> bool:
        raise AssertionError("recursive comparison must not call container __eq__")


@pytest.mark.parametrize(
    ("left", "right", "field"),
    [
        ([1], [True], "payload[0]"),
        ({"x": 1}, {"x": 1.0}, "payload.x"),
        ({"a": [{"b": False}]}, {"a": [{"b": 0}]}, "payload.a[0].b"),
        ([1, 2], [1, 2.0], "payload[1]"),
        ({"x": None}, {}, "payload.x"),
        ({"x": [1, 2]}, {"x": [2, 1]}, "payload.x[0]"),
    ],
)
def test_nested_type_and_value_mismatches_fail_at_the_leaf(left: object, right: object, field: str) -> None:
    result = report(left, right)
    assert result.state.value == "FAIL"
    assert not result.deterministic_parity_verified
    assert result.first_divergence is not None
    assert result.first_divergence.field == field


def test_equal_nested_values_and_float_tolerance_remain_valid() -> None:
    exact = {"a": [1, False, None, {"z": "ok"}]}
    assert report(exact, exact).state.value == "PASS"
    assert report({"score": [1.0, 1.25]}, {"score": [1.0, 1.5]}, absolute_tolerance=0.25).state.value == "PASS"


def test_recursive_walk_never_calls_host_container_equality() -> None:
    assert report(ExplodingEqualityList([1]), [1]).state.value == "PASS"


def test_large_nested_integers_remain_exact() -> None:
    result = report({"quantity": 10**100}, {"quantity": 10**100 + 1})
    assert result.state.value == "FAIL"
    assert result.first_divergence is not None
    assert result.first_divergence.classification is Classification.FEATURE_VALUE_MISMATCH


def test_first_nested_divergence_is_deterministic() -> None:
    left = obs(features={"z": feat([1]), "a": feat([1])})
    right = obs(features={"z": feat([True]), "a": feat([True])})
    result = run([left], [right])
    assert result.first_divergence is not None
    assert result.first_divergence.field == "a[0]"
