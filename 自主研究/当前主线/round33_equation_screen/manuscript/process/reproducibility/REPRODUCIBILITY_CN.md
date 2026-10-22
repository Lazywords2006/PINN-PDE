# R33 复现说明：证据分层、入口与完成门

N04文义修订已同步至本说明与数据字典，来源清单另绑定分析脚本当前哈希；本次仅做静态复核。`read_only_partial_snapshot.json`仍保存原快照时点及当时脚本哈希，没有因文义修订重跑命令，也不代表修订时的实时进度。

文档状态：供完整稿后续整合的复现材料，尚非30/30完成后的定稿。编写快照时间为 `2026-10-23 02:57:22`（UTC+8），对应机器证据见同目录 `source_and_command_audit.json` 与 `read_only_partial_snapshot.json`。本轮只整理文本、读取JSON/源码/环境元数据和执行轻量状态查询，没有导入Torch、安装依赖、训练、模型重载或参考ODE积分。冻结的 `working_revised1.md` 保持原SHA256：`7ca430d7911dda4507469099e493dc2563ef48dff0157b4df862e4ab8f3b3635`。

任务分派时的说明是21项训练、9项待派发，恢复v2复审与完整回归待完成。编写期间新收到的独立v2复审已在静态及轻量测试范围关闭REC-P1-001；完整Torch回归、原21项真实退出及产物验收、新Gate、剩9项派发与最终30/30仍未完成。磁盘 `status.json` 是2026-10-23 01:08:47（UTC+8）的故障前快照，记录21 running、9 queued、0 completed；它不是当前训练进度。02:39:44独立监督记录已有42个进程句柄附着，尚无退出事件或完整结束事件。以上各时点分开解释，不以过期状态、附着成功、checkpoint或结果文件存在替代完成判定。

## 1. 数据层级与实际计数

研究根目录为 `E:\PINN-PDE\自主研究\当前主线\round33_equation_screen`。一项运行由 `(tag, eq, method, seed)` 唯一识别。文件名中的 `hardic_layer` 对应JSON里的 `hardic+layer`，不能把两者当作不同方法。

| 层级/tag | 已有或计划项数 | 用途与边界 |
|---|---:|---|
| `screen` | 已有30 | 原3方程×5构造×2种子，小预算筛选；只有E3通过原三倍门，E1和E2未通过 |
| `confirm` | 已有24 | E1/E3×4方法×3种子完整预算；E1按筛选后的修订1扩展确认，未追改原筛选判定 |
| `causal1`、`causal10` | 已有6+6 | 两档因果权重，完整报告；原A-1联合强基线判定不满足 |
| `pirate` | 已有12 | E1/E3×2构造×3种子；其中4项为Stage5从原checkpoint续至原预算，非额外重训 |
| `axis` | 已有36 | 6个新增参数点×2构造×3种子；弱错配、不满足三倍及退化点保留 |
| `e4screen`、`e4confirm` | 已有8+12 | 体表耦合扩展；20个历史模型缺表面分支，仅体/迹有保存复算支持 |
| `final_ic_v1` | 已有18 | 两个事前指定新初值×3构造×3种子，各自重新训练，不是未知初值泛化 |
| `preflight4_adam`、`preflight4_soap64` | 已有12+12 | 种子100/101、小预算投入检查，G2失败，不进入正式主表 |
| 以上11个tag合计 | **已有176** | 当前既有结果全集，不能将其中小预算和探索性数据全部称为主实验 |
| `sensitivity_tau003_v1`、`sensitivity_tau03_v1` | **计划新增6+6** | 原E1/E3、hardic+layer、种子0/1/2；τ分别为0.03、0.3，默认τ=0.1只读复用旧6项 |
| `final_soap64_v1` | **计划新增18** | 原E1/E3×3构造×3种子，固定官方语义SOAP64配置 |

新增30项全部完成后，独立运行记录总数才是206。正式六臂表预计36行：18个历史Adam默认记录加18个新增SOAP64记录；τ表预计18行：12个新增τ记录加6个历史默认记录。两表共享6个默认记录，因此54个展示行不是54次独立新训练。Stage6分析实际使用48个独立记录；它的来源哈希清单仍包含全部旧398文件，以保护未进入这两张表的历史结果。

