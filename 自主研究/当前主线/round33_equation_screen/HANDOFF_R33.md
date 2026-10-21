# R33 交接文档（2026-10-22 JST 写，从云端会话转到用户本机 i7-14600K）

接手的人（或新的 Claude 会话）先读完本文，再读 `SCREEN_PROTOCOL.md`（含修订 1、2、3）、`SCREEN_REPORT.md`、`E4_PROTOCOL.md`、`RELATED_WORK.md`、`PAPER_PLAN.md`。仓库 `lazywords2006/pinn-pde`，分支 `claude/current-content-progress-e0d951-k5lc11`。目录 `自主研究/当前主线/round33_equation_screen/`（下称 R33 目录）。

## 0. 用户与规则

- 用户在日本，汇报时间一律用日本时间（JST，UTC+9）；报告、回复用中文。
- 论文主题：用神经网络（PINN 及其变种）解偏微分方程。用户反复提到的 “PNN” 在项目里按 PINN 处理（2026-10-13 的原话和档案第一节有记录；Specht 的概率神经网络、乘积神经网络都是分类/推荐模型，不能直接解 PDE，用户已被告知，未提出别的网络）。
- **预注册纪律**：每批实验的判据在看到结果之前写进协议（`SCREEN_PROTOCOL.md` 修订、`E4_PROTOCOL.md`）；之后只能追加“修订”。不为救判据调参；不调 τ、网络规模或预算去迁就某个方法；失败和未达标如实写；不宣称“首次”（新颖性没核完）。
- 云端的 `CLAUDE.md` 要求跑程序交给 Haiku 子会话；**用户现在改用本机跑，本机上可以直接运行命令**。
- 不要自动建 PR，除非用户明确要求。

## 1. 方法与方程（一句话版）

- 方程：一维抛物方程，x∈[0,1]，u_t = D u_xx + R(u)，x=0 处 u_x=0，x=1 处动态（Wentzell 型）边界 c u_t + D u_x + G(u) = 0，初值 f(x)。初值与动态边界在 (x=1,t=0) 不相容（错配 δ），产生时间角点层。
- 方程编号：E1 线性热方程（D=1,c=0.3,G=0.3u,f=x²−0.5）；E2 Allen–Cahn；E3 Fisher–KPP（D=0.1,c=0.3,R=u(1−u),G=u−1,f=0.1(1−x²)）；E4 体–面耦合（D=0.1,通量交换 D u_x=κ(v−u),表面变量 v，通量跳变型错配）。
- 候选方法 hardic+layer：u = f + t·N + δ·w·e^{−t/τ}（τ=0.1 固定）；硬初值加解析角点层校正，网络和优化器不变。E4 用通量层 −2Δ_y√(t/D)·ierfc(…)。校正项的数学是经典的半直线热方程解，PINN 里这个具体用法据检索未见先例（SL-PINN 只做空间边界层）。
- 基线（均已实现于 `pinn1d.py`）：vanilla、hardic、RBA、因果训练（`causal_eps`）、PirateNet（`arch=pirate`）、SOAP（`optimizer=soap`，自己用 float64 实现，因为 heavyball 包不支持 float64）、初值权重 1000 + 首段加密（`w_ic`、`t_refine`）。
- 完整预算：Adam 20000 步（lr 1e-3 指数衰减到 1e-5）、L-BFGS 3000 次，Nf=4096/8192、Nb=256/512、N0=256/512；float64，单线程每进程。

## 2. 已有结果（全部已在仓库 `runs/` 下，每个 run 有 json 和 pt）

