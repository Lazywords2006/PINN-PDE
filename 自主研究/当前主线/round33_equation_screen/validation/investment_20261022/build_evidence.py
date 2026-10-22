"""只读检查 R33 旧/新产物，并生成完整测试投入的预算证据；不训练。"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True,
                        help="本机 Get-CimInstance 快照 JSON，不含身份/序列号")
    args = parser.parse_args()
    dest = Path(__file__).resolve().parent
    r33 = dest.parent.parent
    root = r33.parents[2]
    review = json.loads((r33 / "validation/resolution_20261022/preflight_review.json").read_text(encoding="utf-8"))
    old = json.loads((r33 / "validation/feasibility_review_20261021/existing_data_review.json").read_text(encoding="utf-8"))
    old_ok = all(sha(r33 / name) == h for name, h in old["SHA256清单"].items())
    new_ok = all(
        sha(r33 / row["文件"]) == row["JSON_SHA256"]
        and all(
            sha((r33 / row["文件"]).with_name(a["file"])) == a["sha256"]
            for a in row["产物"].values() if isinstance(a, dict)
        )
        for row in review["逐结果"]
    )
    core = ["pinn1d.py", "problems.py", "soap_baseline.py", "run_artifacts.py", "screen.py"]
    core_ok = subprocess.run(
        ["git", "diff", "--quiet", "c31355c", "--", *[str(r33 / name) for name in core]],
        cwd=root, check=False,
    ).returncode == 0
    protocol_ok = subprocess.run(
        ["git", "diff", "--quiet", "d25bd35", "--", str(r33 / "SCREEN_PROTOCOL.md")],
        cwd=root, check=False,
    ).returncode == 0
    test_log = r33 / "validation/resolution_20261022/pytest_final.log"
    assert "63 passed" in test_log.read_text(encoding="utf-8")
    assert len(old["SHA256清单"]) == 260
    assert len(review["逐结果"]) == 24
    assert old_ok and new_ok and core_ok and protocol_ok

    est = collections.defaultdict(list)
    for row in review["逐结果"]:
        hours = (10 * row["Adam耗时秒"] + 12 * (row["耗时秒"] - row["Adam耗时秒"])) / 3600
        est[row["tag"]].append(hours)
    projections = {
        key: {"min_h": min(values), "median_h": statistics.median(values),
              "max_h": max(values), "projection_only": True}
        for key, values in est.items()
    }
    adam = statistics.median(est["preflight4_adam"])
    soap = statistics.median(est["preflight4_soap64"])
    plan = [
        {"阶段": 1, "工作": "E1 PirateNet 断点续跑", "任务数": 4,
         "新增从头完整训练": 0, "用于规划的并行整批小时区间": [2, 6]},
        {"阶段": 1, "工作": "两方程各一个新初值，三方法三报告种子", "任务数": 18,
         "新增从头完整训练": 18, "八进程理想摊分小时": 18 * adam / 8},
        {"阶段": 2, "工作": "两方程两个附加tau值，三报告种子；仅作灵敏度", "任务数": 12,
         "新增从头完整训练": 12, "八进程理想摊分小时": 12 * adam / 8},
        {"阶段": 2, "工作": "两方程三方法三报告种子；SOAP64固定lr=0.001", "任务数": 18,
         "新增从头完整训练": 18, "八进程理想摊分小时": 18 * soap / 8},
    ]
    host = json.loads(args.host.read_text(encoding="utf-8-sig"))
    counts = {d.name: len(list(d.rglob("*.json")))
              for d in sorted((r33 / "runs").iterdir()) if d.is_dir()}
    for missing in ("soap1e3", "soap3e3", "ic1000"):
        counts.setdefault(missing, 0)
    assert sum(counts.values()) == 154
    result = {
        "状态": "分析与待确认草案；未启动新训练，未修改生效协议",
        "本轮新增训练次数": 0,
        "旧G2判定": "失败，保持停止自动扩展；新目的须另行追加协议",
        "原260文件哈希未变": old_ok,
        "新24结果及产物哈希未变": new_ok,
        "关键代码与已测提交相同": core_ok,
        "SCREEN_PROTOCOL与d25bd35相同": protocol_ok,
        "既有测试通过数": 63,
        "测试结果使用范围": "复用同代码的既有结果；本轮未重跑测试，未来新增方程代码须完整重测",
        "测试日志SHA256": sha(test_log),
        "本机": host,
        "仓库当前tag的JSON数": counts,
        "计时投影模型": "优化阶段full=pilot*5步数*2体点；LBFGS阶段full=pilot*6预算*2体点；非实测预测，忽略早停/closure/负载等非线性",
        "投影": projections,
        "候选初值": {"E1": "0.5*cos(pi*x)", "E1_delta": 0.5 - 0.5 * math.pi**2,
                  "E3": "0.05*(1+cos(pi*x))", "E3_delta": 1 / 0.3 - 0.005 * math.pi**2},
        "阶段草案": plan,
        "总任务数": sum(p["任务数"] for p in plan),
        "新增从头完整训练总数": sum(p["新增从头完整训练"] for p in plan),
        "第一阶段任务数": sum(p["任务数"] for p in plan if p["阶段"] == 1),
        "第二阶段任务数": sum(p["任务数"] for p in plan if p["阶段"] == 2),
        "MLP投影进程小时": 30 * adam + 18 * soap,
        "MLP八进程理想摊分小时": (30 * adam + 18 * soap) / 8,
        "时间规划": {"首阶段小时": [8, 16], "两阶段总小时": [16, 36], "资源复盘小时": 48,
                  "性质": "外推预算，非完整训练实测；第二阶段另行决定"},
        "调参": "零搜索；tau灵敏度不改变默认0.1，不按参考误差倒选方法配置",
        "论文范围": "具体一维E1/E3上的经典角点层修正；不要求普遍优于所有强基线",
    }
    assert result["总任务数"] == 52
    assert result["新增从头完整训练总数"] == 48
    assert result["第一阶段任务数"] == 22 and result["第二阶段任务数"] == 30
    (dest / "investment_evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"检查": "通过", "tag_JSON总数": sum(counts.values()),
                      "任务数": result["总任务数"], "本轮新增训练": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
