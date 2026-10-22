# 投入评估证据

2026-10-22，UTC+8。只读核验原产物、既有测试对应的代码与实际硬件，并作训练时间外推。没有启动新训练或改变实验协议。

- `investment_evidence.json`：旧 260 文件和新 24 结果/产物哈希检查、tag 数量、硬件快照、外推公式、52 个任务的草案计数。
- `build_evidence.py`：标准库脚本，仅重算完整性和预算，不加载训练模型，不执行优化更新。`--host` 指向 `Get-CimInstance` 生成的本机硬件 JSON（UTF-8），计时读取已保存的 `preflight_review.json`。

硬件与磁盘空间是检查时快照，会随环境变化；完整预算时间只是外推。原始硬件查询和运行临时文件在 `D:\CodexRuntime\runs\r33_investment_20261022`。正式方案和限制见 [投入评估](../../FULL_TEST_INVESTMENT_REVIEW_20261022.md)。本文件夹不是新的实验结果 tag。
