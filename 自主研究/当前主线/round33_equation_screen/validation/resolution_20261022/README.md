# 修复与可行性复核材料

全部新实验仅属于 `SCREEN_PROTOCOL.md` 修订 4 的固定 24 次小预算可行性检查，种子 100、101，零调参。结果不进入论文正式主表。完整实验与大规模调参没有启动。研究 run 开始前提交为 `c31355c`；checkpoint 工程探针顺序偏差已经在该提交披露。

**最终判定：24/24 完成，G0/G1 通过，G2 未通过，停止自动扩展。** E1 主比较 7.18 倍；SOAP 叠加虽 5.60 倍，但候选仅 1/2 达绝对误差门。E3 主比较 1.23 倍、叠加 2.43 倍，都未到三倍。本机整批约 30 分钟，原始计时见 `batch_timing.json`。

报告 [修复结果与论文准备度.html](修复结果与论文准备度.html) 已完成 UTF-8、数据判定和 14 个本地链接检查。自动浏览器拒绝本地 file 协议，未绕过策略或改用替代浏览器，未做渲染目视核验；范围见 `delivery_checks.json`。

- `preflight_review.json`：24 次完整模型加载、哈希、原指标/加密参考解复算及 G0/G1/G2 判定。
- `validate_preflight.py`：只读复算程序，不调用训练。相对路径自动定位仓库，须先集齐全部 24 次及本目录证据文件；缺失会报错，不给部分通过结论。
- `checkpoint_review.json`：四个真实历史 checkpoint 的来源及短续跑核对。工作副本仍保留在 D 盘的 16000/16500 步，短探针使用另建副本；没有完成四个完整训练。
- `pytest_final.log`：完整测试 63 passed，包含原 43 项；一个旧测试的 tensor 转标量警告不影响断言。
- `preflight4_adam.log`、`preflight4_soap64.log`：固定批次的真实运行记录。
- `eic_phase1.txt`、`method_phase1.txt`、`eic_phase2.txt`、`method_phase2.txt`：两份独立意见及内容盲评分承诺。评审面向改写前的研究材料，不是当前稿件验收，亦非真实期刊决定。
- `review_protocol_status.json`：如实记录技能格式检查。Phase 2 未按契约逐项给出所需小节，因此正式模拟评审轮次中止，不拼凑综合评分或接受结论。独立意见仅作定性参考，本文的可运行性/论文准备度判断以可核验数据为依据。

本机已核验运行环境：`D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe`，Python 3.12.6、torch 2.14.1+cpu、NumPy 2.5.3。venv、缓存、临时文件和 checkpoint 均留在 `D:\CodexRuntime`，不移动或替换系统 Python。历史云端 Python/CPU 构建不同，不声称跨机器完整轨迹逐位相同。

在 R33 目录只读复核的命令（不会启动训练）：

```powershell
$env:PYTHONPYCACHEPREFIX='D:\CodexRuntime\cache\pycache'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
& 'D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe' 'validation/resolution_20261022/validate_preflight.py'
```

完整测试命令：

```powershell
$env:TEMP='D:\CodexRuntime\temp'
$env:TMP='D:\CodexRuntime\temp'
& 'D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe' -m pytest -q --basetemp='D:\CodexRuntime\runs\r33_verify_tests'
```

旧 130 次产物复核见相邻 `feasibility_review_20261021`；其中 E4 表面权重缺失是历史不可恢复缺口，不能因为体/迹指标通过就声称表面精度已重建。
