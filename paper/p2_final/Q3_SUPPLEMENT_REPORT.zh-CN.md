# SCI 三区独立补充实验报告

执行日期：2026-08-25
设备：NVIDIA RTX 5090 D 32 GB
状态：`Q3_SUPPLEMENT_GO`

## 1. 结论

新的160点独立 supplement 已完整运行。P2 full-shell 在两个势族、3个 checkpoint seeds、
五类参数区域上同时优于 Wang–Xie trace Bloch 适配和 Dai neural-subspace Galerkin Bloch
适配。全部预注册门槛通过，1440行结果与89个 manifest 文件已经在远端和本地分别审计。

主结果：

| 方法 | Overall | Near | Gap-scan | Strict-OOD |
|---|---:|---:|---:|---:|
| **P2 full-shell** | **0.04728** | **0.03804** | **0.06727** | **0.05796** |
| Wang–Xie trace adapted | 0.13114 | 0.09056 | 0.15110 | 0.21776 |
| Dai Galerkin adapted | 0.43367 | 0.42376 | 0.47148 | 0.43758 |

P2 相对 Wang–Xie 适配的点聚类 bootstrap 改善为 63.78%，95% CI
`[59.58%, 67.88%]`；相对 Dai 适配为 89.08%，95% CI `[88.10%, 90.01%]`。

## 2. 协议

- 新 suite：160点，harmonic/Gaussian 各80点；
- 每势族：IID 16、exact 16、near 24、strict-OOD 16、gap-scan 8；
- 与 V2 validation、640点 frozen final、P0、P1、P2 pilot 全部逐参数去重；
- reference：float64 PWE cutoff-24、rank-3、33×33网格；
- seeds：42、137、251；
- 评价矩阵：3方法 × 3 seeds × 160点 = 1440行；
- baseline 训练：1500步，Adam `1e-3`，每步4个参数实例，每实例256点；
- P2 不重新训练，复用审计后的 long-anchor checkpoint；
- bootstrap：2000次，以160个物理参数点为 cluster。

两个基线都获得1500步训练预算，高于 P2 神经初始化器原先的665步，避免通过弱训练预算
人为放大 P2 优势。

## 3. 分 split 结果

| Split | P2 | Wang–Xie adapted | Dai adapted |
|---|---:|---:|---:|
| IID | **0.04533** | 0.13243 | 0.43112 |
| Exact cluster | **0.04239** | 0.09410 | 0.42827 |
| Near cluster | **0.03804** | 0.09056 | 0.42376 |
| Strict OOD | **0.05796** | 0.21776 | 0.43758 |
| Gap scan | **0.06727** | 0.15110 | 0.47148 |

P2 的提升不是只出现在 crossing 邻域；在 strict-OOD 和 gap-scan 上也保持优势。

## 4. 势族与随机种子

### 4.1 势族

| 势族 | P2 | Wang–Xie adapted | Dai adapted |
|---|---:|---:|---:|
| Harmonic honeycomb | **0.03674** | 0.07556 | 0.31648 |
| Gaussian honeycomb | **0.05781** | 0.18671 | 0.55086 |

### 4.2 Seed overall

| Seed | P2 | Wang–Xie adapted | Dai adapted |
|---|---:|---:|---:|
| 42 | **0.04584** | 0.12383 | 0.44431 |
| 137 | **0.04758** | 0.13014 | 0.43107 |
| 251 | **0.04841** | 0.13944 | 0.42564 |

P2 相对两个基线均为 `6/6` family×seed overall 配对获胜。

## 5. 效率和模型规模

| 方法 | 参数量 harmonic / Gaussian | 推理 mean | 推理 p95 |
|---|---:|---:|---:|
| P2 full-shell | 9,156 / 9,220 | 193.75 ms | 209.01 ms |
| Wang–Xie adapted | 9,156 / 9,220 | **2.47 ms** | **2.68 ms** |
| Dai adapted | 9,676 / 9,740 | 205.56 ms | 230.18 ms |

Wang–Xie 适配非常快，但精度明显较低；P2 与 Dai 适配的延迟处于同一数量级，P2 精度
更高。这里的计时是本次统一逐点评价路径，未使用旧 final 的 timing 作为替代。

基线三seed训练总时间：

- Wang–Xie harmonic：275.63 s；Gaussian：382.51 s；
- Dai harmonic：1050.02 s；Gaussian：1148.87 s。

峰值显存约为 Wang–Xie 226 MB、Dai 431 MB，单张消费级 GPU 足够。

## 6. 物理与数值检查

- 最大正交误差：`2.95e-7`；
- mean residual RMS：P2 `0.15030`、Wang–Xie `0.15324`、Dai `0.27381`；
- P2 与 Wang–Xie 的 residual 很接近，但 projector error 差异明显，进一步说明只看 PDE
  residual 不能判断是否选中了正确谱簇。

## 7. 门槛

| Gate | 结果 |
|---|---|
| 身份矩阵与有限性 | PASS |
| Overall 优于两个基线 | PASS |
| Near 优于两个基线 | PASS |
| Gap-scan 优于两个基线 | PASS |
| 每个基线至少5/6配对获胜 | PASS（均6/6） |
| 两个 improvement CI 下界 > 0 | PASS |
| 正交误差 < `1e-4` | PASS |
| 最终判定 | **`Q3_SUPPLEMENT_GO`** |

## 8. 证据

- suite SHA-256：`6d541641b7cadd57078c02b171b1f89cca680c0893c2f0046c3d33562e2c9cd0`；
- reference cache SHA-256：`473f15839e874d31ab3470b458cfc38dc8cee06662b35c86270a369e398f915f`；
- evidence SHA-256：`282cdd418eaa11a68498ee7fbc0198dfc1f362a535385756a7cc38275806afe0`；
- manifest：89文件，远端 audit PASS；
- 本地下载后 SHA：OK；
- 本地重新打开证据、重算 gate：audit PASS；
- 代码提交：`c678cda6f0234d6873ebe911154bd988fe89db05`。

本地证据入口：`results/remote_5090_q3_supplement_go/`。

## 9. 不能过度解释

1. `wang_xie_trace_adapted` 和 `dai_galerkin_adapted` 是根据论文机制在统一 Bloch 网络中
   实现的公式级适配，不是作者官方代码运行结果。
2. Dai 适配在当前设定下收敛较差，Gaussian 某些 seed 的训练目标没有单调下降。它可以
   作为透明的实现级负结果，但不能用来宣称 Dai 原论文方法本身无效。
3. 当前最有说服力的直接期刊近邻证据是 P2 对参数量相同、训练预算更大的 Wang–Xie
   trace 适配仍有稳定优势。
4. 本实验增强了 SCI 三区投稿基础，但 external-gap/Ritz 理论说明、FLOPs 和最终目标期刊
   格式仍需完成。
