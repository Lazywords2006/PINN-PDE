# 基准套件

- `falsification_smoke_v2.json`：当前有效的 24 点可证伪烟测套件，仅用于 smoke，不是论文 final test；
- `sci3_validation_v1.json` 与 `sci3_frozen_test_v1.json`：保留用于审计退役 V1 协议，不能继续作为正式论文验证/测试集；
- 同名 `.sha256` 文件绑定精确内容。验证时从本目录运行 `shasum -a 256 -c <name>.sha256`。

新的正式实验必须先建立对称闭合 PWE 参考、独立 validation 和 640 点 V2 final suite，并在任何训练前冻结其哈希。
