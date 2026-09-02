from __future__ import annotations

import json
import math
from dataclasses import dataclass

from tai_public_finance.cs005_marked_poisson.reporting import serializable


@dataclass(frozen=True)
class _Dummy:
    x: float
    y: str


def test_serializable_handles_dataclass():
    assert serializable(_Dummy(x=1.5, y="a")) == {"x": 1.5, "y": "a"}


def test_serializable_handles_nested_dict_and_list():
    value = {"a": [_Dummy(x=1.0, y="p"), _Dummy(x=2.0, y="q")], "b": (1, 2, 3)}
    result = serializable(value)
    assert result == {"a": [{"x": 1.0, "y": "p"}, {"x": 2.0, "y": "q"}], "b": [1, 2, 3]}


def test_serializable_handles_nonfinite_floats_as_json_safe_strings():
    result = serializable({"nan": math.nan, "inf": math.inf, "neg_inf": -math.inf})
    # json.dumps would silently emit invalid-JSON NaN/Infinity literals otherwise.
    text = json.dumps(result)
    reparsed = json.loads(text)
    assert reparsed == {"nan": "nan", "inf": "inf", "neg_inf": "-inf"}


def test_serializable_passes_through_plain_values():
    assert serializable(3) == 3
    assert serializable(3.5) == 3.5
    assert serializable("s") == "s"
    assert serializable(None) is None