旧398文件由130份早期JSON/base权重的260文件，加24份小预算及22份Stage5新格式结果的138文件组成。新30项预期每项JSON、base PT、完整model PT各一份，共90文件；**90和总计488都是完整验收后的预期清单数量，当前不能写成已经形成完整清单。**

来源入口：

- [旧176结果与398文件总映射](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage5_analysis_20261022/analysis_evidence.json)：`raw_sha256`，已有398项；稿件作者重聚合另见 [writer_data_evidence.json](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/writer_data_evidence.json)。
- [130＋24＋22保存复算的独立来源审查](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/integrity/working_20261023/HISTORICAL_EXECUTION_SCOPE.md)及其 [机器映射](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/integrity/working_20261023/historical_execution_scope.json)：逐结果身份、权重和保存复算报告的对应关系。
- [Stage6冻结任务计划](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_20261022/task_plan.json)：30个精确元组、完整配置和实际worker argv。本说明逐项静态核对命令参数，没有执行这些worker命令。
- 完整后新增90文件将由 `validation/stage6_20261022/results_validation.json` 的逐项 `bundle_sha256` 及最终分析的 `evidence.raw_sha256` 绑定。目录存在、文件名计划或阶段status均不等于这份完整证据已通过。

## 2. 环境、源码和执行身份

| 用途 | 固定或已记录环境 | 解释 |
|---|---|---|
| 本机研究训练与完整数值验证 | `D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe`；工程门记录Python3.12.6、Torch2.14.1+cpu、NumPy2.5.3；本次包元数据另见SciPy1.18.1 | 不更换正在运行的依赖；包METADATA中的Torch版本不含`+cpu`后缀，CPU构建由实际工程门/逐run环境记录支持 |
| 聚合、作图、排版 | `D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe`；pyvenv记录Python3.12.6；当前元数据为NumPy2.5.4、matplotlib3.11.2、pypandoc_binary1.17、PyMuPDF1.26.7 | 与训练环境分开；纯聚合不运行网络；该环境版本不能反写为训练环境版本 |
| 历史云端与续跑来源 | 每个旧JSON的`env`、checkpoint来源及旧复算记录 | 历史Python/构建/硬件不同；不能承诺跨环境完整训练轨迹逐位相同 |
| 临时、日志、cache、checkpoint | `D:\CodexRuntime\temp`、`runs`、`cache\pip`、`cache\uv`、`cache\xdg`、`cache\pycache` | 正式结果留在项目指定路径；不迁移已有解释器，不回退C盘运行存储 |

venv路径不是不可变镜像。环境版本、实际运行命令、源码哈希、协议提交和每项产物必须共同绑定。修订6预注册提交为 `bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a`；[原工程门](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_20261022/engineering_gate.json)包含12个源码/协议/供应商证据哈希。原21项沿用事故前工程门谱系，修复后尚待派发的9项必须绑定新门，不能把当前修复源码倒填到旧进程。当前v2只修改编排与测试，训练、方程、供应商和科学协议保持冻结；实际恢复仍须按恢复链核验。

旧130项审查时保存的训练源码哈希与当前源码不同。已有模型和数值复算仍有来源，但不能宣称所有历史运行均使用当前源码。供应商SOAP本地文件与所绑Git blob仅有末尾一个LF差异，证据见 [soap_upstream_blob.json](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_20261022/soap_upstream_blob.json)；本地 `soap_official64` 是明确的float64适配，不是旧`optimizer=soap`。

## 3. 预算、指标与解释边界

完整默认预算为MLP 4×64、tanh、float64、每进程单线程，Adam/SOAP梯度调用20000，学习率0.001指数降至0.00001，Adam/SOAP阶段体4096、每端边界256、初值256点；L-BFGS名义上限3000、每块50、通常固定体8192、每端512、初值512。SOAP首次调用只初始化，按冻结实现推得19999次参数更新，不另赠一步。L-BFGS内部迭代、closure及块间停滞可能使实际计算不同，均按保存字段报告。

RBA本地变体是例外：两个阶段复用整个Adam固定点集，完整预算为体4096、每端256、初值256；四类残差分别加权，λ初值1，γ=0.999、η=0.01，先网络更新、再用更新前已算残差更新权重，L-BFGS冻结。原JSON的通用`*_fixed`字段不能代替该分支的有效点数。因果训练使用ε=1或10、32箱、三个时变残差分量分别加权；PirateNet为省略原物理信息最小二乘初始化的本地变体。完整细节以冻结稿附录A/C、源码和逐run配置共同解释，不统一改名为严格原文复现。