| tag | 内容 | run 数 | 结论 |
|---|---|---|---|
| screen | 小预算筛选（E1–E3 × 5 方法 × 2 种子） | 30 | 只有 E3 按判据入选；E1 2.89 倍，E2 1.33 倍 |
| confirm | 完整预算确认（E1、E3 × 4 方法 × 3 种子） | 24 | 确认：E1 低 30 倍（1.2e-3 对 3.6e-2），E3 低 5.9 倍（3.9e-4 对 2.3e-3） |
| axis | 参数轴（E1 的 c、E3 的 κ，共 6 点 × 2 方法 × 3 种子） | 36 | 8 点中 6 点成立；错配越大优势越大，预注册预测成立 |
| causal1/causal10 | 因果训练 ε=1、10（叠加在硬初值上） | 12 | E1 低 12.5 倍；E3 只低 2.8 倍（<3，A-1 在 E3 上失败） |
| pirate | PirateNet（hardic、hardic+layer） | 8/12 | E3 完整（5.7e-4 对 1.0e-4，5.5 倍）；E1 只有种子 2（1.7e-2 对 7.6e-4）。**E1 种子 0、1 共 4 个 run 缺** |
| e4screen | E4 小预算筛选 | 8 | 判据不满足（1.39 倍），预测落空 |
| e4confirm | E4 完整预算（探索性，修订 1） | 12 | hardic+layer 5.6e-3 与 vanilla 4.7e-3 打平，都远好于 hardic 7.2e-2；负面结果 |

判定：A-1（强基线）不满足（E3 上 hardic+layer 对 PirateNet+hardic 只低 1.5 倍）；A-2（可叠加）E3 满足，E1 只有 1 个种子，**未能判定**。详见 `SCREEN_REPORT.md`。

## 3. 待办（按优先级）

1. **修订 3 基线**（判据 B-1/B-2/B-3，见 `SCREEN_PROTOCOL.md` 修订 3）：tag `soap1e3`（SOAP lr0=0.001，方法 vanilla、hardic、hardic+layer，E1+E3，种子 0–2，18 个）、`soap3e3`（lr0=0.003，18 个）、`ic1000`（vanilla，w_ic=1000，t_refine=0.3，E1+E3，种子 0–2，6 个）。共 42 个 run。云端已暂停，仓库里这三个 tag 目前都是 0 个 json，本机从头跑（`screen.py` 会自动跳过已有 json，所以中断后重跑同一条命令即可）。
2. **E1 PirateNet 种子 0、1**（tag `pirate`，4 个 run，每个 6–9 小时）：补齐后判 A-2。
3. 把 B-1/B-2/B-3 和 A-2 的结果写进 `SCREEN_REPORT.md` 和 `总览/00_当前研究总档案.md` 的 R33 一节，推送。
4. 读 Awais 等 2026（*Physics-informed neural networks for the heat equation with dynamic (Wentzell) boundary conditions*，Open J. Math. Sci. 10, 526–536，DOI 10.30538/oms2026.0303）全文，确认它的人造解是否本来就相容；把结果写进 `RELATED_WORK.md`。云端没读到（网络限制），本机可读。
5. 论文所需的缺口（`PAPER_PLAN.md`）：换初值的泛化（E1、E3 各再换 2 个 f，重跑 hardic 与 hardic+layer）、自适应采样基线（RAR 类，尚未实现）、可能的二维算例、τ 与 δ 误差的灵敏度。每项先写预注册修订再跑。
6. 论文初稿：论题 A——“现代 PINN 变种在带动态边界的抛物问题上的系统评测与失败诊断；基于经典角点层分析的校正作为补救”。校正项不叫“新方法”，叫“基于经典角点层分析的修正”，引用 Gie–Jung–Temam 与 SL-PINN 作数学和方法来源。E4 作负面结果/局限。

## 4. 本机（i7-14600K：6 个性能核 + 8 个能效核，20 线程）怎么跑

- 环境：Python 3.11+，`pip install torch numpy scipy pytest`（CPU 版即可，从 PyPI 装）。先 `python -m pytest -q test_screen.py`，应为 **43 passed**（含 E4、SOAP、续跑一致性）。
- 并行：每个进程单线程（代码里 `torch.set_num_threads(1)`），`--workers` 取 8–10 比较合适（6 个性能核满载，能效核补一部分）。每个完整预算 run 在云端 2.1GHz Xeon 上约 50 分钟，本机预计更快；PirateNet 更慢（6–9 小时）。
- 中断续跑：设 `R33_CKPT_DIR=一个本地目录`（如 `D:\r33_ckpt`），训练每 500 步存 checkpoint，重启同一条命令会自动续跑，结果与不中断逐位一致（有测试）。`ckpt_sync.sh` 是云端用的 git 镜像脚本，本机不需要。
- 完整预算的公共参数：
  `--set nf=4096 --set nb=256 --set n0=256 --set adam_steps=20000 --set lbfgs_iters=3000 --set nf_fixed=8192 --set nb_fixed=512 --set n0_fixed=512`
