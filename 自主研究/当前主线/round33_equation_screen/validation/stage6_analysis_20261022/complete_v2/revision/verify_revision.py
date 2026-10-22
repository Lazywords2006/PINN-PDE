"""Freeze the three presentation fixes against the preserved complete_v1.

Run with the analysis venv. This reads saved results and draws existing values;
it never imports training code, loads model weights, or updates formal outputs.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone

os.environ.setdefault("MPLCONFIGDIR", r"D:\CodexRuntime\cache\matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", r"D:\CodexRuntime\cache\xdg")
REV = Path(__file__).resolve().parent
V2 = REV.parent
ANALYSIS = V2.parent
ROOT = ANALYSIS.parent.parent
V1 = ANALYSIS / "complete_v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    before = read(REV / "before_manifest.json")
    v1, v2 = read(V1 / "analysis_evidence.json"), read(V2 / "analysis_evidence.json")
    preserved = before["complete_v1_sha256"]
    assert len(preserved) == 9
    assert all(sha(V1 / name) == digest for name, digest in preserved.items())
    assert sha(ROOT / "validation/stage6_20261022/engineering_gate.json") == before["gate_sha256"]
    assert all(sha(ROOT / name) == digest for name, digest in before["gate_bound_source_sha256"].items())
    assert len(before["gate_bound_source_sha256"]) == 12
    assert sha(ROOT / before["review_source"]) == before["review_sha256"]

    allowed = {"generated_local", "figure_metadata", "analysis_code_sha256", "output_sha256"}
    assert set(v1) == set(v2)
    changed = {name for name in v1 if v1[name] != v2[name]}
    assert changed == allowed, changed
    identical = sorted(set(v1) - allowed)
    assert len(v2["records"]) == 48
    assert len(v2["default_groups"]) == 12 and len(v2["tau_groups"]) == 6
    assert v2["analysis_state"] == "complete" and v2["new_task_count"] == 30
    assert len(v2["evidence"]["raw_sha256"]) == 488
    assert all(sha(V2 / name) == digest for name, digest in v2["output_sha256"].items())
    assert all(sha(ANALYSIS / name) == digest for name, digest in v2["analysis_code_sha256"].items())

    csv_checks = {}
    for name, count in (("all_new_runs.csv", 30), ("default_six_arms.csv", 36), ("tau_sensitivity.csv", 18)):
        assert (V1 / name).read_bytes() == (V2 / name).read_bytes()
        with (V2 / name).open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) - 1 == count and len(rows[0]) == 45
        csv_checks[name] = {"byte_identical_to_v1": True, "sha256": sha(V2 / name), "rows": count, "columns": 45}

    old_tree = ast.parse((REV / "before/analyze_stage6.py").read_text(encoding="utf-8-sig"))
    new_tree = ast.parse((ANALYSIS / "analyze_stage6.py").read_text(encoding="utf-8-sig"))
    def without_report(tree):
        return ast.dump(ast.Module(body=[node for node in tree.body
            if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "report")], type_ignores=[]))
    assert without_report(old_tree) == without_report(new_tree)
    text1 = (V1 / "STAGE6_ANALYSIS_20261022.md").read_text(encoding="utf-8")
    text2 = (V2 / "STAGE6_ANALYSIS_20261022.md").read_text(encoding="utf-8")
    old_tables = [line for line in text1.splitlines() if line.startswith("|")]
    new_tables = [line for line in text2.splitlines() if line.startswith("|")]
    assert old_tables == new_tables
    assert [line for line in text1.splitlines() if "B-1/B-2/G2" in line] == [line for line in text2.splitlines() if "B-1/B-2/G2" in line]
    tests_log = (REV / "analysis_tests.log").read_text(encoding="utf-8-sig")
    assert "Ran 26 tests" in tests_log and tests_log.rstrip().endswith("OK")

    visual = []
    visual_dir = REV / "visual_checks"
    visual_dir.mkdir(exist_ok=True)
    for stem in ("default_six_arms", "tau_sensitivity"):
        preview = Path(r"D:\CodexRuntime\runs\r33_stage6_analysis_20261022\complete_v2_visual_preview") / (stem + ".png")
        assert sha(preview) == sha(V2 / (stem + ".png"))
        pdf_preview = Path(r"D:\CodexRuntime\runs\r33_stage6_analysis_20261022\complete_v2_pdf_preview") / (stem + ".png")
        saved = visual_dir / (stem + "_pdf_render.png")
        shutil.copyfile(pdf_preview, saved)
        pdf_text = (REV / (stem + ".pdf.txt")).read_text(encoding="utf-8-sig")
        compact = "".join(pdf_text.split())
        assert "Adam→L-BFGS" in compact
        if stem == "default_six_arms":
            assert "SOAP64→L-BFGS" in compact
        assert "五时刻最大体相对L²误差" in compact
        assert "t={0.05,0.1,0.25,0.5,1}" in compact and "非连续时间上确界" in compact
        info = (REV / (stem + ".pdfinfo.txt")).read_text(encoding="utf-8-sig")
        assert re.search(r"Pages:\s+1\b", info)
        visual.append({"figure": stem, "png_sha256": sha(V2 / (stem + ".png")),
            "png_identical_to_original_resolution_viewed_preview": True,
            "pdf_sha256": sha(V2 / (stem + ".pdf")), "pdf_pages": 1,
            "actual_pdf_render": str(saved.relative_to(V2)), "pdf_render_sha256": sha(saved),
            "required_route_metric_and_time_text_extracted": True,
            "author_visual_review": "PASS: original PNG and actual PDF rendering; readable labels and seed markers, no missing glyphs, overlaps or clipping"})

    spec = importlib.util.spec_from_file_location("verified_plot_stage6", ANALYSIS / "plot_stage6.py")
    plot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plot)
    plot.validate_plot_input(v2)
    plot.font_setup()
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection, PathCollection
    layer_checks = []
    for row in v2["default_groups"] + v2["tau_groups"]:
        fig, ax = plt.subplots()
        plot.draw_group(ax, 0, row, "#D00000")
        lines = [item for item in ax.collections if isinstance(item, LineCollection)]
        points = [item for item in ax.collections if isinstance(item, PathCollection)]
        assert len(lines) == 2 and len(points) == 3
        assert [item.get_zorder() for item in lines] == [2, 3]
        assert [item.get_zorder() for item in points] == [4, 4, 4]
        assert [float(item.get_offsets()[0, 1]) for item in points] == row["seeds"]
        assert list(lines[1].get_segments()[0][:, 1]) == [row["median"], row["median"]]
        layer_checks.append({"tag": row["tag"], "eq": row["eq"], "method": row["method"],
            "tau": row.get("tau"), "range_zorder": 2, "median_zorder": 3,
            "seed_zorders": [4, 4, 4], "seed_values_unchanged": True})
        plt.close(fig)

    source_after = REV / "after"
    source_after.mkdir(exist_ok=True)
    for name in ("analyze_stage6.py", "plot_stage6.py"):
        shutil.copyfile(ANALYSIS / name, source_after / name)
    shutil.copyfile(ROOT / "validation/.gitattributes", source_after / "validation.gitattributes")
    git_root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT).decode().strip())
    source_paths = [ANALYSIS / "analyze_stage6.py", ANALYSIS / "plot_stage6.py", ROOT / "validation/.gitattributes"]
    paths = [str(path.relative_to(git_root)).replace("\\", "/") for path in source_paths]
    diff = subprocess.check_output(["git", "-C", str(git_root), "diff", "--", *paths])
    (REV / "presentation_changes.diff").write_bytes(diff)
    subprocess.run(["git", "-C", str(git_root), "diff", "--check", "--", *paths], check=True, capture_output=True)
    blob_checks = []
    for path in sorted(V2.rglob("*")):
        if not path.is_file() or path.name in ("REVISION_EVIDENCE.json", "git_blob_integrity.json"):
            continue
        relative = path.relative_to(git_root).as_posix()
        attr = subprocess.check_output(["git", "-C", str(git_root), "check-attr", "text", "--", relative]).decode("utf-8")
        assert attr.rstrip().endswith(": text: unset"), attr
        oid = subprocess.check_output(["git", "-C", str(git_root), "hash-object", "-w", "--path", relative, str(path)]).decode().strip()
        blob = subprocess.check_output(["git", "-C", str(git_root), "cat-file", "blob", oid])
        assert blob == path.read_bytes()
        blob_checks.append({"path": path.relative_to(V2).as_posix(), "git_blob_oid": oid,
                            "workspace_and_blob_sha256": sha(path), "text_attribute": "unset"})
    write(REV / "git_blob_integrity.json", {"all_exact": True, "files_checked": len(blob_checks), "files": blob_checks})
    formal = {name: sha(V2 / name) for name in preserved}
    evidence = {"schema": "r33_stage6_presentation_revision_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_INDEPENDENT_TARGETED_REVIEW", "revision": "complete_v2",
        "baseline": "complete_v1", "baseline_commit": before["baseline_commit"],
        "review_source": before["review_source"], "review_source_sha256": before["review_sha256"],
        "addressed_findings": ["S6-F01", "S6-F02", "S6-F03"],
        "complete_v1_preserved_sha256": preserved, "complete_v2_formal_sha256": formal,
        "csv_checks": csv_checks, "identical_analysis_fields": identical,
        "permitted_changed_metadata_fields": sorted(changed),
        "record_count": 48, "default_groups": 12, "tau_groups": 6,
        "all_report_table_lines_unchanged": True, "B1_B2_G2_statement_unchanged": True,
        "analyzer_AST_identical_except_report_function": True,
        "gate_sha256_unchanged": before["gate_sha256"], "all_12_gate_bound_sources_unchanged": True,
        "gate_bound_source_sha256": before["gate_bound_source_sha256"],
        "source_sha256_before": before["source_sha256_before"],
        "source_sha256_after": {str(path.relative_to(ROOT)): sha(path) for path in source_paths},
        "analysis_tests": {"passed": 26, "failed": 0, "log_sha256": sha(REV / "analysis_tests.log")},
        "visual_checks": visual, "all_18_actual_data_group_layer_checks": layer_checks,
        "git_blob_integrity_sha256": sha(REV / "git_blob_integrity.json"),
        "git_blob_files_checked": len(blob_checks), "presentation_diff_sha256": sha(REV / "presentation_changes.diff"),
        "version_mapping_sha256": sha(V2 / "VERSION_MAPPING.md"),
        "verification_script_sha256": sha(Path(__file__)),
        "limits": ["Author rendering and equivalence checks, awaiting independent targeted review",
                   "No new training, model reload, protocol changes or statistical decision changes"]}
    write(REV / "REVISION_EVIDENCE.json", evidence)
    print(json.dumps({"status": evidence["status"], "formal_files": len(formal), "csv_byte_identical": 3,
        "records_unchanged": 48, "analysis_tests_passed": 26, "real_data_layer_groups": len(layer_checks),
        "git_blobs_exact": len(blob_checks), "evidence_sha256": sha(REV / "REVISION_EVIDENCE.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
