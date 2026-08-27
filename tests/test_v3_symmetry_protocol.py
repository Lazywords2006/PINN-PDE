"""Protocol tests for the symmetry-corrected independent audit."""

from __future__ import annotations

import pytest
import torch

from block_kyfan_pinn.metrics import projector_sine_error
from block_kyfan_pinn.p3_rom import _build_rom_basis
from block_kyfan_pinn.physics import periodic_mgs
from block_kyfan_pinn.reference import uniform_grid
from block_kyfan_pinn.suites import file_sha256, write_frozen_suite
from block_kyfan_pinn.v3_protocol import (
    V3_FORMAL_PURPOSE,
    V3_FORMAL_SEED,
    V3_FORMAL_SUITE_ID,
    V3_MODE_POLICY,
)
from scripts.audit_v3_convergence import (
    _periodic_resample_basis,
    build_convergence_gate,
)
from scripts.generate_v3_symmetry_assets import (
    TEST_COUNTS,
    TRAINING_BOUNDS,
    generate_suite_points,
    validate_spectral_point,
)
from scripts.run_v3_symmetry_evaluation import (
    _load_references,
    _validate_formal_suite,
    build_gate,
)


def test_v3_suite_is_deterministic_unique_and_split_balanced() -> None:
    counts = {
        "iid_hidden": 2,
        "exact_cluster": 2,
        "near_cluster": 3,
        "strict_ood": 3,
        "gap_scan": 2,
    }
    first = generate_suite_points(seed=20260827, prefix="unit", counts=counts)
    second = generate_suite_points(seed=20260827, prefix="unit", counts=counts)
    assert first == second
    assert len(first) == 2 * sum(counts.values())
    assert len({row["id"] for row in first}) == len(first)
    assert len(
        {
            (row["family"], tuple(round(value, 14) for value in row["parameters"]))
            for row in first
        }
    ) == len(first)
    for family in {str(row["family"]) for row in first}:
        for split, expected in counts.items():
            assert sum(
                row["family"] == family and row["split"] == split for row in first
            ) == expected


def test_v3_exact_and_near_points_respect_geometric_definitions() -> None:
    counts = {
        "iid_hidden": 1,
        "exact_cluster": 3,
        "near_cluster": 4,
        "strict_ood": 1,
        "gap_scan": 2,
    }
    points = generate_suite_points(seed=20260828, prefix="unit", counts=counts)
    k_point = 1.0 / 3.0
    for point in points:
        parameters = point["parameters"]
        if point["split"] == "exact_cluster":
            assert parameters[0] == k_point
            assert parameters[1] == k_point
            assert parameters[-1] == 0.0
        elif point["split"] == "near_cluster":
            radius = (
                (parameters[0] - k_point) ** 2
                + (parameters[1] - k_point) ** 2
            ) ** 0.5
            assert 0.0015 <= radius <= 0.0125
            assert parameters[-1] == 0.0


def test_v3_in_domain_splits_respect_declared_parameter_bounds() -> None:
    points = generate_suite_points(
        seed=20260829, prefix="bounds", counts=TEST_COUNTS
    )
    for point in points:
        if point["split"] == "strict_ood":
            continue
        start = 2 if point["split"] == "gap_scan" else 0
        for value, (lower, upper) in zip(
            point["parameters"][start:],
            TRAINING_BOUNDS[str(point["family"])][start:],
            strict=True,
        ):
            assert lower <= value <= upper


def test_v3_gate_requires_strong_controls_and_absolute_accuracy() -> None:
    summary = {
        "identity_complete": True,
        "finite_metrics": True,
        "maximum_orthogonality_error": 1e-7,
        "minimum_external_gap": 0.02,
        "methods": {
            "sr_routed25": {
                "overall": 0.03,
                "near_cluster": 0.025,
                "eigenvalue_mae": 0.004,
                "p95": 0.08,
                "maximum": 0.12,
                "max_raw_hermiticity_defect": 1e-6,
                "latency_ms": 30.0,
            },
            "long_anchor": {"overall": 0.12, "near_cluster": 0.09},
            "kinetic_fourier21": {"overall": 0.045, "near_cluster": 0.038},
            "kinetic_fourier25": {"overall": 0.043, "near_cluster": 0.036},
            "fourier_shell2": {"overall": 0.07, "near_cluster": 0.06},
            "fourier_shell3": {
                "overall": 0.028,
                "near_cluster": 0.024,
                "eigenvalue_mae": 0.005,
                "latency_ms": 60.0,
            },
            "wang_xie_adapted": {"overall": 0.09, "near_cluster": 0.07},
            "dai_adapted": {"overall": 0.30, "near_cluster": 0.28},
        },
        "maximum_raw_hermiticity_defect": 1e-6,
        "all_split_kinetic_control_pass": True,
        "family_seed_wins_vs_kinetic": 3,
        "family_seed_nonregressions_vs_kinetic": 6,
        "bootstrap_vs_kinetic": {"low": 0.18, "high": 0.32},
    }
    gate = build_gate(summary)
    assert gate["promotion_go"] is True

    summary["methods"]["kinetic_fourier25"]["overall"] = 0.029
    assert build_gate(summary)["promotion_go"] is False


