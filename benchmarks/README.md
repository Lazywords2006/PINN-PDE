# 基准套件

- `v2_validation.json`：64 点独立、split-balanced validation，只用于 pilot 与模型选择；
- `v2_frozen_test.json`：640 点 final，含 IID、exact、near、strict OOD 与 gap scan；
- `v2_reference_convergence.json`：cutoff 16/20/24 六点收敛审计；
- `falsification_smoke_v2.json`：24 点工程烟测，不是论文 final；
- `p2_validation_v1.json`：96 点 P2 full-shell independent pilot；
- `q3_supplement_v1.json`：160 点独立期刊基线 supplement，已运行一次并关闭；
- `sci3_*_v1.json`：退役 V1，仅保留历史审计，禁止用于新结论。

所有 V2 `.sha256` 都绑定文件原始字节。从本目录核验：

```bash
shasum -a 256 -c v2_validation.sha256
shasum -a 256 -c v2_frozen_test.sha256
shasum -a 256 -c v2_reference_convergence.sha256
```

不要手工编辑 V2 JSON；使用
`python scripts/generate_v2_assets.py --device cpu --suites-only` 确定性重建套件。
`v2_frozen_test.json` 已在 P2 independent pilot GO 后执行唯一一次 final，并永久关闭。
禁止再次运行、读取指标调参或修改套件。新的 SCI-Q3 supplement 必须生成独立套件和新
SHA-256，不能复用 `sci3_*_v1.json` 冒充新实验。

`q3_supplement_v1.json` 已于 2026-08-25 返回 `Q3_SUPPLEMENT_GO`。它同样不得在修改
方法、训练预算或门槛后重跑。
