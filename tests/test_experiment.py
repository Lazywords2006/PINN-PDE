import csv

import pytest

from block_kyfan_pinn.experiment import (
    ExperimentConfig,
    _sample_coordinates,
    _sample_parameters,
    pilot_gate,
    run_experiment,
)


def test_training_coordinates_use_shifted_periodic_grid() -> None:
    coordinates = _sample_coordinates(2, 32, __import__("torch").device("cpu"))
    assert coordinates.shape == (2, 36, 2)
    assert coordinates.requires_grad
    assert float(coordinates.detach().min()) >= 0.0
    assert float(coordinates.detach().max()) < 2.0 * 3.141593


def test_sampling_stream_is_independent_of_global_model_rng() -> None:
    torch = __import__("torch")
    first = torch.Generator(device="cpu").manual_seed(1234)
    coordinates_a = _sample_coordinates(2, 16, torch.device("cpu"), generator=first).detach()
    parameters_a = _sample_parameters(2, torch.device("cpu"), (0.0,) * 4, (1.0,) * 4, generator=first)
    torch.manual_seed(999)
    _ = torch.rand(1000)
    second = torch.Generator(device="cpu").manual_seed(1234)
    coordinates_b = _sample_coordinates(2, 16, torch.device("cpu"), generator=second).detach()
    parameters_b = _sample_parameters(2, torch.device("cpu"), (0.0,) * 4, (1.0,) * 4, generator=second)
    assert torch.equal(coordinates_a, coordinates_b)
    assert torch.equal(parameters_a, parameters_b)


def test_coordinate_sampling_supports_available_accelerator_with_cpu_generator() -> None:
    torch = __import__("torch")
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        pytest.skip("no accelerator available")
    generator = torch.Generator(device="cpu").manual_seed(4321)
    coordinates = _sample_coordinates(2, 16, device, generator=generator)
    assert coordinates.device.type == device.type
    assert coordinates.requires_grad


def test_pilot_gate_requires_stable_interpolation_and_cluster_accuracy() -> None:
    passing = {
        "mean_projector_sine_error": 0.31,
        "std_projector_sine_error": 0.01,
        "aggregate": [
            {"case": "interpolation", "projector_mean": 0.22},
            {"case": "symmetric_cluster", "projector_mean": 0.32},
            {"case": "extrapolation", "projector_mean": 0.43},
        ],
    }
    assert pilot_gate(passing)[0]
    failing = {**passing, "aggregate": [{"case": "interpolation", "projector_mean": 0.28}]}
    assert not pilot_gate(failing)[0]


