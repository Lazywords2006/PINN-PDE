import torch
import csv

from block_kyfan_pinn.protocol import (
    build_falsification_smoke_points,
    is_inside_training_box,
    validate_falsification_points,
)
from block_kyfan_pinn.physics import gaussian_honeycomb_potential, subspace_inclusion_loss
from block_kyfan_pinn.reference import _potential_coefficient, uniform_grid
from scripts.compare_sci3_methods import (
    _apply_holm,
    _matched_pairs_rank_biserial,
    _nested_bootstrap_ci,
    _permutation_p,
)
from scripts.build_v2_smoke_decision import (
    _load_rows,
    _training_checkpoint_hashes,
    _training_seed_set,
)
from scripts.evaluate_sci3_suite import (
    _validate_checkpoint_config,
    _validate_checkpoint_source,
    _validate_reference_cache,
    _validate_suite_payload,
)


def test_exact_paired_permutation_detects_ten_consistent_improvements() -> None:
    assert _permutation_p([1.0] * 10) == 2 / 1024


def test_subspace_inclusion_loss_is_zero_for_identical_basis() -> None:
    raw = torch.randn(2, 40, 2, 2)
    from block_kyfan_pinn.physics import periodic_mgs
    basis = periodic_mgs(raw)
    assert float(subspace_inclusion_loss(basis, basis)) < 1e-6


def test_gaussian_coordinate_and_fourier_reference_agree() -> None:
    parameters = torch.tensor([1 / 3, 1 / 3, 2.0, 0.26, 0.03], dtype=torch.float64)
    coordinates = uniform_grid(129, dtype=torch.float64).unsqueeze(0)
    potential = gaussian_honeycomb_potential(coordinates, parameters.unsqueeze(0))[0]
    mode = (1, 0)
    phase = coordinates[0, :, 0] * mode[0] + coordinates[0, :, 1] * mode[1]
    numeric = torch.mean(torch.complex(potential, torch.zeros_like(potential)) * torch.exp(-1j * phase))
    analytic = _potential_coefficient(mode, parameters, "gaussian_honeycomb")
    assert abs(complex(numeric) - analytic) < 1e-10


def test_training_box_membership_is_family_specific() -> None:
    assert is_inside_training_box([0.31, 0.35, 0.50, 0.02], "harmonic_honeycomb")
    assert not is_inside_training_box([0.25, 0.35, 0.50, 0.02], "harmonic_honeycomb")
    assert is_inside_training_box([0.31, 0.35, 2.50, 0.26, 0.02], "gaussian_honeycomb")
    assert not is_inside_training_box([0.31, 0.35, 2.50, 0.38, 0.02], "gaussian_honeycomb")


def test_falsification_smoke_points_have_strict_ood_and_symmetric_cluster_cases() -> None:
    points = build_falsification_smoke_points(seed=20260729)
    assert len(points) == 24
    for family in ("harmonic_honeycomb", "gaussian_honeycomb"):
        family_points = [point for point in points if point["family"] == family]
        assert {point["split"] for point in family_points} == {
            "iid_hidden",
            "exact_cluster",
            "near_cluster",
            "strict_ood",
        }
        for point in family_points:
            parameters = point["parameters"]
            if point["split"] == "strict_ood":
                assert not is_inside_training_box(parameters, family)
            if point["split"] in {"exact_cluster", "near_cluster"}:
                assert parameters[-1] == 0.0
            if point["split"] == "exact_cluster":
                assert parameters[:2] == [1.0 / 3.0, 1.0 / 3.0]


def test_falsification_validator_rejects_geometric_near_label_without_gap_evidence() -> None:
    points = build_falsification_smoke_points(seed=20260729)
    annotated = []
    for point in points:
        row = dict(point)
        row["internal_gap"] = 0.005 if row["split"] == "near_cluster" else 0.0
        row["external_gap"] = 0.20
        annotated.append(row)
    assert validate_falsification_points(annotated) == []
    bad = [dict(row) for row in annotated]
    next(row for row in bad if row["split"] == "near_cluster")["internal_gap"] = 0.05
    assert any("near_cluster internal_gap" in error for error in validate_falsification_points(bad))


def test_evaluator_rejects_checkpoint_with_different_anchor_semantics() -> None:
    from block_kyfan_pinn.experiment import ExperimentConfig

    config = ExperimentConfig(name="expected", anchor_kind="correct", orthogonalization="dual_path")
    checkpoint_config = {**config.__dict__, "anchor_kind": "none"}
    with __import__("pytest").raises(ValueError, match="anchor_kind"):
        _validate_checkpoint_config(config, checkpoint_config)
    with __import__("pytest").raises(ValueError, match="source fingerprint"):
        _validate_checkpoint_source(config, {"source_fingerprint": "wrong"})


def test_suite_validation_rejects_duplicate_identity() -> None:
    point = {"id": "same", "family": "harmonic_honeycomb", "split": "iid", "parameters": [0.3, 0.3, 0.5, 0.0]}
    with __import__("pytest").raises(ValueError, match="duplicated"):
        _validate_suite_payload({"point_count": 2, "points": [point, dict(point)]})


