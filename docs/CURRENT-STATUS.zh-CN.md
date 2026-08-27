# 当前研究状态

更新日期：2026-08-27

## 一句话结论

旧 P2/Q3 实验已经被外部复审发现的 reciprocal-shell 符号错误判定为 **superseded**，
不能投稿。代码和方法已升级为 V3：**SR-SC-NARR**（spectral-roughness-routed,
symmetry-consistent neural-augmented Rayleigh–Ritz）。修正版24点独立 pilot 和 cutoff/grid
convergence audit 均已通过；新的160点 CUDA confirmation 尚未运行，因此当前状态是
**继续研究，暂不可投稿**。

## 为什么旧论文被废止

旧版 kinetic metric 为 `m1²+m2²+m1m2`，shell 却使用
`max(|m1|,|m2|,|m1-m2|)`。正确 D6 closure 应使用 `m1+m2`。此外 paired
orthogonalization 的 normalization 没有 detach，导致组合试验空间的自动微分出现非局部
grid derivative；旧 rank-21 Fourier control 还使用了两个不对称外层模式。

旧证据哈希仍证明旧代码被如实运行，但不能证明旧方法的对称性或数值正确性。旧 DOCX/PDF、
640点表格和 Q3 supplement 只保留追溯价值。

## V3 方法

1. 保留已封存的3层×64宽度 label-free generalized-trace SiLU MLP；网络训练不依赖 shell
   或 reference labels，所以无需重训。
2. 使用与 positive-cross metric 一致的 D6 shell。
3. Hybrid candidate 由 D6 shell-2、最低 kinetic dictionary 与两个神经方向构成。
4. Pure candidate 为 kinetic-energy 排序且关闭边界简并 ties 的 Fourier dictionary。
5. 使用势函数 shell-1 以外 Fourier tail-energy ratio 路由：spectrally rich 势使用 neural
   augmentation，简单势直接使用 Fourier，完全不读测试标签。
6. Paired normalization 视为离散求积常数；Ritz matrix 显式 Hermitian 化，并报告 raw defect。
7. 正式评价使用65×65网格和 corrected D6 cutoff-24 float64 PWE。

## 最新可用结果（仅 pilot）

24点、两个势族、五种 split、3 seeds 的最新 pilot：

| 方法 | Projector error | Eigenvalue MAE | CPU latency |
|---|---:|---:|---:|
| **SR-SC-NARR** | **0.02978** | **0.00807** | 52.51 ms |
| kinetic Fourier（minimum rank 25） | 0.04172 | 0.01276 | 29.56 ms |
| full D6 shell-3（rank 37） | 0.02960 | 0.00918 | 61.76 ms |
| Wang–Xie adapted | 0.14786 | 0.01746 | 0.82 ms |
| Dai adapted | 0.43386 | 0.10087 | 111.23 ms |

这些结果表明 SR-SC-NARR 相对同等级 Fourier control 有约29%的 projector 改善，并与
rank-37 Fourier 形成较小 trial rank / 较低成本 / 相近精度的 Pareto 点。它不是正式论文
结果，也不能保证 confirmation 继续通过。

Convergence audit（修正版）当前通过：

- cutoff 24→28 reference projector 最大差约 `1.51e-6`；
- 低两本征值最大差约 `6.95e-10`；
- grid 65→97 solver projector 直接差 `2.10e-4`，eigenvalue 差 `4.77e-7`；
- raw Hermiticity defect 已从错误实现的最高约 `0.586` 降到 `1e-5` 量级。

当前源码与 pilot 的绑定指纹为
`27b8d487a8ff81a89d27d49856b3559e51188d0424a143ad7133d9d572f2dbbb`，pilot 证据包
SHA-256 为 `e9f3047ebb0aaf8bd89202de95544d1b8b6a0a6b62fe8a2427ac80d78fffa5b4`。
收敛 JSON / bundle SHA-256 分别为
`b2a104f7dde8e506b9446634af6d716c00c8317adb2d6fa5c8f1484e4cf0e0f2` 和
`1df60548ddf9a6cb124d7f50285f51560ee00bf811721ffac870102398a47616`。

## 下一步唯一主任务

1. formal/pilot 隔离、tie closure、参数边界、provenance 与 projector convergence 修复：
   **已完成并通过复审**；
2. 与当前源码指纹绑定的 pilot / convergence evidence：**已重新生成并通过**；
3. 当前动作：提交并推送 V3 freeze；
4. 之后生成固定 seed 的160点 confirmation suite、reference 与 formal manifest，并单独提交；
5. 在 clean CUDA checkout 上只运行一次正式确认；
6. confirmation 全门槛通过后，重写双语论文、图表、HTML、DOCX/PDF 和投稿判断。

完整冻结标准见 [V3-SYMMETRY-CORRECTION-PROTOCOL.zh-CN.md](V3-SYMMETRY-CORRECTION-PROTOCOL.zh-CN.md)。

## 当前禁止事项

- 禁止提交 v0.3 NMPDE DOCX/PDF；
- 禁止把旧 P2/Q3 数字写成当前结果；
- 禁止在160点 confirmation 打开后修改方法、控制或 gate；
- 禁止把 pilot GO 写成期刊可发表结论；
- 禁止因某个 baseline 收敛差而宣称普适优越性。
