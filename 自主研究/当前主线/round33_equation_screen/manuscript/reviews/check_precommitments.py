"""Check saved reviewer Phase 1 structure; never generate or substitute scores."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent / "full_v1"
ROLES = ("eic", "method", "domain", "perspective", "da")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    contract_path = BASE / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    required = contract["measurement_procedure"]["scoring_plan_schema"]["required"]
    dimensions = contract["acceptance_dimensions"]
    reports = []
    for role in ROLES:
        path = BASE / f"{role}_phase1.md"
        if not path.exists():
            reports.append({"role": role, "state": "pending"})
            continue
        body = path.read_text(encoding="utf-8-sig")
        paraphrase = body.find("## Contract Paraphrase")
        plan = body.find("## Scoring Plan")
        failures = []
        if not (0 <= paraphrase < plan):
            failures.append("required_section_order")
        if not body.rstrip().endswith("[CONTRACT-ACKNOWLEDGED]"):
            failures.append("terminal_acknowledgment")
        paragraphs = re.split(r"\n\s*\n", body[paraphrase:plan])
        covered = [d["id"] for d in dimensions
                   if any(re.search(r"\b" + d["id"] + r"\b", p) for p in paragraphs)]
        if len(covered) != len(dimensions):
            failures.append("paraphrase_dimension_coverage")
        found = list(re.finditer(r"^### (D\d+): ([^\r\n]+)\s*$", body[plan:], re.M))
        headers = [(m[1], m[2].strip()) for m in found]
        if headers != [(d["id"], d["name"]) for d in dimensions]:
            failures.append("scoring_plan_headers")
        for index, match in enumerate(found):
            stop = found[index + 1].start() if index + 1 < len(found) else len(body[plan:])
            section = body[plan:][match.end():stop]
            for field in required:
                if not any(field in line for line in section.splitlines()):
                    failures.append(f"{match[1]}.{field}")
        if re.search(r"^## (Dimension Scores|Failure Condition Checks|Review Body|Editorial Decision)", body, re.M):
            failures.append("phase2_section_in_phase1")
        reports.append({"role": role, "state": "checked", "sha256": digest(path),
                        "structural_pass": not failures, "failures": failures,
                        "paraphrase_covered": covered})
    report = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "contract_sha256": digest(contract_path),
        "metadata_sha256": digest(BASE / "metadata.json"),
        "review_stage": "phase1_only_no_paper_review_yet",
        "required_panel_size": contract["panel_size"],
        "phase1_structurally_usable": sum(r.get("structural_pass", False) for r in reports),
        "reports": reports,
        "limits": "仅检查结构；不证明触发条件语义质量或论文通过。盲性由独立调用只提供契约与元数据保证，不由文本扫描推断。",
    }
    (BASE / "phase1_lint.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if any(r.get("failures") for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