原筛选和小预算投入检查为4000次梯度调用、L-BFGS名义上限500；通常点数为2048/每端128/256，L-BFGS固定4096/每端256/512。筛选种子0/1，投入检查种子100/101；正式报告种子0/1/2。三者不得混合取中位数。

主指标始终先对每个种子在 `t={0.05,0.1,0.25,0.5,1}` 取最大体相对L²，再对种子取中位数。体误差由N64参考和200点Gauss–Legendre求积计算；迹误差在x=1，分母下限10⁻¹²。新完整产物以N96/400点复算，两种设置与原记录的序列容差为rtol=10⁻⁵、atol=10⁻⁹。E1–E3及其参数/初值变体使用源码类`Reference`（主问题Reference1D）：Radau rtol=10⁻¹²、atol=10⁻¹³；E4源码类`ReferenceBS`另用atol=10⁻¹⁴，不套用主问题参数。Stage6工程门在401空间点、五时刻比较N64/N96，门为10⁻⁸；原筛选登记的自检为N48/N96。

独立残差使用 `default_rng(330500)`，按体x8192、体t8192、左边界t1024、右边界t1024、初值x1024的顺序抽样；t均匀位于[10⁻⁴,1]，x均匀位于[0,1]。分别报告PDE、左Neumann、右动态边界、初值的RMS及最大绝对值，不参与训练或选参。五个评价时刻及均匀残差不足以证明t→0角点机制。

默认主参数保持τ=0.1，不依据新误差挑最优档。τ表只报告三档全部种子、中位数/范围、相对默认中位数比及跨档最大/最小中位数比，不另设“鲁棒通过线”。τ=0.1来自历史云端，τ=0.03/0.3来自本机，运行环境同时不同，因此该表不是完全隔离环境后的纯τ因果效应。历史Adam与本机SOAP64的跨组精度差也不能全部归因于优化器。`S6-SOAP`仅在同批本机SOAP64内比较hardic与hardic+layer：两个方程都要求中位数比至少3，且修正组至少2/3种子≤0.01；它是本批叠加判据，不替换旧G2/B-1/B-2，不是发表门槛。

E1/E2原筛选未入选、A-1/G2失败、弱错配退化、新初值个别不利种子和E4相对普通网络无额外收益均保留。历史E4缺表面权重，不能以随机初始化补齐，也不能因未来产物格式修复而把旧表面值改为已复核。

计时至少分开四项：①结果JSON的单轨迹累计时间（PirateNet可含云端checkpoint历史）；②每个attempt的实际启动至退出观测时间，恢复观测可能含轮询延迟；③status记录的runner累计时间，其故障间隙不能冒充调度器活跃时间；④从批次首次开始到最终完成的`batch_elapsed_seconds`，包含孤儿训练间隔。并行attempt或轨迹耗时之和不是整批墙钟。跨环境不据这些值给速度倍数；最终字段以正式分析版本为准。

## 4. 产物验证与工程恢复链

每个新结果先保存兼容base权重与完整model权重，再发布含两份SHA256的JSON。JSON最后原子发布，是一个结果bundle的入口；它仍须通过身份、配置、有限性、完整权重strict加载、原指标和加密指标复算及独立残差检查。任一缺失/损坏/身份不符不得计为完成。旧完整产物的保存复算记录可复用，但必须绑定当前哈希，不能只复用一个PASS字样。

2026-10-23 01:08左右原runner在替换status临时文件时发生WinError5，二次保存也失败；具体占用者未确认。事故门、源码、status/tmp和日志保全于 [incident快照](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/incident_snapshot_20261023_013453_945/snapshot_manifest.json)。独立监督器附着21个launcher和21个实际worker，只在HANDLE真正signaled后记录退出码，不从PID消失、结果出现或STILL_ACTIVE推断成功。

恢复v1独立审查发现“旧产物丢失后可能静默重新排队”的控制流缺口，历史BLOCKED报告保留。v2加入跨重启持久的`required_complete_result`，任何派发前强制核验原恢复任务及此前completed任务，缺失完整bundle必须停审，不能退回checkpoint重训。现有18项原生/AST轻量检查加21项独立AST回归支持该有限工程范围，不能替代完整Torch回归、实际退出或科学产物验收。原完整测试70 passed/1 failed、WMI诊断及独立测试首次收集配置错误均保留，不能写成全过程零警告。

