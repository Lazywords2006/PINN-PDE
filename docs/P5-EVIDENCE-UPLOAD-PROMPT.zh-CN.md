# P5 证据上传提示词

把下面内容发给原来的远端执行机。当前任务只上传已经存在的证据，不重跑实验。

---

你仍然是 PINN-PDE 的远端执行机。P5 已经运行完成，现在缺的是原始证据上传。禁止
重跑 P5、修改结果、重新生成不同时间戳的包、运行 P6 或打开 frozen final。

## 1. 定位并核验原文件

在原运行目录执行：

```bash
cd /mnt/workspace/project/PINN-PDE 2>/dev/null || cd /mnt/workspace/PINN-PDE
ls -lh artifacts/p5-evidence-20260801-092048.tar.gz*
cd artifacts
sha256sum -c p5-evidence-20260801-092048.tar.gz.sha256
cd ..
```

必须得到 SHA-256：

```text
56891c5740eb94c62299b72869d790a1cbdee6abda3fae2903ed822f5e405101
```

如果文件或哈希不一致，立即停止并报告，不得用新包冒充原包。

## 2. 同步允许证据文件进入仓库的最新 main

先备份这两个文件到 `/mnt/workspace/p5-evidence-backup/`，然后：

```bash
mkdir -p /mnt/workspace/p5-evidence-backup
cp artifacts/p5-evidence-20260801-092048.tar.gz* /mnt/workspace/p5-evidence-backup/
git fetch origin
git switch main
git pull --ff-only origin main
cp /mnt/workspace/p5-evidence-backup/p5-evidence-20260801-092048.tar.gz* artifacts/
```

最新 `.gitignore` 已只允许这一个权威 P5 包及 sidecar。确认：

```bash
git status --short
```

只应看到这两个 P5 证据文件，不应提交 `results/`、环境缓存或其他临时包。

## 3. 上传到独立分支

```bash
git switch -c evidence/p5-20260801
git add artifacts/p5-evidence-20260801-092048.tar.gz \
        artifacts/p5-evidence-20260801-092048.tar.gz.sha256
git commit -m "add authoritative P5 promotion evidence"
git push -u origin evidence/p5-20260801
```

不要直接 force push `main`。创建 PR 指向 `main`，然后把 PR 链接发回主控。

## 4. 回传

请只报告：

- `git rev-parse HEAD`；
- PR 链接；
- 证据包字节数；
- 完整 SHA-256；
- `sha256sum -c` 是否为 OK。

完成上传后停止，不运行任何新实验。

---
