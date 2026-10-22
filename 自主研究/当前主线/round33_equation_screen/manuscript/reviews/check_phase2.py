"""Lint original panel outputs without generating or substituting reviewer scores."""
import argparse
import difflib
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROLES = ("eic", "method", "domain", "perspective", "da")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections(text, level):
    matches = list(re.finditer(r"^" + "#" * level + r" ([^\n]+)$", text, re.M))
    return {m[1].strip(): text[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
            for i, m in enumerate(matches)}


def plain(text):
    return re.sub(r"[`*]", "", text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent / "full_v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a previous lint record")
    base = args.directory
    contract = json.loads((base / "contract.json").read_text(encoding="utf-8-sig"))
    manifest = json.loads((base / "inputs/manifest.json").read_text(encoding="utf-8-sig"))
    assert len(ROLES) == contract["panel_size"] == 5
    assert sha(base / "contract.json") == manifest["contract_sha256"]
    required = ("Dimension Scores", "Failure Condition Checks", "Review Body", "Editorial Decision")
    results = []
    for role in ROLES:
        path = base / f"{role}_phase2.md"
        if not path.exists():
            raise SystemExit(f"Pending reviewer: {role}; no partial-panel decision generated")
        packet = base / f"inputs/{role}_phase2_input.md"
        phase1_path = base / f"{role}_phase1.md"
        assert sha(packet) == manifest["packets"][role]["sha256"]
        assert sha(phase1_path) == manifest["packets"][role]["phase1_sha256"]
        body = path.read_text(encoding="utf-8-sig")
        head = sections(body, 2)
        failures = []
        positions = [body.find("## " + title) for title in required]
        if not all(p >= 0 for p in positions) or positions != sorted(positions):
            failures.append("required_section_order")
        dissent = set(re.findall(r"\bD[1-5]\b", head.get("Scoring Plan Dissent", "")))
        if len(dissent) > 1:
            failures.append("multi_dissent")
        scored = sections(head.get("Dimension Scores", ""), 3)
        old = sections(phase1_path.read_text(encoding="utf-8-sig"), 3)
        scores, matches = {}, {}
        for dim in contract["acceptance_dimensions"]:
            key = f'{dim["id"]}: {dim["name"]}'
            text = plain(scored.get(key, ""))
            values = re.findall(r"\bscore\s*:\s*(pass|warn|block)\b", text)
            if len(values) != 1:
                failures.append(f'{dim["id"]}.score_missing_or_duplicate')
                continue
            scores[dim["id"]] = values[0]
            prior = plain(old.get(key, ""))
            trigger_lines = [line for line in prior.splitlines() if "what_triggers_" in line]
            lengths = []
            for line in trigger_lines:
                trigger = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
                match = difflib.SequenceMatcher(None, trigger, text, autojunk=False).find_longest_match()
                lengths.append(trigger[match.a:match.a + match.size])
            longest = max(lengths, key=len, default="")
            matches[dim["id"]] = longest
        conditions = sections(head.get("Failure Condition Checks", ""), 3)
        fired = {}
        for condition in contract["failure_conditions"]:
            cid = condition["condition_id"]
            pieces = [v for k, v in conditions.items() if re.match(r"^" + cid + r"(?:\b|:)", k)]
            values = re.findall(r"\bfired\s*:\s*(true|false)\b", plain("\n".join(pieces)))
            if len(values) != 1:
                failures.append(f"{cid}.fired_missing_or_duplicate")
            else:
                fired[cid] = values[0] == "true"
        if len(scores) == 5:
            expected = {"F1": any(scores[d] == "block" for d in ("D1", "D2", "D3")),
                        "F2": sum(scores[d] != "pass" for d in ("D1", "D2", "D3")) >= 2,
                        "F3": scores["D4"] == "block",
                        "F0": all(scores[d] == "pass" for d in ("D1", "D2", "D3"))}
            if fired != expected:
                failures.append("condition_score_inconsistency")
        candidates = [c for c in contract["failure_conditions"] if fired.get(c["condition_id"])]
        derived = max(candidates, key=lambda c: c["severity"])["action"] if candidates else None
        decision_text = plain(head.get("Editorial Decision", ""))
        declared = re.findall(r"\beditorial_decision\s*[:=]\s*(reject_or_major_revision|major_revision|accept)\b", decision_text)
        expected_action = derived.split("=", 1)[1] if derived else None
        if expected_action is None or expected_action not in declared:
            failures.append("decision_not_derivable_from_fired_condition")
        results.append({"role": role, "path": str(path), "sha256": sha(path), "scores": scores,
                        "fired": fired, "derived_action": derived, "dissent_dimensions": sorted(dissent),
                        "phase1_trigger_substrings": matches, "structural_pass": not failures,
                        "trigger_consistency_requires_orchestrator_read": True,
                        "failures": failures})
    usable = sum(r["structural_pass"] for r in results)
    result = {"checked_utc": datetime.now(timezone.utc).isoformat(), "contract_sha256": sha(base / "contract.json"),
              "panel_size": 5, "usable_phase2_outputs": usable, "reports": results,
              "panel_cardinality_pass": usable == 5,
              "protocol_status": "READY_FOR_SYNTHESIS" if usable == 5 else "PANEL-SHRUNK",
              "limits": "结构与机械一致性核查，不是语义审稿；不替换分数，不修改评语，不决定科研正确性。"}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"usable": usable, "failures": {r["role"]: r["failures"] for r in results}}, ensure_ascii=False))
    return 0 if usable == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
