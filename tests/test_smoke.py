from block_kyfan_pinn.smoke import SmokeConfig, run_smoke


def test_cpu_smoke_training_passes_engineering_gates(tmp_path) -> None:
    result = run_smoke(
        SmokeConfig(device="cpu", steps=12, points=48, width=24, hidden_layers=2),
        output_path=tmp_path / "smoke.json",
    )
    assert result["status"] == "PASS"
    assert result["final_energy"] < result["initial_energy"]
    assert result["orthogonality_error"] < 1e-4
    assert result["residual_rms"] >= 0.0
    assert 0.0 <= result["projector_sine_error"] <= 1.0
    assert len(result["reference_eigenvalues"]) == 2
    assert (tmp_path / "smoke.json").is_file()
