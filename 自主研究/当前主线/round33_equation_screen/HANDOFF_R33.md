# R33 交接文档（2026-10-22 JST 写，从云端会话转到用户本机 i7-14600K）

接手的人（或新的 Claude 会话）先读完本文，再读 `SCREEN_PROTOCOL.md`（含修订 1–6）、`SCREEN_REPORT.md`、`E4_PROTOCOL.md`、`RELATED_WORK.md`、`PAPER_PLAN.md`。仓库 `lazywords2006/pinn-pde`，分支 `claude/current-content-progress-e0d951-k5lc11`。目录 `自主研究/当前主线/round33_equation_screen/`（下称 R33 目录）。

**最新执行状态见 [第13节：Stage6与完整初稿完成态](#r33-complete-20261023)（2026-10-23，UTC+8）：Stage6 30/30完成，当前无训练；全稿核验与正式评审仍未完成。前文运行状态按各自历史时点保留，规则与最新协议继续适用；不按旧命令重跑，旧42/322批次不启动。** 新记录采用明确标注的UTC+8；本机硬件实查为i7-14650HX，原标题是历史交接描述。

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

## 7. 本机接手后的可行性核验与执行限制（2026-10-21，UTC+8）

用户最新要求：**先保证当前数据可行，再运行完整实验；不能把尚不可行的数据直接扩大为大规模实验。** 因此本文第 3、4 节的完整批次命令暂不直接执行。上一轮提出的 322 个新增 run 调参方案仅为草案，修订 4 未获确认、未写入或提交，未启动新研究 run。

本机只读复核见 [数据可行性核验](validation/feasibility_review_20261021/数据可行性核验.html)，机器可读明细及测试日志在同目录。

- 从 130 个已有 PT 重新计算体误差和边界迹误差，原配置与加密参考解/积分点复核均为 130/130 通过。10 个方程/参数点的参考解自检均满足原 1e-8 要求。260 个原 JSON/PT 的 SHA256 前后相同。
- 旧判定保持：修订 1 在 E1、E3 上分别约 30.06、5.92 倍；A-1 不满足；A-2 仅 E3 满足、E1 待补齐；E4 未显示优于 vanilla。数据可复核不等于完整研究主张已经成立。
- 开跑前复现并修复了 `screen.py` 的评估分支错误：所有模型都有 `surface` 函数，但只有 E4 有表面网络，现按 `model.bulk_surface` 判断。原 43 项测试通过；新增 3 个测试在修复前均失败，修复后合计 46 项通过。`pinn1d.py`、`problems.py` 未改。
- **SOAP 暂不能直接作为标准强基线。** 对照官方源码和固定梯度的一步检查，已确认当前实现与官方在首次更新、预条件器更新顺序、刷新基与二阶矩处理方面不等价。这不证明谁性能更好；二次型收敛和本地续跑测试不能替代标准实现一致性核验。三个待跑 tag 仍为 0，不自动开启 42 个完整 run。
- **E4 的 20 个历史 PT 缺少 `model.surf` 权重。** 体解和 u(1,t) 迹误差可复核，v(t) 误差只能保留为原记录，不能标成已从权重复现，也不能补造表面权重。不为补产物自动重跑这 20 个实验。
- 本机 PyTorch 2.7.1+cpu，历史记录为 2.14.1+cu130。本次推理复核通过不等于跨版本训练逐位一致。四个 E1 checkpoint 未启动续跑、未从头重跑；恢复前继续核对版本、状态及完整保存路径。

后续先处理实现、产物和恢复检查，再按用户要求另行预注册最小公平对照及是否升级的条件。小规模证据不充分就保留失败并停止扩展；不修改旧阈值、不按参考解误差倒选主配置、不排除失败种子来取得“可行”。

## 8. 工程修复与有限可行性检查（2026-10-22，新增记录显式用 UTC+8）

用户随后要求“解决掉所有问题，然后分析是否可以运行、是否符合发论文标准”。据此修复工程缺陷并预注册最小对照；**依照先可行再扩大的要求，不把未达标结果直接扩大为 42/322 个完整实验**。旧 JST 时间记录不换算覆盖，新记录标明时区。

### 工程与运行环境

- 原 43 项加新增 20 项，完整测试 **63 passed**；`pinn1d.py` 改动后已完整执行。`problems.py` 未改。原方法的默认行为保留。
- `screen.py` 已修复 E4 分支判断；新 `run_artifacts.py` 保存 base PT、包含所有分支的完整 model PT、元数据和 SHA256，JSON 最后原子发布。跳过旧结果前先核任务/配置/哈希，错误产物拒绝跳过。旧 E4 缺表面权重时不自动补随机分支。
- 旧 `optimizer=soap` 保留为历史自定义变体；新增 `optimizer=soap_official64` 是固定上游更新语义的 float64 适配，float32 多步对照上游及 float64 分解/续跑测试已过。正式基线不可混名，不能直接用第 4 节旧 SOAP 命令冒充新实现。
- 专用 Python：`D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe`；Python 3.12.6、torch 2.14.1+cpu、NumPy 2.5.3、SciPy 1.18.1。系统 Python 保留原样。临时、缓存及运行文件都放 `D:\CodexRuntime`，见 `run_preflight.ps1`。
- 原 130 次体/迹误差可复核，旧 260 个 JSON/PT 哈希未变。E4 的 20 个旧表面网络权重没有保存，无法从现有产物追回；旧 v 误差只作未复核报告值，排除正式定量主张，不自动重跑 20 次。

### checkpoint 恢复：已经准备好，但四个完整训练没有跑完

- 来源固定为镜像提交 `aec7fcdfc0dae861f46ca594d0771c5669af5ad3`，四个 Git blob 均核对通过。原 ZIP、`.ckptgit` 另存 D 盘保留原字节。
- **使用已绑定任务身份的工作副本**：`D:\CodexRuntime\runs\r33_resolution_20261021\checkpoint_restore\checkpoints`。hardic 种子 0/1 仍为 16500 步；hardic+layer 种子 0/1 仍为 16000 步。不要直接按旧第 5 节复制原 ckptgit 后绕过身份检查。
- 每个源另建两份探针各推进两步，四个均有限，模型/优化器/调度器/采样状态本机重复逐位相同；总计 16 次 Adam 更新，无 L-BFGS、无正式结果。不声称云端到本机全轨迹逐位相同。
- 原 ZIP 路径 `D:\CodexRuntime\runs\r33_resolution_20261021\checkpoint_source.zip`；`import_checkpoints.py --source <zip> --out <folder>` 可只做导入核验。**不再加 `--probe` 重复消耗短探针预算**，也不要覆盖已推进的工作副本。详细报告见下方验证目录。

### 小预算判定和论文范围

修订 4 在成功提交 `896fe32`、偏差披露提交 `c31355c` 后才开始 24 次研究对照：两方程、六个比较臂、种子 100/101，无调参；tag `preflight4_adam`、`preflight4_soap64`，各计划 12 次。完整记录和 G0/G1/G2 判定见 [修复结果与论文准备度](validation/resolution_20261022/修复结果与论文准备度.html) 及同目录 `preflight_review.json`。这些种子不进正式论文主表。

**执行偏差不可删去**：第一次提交被固定上游源码的原有行尾空白检查阻断，编排错误导致 checkpoint 16 次工程短更新早于成功提交。源/原工作副本未推进，只改探针副本，未算参考解误差。该事后工程核验已在任何研究性能结果产生前披露，不冒称预注册，不重复探针增加预算；G1/G2 判据未改。

旧 A-1 仍失败，A-2 仍仅 E3 满足/E1 待补四次，E4 未优于 vanilla。E1/E3 对 vanilla 的旧完整预算中位数改善约 45.47/81.60 倍，不能外推为胜过现代强基线。三种子不声称统计显著。新小预算 G2 未过就停止自动扩展；即使过也只能建议另行注册有限完整确认，不自动开跑。下一步先分析不足，再决定有限诊断或公平调参方案；不能用改变阈值、挑好种子或参考误差倒选主候选救门槛。

论文计划已改为一维限定范围的经典角点层修正经验研究。`METHOD_DERIVATION.md` 补了自包含推导及“只硬满足初值、未硬满足完整 PDE/边界”的界限；经典出处与完整稿件仍待完成。`RELATED_WORK.md` 最新节已核 Awais §2–4、两篇 SL-PINN 和 EDRAS 相关章节，撤回旧笔记不当推断，仍不写“首次”。

**修订 4 最终结果**：24/24 完成，两个 tag 各 12，G0/G1 通过，**G2 未通过，停止自动扩展**。E1 主比较 7.18 倍、SOAP 叠加 5.60 倍但候选仅 1/2 ≤1e-2；E3 主比较 1.23 倍、SOAP 叠加 2.43 倍，均低于三倍。全部模型加载及原/加密误差复算通过，旧 260 文件哈希不变。本机整批约 30 分钟墙钟，实际单次 3.7–12.6 分钟；不能据此假定完整训练或 PirateNet 同样快。完整数据表和报告已写入上述验证目录，失败原样保留。

## 9. 论文定位最新澄清与七篇选读（2026-10-22，UTC+8）

用户明确：“不需要普遍强于”，要求至少五篇论文的内容与写法分析。已完成七篇相关原文的重点章节选读、正式发表信息及 DOI 核验，见 [写法分析](PAPER_WRITING_ANALYSIS_20261022.md)。EDRAS 实际已发表于 IJNAM 2026，本轮核了最终全文；相关工作已追加纠正，不能继续只标预印本。

论文目标收束为具体一维问题上的初始相容性分析和经典角点层修正。**不要再把 A-1/G2 的实验投入阈值当成所有方法论文的发表标准。** 现有完整预算局部改善足以开始组织明确范围的初稿，稿件与对应证据仍须闭合；不保证录用。原 G2 失败、停止自动扩展和独立种子小预算不进主表的规则均保留。这轮只读文献、整理分析并调整论文计划，没有运行新训练。

## 10. 完整测试投入评估，尚未开跑（2026-10-22，UTC+8）

用户要求分析是否值得投入完整问题测试。最新草案见 [FULL_TEST_INVESTMENT_REVIEW_20261022.md](FULL_TEST_INVESTMENT_REVIEW_20261022.md)：第一阶段四个 E1 PirateNet 续跑、18 个另一初值的三方法/三种子完整训练，22 个任务；第二阶段可选 τ 灵敏度 12 次与固定 SOAP64 18 次。规划首阶段 8–16 小时，两阶段共 16–36 小时、48 小时复盘；属于外推预算，不是完整训练实测。各新初值先做参考解及完整测试，未通过不训练。旧结果不重跑、旧三个零 tag 不冒名填充。

**本机实查为 Intel i7-14650HX（16 核/24 线程，约 32 GB 内存），与第 4 节历史硬件记录不同。** D 盘运行位置及专用解释器沿用第 8 节。关键代码仍与 63 项通过测试对应版本相同，旧 260 文件与 24 个新结果/模型哈希复核未变。本轮未启动训练、未重复 checkpoint 探针、未修改 `SCREEN_PROTOCOL.md`；当前仍是待确认草案。确认后追加并提交修订 5，不能把 G2 失败改成通过或自动恢复 42/322 次旧批次。

## 11. 用户确认后已启动第一阶段（2026-10-22，UTC+8）

用户已确认第一阶段。修订 5 先提交 `2b67dcb`，实现及工程门提交 `ea12d0e`，完整测试 **71 passed**；新初值参考解及四个 checkpoint 身份核验通过后，于 2026-10-22 13:51（UTC+8）启动后台执行。先四进程 PirateNet 续跑，产物复核通过后自动八进程执行 18 个新初值完整训练；第二阶段未授权，旧 G2/A-1/E4 判定不改。

修改 `problems.py`/`pinn1d.py` 后已重跑全部测试；新增 `IC_CASES` 显式问题，不改变默认问题列表和旧初值，训练代码只增加调用计数等元数据，不改更新/采样/停止规则。参考解 N48/96 差 E1≈8.66e−13、E3≈5.88e−13，E1 独立本征展开≈6.87e−13；四个 checkpoint 没有重复短探针。

实时状态在 `D:\CodexRuntime\runs\r33_stage5_20261022\status.json`，`run_stage5.ps1 -Action Status` 只读查看；各批次日志与缓存/checkpoint 都在 D 盘。不要重做原 checkpoint 导入或覆盖正在推进的工作副本。失败停止后续批次，48 小时设资源复盘点。训练前协议和实现均已推送当前分支，未建 PR。

[启动记录](validation/stage5_20261022/启动记录.md)、工程门与启动快照只代表相应时刻；全部 22 个核验完成后才生成完成记录。

## 12. 第一阶段完成与分析交接（2026-10-22，UTC+8）

第一阶段于 20:07:28 完成，22/22 完整产物及误差复核通过，总墙钟 6.27 小时。四个 E1 PirateNet 已从原 checkpoint 续跑完成；`pirate` 现有 12 个 JSON，**不要再次导入旧 checkpoint 或重复训练**。新初值 `final_ic_v1` 共 18 个完整结果；当前无本批训练进程。

- 原 A-2 现按原阈值判为 **E1、E3 均满足**，中位数比 22.61/5.52；原 A-1 仍失败，G2 仍失败，E4 仍为负面结果。
- 新初值对 hardic 的三种子中位数改善为 E1 2.69、E3 7.34 倍；对 vanilla 为 12.53/69.96 倍。E1 配对 3/3 改善，E3 2/3；E3 seed 0 体误差约高 3.57%。新初值没有事后三倍“通过门”。
- 全库 176 个结果（旧 130 + 小预算 24 + 本轮 22），398 个原始结果文件。旧 260 文件哈希不变；22 个新结果与完成时验证哈希一致，训练源仍匹配 71 项测试后的工程门。
- 数据、图表、全部种子及成本解释见 [第一阶段完整分析](STAGE5_ANALYSIS_20261022.md)、[HTML 阅读版](validation/stage5_analysis_20261022/第一阶段分析与论文证据.html)。`all_runs.csv` 含全部 176 次，必须按 tag 区分；preflight4 的 100/101 种子不进正式主表。
- 独立 PDE 残差不总与解误差同序，必须联同初值/边界解释。实际 L-BFGS 内部迭代与 closure 已留存，新结果未伪装成等计算量。
- 18:54 将当时八个训练工作进程降为 BelowNormal，以缓解前台卡顿；没有修改科学配置。优先级和并发负载变化使墙钟不宜作严格方法开销比较；PirateNet JSON 墙钟还包含云端历史。
- 论文可按“被测一维问题上的经典角点层修正、同架构消融与适用范围”组织初稿。建议优先补经典来源和 12 次 τ 灵敏度；18 次固定 SOAP64 是否加入另行决定。两个建议均未开跑，须另追加并提交协议后执行；旧 42/322 批次仍不启动。

本轮分析只读训练产物，没有改 `problems.py`、`pinn1d.py` 或 `SCREEN_PROTOCOL.md`，不需要为文档整理重复训练或重跑全部测试。复现汇总使用 D 盘独立分析环境 `D:\CodexRuntime\venvs\r33-analysis`，未改专用训练环境。

<a id="r33-complete-20261023"></a>

## 13. Stage6与完整初稿完成态（2026-10-23，UTC+8）

本节更新接手状态，不覆盖前文日期记录、协议或失败。修订6先提交预注册 bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a；Stage6全部30项于06:29:36完成，runner91632真实HANDLE exit0。30项均单attempt、exit0，原21与后9的恢复源码谱系保留；全库现为206份JSON、488个raw文件。当前无训练，禁止照前文旧命令Run；旧42基线及322调参草案不启动。

- 科学来源改读 [complete_v2完整分析](validation/stage6_analysis_20261022/complete_v2/STAGE6_ANALYSIS_20261022.md) 与 [V2_FOLLOWUP限定独立复核](manuscript/integrity/stage6_analysis_20261023/V2_FOLLOWUP.md)。v2只修正图形展示，3份CSV及科学值/配置/判据与v1一致，不是新增训练结果。原始运行完成态仍读 [冻结归档](validation/stage6_20261022/completion_archive_20261023/archive_manifest.json)。
- 同批SOAP64内，H=hardic、HL=hardic+layer；E1/E3的H/HL三种子中位数比分别300.07035/30.82806，HL均3/3≤0.01，满足本批S6-SOAP叠加判据。该局部判据不替代旧B-1/B-2，不是普适发表门槛，也不证明胜过所有现代强基线。旧A-1/G2失败、E4对vanilla无优势、A-2两个问题通过均保留。
- τ跨0.03/0.1/0.3的最大/最小中位数比为E1 1.71581、E3 1.43027；只报告灵敏度，不按结果选参。Adam及τ=0.1主线不变；历史τ=0.1/Adam与本机新批次的环境混杂继续披露。
- 运行/复现材料读 [613断言限定核对](manuscript/process/reproducibility_complete_20261023/REPRODUCIBILITY_COMPLETE_CN.md) 及其机器记录。该报告绑定完成态v1、证据层分明；110项工程回归不等于科学改进。历史130次生产全日志仍缺失，不能由新30份日志补齐；真实人工署名核验仍pending。
- 最新完整初稿为 [manuscript/drafts/complete_v1.md](manuscript/drafts/complete_v1.md)，于07:00:28冻结，SHA-256为8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3，六章正文按冻结统计口径共11434汉字；[冻结清单](manuscript/process/complete_v1/FROZEN_DELIVERY_MANIFEST.json) 与 [Phase4b材料](manuscript/process/complete_v1/writer_phase4b.md) 已保存。全稿integrity/evaluator正在进行，正式五视角评审和最终交付尚未完成；不得写成审查通过、可投稿定稿或录用。

接手后的当前工作是围绕该冻结完整稿完成既定核验/评审并保留记录，不再执行第3、4、10–12节中已过时的“建议训练/待启动”事项。本轮仅更新项目导航与完成状态，不改论文正文、科学协议或原始数据。
