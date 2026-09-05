"""Deep immutability of the public surface, and fingerprint sensitivity."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from tai_public_finance.cs012_poisson_kernels.extended import ExtendedReal, sha256_of_object
from tai_public_finance.cs012_poisson_kernels.inputs import FixtureInput, load_fixtures
from tai_public_finance.cs012_poisson_kernels.kernels import evaluate_kernels
from tai_public_finance.cs012_poisson_kernels.portfolio import decompose, solve_owner_root
from tai_public_finance.cs012_poisson_kernels.projection import (
    project_fiscal_gap,
    safe_account_rank,
)
from tai_public_finance.cs012_poisson_kernels.report import fixture_fingerprint

from .conftest import BRANCH_LITERAL_LAISSEZ_FAIRE

IMMUTABLE_SCALARS = (str, int, float, bool, type(None))


def _walk(value: Any, path: str, seen: set[int]) -> list[str]:
    """Report every mutable object reachable through a public result."""
    if id(value) in seen:
        return []
    seen.add(id(value))
    if isinstance(value, IMMUTABLE_SCALARS):
        return []
    if isinstance(value, (list, dict, set, bytearray)):
        return [f"{path}: mutable {type(value).__name__}"]
    if type(value).__module__ == "numpy" or type(value).__name__ == "ndarray":
        return [f"{path}: numpy object {type(value).__name__}"]
    if isinstance(value, tuple):
        problems = []
        for index, item in enumerate(value):
            problems.extend(_walk(item, f"{path}[{index}]", seen))
        return problems
    if dataclasses.is_dataclass(value):
        problems = []
        if not value.__dataclass_params__.frozen:
            problems.append(f"{path}: dataclass {type(value).__name__} is not frozen")
        for field in dataclasses.fields(value):
            problems.extend(
                _walk(getattr(value, field.name), f"{path}.{field.name}", seen)
            )
        return problems
    return [f"{path}: unclassified object {type(value).__name__}"]


def test_every_public_result_is_deeply_immutable(frozen_fixtures):
    problems: list[str] = []
    for name, item in frozen_fixtures.items():
        outcome = evaluate_kernels(item)
        results = [("kernels", outcome), ("safe", safe_account_rank(outcome))]
        if item.declared_branch != BRANCH_LITERAL_LAISSEZ_FAIRE:
            results += [
                ("decomposition", decompose(outcome)),
                ("root", solve_owner_root(outcome)),
                ("projection", project_fiscal_gap(outcome)),
            ]
        for label, result in results:
            problems.extend(_walk(result, f"{name}.{label}", set()))
    assert problems == [], problems


def test_public_results_reject_attribute_assignment(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["one_mark_alignment"])
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.status = "tampered"
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.marks[0].k_owner = 0.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        decompose(outcome).d_owner = 1.0


def test_no_raw_input_payload_is_reachable_through_a_result(frozen_fixtures):
    """``direct_fields`` builds a fresh dict each call, so mutating one cannot
    reach back into the parsed fixture."""
    item = frozen_fixtures["two_mark_orthogonal_gap"]
    first = item.direct_fields()
    first["owner_exposure"] = 999.0
    first["marks"][0]["payoff_jump"] = 999.0
    second = item.direct_fields()
    assert second["owner_exposure"] == 0.0
    assert second["marks"][0]["payoff_jump"] == 0.5
    assert item.marks[0].payoff_jump == 0.5


def test_mark_ids_and_input_order_are_preserved_explicitly(frozen_fixtures):
    item = frozen_fixtures["two_mark_orthogonal_gap"]
    outcome = evaluate_kernels(item)
    assert item.mark_ids == ("P", "F")
    assert tuple(m.mark_id for m in outcome.require_finite()) == ("P", "F")
    assert tuple(t.mark_id for t in decompose(outcome).terms) == ("P", "F")
    assert tuple(c.mark_id for c in project_fiscal_gap(outcome).components) == ("P", "F")


# --- fingerprint -------------------------------------------------------------------


def _tweaked(item: FixtureInput, **changes: Any) -> FixtureInput:
    return dataclasses.replace(item, **changes)


def test_the_fingerprint_ignores_json_whitespace_and_key_order(fixture_path, frozen_fixtures):
    fixtures = load_fixtures(fixture_path)
    baseline = fixture_fingerprint(fixtures)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    # Re-serialize with different whitespace and reversed key order, then reparse.
    reordered = json.dumps(
        {key: payload[key] for key in reversed(list(payload))}, indent=7
    )
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        alternative = Path(directory) / "reordered.json"
        alternative.write_text(reordered, encoding="utf-8")
        assert fixture_fingerprint(load_fixtures(alternative)) == baseline


def test_the_fingerprint_ignores_prose_but_not_operative_fields(frozen_fixtures):
    item = frozen_fixtures["two_mark_orthogonal_gap"]
    baseline = fixture_fingerprint((item,))
    assert fixture_fingerprint((_tweaked(item, description="different prose"),)) == baseline

    changed = [
        _tweaked(item, fixture_id="renamed"),
        _tweaked(item, owner_exposure=0.1),
        _tweaked(item, government_current_marginal_value=1.5),
        _tweaked(item, worker_consumption=0.0),
        _tweaked(item, marks=tuple(reversed(item.marks))),
        _tweaked(
            item,
            marks=(dataclasses.replace(item.marks[0], lambda_physical=0.21), item.marks[1]),
        ),
        _tweaked(
            item,
            marks=(
                dataclasses.replace(item.marks[0], lambda_risk_neutral=0.21),
                item.marks[1],
            ),
        ),
        _tweaked(
            item,
            marks=(dataclasses.replace(item.marks[0], payoff_jump=0.51), item.marks[1]),
        ),
        _tweaked(
            item,
            marks=(
                dataclasses.replace(
                    item.marks[0],
                    government_successor_marginal_value=ExtendedReal.of(1.21),
                ),
                item.marks[1],
            ),
        ),
        _tweaked(
            item,
            marks=(dataclasses.replace(item.marks[0], mark_id="Q"), item.marks[1]),
        ),
    ]
    for variant in changed:
        assert fixture_fingerprint((variant,)) != baseline, variant.direct_fields()


def test_the_fingerprint_covers_the_specification_identity_and_tolerance_policy(fixture_path):
    fixtures = load_fixtures(fixture_path)
    baseline = fixture_fingerprint(fixtures)
    # Reproduce the fingerprint payload with one specification field changed and
    # confirm it moves, so a stale spec hash cannot pass as the same fingerprint.
    from tai_public_finance.cs012_poisson_kernels import report as report_module

    payload = {
        "specification": {
            "specification_id": "CS012",
            "version": "0.1",
            "sha256": "0" * 64,
        },
        "formula_convention": report_module.FORMULA_CONVENTION,
        "tolerance_policy": report_module.TOLERANCE_POLICY,
        "fixtures": [item.direct_fields() for item in fixtures],
    }
    assert sha256_of_object(payload) != baseline