def test_holm_stops_after_first_failed_hypothesis() -> None:
    comparisons = {
        "first": {"paired_permutation_p": 0.03},
        "second": {"paired_permutation_p": 0.04},
    }
    _apply_holm(comparisons)
    assert not comparisons["first"]["holm_pass"]
    assert not comparisons["second"]["holm_pass"]


def test_matched_pairs_rank_biserial_uses_magnitude_ranks() -> None:
    # Absolute ranks are 1, 2, 3; positive and negative rank sums are both 3.
    assert _matched_pairs_rank_biserial([1.0, 2.0, -3.0]) == 0.0


def test_nested_bootstrap_preserves_constant_paired_effect() -> None:
    ours = {seed: {"a": 0.1, "b": 0.2} for seed in range(3)}
    baseline = {seed: {"a": 0.4, "b": 0.5} for seed in range(3)}
    low, high = _nested_bootstrap_ci(ours, baseline, samples=200)
    assert abs(low - 0.3) < 1e-12
    assert abs(high - 0.3) < 1e-12


def test_decision_builder_rejects_selected_point_subset(tmp_path) -> None:
    seed_dir = tmp_path / "seed_1"
    seed_dir.mkdir()
    (seed_dir / "summary.json").write_text(__import__("json").dumps({
        "suite_id": "suite", "suite_sha256": "abc", "potential_family": "family",
        "checkpoint_seed": 1, "checkpoint_sha256": "a" * 64, "point_count": 1,
    }))
    with (seed_dir / "per_parameter.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "projector_sine_error", "orthogonality_error"))
        writer.writeheader(); writer.writerow({"id": "only", "projector_sine_error": 0.1, "orthogonality_error": 0.0})
    with __import__("pytest").raises(ValueError, match="incomplete point_count"):
        _load_rows(tmp_path, [1], "abc", "suite", "family", {"only", "missing"})
    with __import__("pytest").raises(ValueError, match="config fingerprint mismatch"):
        _load_rows(
            tmp_path, [1], "abc", "suite", "family", {"only"},
            expected_config_fingerprint="expected",
        )
    summary = __import__("json").loads((seed_dir / "summary.json").read_text())
    summary["checkpoint_config_fingerprint"] = "expected"
    (seed_dir / "summary.json").write_text(__import__("json").dumps(summary))
    with __import__("pytest").raises(ValueError, match="not the training final checkpoint"):
        _load_rows(
            tmp_path, [1], "abc", "suite", "family", {"only"},
            expected_config_fingerprint="expected",
            expected_checkpoint_hashes={1: "b" * 64},
        )


def test_decision_builder_rejects_runs_missing_a_configured_seed() -> None:
    training = {"config": {"seeds": [1, 2, 3]}, "runs": [{"seed": 1}, {"seed": 2}]}
    with __import__("pytest").raises(ValueError, match="exactly match config.seeds"):
        _training_seed_set(training, "arm")
    legacy = {"runs": [{"seed": 1}]}
    with __import__("pytest").raises(ValueError, match="explicit legacy-unbound"):
        _training_checkpoint_hashes(legacy, "arm", False)
    assert _training_checkpoint_hashes(legacy, "arm", True) is None
    bound = {"runs": [{"seed": 1, "final_checkpoint_sha256": "c" * 64}]}
    assert _training_checkpoint_hashes(bound, "arm", False) == {1: "c" * 64}


def test_reference_cache_binds_cutoff_and_grid() -> None:
    from block_kyfan_pinn.experiment import ExperimentConfig

    config = ExperimentConfig(name="cache", eval_grid_side=3, reference_cutoff=2)
    payload = {
        "metadata": {"suite_id": "suite", "suite_sha256": "abc", "grid_side": 3, "cutoff": 2},
        "references": {"p": {"basis": torch.zeros(9, 2, 2), "eigenvalues": torch.zeros(3)}},
    }
    references, _ = _validate_reference_cache(payload, config, {"suite_id": "suite"}, "abc", {"p"})
    assert "p" in references
    bad = {**payload, "metadata": {**payload["metadata"], "cutoff": 1}}
    with __import__("pytest").raises(ValueError, match="cutoff"):
        _validate_reference_cache(bad, config, {"suite_id": "suite"}, "abc", {"p"})
    bad_shape = {
        **payload,
        "references": {"p": {"basis": torch.zeros(9, 2, 2), "eigenvalues": torch.zeros(3, 1)}},
    }
    with __import__("pytest").raises(ValueError, match="shape mismatch"):
        _validate_reference_cache(bad_shape, config, {"suite_id": "suite"}, "abc", {"p"})
    non_finite = {
        **payload,
        "references": {"p": {"basis": torch.full((9, 2, 2), float("nan")), "eigenvalues": torch.zeros(3)}},
    }
    with __import__("pytest").raises(ValueError, match="non-finite"):
        _validate_reference_cache(non_finite, config, {"suite_id": "suite"}, "abc", {"p"})
