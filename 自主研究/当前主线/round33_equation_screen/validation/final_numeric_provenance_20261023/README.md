# 2026-10-23 保存权重的只读数值复算证据

本目录补充当前论文体误差和边界迹误差的可审计生产链。它是 2026-10-23 新发生的独立执行记录，不是旧训练日志，不追回旧训练退出码、警告、损失轨迹或未保存的计数。

## 固定范围

- `plan.json` 固定全部 206 个结果及 488 个原始 JSON/PT 文件 SHA256。130 个旧结果的 260 文件还与已有独立复核清单相符。原始数据、结果表和核心代码只读。
- N64/GL200 与 N96/GL400，五时刻 0.05、0.1、0.25、0.5、1；逐值对原记录比较 `rtol=1e-5, atol=1e-9`。
- 每种方程重新求 N48、64、96 参考解；N48/N96 在五时刻与 401 个等距点的最大绝对差要求不超过 `1e-8`。
- 每个模型按原 JSON 的实际配置（包括 PirateNet 架构参数）在 meta 设备构造，然后严格重载 PT；全部预测参数必须实际存在且有限。完整模型与兼容 base PT 逐张量一致。
- 20 个旧 E4 不含表面权重，未加载的 `surf` 分支明确删除。只重算体和边界迹，排除 `v(t)` 与表面/交换残差；没有随机补齐缺失权重。
- 新检查器独立实现重载、求积、比较和生产链，模型前向及参考解调用冻结的原项目实现。它不是另一个独立 PDE 求解器，也不改变原研究判据。

## 真实执行与文件链

专用 Python 为 `D:/CodexRuntime/venvs/r33-torch214/Scripts/python.exe`。每个子进程单线程，最多 8 进程；运行、缓存和临时路径全部位于 `D:/CodexRuntime`。

`recompute_saved_models.py prepare` 固定输入及源码；`run --batch probe --workers 8` 覆盖八个指定实例；独立源码审查后执行 `run --batch full --workers 8`。已有批次目录不能覆盖。检查器没有训练入口；导入模块的训练函数另设禁止调用保护。

每个 reference/model 子进程均保存实际 argv、Windows 命令表示、cwd、起止时间、环境版本、解释器 SHA256、单线程配置、导入模块文件 SHA256、stdout、stderr、结构化 warnings、OS 子进程实际 returncode、输出 NPZ 数组及各项对照。`intended_exit_code` 是进程内部记录，`execution.json.actual_returncode` 是父进程观察到的真实退出码，两者不混用。

原始 JSON/权重在批次前后与每个模型重载前后核对哈希；求积前后核对已加载参数的逐张量字节身份。每个批次新生成参考数组，再由模型工作进程绑定其 SHA256。全部原始 stderr/warnings 和失败结果保留；数值失败导致真实非零退出码，不删除种子、不放宽容差。

执行原件在 `D:/CodexRuntime/runs/r33_final_numeric_provenance_20261023/{probe,full}`，必要证据逐字节复制到 `evidence/{probe,full}`，复制后按完整清单核验。只有实际运行形成的 `summary.json` 才能支持当次结果结论。

`launch_logged.ps1` 另记录全批父进程的真实退出码及完整 stdout/stderr，归档到 `supervisors/full` 或 `supervisors/heldout`；子进程实际退出码仍以各自 `execution.json` 为准。本目录 `.gitattributes` 禁止 Git 文本行尾转换，以保持冻结文件的精确字节身份。

## 已有独立检验点残差的补充核验

`recompute_heldout.py` 与 `heldout_plan.json` 是独立补充入口，不改上述已冻结检查器/计划。覆盖原已保存的 52 条 heldout 记录：stage5 的 PirateNet 4 条及新初值 18 条，stage6 的 30 条。原报告逐字节复制在 `heldout_source_records`；stage6 使用完成归档中的记录。

原定义来自 `stage5_support.py:42` 与 `pinn1d.py:258`，抽样顺序固定为 `default_rng(330500)` 生成体 x 8192、体 t 8192、左边界 t 1024、右边界 t 1024、初值 x 1024。x 均匀分布于 [0,1]，t 均匀分布于 [1e-4,1]，体残差以 1024 点切块。补充脚本独立写出相同数学式的 autograd 计算及 RMS/max_abs 聚合，逐项对旧记录比较，并保存实际点集和每点残差数组。原权重和报告前后检查 SHA256；无训练更新，也不重算旧训练损失。

补充运行须先通过独立源码审核；完成证据位于 `evidence/heldout`。这 52 条均有完整模型，不含旧 E4；不为缺失历史表面分支补生成数值。

## 证据边界

成功复算只能支持当前保存权重下的体/迹误差可重现、输入未被改写及本次生产过程有记录。它不能证明旧训练从未出错、跨机器训练轨迹一致、旧未保存表面输出正确、任意初值泛化或论文满足全部独立审查要求。最终可用性由整体审查在本次真实输出与源码核查后裁定。
