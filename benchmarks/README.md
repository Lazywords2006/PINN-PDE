# 基准套件

- `v2_validation.json`：64 点独立、split-balanced validation，只用于 pilot 与模型选择；
- `v2_frozen_test.json`：640 点 final，含 IID、exact、near、strict OOD 与 gap scan；
- `v2_reference_convergence.json`：cutoff 16/20/24 六点收敛审计；
- `falsification_smoke_v2.json`：24 点工程烟测，不是论文 final；
- `sci3_*_v1.json`：退役 V1，仅保留历史审计，禁止用于新结论。

所有 V2 `.sha256` 都绑定文件原始字节。从本目录核验：

```bash
shasum -a 256 -c v2_validation.sha256
shasum -a 256 -c v2_frozen_test.sha256
shasum -a 256 -c v2_reference_convergence.sha256
```

不要手工编辑 V2 JSON；使用
`python scripts/generate_v2_assets.py --device cpu --suites-only` 确定性重建套件。
最终套件只能在 24-run promotion gate 为 GO 后打开。