恢复顺序以 [RECOVERY_ROUTE.md](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/RECOVERY_ROUTE.md)和 [v2独立复审](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/validation/stage6_recovery_20261023/v2/INDEPENDENT_RECOVERY_REVIEW.md)为准：等原42句柄完整退出证据并确认全部0退出；确认锁释放；资源允许时通过当前源完整回归；冻结观察记录与recovery manifest；生成新Gate；Run再次强制验证原21完整bundle；最后才派发剩余9项。任一未知或非零退出、缺失bundle、数据/源码变化或期限门到期均先停审，同任务工程恢复另留决策，不换种子补正例。本说明没有执行恢复步骤。

历史176项保存复算覆盖当前体/迹数据，但原生产逐worker退出码、完整警告和早期源码绑定不完整；63项与71项历史测试分别有1条已记录警告。补跑模型不能追回这些历史信息，也不能恢复E4表面权重。

## 5. 已核实命令：当前读取、历史来源与未来发布分开

本节所有Python CLI参数均从实际源码AST核对，详情和行号在 `source_and_command_audit.json`。没有用运行训练入口的`--help`进行核验。共同变量与D盘运行目录如下；它们不启动训练、不修改依赖：

```powershell
$r33Project='E:\PINN-PDE\自主研究\当前主线\round33_equation_screen'
$r33AnalysisPython='D:\CodexRuntime\venvs\r33-analysis\Scripts\python.exe'
$env:TEMP='D:\CodexRuntime\temp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='D:\CodexRuntime\cache\pycache'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:MPLCONFIGDIR='D:\CodexRuntime\cache\matplotlib'
$env:XDG_CACHE_HOME='D:\CodexRuntime\cache\xdg'
if (-not (Test-Path -LiteralPath 'D:\CodexRuntime')) { throw 'D盘运行目录不可用。' }
```

**当前可执行的轻量读取。** `--partial`及裸分析入口只输出保存状态、快照年龄与缺口，不生成正式表图或科学判据，不导入Torch。该入口不能检查PID身份或授权恢复，过期status必须结合监督器证据解释。本轮仅执行此只读入口并保存输出。

```powershell
& $r33AnalysisPython (Join-Path $r33Project 'validation\stage6_analysis_20261022\analyze_stage6.py') --partial
if ($LASTEXITCODE -ne 0) { throw '状态读取失败，保留原错误。' }
```

| 历史或受门禁入口 | 已核对的接口与副作用 | 本轮处理 |
|---|---|---|
| `screen.py run` | 子命令支持`--eqs --methods --seeds --workers --set --tag`；会训练/恢复及写正式结果 | 只追溯原日志与配置，不给覆盖旧tag的整批重跑命令 |
| `screen.py report` | 支持`--tag`，打印现有数据；载入方法模块会导入Torch | 当前不调用；既有报表可读取 |
| `run_preflight.ps1` | 仅`-Workers`，默认8；启动固定24项，日志路径固定 | 已完成的历史入口，不重跑 |
| `run_stage5.ps1` | `-Action Gate/Run/Status/Plan`，**默认Run**；Run写固定日志且会训练 | 不裸运行；旧checkpoint已推进时不能重做只接受旧步数的Gate |
| `run_stage6.ps1` | `-Action Gate/Run/Status/Plan`，默认Status；`-Workers`为1–24 | Run会派发；Gate写工程门并运行测试；Status/Plan也先载入Torch，当前不用作轻量查询 |
| `stage6_runner.py` | `--gate --run --plan --status --worker TAG EQ METHOD SEED`互斥；另有`--runtime --workers --set --resource-review-note --recovery-manifest --retry-failed-job` | `--recovery-manifest`只配Gate，`--retry-failed-job`只配Run；科学参数来自冻结计划，不临时改`--set` |
| `validate_preflight.py` | 无自定义CLI参数；不训练但会重载模型，覆盖原`preflight_review.json` | 不直接当作“无写入复核”命令重跑 |
| 旧作者汇编脚本 | `assemble_working.py`会写原初稿；`build_working_tables.py`、`write_phase4b_report.py`会写原过程材料 | 不为复现而覆盖旧过程证据；当前冻结稿不改 |
| `plot_stage6.py` | 提供Python函数`render(audit, output)`，没有独立argparse CLI | 由正式分析入口调用，不编造`--input/--output`绘图命令 |

