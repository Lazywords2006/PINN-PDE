# 修订 5：第一阶段 22 个任务

用户已确认启动；研究运行前的预注册提交为 `2b67dcb`。仅四个 E1 PirateNet 续跑和 18 个新初值完整训练，第二阶段没有授权。

## 工程门

`engineering_gate.json` 记录 71 项完整测试、两个新初值参考解加密核对及 E1 独立本征展开、四个 checkpoint 的只读身份/恢复步数核验、旧 260 文件哈希和源码指纹。`pytest.log` 为对应完整输出。先成功提交协议、再做核验与实现，正式训练后不改旧判据。

## 运行与状态

运行器为仓库根于 R33 的 `run_stage5.ps1` / `stage5_runner.py`；使用 `D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe`，每进程单线程。`run_stage5.ps1 -Action Run` 启动隐藏后台进程；`-Action Status` 只读状态，`-Action Plan` 只列 22 个任务。已有进程仍在时拒绝重复启动。不要在续跑已经推进后重新执行只接受原 16000/16500 位置的 `-Action Gate`，也不要用源 checkpoint 覆盖进度。

实时状态、stdout/stderr 和两个批次的日志在 `D:\CodexRuntime\runs\r33_stage5_20261022`；`status.json` 每约 15 秒更新，含进程号、恢复位置和各任务最近 checkpoint。它区分“结果写出”和“已复核”，结果数不能代替核验通过。

按顺序先四进程 PirateNet，再核验其四个新结果，再八进程执行 18 个新初值训练。正式结果在 `runs/pirate` 的原缺失位置及新 tag `runs/final_ic_v1`。后台运行器不会调参、开启第二阶段或自动建 PR；工程失败停止后续批次，状态与日志保留。48 小时到达资源复盘点时停止派发，保留原子 checkpoint 和未完成记录。

## 完成后产生的文件

- `pirate_validation.json`、`ic_validation.json`：完整模型加载、N64/GL200 与 N96/GL400 误差重算、固定检验点残差及实际调用计数。
- `completion.json`、`第一阶段完成记录.md`：全部 22 个新结果核验完成后才生成。保留 A-2 原判据、逐种子数据和不利结果；旧 A-1/G2/E4 不因新批次改判。

当这些完成文件尚不存在时，不能把本目录的准备记录当作训练完成。现有训练末次 Adam 损失是最后一次按十步间隔保存的值，不是终点重新评估；新 JSON 保留原字段含义。PirateNet 的轨迹墙钟包含从云端 checkpoint 继承的累计时间，本机启动至完成的批次时间应根据运行状态及日志另计。
