# V3 对称性修正与确认协议

冻结日期：2026-08-27

## 1. 为什么必须建立 V3

外部复审发现，旧版 reciprocal shell 使用
`max(|m1|,|m2|,|m1-m2|)`，但代码的 kinetic metric 为

\[
m_1^2+m_2^2+m_1m_2.
\]

与该 metric 一致的 D6 闭合壳层应使用
`max(|m1|,|m2|,|m1+m2|)`。旧640点与 Q3 supplement 的哈希仍能证明旧代码被如实运行，
但不能继续作为“对称闭合方法”的主要发表证据。

V3 同时修复 paired orthogonalization 中 normalization 未 detach 导致的非局部空间导数，
并在 Ritz 特征分解前显式取 Hermitian part。旧结果保留为 superseded historical evidence，
不覆盖、不删除，也不与 V3 数值混写。

## 2. V3 最终候选方法

暂定名：**SR-SC-NARR**（spectral-roughness-routed,
symmetry-consistent neural-augmented Rayleigh–Ritz）。

1. 训练网络仍为已封存的3层×64宽度 label-free generalized-trace SiLU MLP；训练本身不使用
   Fourier shell 或 reference labels，因此无需因 shell 修正重新训练。
2. 基础解析空间为修正后的19模态 D6 shell-2。
3. Hybrid candidate 使用 shell-2、当前参数下最低 kinetic rank-21 dictionary 的并集，
   再加入两个神经方向；pilot 中总 trial rank 为25。
4. Pure candidate 使用最低 kinetic rank-25 Fourier dictionary。
5. 路由只读取势函数的 Fourier tail-energy ratio：shell-1 以外能量比例大于0.1时使用
   hybrid，否则使用 pure Fourier。该规则不读取 projector labels、test errors 或 reference。
6. Reduced matrix 使用 `(A+A*)/2`；同时报告未经修正的 Hermiticity defect。
7. 正式评价使用65×65网格。cutoff-24 的最大坐标频率差为48，65点周期求积不会把这些
   差频混叠为零频。

## 3. Pilot（只允许工程和方法修正）

- 24个全新点，两个势族；
- 五种 split 均覆盖；
- 3个封存 checkpoint seeds；
- 评价 projector error、Ritz eigenvalue MAE、residual、tail、raw Hermiticity defect 和成本；
- pilot 可以发现和修复代码错误、确定最终候选，但不得作为主要论文表格。

当前 pilot 结果：`V3_SYMMETRY_PILOT_GO`。主要数值：

- SR-SC-NARR overall `0.02978`；
- pure kinetic Fourier（minimum rank 25, tie-closed）`0.04172`；
- full D6 shell-3 rank37 `0.02960`；
- SR-SC-NARR eigenvalue MAE `0.00807`，shell-3 为 `0.00918`；
- stratified point bootstrap 对 Fourier control 的改善区间为 `[25.94%, 30.32%]`；
- proposed-method raw Hermiticity defect 最大 `2.63e-6`；
- SR-SC-NARR 在 pilot CPU 路径上比 shell-3 快约15%，但正式效率结论只以 CUDA 为准；
- 当前源码绑定的 pilot bundle SHA-256：
  `e9f3047ebb0aaf8bd89202de95544d1b8b6a0a6b62fe8a2427ac80d78fffa5b4`。

独立 convergence audit 也已 `GO`：cutoff 24→28 的最大 projector 差为 `1.51e-6`，
低两本征值最大差为 `6.95e-10`；grid 65→97 的 solver projector 直接差为 `2.10e-4`，
Ritz eigenvalue 差为 `4.77e-7`，raw Hermiticity defect 为 `4.87e-6`。
收敛 JSON / bundle SHA-256 为
`b2a104f7dde8e506b9446634af6d716c00c8317adb2d6fa5c8f1484e4cf0e0f2` / 
`1df60548ddf9a6cb124d7f50285f51560ee00bf811721ffac870102398a47616`。

## 4. 正式确认集的生成纪律

1. 本协议、代码、测试、gate 和 pilot 先提交并推送；
2. 正式 test suite 在该提交之后用新的 seed 生成；
3. suite 必须与仓库内所有旧 suite 逐参数去重；
4. reference 使用修正 D6 cutoff-24、float64、rank3、65×65 grid；
5. exact points 要求 internal gap `<1e-3`；near points `<2e-2`；所有点 external gap
   `>1e-2`；
6. 方法、阈值、checkpoint 和控制在打开 test 后不得修改；
7. 正式运行必须在 clean Git checkout 上执行并记录 commit、环境、GPU、原始 rows、summary、
   gate、reference、suite、checkpoint、源码 fingerprint 和 SHA-256 manifest；
8. 该 test 是 procedurally frozen，不宣称由第三方 escrow 或不可见服务器保管。

## 5. 正式成功门槛

- 身份矩阵无缺失、无重复，全部数值 finite；
- maximum orthogonality error `<1e-4`；
- raw Hermiticity defect `<1e-4`；
- minimum sampled external gap `>1e-2`；
- SR-SC-NARR overall projector error `<0.06`；
- eigenvalue MAE `<0.02`；
- p95 `<0.15`，maximum `<0.25`；
- overall 与 near 均优于 long-anchor、Fourier shell-2 和 kinetic Fourier-25；
- 所有 split 对 Fourier-25 不回退；
- 6个 family×seed 中至少3个严格获胜且6个全部不回退；
- 对 Fourier-25 的 family×split-stratified point bootstrap 改善95%下界至少10%；
- 相对 rank37 shell-3：projector error 不超过其1.25倍，且 eigenvalue MAE 不高于它；
- 独立 convergence audit 通过 cutoff 24/28、grid 65/97 和 raw Hermiticity 门槛。

## 6. 必须停止或转向的情况

若正式确认失败，不允许移动门槛或在 test 上继续修改 SR-SC-NARR。应执行以下之一：

1. 若 Fourier-25 与 shell-3 在精度—成本上支配神经方法，停止“神经增强求解器”主张，转为
   对称 Fourier/Ritz 数值分析论文；
2. 若只在 localized Gaussian 势上有效，缩窄为“谱复杂度决定神经增强是否有用”的条件性
   研究，不再声称跨势族普适；
3. 若 reference/grid convergence 失败，先修数值离散，不发表当前实验；
4. 若 corrected Wang–Xie 适配在正式点上追平或反超，保留结果并进一步缩窄创新范围。

## 7. 唯一一次正式结果（2026-08-28）

状态：`V3_FORMAL_PROMOTION_GO`，17项 formal/convergence gate 全部为 true。

- 160点 × 3 seeds × 11方法 = 5,280行；
- SR-SC-NARR overall `0.030929`，eigenvalue MAE `0.009837`；
- Fourier-25 overall `0.043425`；改善28.76%，bootstrap 95%区间
  `[28.08%,29.44%]`；
- harmonic 80点全部走 Fourier 并与 control 持平；Gaussian 80点全部走 hybrid 并改善
  31.75%；
- shell-3 overall `0.030799`：本文 projector error 高0.42%，但 eigenvalue MAE 低12.75%、
  latency 低19.84%、trial rank 25–27 对37；
- proposed raw Hermiticity defect `7.13e-6`，最大正交误差 `2.47e-7`；
- 正式设备 NVIDIA A10，CUDA 12.8，峰值 allocated/reserved 显存1.24/1.26GB。

Evidence SHA-256：
`108a4b042549ead58f7b13f42b6ace4685e93a4e8a54e9563b044c03c29ad78c`。

正式 suite 已永久关闭。后续 roughness sweep 只能作为固定方法的外部补充，禁止重新选择阈值。
