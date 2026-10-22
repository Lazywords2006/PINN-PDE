# R33 简洁数据字典

版本快照：`2026-10-23 02:57:22`（UTC+8）。这是既有字段与计划输出的解释，不含未完成Stage6结果。路径、源码哈希、CLI核对和当前状态见同目录 `source_and_command_audit.json`。`null`、字段缺失和CSV空单元表示未保存或不适用，不能替换为0或PASS。

## 1. 身份、路径与产物

| 字段/文件 | 含义 | 读取注意 |
|---|---|---|
| `(tag, eq, method, seed)` | 规范任务四元组；Stage6计划和验证报告采用此顺序 | `load_result(expected_job=...)`接口内部顺序为`(eq, method, seed, tag)`，不能直接混用位置 |
| `tag` | 阶段与配置批次 | 新τ tag明确为`sensitivity_tau003_v1`和`sensitivity_tau03_v1`；默认`.1`来自`confirm` |
| `eq` | 问题注册名 | 原E1/E2/E3、参数轴、两个新初值和E4各自定义，不能用同一个名称替换不同初值 |
| `method` | `vanilla`、`hardic`、`rba`、`layer`、`hardic+layer` | 主文`rba`显示为RBA本地变体；后两批并非包含全部5方法 |
| `seed`、`config.seed` | 报告种子及实际配置种子 | 必须一致；0/1筛选、0/1/2正式、100/101投入检查分开 |
| `runs/<tag>/<eq>/<method文件名>_s<seed>.json` | 单次原始记录入口 | 文件名把`+`换成`_`，JSON身份才是规范标签 |
| 同stem的`.pt` | 兼容base网络权重 | 早期130项仅此权重；E4缺表面分支，不能独立重建完整模型 |
| 同stem的`.model.pt` | 新格式完整模型bundle | `format=r33_complete_model_v1`；含metadata与严格完整state_dict |
| `artifacts.version` | 当前新格式为1 | 不能将没有该字段的历史格式自动判为损坏；按对应历史范围核对 |
| `artifacts.base/model.file`、`sha256` | 同目录权重文件名和校验值 | 不接受路径跳转；同时与验证报告bundle清单核对 |
| `env.python/torch/numpy` | 该结果记录的实际环境版本 | 与包元数据快照或当前解释器版本不同层级；旧记录不回填新版本 |

## 2. 科学配置与误差

| 字段 | 定义 | 边界 |
|---|---|---|
| `config.width/depth/arch` | 网络宽度、深度与`mlp/pirate` | PirateNet变体另看blocks/Fourier/初始化说明 |
| `config.optimizer` | `adam`、旧`soap`或`soap_official64` | 新固定对照仅最后一种；老JSON缺字段不能当作当前代码已验证全历史 |
| `config.adam_steps`、`lr0/lr1` | 第一优化阶段调用上限及指数调度端点 | 字段名含Adam，SOAP仍复用该字段，不表示SOAP运行了Adam |
| `config.nf/nb/n0` | 第一阶段体/每一个边界/初值点数 | `nb`不是两端总数 |
| `config.nf_fixed/nb_fixed/n0_fixed` | 通用L-BFGS固定点配置 | RBA分支复用整个固定Adam点集，通用字段不等于有效点数 |
| `config.lbfgs_iters/lbfgs_chunk` | 名义L-BFGS预算及外部每块计数 | 不是实际内部迭代或closure数 |
| `config.tau` | 层衰减时间 | 主配置0.1；新增0.03/0.3仅灵敏度，不倒选主值 |
| `config.w_ic/t_refine` | 初值软损失系数与早期时间采样比例 | 当前正式共享配置1/0；历史未执行草案不能填入结果 |
| `config.rba_gamma/rba_eta` | 注意力历史衰减和增量 | 本地λ₀=1、先网络后权重、分量内归一化、平方前乘λ |
| `config.causal_eps/causal_chunks` | 因果强度及时间箱数 | ε=1或10，32箱；各分量分别加权 |
| `config.soap_beta/soap_freq` | Shampoo平均参数及基刷新间隔 | 新SOAP64固定0.95/10，其他betas/weight_decay见冻结实现 |
| `delta` | E1–E3的初始时间导数错配 `b−a` | 已知初值与方程直接计算；E4使用自身交换/通量失配定义，不能强套主问题公式 |
| `metrics.times` | `[0.05,0.1,0.25,0.5,1]` | 顺序、长度和数值均应精确匹配协议 |
| `metrics.vol` | 同时刻体相对L²序列，Gauss–Legendre加权 | N64/GL200原评价；不是连续时间上确界 |
| `metrics.trace` | x=1的相对误差序列，分母`max(abs(ref),1e−12)` | 不是独立表面网络变量误差 |
| `metrics.surface_abs` | E4独立表面变量的绝对误差历史字段 | 旧20项缺表面权重，保留历史记录但不作完整可复现定量证据 |
| `max_vol/max_trace` | 各自五时刻序列最大值 | 必须等于原序列max，不先跨种子求平均 |
| 组中位数、比值、达标数 | 先每seed时刻max，再跨seed中位数；主比较为基线中位数/修正中位数；`≤0.01`计数 | 三种子描述统计；比值不是配对比值中位数；分母0时比值为空并注明，不造Infinity |

