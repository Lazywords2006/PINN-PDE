# 外部基线索引

第三方源码不再内嵌到本仓库，以免重复保存上游 Git 历史或分发许可证不明确的压缩包。复现时请从官方仓库检出下列固定提交：

| 官方实现 | 固定提交 | 许可证 | 本项目用途 |
|---|---|---|---|
| [Mian neural Bloch eigensolver](https://github.com/haarisamian/neural-bloch-eigensolver) | `7ba841f26301cf5047647d26ad30a1def25c1276` | MIT | honeycomb ordered Bloch eigensolver 参考实现 |
| [Fanaskov subspace regression](https://github.com/VLSF/subreg) | `be1fb468c232740e93c932cf643b9cdb986f504d` | CC0 | 监督式 Grassmann/subspace regression 依据 |
| [NeuralSVD](https://github.com/jongharyu/neural-svd) | `742f56793ef675afcd3166480ce3241151c4d1a4` | MIT | Operator SVD 候选增强基线 |
| Wang–Xie TNN 作者压缩包 | 2026-07-12 下载版本 | 未发现许可证 | 仅用于核对 `Trace(B^-1A)`，不再分发 |

示例：

```bash
git clone https://github.com/haarisamian/neural-bloch-eigensolver.git
git -C neural-bloch-eigensolver checkout 7ba841f26301cf5047647d26ad30a1def25c1276
```

当前 V2 promotion pilot 实际包含 P1 block、ordered residual、Wang–Xie trace 公式适配和
P3。项目内 `wang_xie_trace`、`dai_galerkin` 和 `causal_sort` 都是针对统一 Bloch 参数
网络的公式级适配，不得写成作者官方代码直接运行结果。正式投稿矩阵仍需补 Dai/Galerkin
和监督 Grassmann 上界，并保存固定提交号、环境、参数量、训练预算与适配差异。