def test_v3_spectral_validation_enforces_cluster_semantics() -> None:
    validate_spectral_point("exact_cluster", internal_gap=1e-8, external_gap=0.02)
    validate_spectral_point("near_cluster", internal_gap=0.01, external_gap=0.03)
    with pytest.raises(ValueError, match="exact-cluster"):
        validate_spectral_point("exact_cluster", internal_gap=0.002, external_gap=0.03)
    with pytest.raises(ValueError, match="exact-cluster"):
        validate_spectral_point("exact_cluster", internal_gap=0.001, external_gap=0.03)
    with pytest.raises(ValueError, match="near-cluster"):
        validate_spectral_point("near_cluster", internal_gap=0.03, external_gap=0.03)
    with pytest.raises(ValueError, match="near-cluster"):
        validate_spectral_point("near_cluster", internal_gap=0.02, external_gap=0.03)
    with pytest.raises(ValueError, match="external gap"):
        validate_spectral_point("iid_hidden", internal_gap=0.1, external_gap=0.009)


def test_v3_convergence_gate_requires_reference_and_grid_stability() -> None:
    summary = {
        "max_reference_projector_24_28": 2e-4,
        "max_reference_eigenvalue_24_28": 2e-6,
        "max_solver_projector_grid_difference": 2e-4,
        "max_solver_eigenvalue_grid_difference": 2e-5,
        "max_raw_hermiticity_defect": 2e-5,
    }
    assert build_convergence_gate(summary)["convergence_go"] is True
    summary["max_solver_projector_grid_difference"] = 0.002
    assert build_convergence_gate(summary)["convergence_go"] is False


def test_periodic_resampling_preserves_a_low_frequency_subspace() -> None:
    lower_grid = uniform_grid(17).unsqueeze(0)
    upper_grid = uniform_grid(25).unsqueeze(0)
    modes = [(0, 0), (1, -1)]
    lower = periodic_mgs(_build_rom_basis(lower_grid, modes))
    upper = periodic_mgs(_build_rom_basis(upper_grid, modes))
    resampled = _periodic_resample_basis(
        lower, source_side=17, target_side=25
    )
    assert projector_sine_error(resampled, upper) < 1e-6


def test_v3_reference_loader_rejects_duplicate_physical_points(tmp_path) -> None:
    points = [
        {
            "id": identity,
            "family": "harmonic_honeycomb",
            "split": "iid_hidden",
            "parameters": [0.31, 0.35, 0.5, 0.0],
        }
        for identity in ("duplicate-a", "duplicate-b")
    ]
    suite = tmp_path / "suite.json"
    payload = {
        "suite_id": "duplicate-suite",
        "protocol_version": 2,
        "point_count": 2,
        "points": points,
    }
    suite_hash = write_frozen_suite(payload, suite)
    cache = tmp_path / "references.pt"
    references = {
        point["id"]: {
            "basis": periodic_mgs(
                _build_rom_basis(uniform_grid(65).unsqueeze(0), [(0, 0), (1, 0)])
            )[0],
            "eigenvalues": torch.tensor([0.0, 1.0, 2.0]),
        }
        for point in points
    }
    torch.save(
        {
            "metadata": {
                "suite_id": "duplicate-suite",
                "suite_sha256": suite_hash,
                "grid_side": 65,
                "cutoff": 24,
                "rank": 3,
                "point_count": 2,
                "mode_shape": "hexagonal_d6",
            },
            "references": references,
        },
        cache,
    )
    cache.with_suffix(".sha256").write_text(
        f"{file_sha256(cache)}  {cache.name}\n"
    )
    with pytest.raises(ValueError, match="duplicate physical"):
        _load_references(suite, cache)


def test_formal_suite_requires_every_frozen_identifier() -> None:
    points = generate_suite_points(
        seed=V3_FORMAL_SEED, prefix="formal", counts=TEST_COUNTS
    )
    suite = {
        "suite_id": V3_FORMAL_SUITE_ID,
        "protocol_version": 2,
        "purpose": V3_FORMAL_PURPOSE,
        "generation_seed": V3_FORMAL_SEED,
        "mode_policy": V3_MODE_POLICY,
    }
    _validate_formal_suite(suite, points)
    for key, wrong in (
        ("suite_id", "copied-suite"),
        ("generation_seed", V3_FORMAL_SEED + 1),
        ("mode_policy", "wrong-policy"),
        ("purpose", "pilot"),
    ):
        changed = {**suite, key: wrong}
        with pytest.raises(ValueError):
            _validate_formal_suite(changed, points)
    modified_points = [dict(point) for point in points]
    modified_points[0] = {
        **modified_points[0],
        "parameters": [
            float(modified_points[0]["parameters"][0]) + 1e-6,
            *modified_points[0]["parameters"][1:],
        ],
    }
    with pytest.raises(ValueError, match="physical point digest"):
        _validate_formal_suite(suite, modified_points)
    swapped_points = [dict(point) for point in points]
    first = next(
        index
        for index, point in enumerate(swapped_points)
        if point["family"] == "harmonic_honeycomb"
        and point["split"] == "iid_hidden"
    )
    second = next(
        index
        for index, point in enumerate(swapped_points)
        if point["family"] == "harmonic_honeycomb"
        and point["split"] == "exact_cluster"
    )
    swapped_points[first]["split"], swapped_points[second]["split"] = (
        swapped_points[second]["split"],
        swapped_points[first]["split"],
    )
    with pytest.raises(ValueError, match="physical point digest"):
        _validate_formal_suite(suite, swapped_points)