## 3. 训练日志、调用与时间

| 字段 | 定义 | 缺失/解释规则 |
|---|---|---|
| `history.loss` | 第一优化阶段按间隔保存的训练损失 | 不等于每一步全轨迹；不同损失结构不能直接作统一精度排名 |
| `final_adam_loss` | `history.loss[-1]`，应标为“第一阶段末次记录损失” | 按零基索引每10步记录：4000预算末条为3990、20000预算末条为19990。该损失在相应步参数更新前计算、更新后写入日志，不是训练终点重新评估；SOAP也沿用此名字 |
| `final_lbfgs_loss`、`history.lbfgs_loss` | 最后固定点损失及块间损失序列 | 不替代独立参考误差或独立残差 |
| `history.adam_gradient_calls` | 第一阶段成功走完后由`cfg.adam_steps`写入的预算/调用数记录 | 依赖冻结训练循环和完成证据，非独立逐步增量计数器或外部逐步观测；新完整任务要求20000，旧未保存的值不反推补填 |
| `optimizer_accounting.parameter_updates_inferred_from_frozen_optimizer_semantics` | 依据固定优化器语义推得的参数更新数 | SOAP为19999、Adam为20000；它是推得数，不冒称逐步外部观测 |
| `history.lbfgs_budget_used` | 外部每块加50的名义累计计数 | 与下面内部计数区分 |
| `history.lbfgs_n_iter/lbfgs_func_evals` | 优化器保存的实际内部迭代/目标梯度闭包调用 | 原记录未保存则空，不用名义3000替代 |
| `history.lbfgs_stop_reason` | `budget_exhausted`或`loss_stagnation`等枚举 | Stage6完整结果只接受其冻结验证器规定的合法终止类型 |
| `history.resumed_at` | 已保存恢复位置列表 | 空列表不证明从未发生任何外部过程事件；结合attempt/日志 |
| `wall_seconds/adam_seconds` | 该训练轨迹记录的总耗时/第一阶段耗时 | 续跑可含保存checkpoint中的历史时间；不是统一硬件可比墙钟 |
| status中`attempts` | 每次启动、结束、退出与诊断记录 | 原训练/恢复谱系分别保留；未知退出不能填0 |
| `batch_elapsed_seconds` | 从首次批次开始到当前/完成的整批历时 | 包含孤儿训练与恢复等待；与runner累计和各attempt之和分开 |
| `total_runner_wall_seconds` | status保存的累计runner时间 | 不自动填补进程退出后的监测间隔；需读`runner_wall_timing_note` |
| 分析报告`costs.local_batch_elapsed_seconds/local_runner_elapsed_seconds/local_attempt_wall_seconds_sum` | 分别映射整批历时、status保存的runner累计、所有新任务attempt时间之和 | 三者不能互相补值或替代；并行attempt之和不是批次墙钟 |