**未来30/30后的正式分析。** 仅在status、验证报告、summary都完整一致、全部30配置与产物核对成功、旧398及新90哈希/源码/协议绑定通过后执行。输出必须是分析目录内一个全新子目录；不覆盖旧正式分析。门失败退出2并不给正式表图。以下是未来发布模板，本轮未执行：

```powershell
$r33AnalysisOutput=Join-Path $r33Project ('validation\stage6_analysis_20261022\complete_v1_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
if (Test-Path -LiteralPath $r33AnalysisOutput) { throw '目标目录已存在，不覆盖。' }
& $r33AnalysisPython (Join-Path $r33Project 'validation\stage6_analysis_20261022\analyze_stage6.py') --final --output $r33AnalysisOutput
if ($LASTEXITCODE -ne 0) { throw '正式分析门未通过，不能进入完整结果排版。' }
```

**未来冻结完整稿后的排版。** `render_manuscript.py`接受位置参数source及必填`--output`、`--label`，`--pdf`同时请求PDF；HTML本来就会生成，没有`--html`参数。渲染器可能覆盖同输出目录的同名文件，因此调用者必须指定新的输出目录。以下模板先要求真实`complete_v1.md`存在，本轮未执行：

```powershell
$r33CompleteSource=Join-Path $r33Project 'manuscript\drafts\complete_v1.md'
if (-not (Test-Path -LiteralPath $r33CompleteSource)) { throw '完整稿尚不存在，不能以工作稿冒充。' }
$r33RenderOutput=Join-Path $r33Project ('manuscript\rendered\complete_v1_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
if (Test-Path -LiteralPath $r33RenderOutput) { throw '排版目录已存在，不覆盖。' }
& $r33AnalysisPython (Join-Path $r33Project 'manuscript\render_manuscript.py') $r33CompleteSource --output $r33RenderOutput --label '完整初稿v1；内部核查版本，未投稿' --pdf
if ($LASTEXITCODE -ne 0) { throw '排版失败，保留源和日志。' }
```

HTML为离线原生MathML，PDF用既有XeLaTeX，编译关闭自动安装包与shell执行。中间TeX、编译日志和逐页预览在D盘。自动缺字/页面几何检查不能替代实际HTML/PDF目视检查。完整图表只使用最终真实数据；n=3展示全部种子、中位数和范围，不画成置信区间。

## 6. 完整后必须更新的条目

1. 以最终时间快照替换本说明的在途状态；分别记录原21退出、完整Torch回归、新Gate、后9实际派发及30/30产物验收，不将工程轻量测试计入训练结果。
2. 引用最终`results_validation.json`、`summary.json`和正式`analysis_evidence.json`的真实路径与哈希；核实旧398、新90、总488与精确30任务集合，不把预期数量写成实测。
3. 对照最终分析接口更新整批历时、runner累计与attempt时间的字段；保留故障、资源暂停、恢复和额外耗时。
4. 合并已关闭F01–F05及后续N01/N02/N03/N04：RBA v2可选首步注意力学习率写明η*=1，非网络学习率；Radau绝对容差区分主问题与E4；AI参与范围按下述声明，作者核验不预先签署。N04明确第一阶段调用记录是成功完成后由`cfg.adam_steps`写入，依赖冻结循环及完成证据，非独立逐步计数；L-BFGS内部迭代/closure来自实际优化器状态。损失表头使用“末次记录损失”，说明它是零基步3990/19990更新前计算、更新后记录的抽样损失，不是终点重评。
5. 冻结完整正文和图表，再做完整性核验、规定的独立多视角自动审查、逐项响应及最终数字/引用/排版核对。工作稿复核不能代替完整稿最终检查，内部自动审查不是期刊同行评审或录用。

AI参与声明候选文本见 [AI_USE_STATEMENT_N03_CN.md](E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/process/reproducibility/AI_USE_STATEMENT_N03_CN.md)。本地资料尚不等于公开发布的数据集，公开仓库、许可证、DOI及作者身份信息均待实际确认，不预填不存在的公开链接。
