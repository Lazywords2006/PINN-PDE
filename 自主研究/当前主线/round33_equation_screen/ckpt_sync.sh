#!/usr/bin/env bash
# 把 R33_CKPT_DIR 里的 checkpoint 定期镜像到 git 数据分支（单提交 amend + force push，历史不增长），
# 容器重启后再次运行本脚本即可恢复。用法：
#   R33_CKPT_DIR=/tmp/r33_ckpt bash ckpt_sync.sh restore   # 启动训练前先恢复
#   R33_CKPT_DIR=/tmp/r33_ckpt bash ckpt_sync.sh loop      # 后台循环推送（每 600 秒）
# 只动数据分支 $CKPT_BRANCH，不碰主分支。run 完成后 screen.py 会删除对应 ckpt，本脚本同步删除镜像。
set -u
CKPT_DIR="${R33_CKPT_DIR:-/tmp/r33_ckpt}"
CKPT_BRANCH="${CKPT_BRANCH:-claude/r33-ckpt-store-k5lc11}"
REMOTE_URL="${CKPT_REMOTE_URL:-$(git -C "$(dirname "$0")" remote get-url origin)}"
STORE=/tmp/r33_ckpt_store
INTERVAL="${CKPT_INTERVAL:-600}"
mkdir -p "$CKPT_DIR"

init_store() {
  [ -d "$STORE/.git" ] && return
  if git ls-remote --exit-code --heads "$REMOTE_URL" "$CKPT_BRANCH" >/dev/null 2>&1; then
    git clone -q --depth 1 --branch "$CKPT_BRANCH" "$REMOTE_URL" "$STORE"
  else
    mkdir -p "$STORE" && git -C "$STORE" init -q && git -C "$STORE" checkout -q -b "$CKPT_BRANCH"
    git -C "$STORE" remote add origin "$REMOTE_URL"
    echo "r33 checkpoint mirror" > "$STORE/README"
    git -C "$STORE" add -A && git -C "$STORE" -c user.name=ckpt -c user.email=ckpt@local commit -q -m "init"
  fi
}

restore() {
  init_store
  for f in "$STORE"/*.ckptgit; do
    [ -e "$f" ] || continue
    dst="$CKPT_DIR/$(basename "${f%.ckptgit}").ckpt"
    # 本地已有且更新则不覆盖
    if [ ! -e "$dst" ] || [ "$f" -nt "$dst" ]; then cp -p "$f" "$dst"; echo "restored $dst"; fi
  done
}

push_once() {
  init_store
  changed=0
  for f in "$CKPT_DIR"/*.ckpt; do
    [ -e "$f" ] || continue
    dst="$STORE/$(basename "${f%.ckpt}").ckptgit"
    if [ ! -e "$dst" ] || [ "$f" -nt "$dst" ]; then cp -p "$f" "$dst"; changed=1; fi
  done
  for g in "$STORE"/*.ckptgit; do
    [ -e "$g" ] || continue
    [ -e "$CKPT_DIR/$(basename "${g%.ckptgit}").ckpt" ] || { rm -f "$g"; changed=1; }
  done
  [ "$changed" = 1 ] || return 0
  git -C "$STORE" add -A
  git -C "$STORE" -c user.name=ckpt -c user.email=ckpt@local commit -q --amend -m "ckpt $(date -u +%FT%TZ)"
  for i in 1 2 3 4; do
    git -C "$STORE" push -q -f origin "$CKPT_BRANCH" 2>/dev/null && { echo "pushed $(date -u +%T)"; return 0; }
    sleep $((2 ** i))
  done
  echo "push failed" >&2
}

case "${1:-}" in
  restore) restore ;;
  push) push_once ;;
  loop) restore; while true; do push_once; sleep "$INTERVAL"; done ;;
  *) echo "usage: $0 restore|push|loop" >&2; exit 2 ;;
esac
