# P2 期刊论文提纲

## 暂定标题

**Basis-Invariant Neural-Augmented Rayleigh–Ritz Solver for Parameterized Bloch Spectral Clusters with Eigenvalue Crossings**

中文：**面向本征值交叉的参数化 Bloch 谱簇基底不变神经增强 Rayleigh–Ritz 求解器**

## 核心研究问题

如何在不对交叉能带逐条编号、不使用本征函数监督标签的前提下，快速、稳定地求解一族
二维周期 Bloch–Schrödinger PDE 的最低 rank-2 谱簇，并在 near crossing、严格 OOD 和
gap-scan 区域同时保持精度？

## 建议结构与字数

### 1. Introduction（900–1100词）

- 神经 PDE 求解器与参数摊销；
- 本征值交叉导致逐模态标签不连续；
- 普通 PINN/ROM 的 near/gap 冲突；
- 本文解决对象和主要贡献；
- 贡献避免使用“首次提出 Rayleigh–Ritz”等过度表述。

### 2. Related Work（900–1200词）

- PINN 与神经本征求解器；
- Ky Fan/trace 多本征对；
- neural subspace + Galerkin；
- 参数化 eigenspace/Grassmann 学习；
- Bloch 周期量子/色散 PINN；
- 误差触发校正、混合神经数值求解器。

### 3. Problem Formulation（700–900词）

- 二维 Bloch–Schrödinger 方程、周期边界；
- harmonic/Gaussian honeycomb；
- 内部 gap、外部 gap 和 rank-2 projector；
- 评价指标与参数域。

### 4. Method（1300–1700词）

#### 4.1 Label-free neural coarse subspace

- 周期特征 SiLU MLP；
- 物理 anchor；
- generalized-trace 训练；
- 复数 MGS。

#### 4.2 Basis-invariant analytic augmentation

- 完整二阶六角 shell；
- 去除重复/依赖方向；
- 试验空间定义。

#### 4.3 Fast paired Hamiltonian assembly

- neural 两列自动微分；
- Fourier 列解析 Hamiltonian；
- 对 \((W,HW)\) 同步施加正交变换。

#### 4.4 Rank-two Ritz extraction

- 小型 Ritz 矩阵；
- 最低两向量；
- 基底不变性说明。

#### 4.5 Complexity

- 网络 forward；
- 2 列 AD；
- 19 列解析；
- 21×21 eigensolve；
- 与 PWE cutoff-24 比较。

### 5. Experimental Protocol（900–1100词）

- 设备与环境；
- development/pilot/final 隔离；
- 10 方法、3 seeds、640 点；
- 5 splits 与2势族；
- reference convergence；
- 2,000点聚类 bootstrap；
- 证据与复现。

### 6. Results（1200–1500词）

- 主结果表；
- split/family；
- 消融；
- 配对散点/CDF；
- bootstrap；
- 精度—延迟和 PWE 对比。

### 7. Discussion（800–1000词）

- 为什么神经+完整 shell 有效；
- 为什么 outer shell、纯 Fourier 和 amortized ROM 失败；
- neural PDE 与混合谱方法定位；
- 与最近邻期刊工作的差异；
- 局限、有效性威胁和外推边界。

### 8. Conclusion（250–350词）

- 回答研究问题；
- 不重复摘要数字堆砌；
- 下一步：理论界、更多晶格、时变/非线性谱问题。

## 摘要应包含的数字

- 640 frozen-final points；
- 3 seeds、2 families、10 methods；
- overall 0.04532 versus long-anchor 0.14719；
- overall improvement 69.2%，95% CI [67.7%,70.8%]；
- near improvement 56.3%，95% CI [53.2%,59.2%]；
- 107.8ms versus PWE 313.4ms；
- 6/6 family-seed wins。

## 核心贡献建议写法

1. 将参数化 Bloch 内部交叉问题表述为固定秩谱簇学习，避免逐模态标签不连续；
2. 提出神经粗子空间与完整六角 Fourier shell 的基底不变紧凑 Ritz 精化框架；
3. 提出 neural/analytic Hamiltonian 配对装配，将高维逐列 AD 变为仅2列 AD；
4. 通过两势族、5 splits、3 seeds、640点 frozen final 和 cluster bootstrap 验证精度与效率。

## 不应写成贡献的内容

- Ky Fan、Rayleigh–Ritz、Galerkin、PWE、Fourier 基或 MGS 本身；
- 单纯使用 RTX 5090；
- 只换激活函数；
- P5/P1 的失败机制；它们只能作为动机和消融证据。
