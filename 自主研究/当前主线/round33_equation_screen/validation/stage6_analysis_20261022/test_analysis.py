"""Standard-library unit tests; synthetic inputs stay in tests and never make figures."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import analyze_stage6 as a
import plot_stage6 as p


class AnalysisTests(unittest.TestCase):
    def test_exact_registered_matrix(self):
        self.assertEqual(len(a.JOBS), 30)
        self.assertEqual(len(set(a.JOBS)), 30)
        self.assertEqual({j[3] for j in a.JOBS}, {0, 1, 2})
        self.assertEqual(len(a.OLD_JOBS), 18)

    def test_duplicate_task_rejected_even_if_count_thirty(self):
        rows = [{"job": list(j)} for j in a.JOBS]
        rows[-1] = rows[0]
        with self.assertRaises(ValueError):
            a.exact_jobs(rows, a.JOBS, "synthetic test")

    def test_missing_task_rejected(self):
        with self.assertRaises(ValueError):
            a.exact_jobs([{"job": list(j)} for j in a.JOBS[:-1]], a.JOBS, "synthetic test")

    def test_wrong_seed_rejected(self):
        rows = [{"job": list(j)} for j in a.JOBS]
        rows[0]["job"][-1] = 100
        with self.assertRaises(ValueError):
            a.exact_jobs(rows, a.JOBS, "synthetic test")

    def test_tolerance_is_reference_relative(self):
        a.close_sequence([1.000009] * 5, [1.] * 5, "within")
        with self.assertRaises(ValueError):
            a.close_sequence([1.00002] * 5, [1.] * 5, "outside")

    def test_truncated_sequence_rejected(self):
        with self.assertRaises(ValueError):
            a.close_sequence([1.] * 4, [1.] * 5, "short")

    def test_nonfinite_nested_values_rejected(self):
        with self.assertRaises(ValueError):
            a.finite({"heldout": {"pde": float("nan")}})

    def test_complete_gate_fails_before_outputs_while_running(self):
        with tempfile.TemporaryDirectory(dir=r"D:\CodexRuntime\temp") as folder:
            runtime = Path(folder)
            a.write(runtime / "status.json", {"phase": "running", "tasks": []})
            with self.assertRaisesRegex(ValueError, "仅允许 --partial"):
                a.completion_gate(root=runtime, stage=runtime, runtime=runtime)
            self.assertEqual({x.name for x in runtime.iterdir()}, {"status.json"})

    def test_completed_label_alone_cannot_pass_gate(self):
        with tempfile.TemporaryDirectory(dir=r"D:\CodexRuntime\temp") as folder:
            runtime = Path(folder)
            a.write(runtime / "status.json", {"phase": "completed", "tasks": []})
            with self.assertRaisesRegex(ValueError, "任务缺失或重复"):
                a.completion_gate(root=runtime, stage=runtime, runtime=runtime)

    def test_partial_never_returns_final_judgment(self):
        with tempfile.TemporaryDirectory(dir=r"D:\CodexRuntime\temp") as folder:
            runtime = Path(folder)
            a.write(runtime / "status.json", {"phase": "running", "tasks": [{"state": "running"}]})
            result = a.partial_status(root=runtime, stage=runtime, runtime=runtime)
            self.assertEqual(result["analysis_state"], "partial")
            self.assertFalse(result["final_criteria_evaluated"])
            self.assertNotIn("S6_SOAP", result)
            self.assertEqual(result["counts"]["running"], 1)

    def test_soap_boundary_inclusive(self):
        result = a.soap_judgment({"median": .03}, {"median": .01, "under_1e2": 2})
        self.assertTrue(result["passed"])

    def test_stale_snapshot_is_not_live_progress(self):
        observed = a.datetime(2026, 10, 23, 2, tzinfo=a.timezone.utc)
        result = a.snapshot_freshness({"updated_utc": "2026-10-23T01:00:00Z"}, observed)
        self.assertEqual(result["timestamp_status"], "stale")
        self.assertEqual(result["age_seconds"], 3600)
        self.assertFalse(result["runner_identity_verified"])

    def test_recent_snapshot_does_not_verify_process(self):
        observed = a.datetime(2026, 10, 23, 2, tzinfo=a.timezone.utc)
        result = a.snapshot_freshness({"updated_utc": "2026-10-23T02:00:00+00:00"}, observed)
        self.assertEqual(result["timestamp_status"], "recent_snapshot")
        self.assertFalse(result["runner_identity_verified"])

    def test_bad_or_future_timestamp_cannot_imply_freshness(self):
        observed = a.datetime(2026, 10, 23, 2, tzinfo=a.timezone.utc)
        for value in (None, "invalid", "2026-10-23T02:00:00"):
            self.assertEqual(a.snapshot_freshness({"updated_utc": value}, observed)["timestamp_status"], "unknown_timestamp")
        self.assertEqual(a.snapshot_freshness({"updated_utc": "2026-10-23T03:00:00Z"}, observed)["timestamp_status"], "clock_inconsistent")

    def test_soap_ratio_alone_is_not_enough(self):
        result = a.soap_judgment({"median": .1}, {"median": .02, "under_1e2": 1})
        self.assertFalse(result["passed"])

    def test_soap_success_count_alone_is_not_enough(self):
        result = a.soap_judgment({"median": .02}, {"median": .009, "under_1e2": 3})
        self.assertFalse(result["passed"])

    def test_both_zero_is_not_threefold_improvement(self):
        result = a.soap_judgment({"median": 0}, {"median": 0, "under_1e2": 3})
        self.assertFalse(result["passed"])
        self.assertIsNone(result["hardic_over_layer"])

    def test_old_diagnostics_are_missing_not_zero(self):
        row = {"tag": "confirm", "eq": "E1_heat", "method": "vanilla", "seed": 0,
               "optimizer": "adam", "tau": .1, "training_location": "历史云端 confirm",
               "max_vol": .1, "max_trace": .2, "final_adam_loss": .1, "final_lbfgs_loss": .01,
               "recorded_wall_seconds": 1000, "recorded_adam_seconds": 800, "source": "test-only",
               "source_sha256": "test-only", "missing_diagnostics_note": "未保存", "calls": {},
               "resumed_at": [], "metrics": {"vol": [1.] * 5, "trace": [2.] * 5},
               "heldout": None, "optimizer_accounting": None, "environment": {}, "attempts": None}
        result = a.flat(row)
        self.assertIsNone(result["heldout_pde_rms"])
        self.assertIsNone(result["attempt_wall_seconds_sum"])
        self.assertIsNone(result["optimizer_parameter_updates_semantics"])

    def test_partial_cannot_render(self):
        with self.assertRaises(ValueError):
            p.validate_plot_input({"analysis_state": "partial", "new_task_count": 30})

    def test_local_chinese_font_exists_and_covers_labels(self):
        metadata = p.font_setup()
        self.assertTrue(metadata["chinese_glyph_check"])
        self.assertTrue(Path(metadata["font_file"]).is_file())

    @staticmethod
    def synthetic_records_for_aggregation_only():
        records = {}
        for job in a.OLD_JOBS + a.JOBS:
            tag, eq, method, seed = job
            is_old = tag == "confirm"
            tau = .03 if tag == "sensitivity_tau003_v1" else .3 if tag == "sensitivity_tau03_v1" else .1
            base = .001 * (seed + 1)
            if method == "hardic":
                base *= 4 if eq == "E1_heat" else 2
            elif method == "vanilla":
                base *= 8
            base *= tau / .1
            records[job] = {"job": list(job), "tag": tag, "eq": eq, "method": method, "seed": seed,
                            "tau": tau, "optimizer": "soap_official64" if tag == "final_soap64_v1" else "adam",
                            "training_location": "历史云端 confirm" if is_old else "本机 stage6",
                            "max_vol": base, "max_trace": base * 2,
                            "recorded_wall_seconds": 10000 if is_old else 100,
                            "attempts": None if is_old else [{"wall_seconds": 105}]}
        return records

    def test_soap_joint_does_not_hide_one_failed_equation(self):
        audit = a.summarize(self.synthetic_records_for_aggregation_only(),
                            {"runtime_status": {"total_runner_wall_seconds": 1000}})
        self.assertEqual(audit["S6_SOAP"]["conclusion"], "部分满足")
        self.assertFalse(audit["S6_SOAP"]["joint_passed"])
        self.assertEqual([r["passed"] for r in audit["S6_SOAP"]["per_equation"]], [True, False])

    def test_tau_all_three_levels_retained_without_reselecting_main(self):
        audit = a.summarize(self.synthetic_records_for_aggregation_only(),
                            {"runtime_status": {"total_runner_wall_seconds": 1000}})
        self.assertEqual(len(audit["tau_groups"]), 6)
        for row in audit["tau_summary"]:
            self.assertEqual(row["main_tau_unchanged"], .1)
            self.assertFalse(row["tau_selected_from_results"])
            self.assertAlmostEqual(row["across_tau_max_over_min_median"], 10)
        self.assertEqual(len(audit["default_groups"]), 12)
        self.assertEqual(sum(len(r["seeds"]) for r in audit["default_groups"]), 36)

    def test_cloud_and_local_times_are_separate(self):
        audit = a.summarize(self.synthetic_records_for_aggregation_only(),
                            {"runtime_status": {"total_runner_wall_seconds": 1000}})
        costs = audit["costs"]
        self.assertEqual(costs["new_local_30"]["trajectory_seconds_sum"], 3000)
        self.assertEqual(costs["historical_cloud_18"]["trajectory_seconds_sum"], 180000)
        self.assertEqual(costs["local_runner_elapsed_seconds"], 1000)
        self.assertEqual(costs["local_attempt_wall_seconds_sum"], 3150)
        self.assertNotIn("speedup", costs)

    def test_plot_refuses_unbound_aggregates_without_drawing(self):
        audit = a.summarize(self.synthetic_records_for_aggregation_only(),
                            {"runtime_status": {"total_runner_wall_seconds": 1000}})
        with self.assertRaisesRegex(ValueError, "完整性绑定"):
            p.validate_plot_input(audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