- 命令（在 R33 目录下）：
  - SOAP lr 1e-3：`python screen.py run --eqs E1_heat,E3_fisher --methods vanilla,hardic,hardic+layer --seeds 0,1,2 --workers 8 --tag soap1e3 --set optimizer=soap --set lr0=0.001 <公共参数>`
  - SOAP lr 3e-3：同上，`--tag soap3e3 --set lr0=0.003`
  - 初值权重：`python screen.py run --eqs E1_heat,E3_fisher --methods vanilla --seeds 0,1,2 --workers 8 --tag ic1000 --set w_ic=1000 --set t_refine=0.3 <公共参数>`
  - E1 PirateNet 补跑：`python screen.py run --eqs E1_heat --methods hardic,hardic+layer --seeds 0,1 --workers 4 --tag pirate --set arch=pirate <公共参数>`
  - 汇总：`python screen.py report --tag <tag>`
- 提交：结果在 `runs/<tag>/<eq>/<method>_s<seed>.json` 与 `.pt`；`git add runs/<tag>/`，提交，`git pull --rebase` 后 `git push`。不要提交 `.ckpt`（已在 `.gitignore`）。

## 5. 云端会话状态（2026-10-22 JST 更新：全部已归档暂停）

用户决定改在本机跑，云端三个 Haiku 会话已于 2026-10-21 13:53 UTC（22:53 JST）归档（容器释放，进程已停），不会再往仓库推送：

- `session_01Eq7RvsiwjG6HiRKdLoe2Fp`（soap1e3 + ic1000）：归档时 **0 个 run 完成**，没有任何结果文件；从头跑。
- `session_01X9pp726kqWgNZxz4h3AU9z`（soap3e3）：归档时 **0 个 run 完成**；从头跑。
- `session_014aeWV1Qxi9u64Z8oBFde84`（E1 PirateNet 种子 0、1）：归档时 4 个 run 都在 Adam 阶段，**镜像分支 `claude/r33-ckpt-store-k5lc11`（提交 aec7fcd，2026-10-21 13:52 UTC）里有最新 checkpoint**：hardic 种子 0、1 在第 16500 步，hardic+layer 种子 0、1 在第 16000 步（总 20000 步，之后还有 L-BFGS 3000 次）。**本机可以从这些 checkpoint 续跑，省掉约 80% 的 Adam 时间**：
  1. `git clone --branch claude/r33-ckpt-store-k5lc11 --depth 1 <仓库地址> ckpt_store`（或在 R33 目录用 `CKPT_BRANCH=claude/r33-ckpt-store-k5lc11 R33_CKPT_DIR=<本地目录> bash ckpt_sync.sh restore`，需要 bash 和 git）；
  2. 镜像里的文件名是 `pirate__E1_heat__<method>_s<seed>.ckptgit`，把它们复制到 `R33_CKPT_DIR` 下并改扩展名为 `.ckpt`（例如 `pirate__E1_heat__hardic_s0.ckpt`；hardic+layer 的文件名里 `+` 已换成 `_`，以镜像里的实际名字为准）；
  3. 设 `R33_CKPT_DIR` 后运行第 4 节的 PirateNet 命令，会自动续跑（续跑结果与不中断逐位一致，有测试；checkpoint 是同一版代码、float64 存的，不要换 torch 大版本以免状态不兼容）。
- 若需要云端会话恢复，用 `unarchive_session`；但新开会话更干净。云端容器会反复重启，不推荐继续在云端跑长任务。

## 6. 容易踩的坑

- 不要改 `pinn1d.py` 里既有方法的默认行为；既有结果依赖它（测试覆盖了续跑一致性和 E1–E4）。新增功能只通过 `Config` 新字段，默认值不变。
- E4 的参考解移植时出过实现错误（通量条件行漏乘 D），被测试发现；改动 `problems.py` 后必须重跑全部测试。
- 参考解自检要求 ≤1e-8；不要为了迁就某方法改输出时刻（0.05、0.1、0.25、0.5、1）。
- SOAP 是自己的实现，不是官方库：论文里要写明，并说明已用 float64 和续跑测试验证。
- `RELATED_WORK.md` 里的文献摘要多数只读到摘要，写论文前必须核原文。