def test_tiny_experiment_writes_checkpoint_metrics_and_summary(tmp_path) -> None:
    config = ExperimentConfig(
        name="test",
        device="cpu",
        seeds=(3,),
        steps=4,
        points=32,
        parameter_batch=2,
        width=16,
        hidden_layers=1,
        anchor_scale=0.05,
        residual_weight=0.01,
        residual_start_fraction=0.0,
        eval_grid_side=7,
        reference_cutoff=2,
        output_dir=str(tmp_path),
    )
    summary = run_experiment(config)
    assert summary["status"] == "COMPLETE"
    assert summary["config"]["anchor_scale"] == 0.05
    assert (tmp_path / "seed_3" / "final.pt").is_file()
    assert (tmp_path / "seed_3" / "metrics.csv").is_file()
    assert (tmp_path / "seed_3" / "training.csv").is_file()
    assert (tmp_path / "summary.json").is_file()
    assert (tmp_path / "aggregate.csv").is_file()
    with (tmp_path / "seed_3" / "metrics.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert all(0.0 <= float(row["projector_sine_error"]) <= 1.0 for row in rows)
    run_experiment(config)
    with (tmp_path / "seed_3" / "training.csv").open() as handle:
        assert list(csv.DictReader(handle))


def test_resume_rejects_changed_scientific_config(tmp_path) -> None:
    config = ExperimentConfig(
        name="resume_guard",
        device="cpu",
        seeds=(17,),
        steps=1,
        points=16,
        parameter_batch=1,
        width=8,
        hidden_layers=1,
        eval_grid_side=5,
        reference_cutoff=1,
        output_dir=str(tmp_path),
    )
    run_experiment(config)
    changed = ExperimentConfig(**{**config.__dict__, "anchor_scale": 0.2})
    with pytest.raises(ValueError, match="configuration fingerprint"):
        run_experiment(changed)


def test_experiment_rejects_duplicate_seeds(tmp_path) -> None:
    config = ExperimentConfig(
        name="duplicate_seed_guard",
        device="cpu",
        seeds=(7, 7),
        steps=1,
        points=8,
        output_dir=str(tmp_path),
    )
    with pytest.raises(ValueError, match="seeds must be unique"):
        run_experiment(config)


def test_completed_checkpoint_can_finalize_after_evaluation_interruption(tmp_path) -> None:
    config = ExperimentConfig(
        name="finalize_recovery",
        device="cpu",
        seeds=(19,),
        steps=1,
        points=16,
        parameter_batch=1,
        width=8,
        hidden_layers=1,
        eval_grid_side=5,
        reference_cutoff=1,
        checkpoint_every=1,
        resume=True,
        output_dir=str(tmp_path),
    )
    first = run_experiment(config)
    original_initial = first["runs"][0]["initial_loss"]
    (tmp_path / "seed_19" / "run_summary.json").unlink()
    (tmp_path / "seed_19" / "final.pt").unlink()
    recovered = run_experiment(config)
    assert recovered["runs"][0]["finalized_from_completed_checkpoint"]
    assert recovered["runs"][0]["initial_loss"] == original_initial
    assert (tmp_path / "seed_19" / "final.pt").is_file()


def test_partial_resume_preserves_original_initial_loss(tmp_path, monkeypatch) -> None:
    torch = __import__("torch")
    config = ExperimentConfig(
        name="partial_resume",
        device="cpu",
        seeds=(23,),
        steps=3,
        points=16,
        parameter_batch=1,
        width=8,
        hidden_layers=1,
        eval_grid_side=5,
        reference_cutoff=1,
        checkpoint_every=1,
        resume=True,
        output_dir=str(tmp_path),
    )
    original_step = torch.optim.Adam.step
    calls = 0

    def interrupted_step(optimizer, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated interruption")
        return original_step(optimizer, *args, **kwargs)

    monkeypatch.setattr(torch.optim.Adam, "step", interrupted_step)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        run_experiment(config)
    checkpoint = torch.load(tmp_path / "seed_23" / "latest.pt", weights_only=False)
    original_initial = float(checkpoint["training_rows"][0]["loss"])
    monkeypatch.setattr(torch.optim.Adam, "step", original_step)
    recovered = run_experiment(config)
    assert recovered["runs"][0]["initial_loss"] == original_initial


def test_tiny_ordered_residual_baseline_runs(tmp_path) -> None:
    config = ExperimentConfig(
        name="ordered",
        method="ordered_residual",
        device="cpu",
        seeds=(4,),
        steps=2,
        points=24,
        parameter_batch=1,
        width=12,
        hidden_layers=1,
        eval_grid_side=7,
        reference_cutoff=2,
        output_dir=str(tmp_path),
    )
    summary = run_experiment(config)
    assert summary["status"] == "COMPLETE"
    assert summary["config"]["method"] == "ordered_residual"


@pytest.mark.parametrize("method", ("wang_xie_trace", "dai_galerkin", "causal_sort"))
def test_tiny_recent_subspace_baselines_run(tmp_path, method) -> None:
    output = tmp_path / method
    config = ExperimentConfig(
        name=method,
        method=method,
        device="cpu",
        seeds=(5,),
        steps=1,
        points=24,
        parameter_batch=1,
        width=12,
        hidden_layers=1,
        eval_grid_side=7,
        reference_cutoff=2,
        output_dir=str(output),
    )
    summary = run_experiment(config)
    assert summary["status"] == "COMPLETE"
    assert summary["config"]["method"] == method