## 4. 验证与完成证据

N04待并入完整稿的方法说明及表头：第一阶段调用记录来自完成后写入的配置值，L-BFGS内部迭代/closure才是优化器状态中的实际计数；`final_adam_loss`须标为“末次记录损失”，并说明其更新前计算、更新后记录及非终点重评的含义。此项只修正文义，不修改原字段或原数据。

| 字段/报告 | 含义 | 完成要求 |
|---|---|---|
| `json_sha256`、`bundle_sha256` | 验证时读到的结果与JSON/base/model三文件哈希 | 必须与当前文件、原JSON内artifact清单同时一致 |
| `complete_and_recomputed` | 完整模型已加载并完成两组指标复算的记录 | 只能与绑定哈希和具体复算值一起使用，不能孤立引用true |
| `recomputed_N64_GL200` | 原设置重算体/迹序列 | 与原记录逐项allclose，rtol1e−5、atol1e−9 |
| `dense_metrics_N96_GL400` | 加密设置重算体/迹序列 | 同一容差；不是重新训练 |
| `heldout.{pde,left_neumann,right_dynamic,initial}.{rms,max_abs,n}` | 固定独立检验点残差 | `n`分别8192、1024、1024、1024；各分量独立报告 |
| `results_validation.json` | Stage6逐任务正式验证记录 | 精确30个任务；`complete=true`且`validated_count=required_count=30` |
| `summary.json` | Stage6队列完成汇总 | results应与验证报告完全一致，旧文件unchanged及协议身份齐全 |
| `status.phase/tasks/counts/updated_utc` | 保存的调度状态、逐项状态及快照时间 | 老快照不能证明实时运行；最终门需所有任务completed且pid为空 |
| `source_lineage/recovery_incidents/applied_recoveries` | 原/新代码门和恢复证据谱系 | 保留原21身份及故障事实，不把当前代码倒填原进程 |
| `required_complete_result` | 原恢复/此前completed任务的强制完整产物标记 | 缺JSON或bundle不能重新排队；失败后的下一次Run仍须保留必验 |

## 5. 最终派生文件与常见命名陷阱

`all_new_runs.csv`预计30行；`default_six_arms.csv`预计36行；`tau_sensitivity.csv`预计18行，均由正式完成门产生，当前未生成就不能宣称可下载。CSV含规范身份、source/SHA、每时刻vol/trace、损失、实际调用、heldout及环境来源。旧默认组未保存的heldout或调用字段保持空，并附`missing_diagnostics_note`。

最终 `analysis_evidence.json` 的 `records`为18旧默认＋30新结果；`default_groups`和`tau_groups`保存分组统计。分组字段 **`seeds`实际存的是按seed0/1/2排列的三个最大体误差值，不是种子编号**，规范编号应读单条record的`seed`。`trace_seeds`同理是迹误差值。`median/min/max`为三值描述统计；`under_1e2`是≤0.01个数，不是概率。

`S6_SOAP`保存逐方程及联合叠加判据，`tau_summary`保存跨档中位数最大/最小比。`evidence.raw_sha256`完整后应含488原始文件哈希；`input_sha256`绑定status/验证/summary/Gate/计划；`output_sha256`绑定派生CSV、图表和报告。实际最终字段及时间分解仍须在30/30后核对当前正式分析源码，不能把本字典的预期名替代真实输出。

解析图 `analytic_layer.png/pdf`及2728行CSV是辅助函数Q=w_t的直接计算，C=0.3，不含错配幅度或衰减，不是PINN预测、原有限区间参考解或训练性能数据。它与新30项实验结果分开索引。
